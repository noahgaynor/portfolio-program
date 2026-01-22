"""
Portfolio Manager Module

Manages portfolio allocation with sector constraints, tracks positions,
and calculates performance metrics.
"""
import json
import logging
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional, Tuple
from collections import defaultdict

from config import (
    DATA_DIR,
    MAX_SECTOR_ALLOCATION,
    MIN_SECTORS_REQUIRED,
    TARGET_POSITIONS
)

logger = logging.getLogger(__name__)


class PortfolioManager:
    """Manages portfolio state, allocations, and constraints."""

    def __init__(self, data_dir: Path = DATA_DIR):
        """
        Initialize the portfolio manager.

        Args:
            data_dir: Directory for storing portfolio data
        """
        self.data_dir = Path(data_dir)
        self.data_dir.mkdir(parents=True, exist_ok=True)

        self.portfolio_file = self.data_dir / "portfolio.json"
        self.history_file = self.data_dir / "history.json"
        self.signals_file = self.data_dir / "signals.json"

        self.portfolio = self._load_portfolio()
        self.history = self._load_history()

    def _load_portfolio(self) -> Dict:
        """Load portfolio state from file."""
        if self.portfolio_file.exists():
            try:
                with open(self.portfolio_file, 'r') as f:
                    return json.load(f)
            except Exception as e:
                logger.error(f"Error loading portfolio: {e}")

        # Return default empty portfolio
        return {
            'positions': {},
            'cash_weight': 1.0,
            'last_update': None,
            'inception_date': datetime.now().isoformat()
        }

    def _load_history(self) -> List[Dict]:
        """Load portfolio history from file."""
        if self.history_file.exists():
            try:
                with open(self.history_file, 'r') as f:
                    return json.load(f)
            except Exception as e:
                logger.error(f"Error loading history: {e}")
        return []

    def _save_portfolio(self):
        """Save portfolio state to file."""
        try:
            with open(self.portfolio_file, 'w') as f:
                json.dump(self.portfolio, f, indent=2)
        except Exception as e:
            logger.error(f"Error saving portfolio: {e}")

    def _save_history(self):
        """Save portfolio history to file."""
        try:
            with open(self.history_file, 'w') as f:
                json.dump(self.history, f, indent=2)
        except Exception as e:
            logger.error(f"Error saving history: {e}")

    def save_signals(self, signals: Dict):
        """Save current signals to file for frontend."""
        try:
            with open(self.signals_file, 'w') as f:
                json.dump(signals, f, indent=2)
        except Exception as e:
            logger.error(f"Error saving signals: {e}")

    def get_current_holdings(self) -> List[str]:
        """Get list of currently held symbols."""
        return list(self.portfolio.get('positions', {}).keys())

    def get_sector_allocations(self) -> Dict[str, float]:
        """Calculate current allocation by sector."""
        sector_weights = defaultdict(float)
        positions = self.portfolio.get('positions', {})

        for symbol, position in positions.items():
            sector = position.get('sector', 'Unknown')
            weight = position.get('weight', 0)
            sector_weights[sector] += weight

        return dict(sector_weights)

    def get_sector_count(self) -> int:
        """Get number of unique sectors in portfolio."""
        positions = self.portfolio.get('positions', {})
        sectors = set(p.get('sector', 'Unknown') for p in positions.values())
        return len(sectors)

    def calculate_allocations(
        self,
        qualifying_stocks: List[Dict],
        current_positions: Dict[str, Dict]
    ) -> Dict[str, float]:
        """
        Calculate target allocations respecting sector constraints.

        Strategy:
        1. Equal weight base allocation
        2. Reduce weights for sectors exceeding MAX_SECTOR_ALLOCATION
        3. Ensure MIN_SECTORS_REQUIRED is met

        Args:
            qualifying_stocks: List of stocks that qualify for entry
            current_positions: Current portfolio positions

        Returns:
            Dictionary mapping symbols to target weights
        """
        if not qualifying_stocks:
            return {}

        # Combine existing positions and new candidates
        all_stocks = []

        # Add current positions that are still qualifying
        current_symbols = set(current_positions.keys())
        for stock in qualifying_stocks:
            if stock['symbol'] in current_symbols:
                all_stocks.append(stock)

        # Add new entry candidates
        for stock in qualifying_stocks:
            if stock['symbol'] not in current_symbols:
                all_stocks.append(stock)

        if not all_stocks:
            return {}

        # Start with equal weights
        n_stocks = len(all_stocks)
        base_weight = 1.0 / n_stocks

        # Group by sector
        sector_stocks = defaultdict(list)
        for stock in all_stocks:
            sector = stock.get('sector', 'Unknown')
            sector_stocks[sector].append(stock)

        # Calculate sector weights and adjust if needed
        allocations = {}
        sector_weights = {}

        for sector, stocks in sector_stocks.items():
            sector_total_weight = len(stocks) * base_weight

            if sector_total_weight > MAX_SECTOR_ALLOCATION:
                # Cap sector at MAX_SECTOR_ALLOCATION
                adjusted_weight = MAX_SECTOR_ALLOCATION / len(stocks)
                for stock in stocks:
                    allocations[stock['symbol']] = adjusted_weight
                sector_weights[sector] = MAX_SECTOR_ALLOCATION
            else:
                for stock in stocks:
                    allocations[stock['symbol']] = base_weight
                sector_weights[sector] = sector_total_weight

        # Normalize weights to sum to 1.0 (or less if we're in cash)
        total_weight = sum(allocations.values())
        if total_weight > 0:
            # Keep some cash if we don't have enough qualifying stocks
            target_invested = min(1.0, total_weight)
            scale_factor = target_invested / total_weight

            for symbol in allocations:
                allocations[symbol] *= scale_factor

        return allocations

    def check_sector_constraints(
        self,
        new_stock: Dict,
        current_allocations: Dict[str, float],
        stock_sectors: Dict[str, str]
    ) -> Tuple[bool, str]:
        """
        Check if adding a new stock would violate sector constraints.

        Args:
            new_stock: Stock to potentially add
            current_allocations: Current weight allocations
            stock_sectors: Mapping of symbols to sectors

        Returns:
            Tuple of (is_allowed, reason_if_not)
        """
        new_sector = new_stock.get('sector', 'Unknown')

        # Calculate current sector allocation
        sector_weight = sum(
            weight for symbol, weight in current_allocations.items()
            if stock_sectors.get(symbol, 'Unknown') == new_sector
        )

        # Check if adding this stock would exceed sector limit
        n_current = len(current_allocations)
        proposed_weight = 1.0 / (n_current + 1)

        if sector_weight + proposed_weight > MAX_SECTOR_ALLOCATION:
            return False, f"Would exceed {MAX_SECTOR_ALLOCATION*100}% sector limit for {new_sector}"

        return True, ""

    def process_daily_update(
        self,
        scan_results: Dict[str, Dict],
        qualifying_stocks: List[Dict],
        exit_candidates: List[Dict],
        entry_candidates: List[Dict]
    ) -> Dict:
        """
        Process end-of-day update and generate recommendations.

        Args:
            scan_results: Full scan results for all symbols
            qualifying_stocks: Stocks meeting all criteria
            exit_candidates: Stocks to sell
            entry_candidates: New stocks to buy

        Returns:
            Update summary with buy/sell recommendations
        """
        timestamp = datetime.now().isoformat()
        current_positions = self.portfolio.get('positions', {})

        # Process exits
        sells = []
        for exit_stock in exit_candidates:
            symbol = exit_stock['symbol']
            if symbol in current_positions:
                position = current_positions[symbol]
                sells.append({
                    'symbol': symbol,
                    'name': exit_stock.get('name', symbol),
                    'reason': exit_stock['reason'],
                    'entry_price': position.get('entry_price'),
                    'entry_date': position.get('entry_date'),
                    'exit_price': exit_stock.get('current_price'),
                    'exit_date': timestamp
                })
                del current_positions[symbol]

        # Calculate new allocations with remaining positions + new entries
        remaining_qualifying = [
            s for s in qualifying_stocks
            if s['symbol'] in current_positions or s['symbol'] in [e['symbol'] for e in entry_candidates]
        ]

        new_allocations = self.calculate_allocations(
            remaining_qualifying,
            current_positions
        )

        # Process entries
        buys = []
        for entry_stock in entry_candidates:
            symbol = entry_stock['symbol']

            # Get stock's sector info
            stock_sectors = {
                s: current_positions.get(s, {}).get('sector', scan_results.get(s, {}).get('sector', 'Unknown'))
                for s in current_positions
            }

            # Check sector constraints
            allowed, reason = self.check_sector_constraints(
                entry_stock,
                {s: p.get('weight', 0) for s, p in current_positions.items()},
                stock_sectors
            )

            if allowed or len(current_positions) < MIN_SECTORS_REQUIRED:
                weight = new_allocations.get(symbol, 1.0 / max(len(new_allocations), 1))

                buys.append({
                    'symbol': symbol,
                    'name': entry_stock.get('name', symbol),
                    'sector': entry_stock.get('sector', 'Unknown'),
                    'entry_price': entry_stock.get('current_price'),
                    'entry_date': timestamp,
                    'weight': weight
                })

                current_positions[symbol] = {
                    'symbol': symbol,
                    'name': entry_stock.get('name', symbol),
                    'sector': entry_stock.get('sector', 'Unknown'),
                    'entry_price': entry_stock.get('current_price'),
                    'entry_date': timestamp,
                    'weight': weight
                }

        # Recalculate all weights after changes
        if current_positions:
            final_qualifying = [
                s for s in qualifying_stocks
                if s['symbol'] in current_positions
            ]
            final_allocations = self.calculate_allocations(
                final_qualifying,
                {}  # Recalculate from scratch
            )

            for symbol, weight in final_allocations.items():
                if symbol in current_positions:
                    current_positions[symbol]['weight'] = weight

        # Update portfolio state
        self.portfolio['positions'] = current_positions
        self.portfolio['last_update'] = timestamp
        self.portfolio['cash_weight'] = 1.0 - sum(
            p.get('weight', 0) for p in current_positions.values()
        )

        # Create update record
        update_record = {
            'timestamp': timestamp,
            'buys': buys,
            'sells': sells,
            'portfolio_snapshot': {
                'positions': list(current_positions.keys()),
                'num_positions': len(current_positions),
                'sector_allocation': self.get_sector_allocations(),
                'num_sectors': self.get_sector_count()
            }
        }

        # Add to history
        self.history.append(update_record)

        # Save all data
        self._save_portfolio()
        self._save_history()

        return update_record

    def get_portfolio_summary(self) -> Dict:
        """
        Get current portfolio summary.

        Returns:
            Dictionary with portfolio summary information
        """
        positions = self.portfolio.get('positions', {})

        return {
            'num_positions': len(positions),
            'positions': list(positions.values()),
            'sector_allocation': self.get_sector_allocations(),
            'num_sectors': self.get_sector_count(),
            'cash_weight': self.portfolio.get('cash_weight', 1.0),
            'last_update': self.portfolio.get('last_update'),
            'inception_date': self.portfolio.get('inception_date')
        }

    def calculate_performance(self, current_prices: Dict[str, float]) -> Dict:
        """
        Calculate portfolio performance metrics.

        Args:
            current_prices: Dictionary mapping symbols to current prices

        Returns:
            Performance metrics dictionary
        """
        positions = self.portfolio.get('positions', {})
        total_return = 0.0
        position_returns = []

        for symbol, position in positions.items():
            entry_price = position.get('entry_price', 0)
            current_price = current_prices.get(symbol, entry_price)
            weight = position.get('weight', 0)

            if entry_price > 0:
                position_return = (current_price - entry_price) / entry_price
                weighted_return = position_return * weight
                total_return += weighted_return

                position_returns.append({
                    'symbol': symbol,
                    'entry_price': entry_price,
                    'current_price': current_price,
                    'return_pct': position_return * 100,
                    'weight': weight,
                    'weighted_return_pct': weighted_return * 100
                })

        return {
            'total_return_pct': total_return * 100,
            'position_returns': sorted(
                position_returns,
                key=lambda x: x['return_pct'],
                reverse=True
            ),
            'best_performer': max(position_returns, key=lambda x: x['return_pct']) if position_returns else None,
            'worst_performer': min(position_returns, key=lambda x: x['return_pct']) if position_returns else None,
            'calculation_time': datetime.now().isoformat()
        }

    def get_history(self, limit: int = 30) -> List[Dict]:
        """
        Get recent portfolio history.

        Args:
            limit: Maximum number of records to return

        Returns:
            List of historical update records
        """
        return self.history[-limit:] if self.history else []
