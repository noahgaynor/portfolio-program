"""
V-Stop (Volatility Stop) Indicator Implementation

Ported from TradingView Pine Script "Volatility Stop MTF" by TradingView
This implementation calculates the V-Stop indicator which uses ATR-based
volatility to determine trend direction and stop levels.
"""
import numpy as np
import pandas as pd
from typing import Tuple, Optional


def calculate_atr(high: pd.Series, low: pd.Series, close: pd.Series, length: int) -> pd.Series:
    """
    Calculate Average True Range (ATR) using RMA (Relative Moving Average).

    Args:
        high: High prices
        low: Low prices
        close: Close prices
        length: ATR period length

    Returns:
        ATR values as a pandas Series
    """
    # Calculate True Range
    prev_close = close.shift(1)
    tr1 = high - low
    tr2 = abs(high - prev_close)
    tr3 = abs(low - prev_close)
    true_range = pd.concat([tr1, tr2, tr3], axis=1).max(axis=1)

    # Calculate RMA (same as EMA with alpha = 1/length)
    # Pine Script's ta.rma uses: rma = alpha * source + (1 - alpha) * rma[1]
    alpha = 1.0 / length
    atr = true_range.ewm(alpha=alpha, adjust=False).mean()

    return atr


def calculate_vstop(
    source: pd.Series,
    high: pd.Series,
    low: pd.Series,
    close: pd.Series,
    length: int = 20,
    atr_factor: float = 2.0
) -> Tuple[pd.Series, pd.Series]:
    """
    Calculate V-Stop indicator values and trend direction.

    This implements the vStop function from the Pine Script indicator.
    The V-Stop line moves with price action and flips direction when
    price crosses the stop level.

    Args:
        source: Source price series (typically close)
        high: High prices
        low: Low prices
        close: Close prices
        length: ATR calculation length (default: 20)
        atr_factor: ATR multiplier for stop distance (default: 2.0)

    Returns:
        Tuple of (stop_values, trend_up) where:
            - stop_values: The V-Stop line values
            - trend_up: Boolean series (True = uptrend/bullish, False = downtrend/bearish)
    """
    n = len(source)

    # Calculate ATR
    atr = calculate_atr(high, low, close, length)
    atr_mult = atr * atr_factor

    # Initialize arrays
    trend_up = np.zeros(n, dtype=bool)
    stop = np.zeros(n)
    max_price = np.zeros(n)
    min_price = np.zeros(n)

    # Handle NaN values in source
    src = source.fillna(close).values
    atr_m = atr_mult.values

    # Get the integer position of the first valid index
    first_valid_idx = source.first_valid_index()
    if first_valid_idx is not None:
        first_valid_pos = source.index.get_loc(first_valid_idx)
    else:
        first_valid_pos = 0

    # Ensure we have enough data for ATR calculation
    start_pos = max(length, first_valid_pos)

    # Set initial values
    trend_up[0] = True
    max_price[0] = src[0]
    min_price[0] = src[0]
    stop[0] = src[0]

    # Iterate through the series (Pine Script logic ported)
    for i in range(1, n):
        # Skip if ATR is not valid yet
        if np.isnan(atr_m[i]) or atr_m[i] == 0:
            trend_up[i] = trend_up[i-1]
            max_price[i] = src[i]
            min_price[i] = src[i]
            stop[i] = src[i]
            continue

        # Update max/min tracking
        max_price[i] = max(max_price[i-1], src[i])
        min_price[i] = min(min_price[i-1], src[i])

        # Calculate potential stop levels
        if trend_up[i-1]:
            # In uptrend: stop trails below price
            new_stop = max_price[i] - atr_m[i]
            stop[i] = max(stop[i-1], new_stop)
        else:
            # In downtrend: stop trails above price
            new_stop = min_price[i] + atr_m[i]
            stop[i] = min(stop[i-1], new_stop)

        # Check for trend reversal
        trend_up[i] = src[i] - stop[i] >= 0

        # If trend changed, reset max/min and recalculate stop
        if trend_up[i] != trend_up[i-1]:
            max_price[i] = src[i]
            min_price[i] = src[i]
            if trend_up[i]:
                stop[i] = max_price[i] - atr_m[i]
            else:
                stop[i] = min_price[i] + atr_m[i]

    # Convert to pandas Series with original index
    stop_series = pd.Series(stop, index=source.index)
    trend_series = pd.Series(trend_up, index=source.index)

    return stop_series, trend_series


def get_vstop_signal(
    df: pd.DataFrame,
    length: int = 20,
    atr_factor: float = 2.0,
    source_col: str = 'Close'
) -> dict:
    """
    Calculate V-Stop and return current signal state.

    Args:
        df: DataFrame with OHLC data (must have 'Open', 'High', 'Low', 'Close' columns)
        length: ATR period length
        atr_factor: ATR multiplier
        source_col: Column to use as source (default: 'Close')

    Returns:
        Dictionary with signal information:
            - is_bullish: Current trend direction
            - stop_value: Current stop level
            - trend_changed: Whether trend just changed
            - bars_in_trend: Number of bars in current trend
    """
    # Normalize column names (yfinance uses various cases)
    df_normalized = df.copy()
    df_normalized.columns = [col.title() if isinstance(col, str) else col for col in df_normalized.columns]

    # Handle multi-level columns from yfinance
    if isinstance(df_normalized.columns, pd.MultiIndex):
        df_normalized.columns = df_normalized.columns.get_level_values(0)

    source = df_normalized[source_col]
    high = df_normalized['High']
    low = df_normalized['Low']
    close = df_normalized['Close']

    stop_values, trend_up = calculate_vstop(source, high, low, close, length, atr_factor)

    # Get current state
    current_trend = trend_up.iloc[-1]
    prev_trend = trend_up.iloc[-2] if len(trend_up) > 1 else current_trend

    # Count bars in current trend
    bars_in_trend = 0
    for i in range(len(trend_up) - 1, -1, -1):
        if trend_up.iloc[i] == current_trend:
            bars_in_trend += 1
        else:
            break

    return {
        'is_bullish': bool(current_trend),
        'stop_value': float(stop_values.iloc[-1]),
        'current_price': float(close.iloc[-1]),
        'trend_changed': current_trend != prev_trend,
        'bars_in_trend': bars_in_trend,
        'stop_series': stop_values,
        'trend_series': trend_up
    }


def check_mtf_alignment(
    daily_signal: dict,
    weekly_signal: dict,
    monthly_signal: dict
) -> dict:
    """
    Check if all three timeframes are aligned bullish.

    Args:
        daily_signal: V-Stop signal from daily timeframe
        weekly_signal: V-Stop signal from weekly timeframe
        monthly_signal: V-Stop signal from monthly timeframe

    Returns:
        Dictionary with alignment status and details
    """
    all_bullish = (
        daily_signal['is_bullish'] and
        weekly_signal['is_bullish'] and
        monthly_signal['is_bullish']
    )

    return {
        'all_bullish': all_bullish,
        'daily_bullish': daily_signal['is_bullish'],
        'weekly_bullish': weekly_signal['is_bullish'],
        'monthly_bullish': monthly_signal['is_bullish'],
        'daily_stop': daily_signal['stop_value'],
        'weekly_stop': weekly_signal['stop_value'],
        'monthly_stop': monthly_signal['stop_value'],
        'current_price': daily_signal['current_price']
    }
