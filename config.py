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
MAX_SECTOR_ALLOCATION = 0.20  # 20% max per sector
MIN_SECTORS_REQUIRED = 3      # Minimum 3 sectors in portfolio
TARGET_POSITIONS = 20         # Target number of positions (can exceed)

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
