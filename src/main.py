"""
Main Orchestration Script

Coordinates the daily portfolio update process:
1. Load watchlist
2. Scan all symbols for V-Stop signals
3. Identify entry/exit candidates
4. Update portfolio allocations
5. Save data for frontend
6. Send notifications
"""
import json
import logging
import sys
from datetime import datetime
from pathlib import Path
from typing import List, Dict, Optional
import shutil

# Add parent directory to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent))

from config import DATA_DIR, DOCS_DIR, DEFAULT_CORRELATION_THRESHOLD
from src.data_fetcher import DataFetcher
from src.scanner import MTFScanner
from src.portfolio import PortfolioManager
from src.notifier import TelegramNotifier
from src.correlation import filter_correlated_entries

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


def load_settings(filepath: Path = DATA_DIR / "settings.json") -> Dict:
    """
    Load user settings from JSON file.

    Args:
        filepath: Path to settings file

    Returns:
        Settings dictionary
    """
    default_settings = {
        'correlation_threshold': DEFAULT_CORRELATION_THRESHOLD
    }

    if not filepath.exists():
        logger.info(f"Settings file not found, using defaults: {default_settings}")
        return default_settings

    try:
        with open(filepath, 'r') as f:
            settings = json.load(f)
            # Merge with defaults for any missing keys
            for key, value in default_settings.items():
                if key not in settings:
                    settings[key] = value
            logger.info(f"Loaded settings: correlation_threshold={settings['correlation_threshold']}")
            return settings
    except Exception as e:
        logger.error(f"Error loading settings: {e}, using defaults")
        return default_settings


def load_watchlist(filepath: Path = DATA_DIR / "watchlist.json") -> List[str]:
    """
    Load watchlist from JSON file.

    Args:
        filepath: Path to watchlist file

    Returns:
        List of stock symbols
    """
    import os
    logger.info(f"Current working directory: {os.getcwd()}")
    logger.info(f"DATA_DIR: {DATA_DIR}")
    logger.info(f"Loading watchlist from: {filepath}")
    logger.info(f"File exists: {filepath.exists()}")

    try:
        with open(filepath, 'r') as f:
            data = json.load(f)
            symbols = data.get('symbols', [])
            logger.info(f"Loaded {len(symbols)} symbols: {symbols[:5]}{'...' if len(symbols) > 5 else ''}")
            return symbols
    except FileNotFoundError:
        logger.error(f"Watchlist NOT FOUND at {filepath}")
        # Try alternative paths
        alt_paths = [
            Path("data/watchlist.json"),
            Path("./data/watchlist.json"),
            Path(__file__).parent.parent / "data" / "watchlist.json"
        ]
        for alt in alt_paths:
            logger.info(f"Trying alternative: {alt} (exists: {alt.exists()})")
            if alt.exists():
                try:
                    with open(alt, 'r') as f:
                        data = json.load(f)
                        symbols = data.get('symbols', [])
                        logger.info(f"SUCCESS: Loaded {len(symbols)} symbols from {alt}")
                        return symbols
                except Exception as e:
                    logger.error(f"Failed to load from {alt}: {e}")
        return []
    except Exception as e:
        logger.error(f"Error loading watchlist: {e}")
        return []


def copy_data_to_docs():
    """Copy data files to docs directory for GitHub Pages."""
    docs_data_dir = DOCS_DIR / "data"
    docs_data_dir.mkdir(parents=True, exist_ok=True)

    for filename in ["portfolio.json", "history.json", "signals.json", "watchlist.json", "settings.json"]:
        src = DATA_DIR / filename
        dst = docs_data_dir / filename
        if src.exists():
            shutil.copy2(src, dst)
            logger.info(f"Copied {filename} to docs/data/")


