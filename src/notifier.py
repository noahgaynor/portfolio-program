"""
Notification Module

Sends alerts via Telegram when portfolio changes occur.
"""
import logging
import requests
from typing import Dict, List, Optional
from datetime import datetime

from config import TELEGRAM_BOT_TOKEN, TELEGRAM_CHAT_ID

logger = logging.getLogger(__name__)


class TelegramNotifier:
    """Sends notifications via Telegram Bot API."""

    def __init__(
        self,
        bot_token: str = TELEGRAM_BOT_TOKEN,
        chat_id: str = TELEGRAM_CHAT_ID
    ):
        """
        Initialize the Telegram notifier.

        Args:
            bot_token: Telegram bot token
            chat_id: Telegram chat ID to send messages to
        """
        self.bot_token = bot_token
        self.chat_id = chat_id
        self.base_url = f"https://api.telegram.org/bot{bot_token}"

    def is_configured(self) -> bool:
        """Check if Telegram is properly configured."""
        return bool(self.bot_token and self.chat_id)

    def send_message(self, text: str, parse_mode: str = "HTML") -> bool:
        """
        Send a message via Telegram.

        Args:
            text: Message text
            parse_mode: Parse mode (HTML or Markdown)

        Returns:
            True if successful, False otherwise
        """
        if not self.is_configured():
            logger.warning("Telegram not configured, skipping notification")
            return False

        try:
            url = f"{self.base_url}/sendMessage"
            payload = {
                "chat_id": self.chat_id,
                "text": text,
                "parse_mode": parse_mode
            }

            response = requests.post(url, json=payload, timeout=10)
            response.raise_for_status()

            return True

        except Exception as e:
            logger.error(f"Error sending Telegram message: {e}")
            return False

    def format_buy_signal(self, buy: Dict) -> str:
        """Format a buy signal for Telegram."""
        return (
            f"🟢 <b>BUY</b> {buy['symbol']}\n"
            f"   {buy.get('name', '')}\n"
            f"   Sector: {buy.get('sector', 'Unknown')}\n"
            f"   Price: ${buy.get('entry_price', 0):.2f}\n"
            f"   Weight: {buy.get('weight', 0)*100:.1f}%"
        )

    def format_sell_signal(self, sell: Dict) -> str:
        """Format a sell signal for Telegram."""
        entry_price = sell.get('entry_price', 0) or 0
        exit_price = sell.get('exit_price', 0) or 0

        if entry_price > 0 and exit_price > 0:
            return_pct = (exit_price - entry_price) / entry_price * 100
            return_str = f"{'🟢' if return_pct >= 0 else '🔴'} {return_pct:+.1f}%"
        else:
            return_str = "N/A"

        return (
            f"🔴 <b>SELL</b> {sell['symbol']}\n"
            f"   {sell.get('name', '')}\n"
            f"   Reason: {sell.get('reason', 'Signal change')}\n"
            f"   Exit Price: ${exit_price:.2f}\n"
            f"   Return: {return_str}"
        )

    def send_daily_update(self, update: Dict) -> bool:
        """
        Send daily portfolio update notification.

        Args:
            update: Update dictionary from PortfolioManager

        Returns:
            True if successful
        """
        timestamp = update.get('timestamp', datetime.now().isoformat())
        buys = update.get('buys', [])
        sells = update.get('sells', [])
        snapshot = update.get('portfolio_snapshot', {})

        # Build message
        lines = [
            f"📊 <b>V-Stop Portfolio Update</b>",
            f"📅 {timestamp[:10]}",
            ""
        ]

        if not buys and not sells:
            lines.append("No changes today.")
        else:
            if sells:
                lines.append(f"<b>SELLS ({len(sells)})</b>")
                for sell in sells:
                    lines.append(self.format_sell_signal(sell))
                lines.append("")

            if buys:
                lines.append(f"<b>BUYS ({len(buys)})</b>")
                for buy in buys:
                    lines.append(self.format_buy_signal(buy))
                lines.append("")

        # Portfolio summary
        lines.extend([
            "<b>Portfolio Summary</b>",
            f"   Positions: {snapshot.get('num_positions', 0)}",
            f"   Sectors: {snapshot.get('num_sectors', 0)}"
        ])

        # Sector breakdown
        sector_alloc = snapshot.get('sector_allocation', {})
        if sector_alloc:
            lines.append("\n<b>Sector Allocation</b>")
            for sector, weight in sorted(sector_alloc.items(), key=lambda x: -x[1]):
                lines.append(f"   {sector}: {weight*100:.1f}%")

        message = "\n".join(lines)
        return self.send_message(message)

    def send_signal_alert(
        self,
        signal_type: str,
        symbol: str,
        details: Dict
    ) -> bool:
        """
        Send an immediate signal alert.

        Args:
            signal_type: 'BUY' or 'SELL'
            symbol: Stock symbol
            details: Signal details

        Returns:
            True if successful
        """
        if signal_type == 'BUY':
            message = f"🚨 <b>NEW BUY SIGNAL</b>\n\n{self.format_buy_signal(details)}"
        else:
            message = f"🚨 <b>NEW SELL SIGNAL</b>\n\n{self.format_sell_signal(details)}"

        return self.send_message(message)

    def send_error_alert(self, error_message: str) -> bool:
        """
        Send an error alert.

        Args:
            error_message: Error description

        Returns:
            True if successful
        """
        message = (
            f"⚠️ <b>V-Stop Portfolio Error</b>\n\n"
            f"{error_message}\n\n"
            f"Please check the system logs."
        )
        return self.send_message(message)

    def send_test_message(self) -> bool:
        """Send a test message to verify configuration."""
        message = (
            "✅ <b>V-Stop Portfolio Bot</b>\n\n"
            "Telegram notifications are configured correctly!"
        )
        return self.send_message(message)


def get_notifier() -> TelegramNotifier:
    """Get a configured notifier instance."""
    return TelegramNotifier()
