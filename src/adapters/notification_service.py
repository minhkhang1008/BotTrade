import logging
import httpx
from src.core.models import Signal
from src.storage.database import db

logger = logging.getLogger(__name__)

_notification_service = None

class NotificationService:
    def __init__(self, bot_token: str):
        self.bot_token = bot_token
        self.is_enabled = bool(bot_token)

    async def send_signal_notification(self, signal: Signal):
        """
        Gửi tín hiệu Telegram ĐÍCH DANH cho những user đang theo dõi mã này.
        Hàm này sẽ gọi xuống database để lọc ra danh sách user_id và chat_id phù hợp.
        """
        if not self.is_enabled:
            return

        # 1. Lấy danh sách những người ĐANG THEO DÕI mã cổ phiếu này (có chat_id)
        target_users = await db.get_users_tracking_symbol(signal.symbol)
        
        if not target_users:
            logger.info(f"🔕 Bỏ qua Telegram: Không có user nào theo dõi mã {signal.symbol} hoặc chưa liên kết Telegram.")
            return

        # 2. Định dạng tin nhắn gửi đi an toàn (tránh lỗi thiếu thuộc tính type)
        signal_action = "BUY"
        if hasattr(signal, 'type') and signal.type:
            signal_action = signal.type.value if hasattr(signal.type, 'value') else str(signal.type)
        elif hasattr(signal, 'action') and signal.action:
            signal_action = signal.action.value if hasattr(signal.action, 'value') else str(signal.action)

        message = (
            f"🔔 TÍN HIỆU {signal_action}: {signal.symbol}\n"
            f"💰 Giá vào: {signal.entry:,.0f}\n"
            f"🛑 Cắt lỗ: {signal.stop_loss:,.0f}\n"
            f"🎯 Chốt lời: {signal.take_profit:,.0f}\n"
            f"-----------------------\n"
            f"🤖 BotTrade cá nhân hóa"
        )

        # 3. Rải tin nhắn bằng httpx
        success_count = 0
        try:
            async with httpx.AsyncClient() as client:
                for user in target_users:
                    chat_id = user["chat_id"]
                    try:
                        resp = await client.post(
                            f"https://api.telegram.org/bot{self.bot_token}/sendMessage",
                            json={"chat_id": chat_id, "text": message}
                        )
                        if resp.status_code == 200:
                            success_count += 1
                        else:
                            logger.error(f"❌ Telegram API lỗi {resp.status_code} cho chat_id {chat_id}: {resp.text}")
                    except Exception as req_e:
                        logger.error(f"❌ Lỗi HTTP khi gửi cho chat_id {chat_id}: {req_e}")
                        
            logger.info(f"✅ Đã bắn tỉa tín hiệu {signal.symbol} tới {success_count}/{len(target_users)} users.")
        except Exception as e:
            logger.error(f"❌ Lỗi tổng rải Telegram: {e}")

def init_notification_service(bot_token: str, chat_id: str = None) -> NotificationService:
    global _notification_service
    _notification_service = NotificationService(bot_token)
    return _notification_service

def get_notification_service() -> NotificationService:
    return _notification_service