"""
Bot Trade - Notification Service
Sends notifications via Telegram when signals are triggered.

Setup:
1. Create a Telegram bot via @BotFather -> Get BOT_TOKEN
2. Start chat with your bot and send /start
3. Get your Chat ID via @userinfobot or https://api.telegram.org/bot<TOKEN>/getUpdates
4. Set TELEGRAM_BOT_TOKEN and TELEGRAM_CHAT_ID in .env
"""
import asyncio
import logging
from typing import Optional
from datetime import datetime

import httpx

from ..core.models import Signal, SignalType

logger = logging.getLogger(__name__)


class NotificationService:
    """
    Telegram notification service for trading signals.
    
    Sends push notifications to Telegram - works even when web is closed.
    """
    
    TELEGRAM_API_URL = "https://api.telegram.org/bot{token}/sendMessage"
    
    def __init__(self, bot_token: str = "", chat_id: str = ""):
        self.bot_token = bot_token
        self.chat_id = chat_id
        self._enabled = bool(bot_token and chat_id)
        
        if self._enabled:
            logger.info("✅ Telegram notifications enabled")
        else:
            logger.warning("⚠️ Telegram notifications disabled (missing TELEGRAM_BOT_TOKEN or TELEGRAM_CHAT_ID)")
    
    @property
    def is_enabled(self) -> bool:
        """Check if notifications are enabled."""
        return self._enabled
    
    def configure(self, bot_token: str, chat_id: str):
        """Configure or update Telegram credentials."""
        self.bot_token = bot_token
        self.chat_id = chat_id
        self._enabled = bool(bot_token and chat_id)
        
        if self._enabled:
            logger.info("✅ Telegram notifications configured")
    
    async def send_message(self, text: str, parse_mode: str = "HTML") -> bool:
        """
        Send a message to Telegram.
        
        Args:
            text: Message text (supports HTML formatting)
            parse_mode: HTML or Markdown
            
        Returns:
            True if sent successfully
        """
        if not self._enabled:
            logger.debug("Notification skipped: Telegram not configured")
            return False
        
        url = self.TELEGRAM_API_URL.format(token=self.bot_token)
        payload = {
            "chat_id": self.chat_id,
            "text": text,
            "parse_mode": parse_mode,
            "disable_web_page_preview": True
        }
        
        try:
            async with httpx.AsyncClient() as client:
                response = await client.post(url, json=payload, timeout=10.0)
                
                if response.status_code == 200:
                    logger.info("📱 Telegram notification sent")
                    return True
                else:
                    logger.error(f"Telegram API error: {response.status_code} - {response.text}")
                    return False
                    
        except Exception as e:
            logger.error(f"Failed to send Telegram notification: {e}")
            return False
    
    async def send_signal_notification(self, signal: Signal) -> bool:
        """
        Send trading signal notification.
        
        Args:
            signal: The trading signal to notify about
            
        Returns:
            True if sent successfully
        """
        # Calculate risk/reward info
        risk = abs(signal.entry - signal.stop_loss)
        reward = abs(signal.take_profit - signal.entry)
        rr_ratio = reward / risk if risk > 0 else 0
        
        # Determine signal emoji
        if signal.signal_type == SignalType.BUY:
            emoji = "🟢"
            action = "MUA"
        else:
            emoji = "🔴"
            action = "BÁN"
        
        # Format message
        message = f"""
{emoji} <b>TÍN HIỆU {action}</b> {emoji}

<b>Mã:</b> {signal.symbol}
<b>Giá vào:</b> {signal.entry:,.0f} VND
<b>Stop Loss:</b> {signal.stop_loss:,.0f} VND
<b>Take Profit:</b> {signal.take_profit:,.0f} VND

📊 <b>Chi tiết:</b>
• Risk: {risk:,.0f} VND ({risk/signal.entry*100:.2f}%)
• Reward: {reward:,.0f} VND ({reward/signal.entry*100:.2f}%)
• R:R = 1:{rr_ratio:.1f}
• Số lượng: {signal.quantity} cổ phiếu

🕐 {datetime.now().strftime("%H:%M:%S %d/%m/%Y")}

<i>Lý do: {signal.reason or "N/A"}</i>
"""
        
        return await self.send_message(message.strip())
    
    async def send_system_notification(self, title: str, message: str) -> bool:
        """
        Send system notification (connection status, errors, etc.)
        
        Args:
            title: Notification title
            message: Notification message
            
        Returns:
            True if sent successfully
        """
        text = f"🤖 <b>{title}</b>\n\n{message}"
        return await self.send_message(text)
    
    async def send_test_notification(self) -> bool:
        """Send a test notification to verify setup."""
        message = """
🔔 <b>Test Notification</b>

✅ Telegram notifications are working!

This message confirms that your BotTrade notification setup is correct.

🤖 BotTrade - Trading Signal Assistant
"""
        return await self.send_message(message.strip())


# Global instance (will be configured in main.py)
notification_service: Optional[NotificationService] = None


def get_notification_service() -> Optional[NotificationService]:
    """Get the global notification service instance."""
    return notification_service


def init_notification_service(bot_token: str = "", chat_id: str = "") -> NotificationService:
    """Initialize the global notification service."""
    global notification_service
    notification_service = NotificationService(bot_token, chat_id)
    return notification_service
