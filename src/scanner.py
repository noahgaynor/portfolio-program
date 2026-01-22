"""
Multi-Timeframe Scanner Module

Scans stocks across daily, weekly, and monthly timeframes using the V-Stop indicator
to identify stocks with bullish alignment on all timeframes.
"""
import logging
from typing import Dict, List, Optional
from datetime import datetime
import pandas as pd

from src.data_fetcher import DataFetcher
from src.vstop import get_vstop_signal, check_mtf_alignment
from config import VSTOP_LENGTH, VSTOP_ATR_FACTOR

logger = logging.getLogger(__name__)


class MTFScanner:
    """Multi-timeframe V-Stop scanner."""

    def __init__(self, data_fetcher: Optional[DataFetcher] = None):
        """
        Initialize the scanner.

        Args:
            data_fetcher: Optional DataFetcher instance (creates one if not provided)
        """
        self.data_fetcher = data_fetcher or DataFetcher()

    def scan_symbol(self, symbol: str) -> Optional[Dict]:
        """
        Scan a single symbol across all timeframes.

        Args:
            symbol: Stock ticker symbol

        Returns:
            Dictionary with scan results or None if scan failed
        """
        try:
            # Fetch data for all timeframes
            mtf_data = self.data_fetcher.fetch_multi_timeframe(symbol)

            # Check if we have data for all timeframes
            for tf_name, df in mtf_data.items():
                if df is None or df.empty:
                    logger.warning(f"Missing {tf_name} data for {symbol}")
                    return None

            # Calculate V-Stop signals for each timeframe
            daily_signal = get_vstop_signal(
                mtf_data['daily'],
                VSTOP_LENGTH,
                VSTOP_ATR_FACTOR
            )
            weekly_signal = get_vstop_signal(
                mtf_data['weekly'],
                VSTOP_LENGTH,
                VSTOP_ATR_FACTOR
            )
            monthly_signal = get_vstop_signal(
                mtf_data['monthly'],
                VSTOP_LENGTH,
                VSTOP_ATR_FACTOR
            )

            # Check alignment
            alignment = check_mtf_alignment(daily_signal, weekly_signal, monthly_signal)

            # Get stock info
            stock_info = self.data_fetcher.get_stock_info(symbol)

            return {
                'symbol': symbol,
                'name': stock_info['name'],
                'sector': stock_info['sector'],
                'industry': stock_info['industry'],
                'current_price': alignment['current_price'],
                'all_bullish': alignment['all_bullish'],
                'daily_bullish': alignment['daily_bullish'],
                'weekly_bullish': alignment['weekly_bullish'],
                'monthly_bullish': alignment['monthly_bullish'],
                'daily_stop': alignment['daily_stop'],
                'weekly_stop': alignment['weekly_stop'],
                'monthly_stop': alignment['monthly_stop'],
                'daily_bars_in_trend': daily_signal['bars_in_trend'],
                'weekly_bars_in_trend': weekly_signal['bars_in_trend'],
                'monthly_bars_in_trend': monthly_signal['bars_in_trend'],
                'scan_time': datetime.now().isoformat()
            }

        except Exception as e:
            logger.error(f"Error scanning {symbol}: {e}")
            return None

    def scan_watchlist(self, symbols: List[str]) -> Dict[str, Dict]:
        """
        Scan all symbols in the watchlist.

        Args:
            symbols: List of stock ticker symbols

        Returns:
            Dictionary mapping symbols to their scan results
        """
        results = {}
        total = len(symbols)

        for i, symbol in enumerate(symbols, 1):
            logger.info(f"Scanning {symbol} ({i}/{total})...")
            result = self.scan_symbol(symbol)
            if result:
                results[symbol] = result

        return results

    def get_qualifying_stocks(self, scan_results: Dict[str, Dict]) -> List[Dict]:
        """
        Filter scan results to get stocks that qualify for the portfolio.

        Qualifying criteria: All three timeframes (D, W, M) must be bullish.

        Args:
            scan_results: Dictionary of scan results from scan_watchlist

        Returns:
            List of qualifying stock dictionaries, sorted by monthly trend strength
        """
        qualifying = [
            result for result in scan_results.values()
            if result['all_bullish']
        ]

        # Sort by trend strength (monthly bars in trend as primary sort)
        qualifying.sort(key=lambda x: (
            x['monthly_bars_in_trend'],
            x['weekly_bars_in_trend'],
            x['daily_bars_in_trend']
        ), reverse=True)

        return qualifying

    def get_exit_candidates(
        self,
        current_holdings: List[str],
        scan_results: Dict[str, Dict]
    ) -> List[Dict]:
        """
        Identify stocks that should be sold (no longer qualifying).

        A stock should be sold when its DAILY V-Stop turns bearish.

        Args:
            current_holdings: List of currently held symbols
            scan_results: Current scan results

        Returns:
            List of stocks that should be sold
        """
        exit_candidates = []

        for symbol in current_holdings:
            if symbol in scan_results:
                result = scan_results[symbol]
                # Exit when daily turns bearish
                if not result['daily_bullish']:
                    exit_candidates.append({
                        'symbol': symbol,
                        'name': result['name'],
                        'reason': 'Daily V-Stop turned bearish',
                        'current_price': result['current_price'],
                        'daily_bullish': result['daily_bullish'],
                        'weekly_bullish': result['weekly_bullish'],
                        'monthly_bullish': result['monthly_bullish']
                    })
            else:
                # Symbol not in results (may have been delisted or error)
                exit_candidates.append({
                    'symbol': symbol,
                    'name': symbol,
                    'reason': 'Unable to scan (may be delisted)',
                    'current_price': None,
                    'daily_bullish': None,
                    'weekly_bullish': None,
                    'monthly_bullish': None
                })

        return exit_candidates

    def get_entry_candidates(
        self,
        qualifying_stocks: List[Dict],
        current_holdings: List[str]
    ) -> List[Dict]:
        """
        Get new stocks that qualify for entry (not already held).

        Args:
            qualifying_stocks: List of all qualifying stocks
            current_holdings: List of currently held symbols

        Returns:
            List of new entry candidates
        """
        return [
            stock for stock in qualifying_stocks
            if stock['symbol'] not in current_holdings
        ]

    def generate_signal_summary(self, scan_results: Dict[str, Dict]) -> Dict:
        """
        Generate a summary of all signals.

        Args:
            scan_results: Dictionary of scan results

        Returns:
            Summary dictionary with counts and lists
        """
        all_bullish = []
        daily_only = []
        weekly_only = []
        monthly_only = []
        all_bearish = []
        mixed = []

        for symbol, result in scan_results.items():
            d = result['daily_bullish']
            w = result['weekly_bullish']
            m = result['monthly_bullish']

            if d and w and m:
                all_bullish.append(result)
            elif not d and not w and not m:
                all_bearish.append(result)
            elif d and not w and not m:
                daily_only.append(result)
            elif w and not d and not m:
                weekly_only.append(result)
            elif m and not d and not w:
                monthly_only.append(result)
            else:
                mixed.append(result)

        return {
            'total_scanned': len(scan_results),
            'all_bullish_count': len(all_bullish),
            'all_bearish_count': len(all_bearish),
            'all_bullish': all_bullish,
            'all_bearish': all_bearish,
            'daily_only': daily_only,
            'weekly_only': weekly_only,
            'monthly_only': monthly_only,
            'mixed': mixed,
            'scan_time': datetime.now().isoformat()
        }
