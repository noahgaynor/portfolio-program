"""
Portfolio Manager Module

Manages portfolio allocation with position weight constraints, tracks positions,
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
    MAX_POSITION_WEIGHT,
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

    def calculate_allocations(self, num_positions: int) -> float:
        """
        Calculate weight per position (max 7% each).

        Args:
            num_positions: Number of positions to allocate

        Returns:
            Weight per position (capped at MAX_POSITION_WEIGHT)
        """
        if num_positions <= 0:
            return 0.0

        # Each position gets equal weight, capped at MAX_POSITION_WEIGHT (7%)
        equal_weight = 1.0 / num_positions
        return min(equal_weight, MAX_POSITION_WEIGHT)

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

        # Process entries - add all qualifying new stocks (each gets 7% max)
        buys = []
        for entry_stock in entry_candidates:
            symbol = entry_stock['symbol']

            buys.append({
                'symbol': symbol,
                'name': entry_stock.get('name', symbol),
                'sector': entry_stock.get('sector', 'Unknown'),
                'entry_price': entry_stock.get('current_price'),
                'entry_date': timestamp,
                'weight': MAX_POSITION_WEIGHT
            })

            current_positions[symbol] = {
                'symbol': symbol,
                'name': entry_stock.get('name', symbol),
                'sector': entry_stock.get('sector', 'Unknown'),
                'entry_price': entry_stock.get('current_price'),
                'entry_date': timestamp,
                'weight': MAX_POSITION_WEIGHT
            }

        # Recalculate all weights - each position gets 7% max
        total_invested = 0.0
        for symbol in current_positions:
            current_positions[symbol]['weight'] = MAX_POSITION_WEIGHT
            total_invested += MAX_POSITION_WEIGHT

        # Update portfolio state
        self.portfolio['positions'] = current_positions
        self.portfolio['last_update'] = timestamp
        self.portfolio['cash_weight'] = max(0.0, 1.0 - total_invested)

        # Create update record
        update_record = {
            'timestamp': timestamp,
            'buys': buys,
            'sells': sells,
            'portfolio_snapshot': {
                'positions': list(current_positions.keys()),
                'num_positions': len(current_positions),
                'total_invested': total_invested,
                'cash_weight': self.portfolio['cash_weight']
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
        total_invested = sum(p.get('weight', 0) for p in positions.values())

        return {
            'num_positions': len(positions),
            'positions': list(positions.values()),
            'total_invested': total_invested,
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
