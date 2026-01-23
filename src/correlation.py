"""
Correlation Analysis Module

Calculates pairwise correlations between symbols using daily returns
to help build a diversified, uncorrelated portfolio.
"""
import logging
import random
from typing import Dict, List, Optional, Tuple
import pandas as pd
import numpy as np

from config import CORRELATION_LOOKBACK_DAYS, DEFAULT_CORRELATION_THRESHOLD

logger = logging.getLogger(__name__)


def calculate_daily_returns(prices: pd.Series) -> pd.Series:
    """
    Calculate daily returns from price series.

    Args:
        prices: Series of closing prices

    Returns:
        Series of daily percentage returns
    """
    return prices.pct_change().dropna()


def calculate_correlation(returns1: pd.Series, returns2: pd.Series) -> float:
    """
    Calculate Pearson correlation between two return series.

    Args:
        returns1: First return series
        returns2: Second return series

    Returns:
        Correlation coefficient (-1 to 1)
    """
    # Align the series by index
    aligned = pd.concat([returns1, returns2], axis=1, join='inner')

    if len(aligned) < 20:  # Need minimum data points
        logger.warning(f"Insufficient data for correlation: {len(aligned)} points")
        return 0.0

    return aligned.iloc[:, 0].corr(aligned.iloc[:, 1])


def calculate_correlation_matrix(
    daily_data: Dict[str, pd.DataFrame],
    lookback_days: int = CORRELATION_LOOKBACK_DAYS
) -> pd.DataFrame:
    """
    Calculate pairwise correlation matrix for all symbols.

    Args:
        daily_data: Dictionary mapping symbols to DataFrames with 'Close' column
        lookback_days: Number of trading days to use

    Returns:
        DataFrame with correlation matrix
    """
    symbols = list(daily_data.keys())
    returns_dict = {}

    for symbol in symbols:
        df = daily_data[symbol]
        if df is not None and 'Close' in df.columns and len(df) >= lookback_days:
            # Get last N days of returns
            prices = df['Close'].tail(lookback_days + 1)
            returns_dict[symbol] = calculate_daily_returns(prices)

    if not returns_dict:
        return pd.DataFrame()

    # Create returns DataFrame
    returns_df = pd.DataFrame(returns_dict)

    # Calculate correlation matrix
    corr_matrix = returns_df.corr()

    return corr_matrix


def get_correlation(
    symbol1: str,
    symbol2: str,
    daily_data: Dict[str, pd.DataFrame],
    lookback_days: int = CORRELATION_LOOKBACK_DAYS
) -> float:
    """
    Get correlation between two specific symbols.

    Args:
        symbol1: First symbol
        symbol2: Second symbol
        daily_data: Dictionary mapping symbols to DataFrames
        lookback_days: Number of trading days to use

    Returns:
        Correlation coefficient
    """
    df1 = daily_data.get(symbol1)
    df2 = daily_data.get(symbol2)

    if df1 is None or df2 is None:
        logger.warning(f"Missing data for correlation: {symbol1} or {symbol2}")
        return 0.0

    if 'Close' not in df1.columns or 'Close' not in df2.columns:
        return 0.0

    # Get returns for lookback period
    prices1 = df1['Close'].tail(lookback_days + 1)
    prices2 = df2['Close'].tail(lookback_days + 1)

    returns1 = calculate_daily_returns(prices1)
    returns2 = calculate_daily_returns(prices2)

    return calculate_correlation(returns1, returns2)


def filter_correlated_entries(
    new_candidates: List[Dict],
    existing_positions: List[str],
    daily_data: Dict[str, pd.DataFrame],
    threshold: float = DEFAULT_CORRELATION_THRESHOLD,
    lookback_days: int = CORRELATION_LOOKBACK_DAYS
) -> Tuple[List[Dict], List[Dict]]:
    """
    Filter out new entry candidates that are too correlated with existing positions.

    Args:
        new_candidates: List of candidate stocks to potentially add
        existing_positions: List of symbols already in portfolio
        daily_data: Dictionary mapping symbols to DataFrames
        threshold: Maximum allowed correlation (e.g., 0.75 = 75%)
        lookback_days: Number of trading days for correlation calculation

    Returns:
        Tuple of (accepted_candidates, rejected_candidates)
    """
    if not new_candidates:
        return [], []

    if not existing_positions:
        # No existing positions - accept all candidates
        # But still need to check correlation among candidates themselves
        return _filter_among_candidates(new_candidates, daily_data, threshold, lookback_days)

    accepted = []
    rejected = []

    # Shuffle candidates for random tie-breaking when multiple new entries
    # would correlate with each other
    shuffled_candidates = new_candidates.copy()
    random.shuffle(shuffled_candidates)

    # Track which symbols we've accepted (existing + newly accepted)
    portfolio_symbols = set(existing_positions)

    for candidate in shuffled_candidates:
        symbol = candidate['symbol']
        is_correlated = False
        correlated_with = None
        max_corr = 0.0

        # Check correlation against all portfolio symbols
        for portfolio_symbol in portfolio_symbols:
            corr = get_correlation(symbol, portfolio_symbol, daily_data, lookback_days)

            if abs(corr) > threshold:
                is_correlated = True
                if abs(corr) > abs(max_corr):
                    max_corr = corr
                    correlated_with = portfolio_symbol

        if is_correlated:
            candidate['rejection_reason'] = f"Too correlated with {correlated_with} ({max_corr:.1%})"
            rejected.append(candidate)
            logger.info(f"Rejected {symbol}: correlated {max_corr:.1%} with {correlated_with}")
        else:
            accepted.append(candidate)
            portfolio_symbols.add(symbol)  # Add to portfolio for subsequent checks
            logger.info(f"Accepted {symbol}: passes correlation filter")

    return accepted, rejected


def _filter_among_candidates(
    candidates: List[Dict],
    daily_data: Dict[str, pd.DataFrame],
    threshold: float,
    lookback_days: int
) -> Tuple[List[Dict], List[Dict]]:
    """
    Filter candidates when there are no existing positions.
    Ensures new candidates aren't too correlated with each other.

    Args:
        candidates: List of candidate stocks
        daily_data: Dictionary mapping symbols to DataFrames
        threshold: Maximum allowed correlation
        lookback_days: Number of trading days for correlation calculation

    Returns:
        Tuple of (accepted_candidates, rejected_candidates)
    """
    if len(candidates) <= 1:
        return candidates, []

    accepted = []
    rejected = []

    # Shuffle for random selection among correlated pairs
    shuffled = candidates.copy()
    random.shuffle(shuffled)

    accepted_symbols = set()

    for candidate in shuffled:
        symbol = candidate['symbol']
        is_correlated = False
        correlated_with = None
        max_corr = 0.0

        for accepted_symbol in accepted_symbols:
            corr = get_correlation(symbol, accepted_symbol, daily_data, lookback_days)

            if abs(corr) > threshold:
                is_correlated = True
                if abs(corr) > abs(max_corr):
                    max_corr = corr
                    correlated_with = accepted_symbol

        if is_correlated:
            candidate['rejection_reason'] = f"Too correlated with {correlated_with} ({max_corr:.1%})"
            rejected.append(candidate)
        else:
            accepted.append(candidate)
            accepted_symbols.add(symbol)

    return accepted, rejected