def run_daily_update(
    watchlist: Optional[List[str]] = None,
    send_notifications: bool = True
) -> Dict:
    """
    Run the full daily update process.

    Args:
        watchlist: Optional list of symbols (loads from file if not provided)
        send_notifications: Whether to send Telegram notifications

    Returns:
        Update results dictionary
    """
    logger.info("Starting daily V-Stop portfolio update...")
    start_time = datetime.now()

    # Initialize components
    data_fetcher = DataFetcher()
    scanner = MTFScanner(data_fetcher)
    portfolio_manager = PortfolioManager()
    notifier = TelegramNotifier()

    # Load settings
    settings = load_settings()
    correlation_threshold = settings.get('correlation_threshold', DEFAULT_CORRELATION_THRESHOLD)
    logger.info(f"Using correlation threshold: {correlation_threshold:.0%}")

    # Load watchlist
    if watchlist is None:
        watchlist = load_watchlist()

    if not watchlist:
        logger.error("No symbols in watchlist!")
        return {'error': 'Empty watchlist'}

    logger.info(f"Scanning {len(watchlist)} symbols...")

    # Scan all symbols
    scan_results = scanner.scan_watchlist(watchlist)
    logger.info(f"Successfully scanned {len(scan_results)}/{len(watchlist)} symbols")

    # Generate signal summary
    signal_summary = scanner.generate_signal_summary(scan_results)

    # Get qualifying stocks
    qualifying_stocks = scanner.get_qualifying_stocks(scan_results)
    logger.info(f"Found {len(qualifying_stocks)} qualifying stocks (all bullish)")

    # Get current holdings
    current_holdings = portfolio_manager.get_current_holdings()
    logger.info(f"Current holdings: {len(current_holdings)} positions")

    # Identify exit and entry candidates
    exit_candidates = scanner.get_exit_candidates(current_holdings, scan_results)
    entry_candidates = scanner.get_entry_candidates(qualifying_stocks, current_holdings)

    logger.info(f"Exit candidates: {len(exit_candidates)}")
    logger.info(f"Entry candidates (before correlation filter): {len(entry_candidates)}")

    # Apply correlation filter to entry candidates
    # Build daily data dict for correlation calculation
    daily_data = {}
    for symbol in list(current_holdings) + [c['symbol'] for c in entry_candidates]:
        data = data_fetcher.fetch_symbol_data(symbol)
        if data and 'daily' in data:
            daily_data[symbol] = data['daily']

    # Filter out correlated entries
    filtered_entries, rejected_entries = filter_correlated_entries(
        new_candidates=entry_candidates,
        existing_positions=current_holdings,
        daily_data=daily_data,
        threshold=correlation_threshold
    )

    logger.info(f"Entry candidates (after correlation filter): {len(filtered_entries)}")
    if rejected_entries:
        logger.info(f"Rejected due to correlation: {[r['symbol'] for r in rejected_entries]}")

    # Use filtered entries
    entry_candidates = filtered_entries

    # Process the daily update
    update_result = portfolio_manager.process_daily_update(
        scan_results=scan_results,
        qualifying_stocks=qualifying_stocks,
        exit_candidates=exit_candidates,
        entry_candidates=entry_candidates
    )

    # Calculate performance
    current_prices = {
        symbol: result['current_price']
        for symbol, result in scan_results.items()
    }
    performance = portfolio_manager.calculate_performance(current_prices)

    # Save signals data for frontend
    signals_data = {
        'scan_results': scan_results,
        'signal_summary': signal_summary,
        'qualifying_stocks': qualifying_stocks,
        'rejected_correlated': rejected_entries,
        'correlation_threshold': correlation_threshold,
        'last_update': datetime.now().isoformat()
    }
    portfolio_manager.save_signals(signals_data)

    # Copy data to docs for GitHub Pages
    copy_data_to_docs()

    # Send notifications if configured
    if send_notifications and notifier.is_configured():
        try:
            notifier.send_daily_update(update_result)
            logger.info("Telegram notification sent")
        except Exception as e:
            logger.error(f"Failed to send notification: {e}")

    # Calculate execution time
    execution_time = (datetime.now() - start_time).total_seconds()
    logger.info(f"Daily update completed in {execution_time:.1f} seconds")

    return {
        'status': 'success',
        'timestamp': datetime.now().isoformat(),
        'execution_time_seconds': execution_time,
        'symbols_scanned': len(scan_results),
        'qualifying_count': len(qualifying_stocks),
        'buys': update_result.get('buys', []),
        'sells': update_result.get('sells', []),
        'portfolio_summary': portfolio_manager.get_portfolio_summary(),
        'performance': performance
    }


