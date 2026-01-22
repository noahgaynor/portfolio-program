"""
Data Fetcher Module

Fetches price data and stock information from Yahoo Finance using yfinance.
"""
import yfinance as yf
import pandas as pd
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Tuple
import logging
import time

from config import LOOKBACK_DAYS, MIN_HISTORY_DAYS, TIMEFRAMES

logger = logging.getLogger(__name__)


class DataFetcher:
    """Fetches and caches stock data from Yahoo Finance."""

    def __init__(self):
        self._cache: Dict[str, Dict] = {}
        self._sector_cache: Dict[str, str] = {}

    def get_stock_info(self, symbol: str) -> Dict:
        """
        Get stock information including sector.

        Args:
            symbol: Stock ticker symbol

        Returns:
            Dictionary with stock info (name, sector, industry, etc.)
        """
        try:
            ticker = yf.Ticker(symbol)
            info = ticker.info

            return {
                'symbol': symbol,
                'name': info.get('longName', info.get('shortName', symbol)),
                'sector': info.get('sector', 'Unknown'),
                'industry': info.get('industry', 'Unknown'),
                'market_cap': info.get('marketCap', 0),
                'currency': info.get('currency', 'USD'),
                'exchange': info.get('exchange', 'Unknown')
            }
        except Exception as e:
            logger.error(f"Error fetching info for {symbol}: {e}")
            return {
                'symbol': symbol,
                'name': symbol,
                'sector': 'Unknown',
                'industry': 'Unknown',
                'market_cap': 0,
                'currency': 'USD',
                'exchange': 'Unknown'
            }

    def get_sector(self, symbol: str) -> str:
        """
        Get sector for a symbol (cached).

        Args:
            symbol: Stock ticker symbol

        Returns:
            Sector name string
        """
        if symbol not in self._sector_cache:
            info = self.get_stock_info(symbol)
            self._sector_cache[symbol] = info['sector']
        return self._sector_cache[symbol]

    def fetch_ohlcv(
        self,
        symbol: str,
        interval: str = '1d',
        lookback_days: int = LOOKBACK_DAYS
    ) -> Optional[pd.DataFrame]:
        """
        Fetch OHLCV data for a symbol.

        Args:
            symbol: Stock ticker symbol
            interval: Data interval ('1d', '1wk', '1mo')
            lookback_days: Number of days to look back

        Returns:
            DataFrame with OHLCV data or None if failed
        """
        try:
            ticker = yf.Ticker(symbol)

            # Calculate date range
            end_date = datetime.now()
            start_date = end_date - timedelta(days=lookback_days)

            # Fetch data
            df = ticker.history(
                start=start_date,
                end=end_date,
                interval=interval,
                auto_adjust=True
            )

            if df.empty or len(df) < MIN_HISTORY_DAYS // (7 if interval == '1wk' else 30 if interval == '1mo' else 1):
                logger.warning(f"Insufficient data for {symbol} at {interval} interval")
                return None

            return df

        except Exception as e:
            logger.error(f"Error fetching data for {symbol}: {e}")
            return None

    def fetch_multi_timeframe(
        self,
        symbol: str,
        lookback_days: int = LOOKBACK_DAYS
    ) -> Dict[str, Optional[pd.DataFrame]]:
        """
        Fetch data for all required timeframes.

        Args:
            symbol: Stock ticker symbol
            lookback_days: Number of days to look back

        Returns:
            Dictionary with DataFrames for each timeframe
        """
        result = {}

        for tf_name, tf_interval in TIMEFRAMES.items():
            # For weekly/monthly, we need more historical data
            adjusted_lookback = lookback_days
            if tf_interval == '1wk':
                adjusted_lookback = max(lookback_days, 365 * 2)  # 2 years for weekly
            elif tf_interval == '1mo':
                adjusted_lookback = max(lookback_days, 365 * 5)  # 5 years for monthly

            df = self.fetch_ohlcv(symbol, tf_interval, adjusted_lookback)
            result[tf_name] = df

            # Small delay to avoid rate limiting
            time.sleep(0.1)

        return result

    def fetch_batch(
        self,
        symbols: List[str],
        interval: str = '1d',
        lookback_days: int = LOOKBACK_DAYS
    ) -> Dict[str, pd.DataFrame]:
        """
        Fetch data for multiple symbols efficiently.

        Args:
            symbols: List of stock ticker symbols
            interval: Data interval
            lookback_days: Number of days to look back

        Returns:
            Dictionary mapping symbols to their DataFrames
        """
        result = {}

        # Calculate date range
        end_date = datetime.now()
        start_date = end_date - timedelta(days=lookback_days)

        try:
            # Batch download
            data = yf.download(
                symbols,
                start=start_date,
                end=end_date,
                interval=interval,
                group_by='ticker',
                auto_adjust=True,
                threads=True
            )

            # Split into individual DataFrames
            if len(symbols) == 1:
                result[symbols[0]] = data
            else:
                for symbol in symbols:
                    if symbol in data.columns.get_level_values(0):
                        df = data[symbol].dropna(how='all')
                        if not df.empty:
                            result[symbol] = df

        except Exception as e:
            logger.error(f"Error in batch fetch: {e}")
            # Fallback to individual fetches
            for symbol in symbols:
                df = self.fetch_ohlcv(symbol, interval, lookback_days)
                if df is not None:
                    result[symbol] = df

        return result

    def get_current_price(self, symbol: str) -> Optional[float]:
        """
        Get current/latest price for a symbol.

        Args:
            symbol: Stock ticker symbol

        Returns:
            Current price or None if failed
        """
        try:
            ticker = yf.Ticker(symbol)
            # Try to get from fast_info first
            try:
                return ticker.fast_info['lastPrice']
            except:
                pass

            # Fallback to history
            hist = ticker.history(period='1d')
            if not hist.empty:
                return float(hist['Close'].iloc[-1])

            return None
        except Exception as e:
            logger.error(f"Error getting price for {symbol}: {e}")
            return None

    def validate_symbol(self, symbol: str) -> bool:
        """
        Check if a symbol is valid and tradeable.

        Args:
            symbol: Stock ticker symbol

        Returns:
            True if valid, False otherwise
        """
        try:
            ticker = yf.Ticker(symbol)
            info = ticker.info
            # Check if we got valid info back
            return info.get('regularMarketPrice') is not None or info.get('currentPrice') is not None
        except:
            return False

    def get_batch_sectors(self, symbols: List[str]) -> Dict[str, str]:
        """
        Get sectors for multiple symbols.

        Args:
            symbols: List of stock ticker symbols

        Returns:
            Dictionary mapping symbols to sectors
        """
        result = {}
        for symbol in symbols:
            result[symbol] = self.get_sector(symbol)
            time.sleep(0.05)  # Small delay to avoid rate limiting
        return result
