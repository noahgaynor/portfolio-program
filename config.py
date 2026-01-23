"""
Configuration settings for the V-Stop Portfolio Recommender
"""
import os
from pathlib import Path

# Project paths
PROJECT_ROOT = Path(__file__).parent
DATA_DIR = PROJECT_ROOT / "data"
DOCS_DIR = PROJECT_ROOT / "docs"

# V-Stop indicator settings (matching Pine Script defaults)
VSTOP_LENGTH = 20
VSTOP_ATR_FACTOR = 2.0

# Portfolio constraints
MAX_POSITION_WEIGHT = 0.07    # 7% max per single position
TARGET_POSITIONS = 14         # Target number of positions (14 * 7% = 98%)

# Correlation settings
CORRELATION_LOOKBACK_DAYS = 90    # Trading days for correlation calculation
DEFAULT_CORRELATION_THRESHOLD = 0.75  # Max correlation allowed (75%)

# Timeframes for multi-timeframe analysis
TIMEFRAMES = {
    'daily': '1d',
    'weekly': '1wk',
    'monthly': '1mo'
}

# Data fetching settings
LOOKBACK_DAYS = 365  # Days of historical data to fetch
MIN_HISTORY_DAYS = 60  # Minimum days required for valid calculation

# Telegram settings (set via environment variables)
TELEGRAM_BOT_TOKEN = os.environ.get('TELEGRAM_BOT_TOKEN', '')
TELEGRAM_CHAT_ID = os.environ.get('TELEGRAM_CHAT_ID', '')

# Market timezone
MARKET_TIMEZONE = 'America/New_York'
MARKET_CLOSE_HOUR = 16  # 4 PM ET