def run_scan_only(watchlist: Optional[List[str]] = None) -> Dict:
    """
    Run scan without updating portfolio (useful for testing).

    Args:
        watchlist: Optional list of symbols

    Returns:
        Scan results dictionary
    """
    logger.info("Running scan only (no portfolio update)...")

    data_fetcher = DataFetcher()
    scanner = MTFScanner(data_fetcher)

    if watchlist is None:
        watchlist = load_watchlist()

    if not watchlist:
        return {'error': 'Empty watchlist'}

    scan_results = scanner.scan_watchlist(watchlist)
    signal_summary = scanner.generate_signal_summary(scan_results)
    qualifying_stocks = scanner.get_qualifying_stocks(scan_results)

    return {
        'status': 'success',
        'timestamp': datetime.now().isoformat(),
        'scan_results': scan_results,
        'signal_summary': signal_summary,
        'qualifying_stocks': qualifying_stocks
    }


def main():
    """Main entry point."""
    import argparse

    parser = argparse.ArgumentParser(description='V-Stop Portfolio Recommender')
    parser.add_argument('--scan-only', action='store_true',
                        help='Run scan without updating portfolio')
    parser.add_argument('--no-notify', action='store_true',
                        help='Skip Telegram notifications')
    parser.add_argument('--test-telegram', action='store_true',
                        help='Send test Telegram message')
    parser.add_argument('--symbols', nargs='+',
                        help='Override watchlist with specific symbols')

    args = parser.parse_args()

    if args.test_telegram:
        notifier = TelegramNotifier()
        if notifier.send_test_message():
            print("Test message sent successfully!")
        else:
            print("Failed to send test message. Check your configuration.")
        return

    watchlist = args.symbols if args.symbols else None

    if args.scan_only:
        result = run_scan_only(watchlist)
    else:
        result = run_daily_update(
            watchlist=watchlist,
            send_notifications=not args.no_notify
        )

    # Print summary
    print("\n" + "="*50)
    print("V-STOP PORTFOLIO UPDATE SUMMARY")
    print("="*50)

    if result.get('status') == 'success':
        print(f"Timestamp: {result['timestamp']}")
        print(f"Symbols Scanned: {result.get('symbols_scanned', 'N/A')}")
        print(f"Qualifying Stocks: {result.get('qualifying_count', 'N/A')}")

        buys = result.get('buys', [])
        sells = result.get('sells', [])

        if buys:
            print(f"\nBUYS ({len(buys)}):")
            for buy in buys:
                print(f"  + {buy['symbol']} ({buy.get('sector', 'Unknown')}) @ ${buy.get('entry_price', 0):.2f}")

        if sells:
            print(f"\nSELLS ({len(sells)}):")
            for sell in sells:
                print(f"  - {sell['symbol']} @ ${sell.get('exit_price', 0):.2f} ({sell.get('reason', '')})")

        summary = result.get('portfolio_summary', {})
        if summary:
            print(f"\nPORTFOLIO:")
            print(f"  Positions: {summary.get('num_positions', 0)}")
            print(f"  Sectors: {summary.get('num_sectors', 0)}")
            print(f"  Cash: {summary.get('cash_weight', 1.0)*100:.1f}%")

        perf = result.get('performance', {})
        if perf:
            print(f"\nPERFORMANCE:")
            print(f"  Total Return: {perf.get('total_return_pct', 0):.2f}%")

    else:
        print(f"Error: {result.get('error', 'Unknown error')}")


if __name__ == "__main__":
    main()
