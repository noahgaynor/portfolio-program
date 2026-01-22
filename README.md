# V-Stop Portfolio Recommender

A Python-based portfolio recommendation system that uses the V-Stop (Volatility Stop MTF) indicator to identify stocks trending bullish across multiple timeframes (Daily, Weekly, Monthly).

## Features

- **Multi-Timeframe V-Stop Analysis**: Scans stocks for bullish alignment on Daily, Weekly, and Monthly timeframes
- **Sector-Balanced Portfolio**: Automatically maintains diversification with sector constraints (max 20% per sector, min 3 sectors)
- **Automated Daily Updates**: GitHub Actions runs the scanner after market close
- **Web Dashboard**: GitHub Pages hosts a real-time dashboard showing portfolio status
- **Telegram Notifications**: Get alerts when buy/sell signals trigger
- **Performance Tracking**: Track portfolio returns and historical activity

## Quick Start

### 1. Clone and Install

```bash
git clone <your-repo-url>
cd portfolio-program
pip install -r requirements.txt
```

### 2. Configure Watchlist

Edit `data/watchlist.json` to add your symbols:

```json
{
  "name": "My Watchlist",
  "symbols": ["AAPL", "MSFT", "GOOGL", "AMZN", ...]
}
```

### 3. Run Manually

```bash
# Full update with portfolio changes
python -m src.main

# Scan only (no portfolio changes)
python -m src.main --scan-only

# Test with specific symbols
python -m src.main --symbols AAPL MSFT GOOGL

# Skip Telegram notifications
python -m src.main --no-notify
```

### 4. Set Up GitHub Actions (Automated Daily Updates)

1. Push your repo to GitHub
2. Add repository secrets:
   - `TELEGRAM_BOT_TOKEN`: Your Telegram bot token
   - `TELEGRAM_CHAT_ID`: Your chat ID
3. Enable GitHub Pages (Settings > Pages > Source: GitHub Actions)

The workflow runs automatically at 4:30 PM ET on weekdays.

## Project Structure

```
portfolio-program/
├── src/
│   ├── vstop.py          # V-Stop indicator implementation
│   ├── scanner.py        # Multi-timeframe scanner
│   ├── portfolio.py      # Portfolio manager
│   ├── data_fetcher.py   # Yahoo Finance data fetcher
│   ├── notifier.py       # Telegram notifications
│   └── main.py           # Main orchestration
├── data/
│   ├── watchlist.json    # Your watchlist
│   ├── portfolio.json    # Current portfolio state
│   ├── history.json      # Historical activity
│   └── signals.json      # Latest scan results
├── docs/                  # GitHub Pages frontend
│   ├── index.html
│   ├── css/styles.css
│   ├── js/app.js
│   └── data/             # Data for frontend
├── .github/workflows/
│   └── daily_update.yml  # GitHub Actions workflow
├── config.py             # Configuration settings
└── requirements.txt
```

## V-Stop Indicator Logic

The V-Stop (Volatility Stop) indicator is based on ATR (Average True Range):

1. **Uptrend**: Stop trails below price at `max_price - (ATR * factor)`
2. **Downtrend**: Stop trails above price at `min_price + (ATR * factor)`
3. **Reversal**: When price crosses the stop level

### Entry Criteria
A stock qualifies for the portfolio when ALL THREE timeframes show bullish signals:
- Daily V-Stop is bullish
- Weekly V-Stop is bullish
- Monthly V-Stop is bullish

### Exit Criteria
A stock is sold when the Daily V-Stop turns bearish (confirmed at EOD).

## Configuration

Edit `config.py` to adjust settings:

```python
# V-Stop settings
VSTOP_LENGTH = 20          # ATR period
VSTOP_ATR_FACTOR = 2.0     # ATR multiplier

# Portfolio constraints
MAX_SECTOR_ALLOCATION = 0.20  # Max 20% per sector
MIN_SECTORS_REQUIRED = 3      # Minimum 3 sectors
TARGET_POSITIONS = 20         # Target number of positions
```

## Telegram Setup

1. Create a bot via [@BotFather](https://t.me/botfather)
2. Get your chat ID via [@userinfobot](https://t.me/userinfobot)
3. Set environment variables or GitHub secrets:
   ```bash
   export TELEGRAM_BOT_TOKEN="your-bot-token"
   export TELEGRAM_CHAT_ID="your-chat-id"
   ```

Test your setup:
```bash
python -m src.main --test-telegram
```

## Dashboard

Access your dashboard at: `https://<username>.github.io/<repo-name>/`

Features:
- Current portfolio positions
- Sector allocation chart
- Signal status for all watchlist symbols
- Recent buy/sell activity
- Historical transactions

## API Reference

### Scanner

```python
from src.scanner import MTFScanner
from src.data_fetcher import DataFetcher

scanner = MTFScanner(DataFetcher())
results = scanner.scan_watchlist(['AAPL', 'MSFT', 'GOOGL'])
qualifying = scanner.get_qualifying_stocks(results)
```

### V-Stop Calculation

```python
from src.vstop import get_vstop_signal
import yfinance as yf

df = yf.Ticker('AAPL').history(period='1y')
signal = get_vstop_signal(df, length=20, atr_factor=2.0)
print(f"Bullish: {signal['is_bullish']}, Stop: ${signal['stop_value']:.2f}")
```

## Disclaimer

This software is for informational and educational purposes only. It is not financial advice. Always do your own research and consult with a qualified financial advisor before making investment decisions. Past performance does not guarantee future results.

## License

MIT License
