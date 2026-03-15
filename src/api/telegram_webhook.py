import os
import httpx
from fastapi import APIRouter, Request
from src.storage.supabase_client import supabase

router = APIRouter()

@router.post("/telegram/webhook")
async def telegram_webhook(request: Request):
    data = await request.json()
    
    if "message" not in data or "text" not in data["message"]:
        return {"status": "ignored"}
        
    chat_id = data["message"]["chat"]["id"]
    text = data["message"]["text"]
    
    if text.startswith("/start "):
        user_id = text.split(" ")[1] 
        
        try:
            supabase.table("users").update({"telegram_chat_id": str(chat_id)}).eq("id", user_id).execute()
            
            bot_token = os.environ.get("TELEGRAM_BOT_TOKEN")
            async with httpx.AsyncClient() as client:
                await client.post(
                    f"https://api.telegram.org/bot{bot_token}/sendMessage",
                    json={
                        "chat_id": chat_id,
                        "text": "✅ Kết nối thành công! Từ nay BotTrade sẽ gửi tín hiệu Mua/Bán trực tiếp cho bạn vào nhóm này."
                    }
                )
        except Exception as e:
            print(f"Lỗi khi liên kết Telegram: {e}")
            
    return {"status": "ok"}