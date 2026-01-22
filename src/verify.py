#!/usr/bin/env python3
"""
V-Stop Verification Tool

Run with: python -m src.verify SYMBOL [SYMBOL2 ...]
Example:  python -m src.verify KLAC AAPL MSFT
"""

import sys
from .data_fetcher import DataFetcher
from .vstop import calculate_vstop


def verify_symbol(symbol: str):
    """Fetch data and calculate V-Stop for all timeframes, displaying results."""
    print(f"\n{'='*60}")
    print(f"  V-STOP VERIFICATION: {symbol}")
    print(f"{'='*60}")

    fetcher = DataFetcher()
    data = fetcher.fetch_symbol_data(symbol)

    if not data:
        print(f"  ERROR: Could not fetch data for {symbol}")
        return

    timeframes = ['daily', 'weekly', 'monthly']

    for tf in timeframes:
        df = data.get(tf)
        if df is None or df.empty:
            print(f"\n  {tf.upper():8} | No data available")
            continue

        result = calculate_vstop(df)

        if result is None:
            print(f"\n  {tf.upper():8} | V-Stop calculation failed")
            continue

        # Get latest values
        latest_close = df['Close'].iloc[-1]
        latest_stop = result['stop'].iloc[-1]
        latest_trend = result['trend'].iloc[-1]
        latest_atr = result['atr'].iloc[-1]

        direction = "BULLISH 🟢" if latest_trend == 1 else "BEARISH 🔴"

        # Calculate distance from stop
        if latest_trend == 1:
            distance = ((latest_close - latest_stop) / latest_close) * 100
            distance_str = f"{distance:.2f}% above stop"
        else:
            distance = ((latest_stop - latest_close) / latest_close) * 100
            distance_str = f"{distance:.2f}% below stop"

        print(f"\n  {tf.upper():8} | {direction}")
        print(f"  {'':8} | Close:    ${latest_close:.2f}")
        print(f"  {'':8} | V-Stop:   ${latest_stop:.2f}")
        print(f"  {'':8} | ATR:      ${latest_atr:.2f}")
        print(f"  {'':8} | Distance: {distance_str}")
        print(f"  {'':8} | Last bar: {df.index[-1].strftime('%Y-%m-%d')}")

    # Summary
    print(f"\n  {'-'*56}")
    all_bullish = True
    for tf in timeframes:
        df = data.get(tf)
        if df is not None and not df.empty:
            result = calculate_vstop(df)
            if result is not None and result['trend'].iloc[-1] != 1:
                all_bullish = False
                break

    if all_bullish:
        print(f"  OVERALL: ALL TIMEFRAMES BULLISH ✅ - Qualifies for portfolio")
    else:
        print(f"  OVERALL: NOT ALL BULLISH ❌ - Does not qualify")

    print(f"{'='*60}\n")


def main():
    if len(sys.argv) < 2:
        print("Usage: python -m src.verify SYMBOL [SYMBOL2 ...]")
        print("Example: python -m src.verify KLAC AAPL MSFT")
        sys.exit(1)

    symbols = [s.upper() for s in sys.argv[1:]]

    print("\n" + "="*60)
    print("  V-STOP MTF VERIFICATION TOOL")
    print("  Parameters: Length=10, Factor=3.0 (ATR multiplier)")
    print("="*60)

    for symbol in symbols:
        verify_symbol(symbol)


if __name__ == "__main__":
    main()
