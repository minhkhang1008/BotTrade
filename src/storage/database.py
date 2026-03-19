import asyncio
import json
from typing import List, Optional
from datetime import datetime
from src.storage.supabase_client import supabase
from src.core.models import Bar, Signal, SignalType, SignalStatus

class Database:
    async def connect(self):
        print("✅ Đã kết nối Supabase (PostgreSQL) thành công!")
        
    async def disconnect(self):
        pass

    # Hàm hỗ trợ tương thích đa phiên bản để chuyển Object thành Dictionary
    def _to_dict(self, obj):
        if hasattr(obj, 'model_dump'):
            return obj.model_dump()
        elif hasattr(obj, 'dict'):
            return obj.dict()
        return obj.__dict__.copy()

    async def save_bar(self, bar: Bar):
        def _insert():
            data = self._to_dict(bar)
            data['timestamp'] = data['timestamp'].isoformat()
            if 'volume' in data and data['volume'] is not None:
                data['volume'] = int(data['volume'])
            try:
                supabase.table("bars").upsert(data, on_conflict="symbol,timeframe,timestamp").execute()
            except Exception as e:
                print(f"⚠️ Lỗi lưu Nến lên Supabase: {e}")
        await asyncio.to_thread(_insert)

    async def save_bars(self, bars: List[Bar]):
        if not bars: return
        def _insert_many():
            data = []
            for b in bars:
                d = self._to_dict(b)
                d['timestamp'] = d['timestamp'].isoformat()
                if 'volume' in d and d['volume'] is not None:
                    d['volume'] = int(d['volume'])
                data.append(d)
            try:
                supabase.table("bars").upsert(data, on_conflict="symbol,timeframe,timestamp").execute()
            except Exception as e:
                print(f"⚠️ Lỗi lưu cụm Nến lên Supabase: {e}")
        await asyncio.to_thread(_insert_many)

    async def get_bars(self, symbol: str, timeframe: str = "1H", limit: int = 100) -> List[Bar]:
        def _get():
            try:
                # Lấy nến mới nhất rồi đảo ngược lại đúng chiều thời gian
                res = supabase.table("bars").select("*").eq("symbol", symbol).eq("timeframe", timeframe).order("timestamp", desc=True).limit(limit).execute()
                rows = res.data
                rows.reverse() 
                bars = []
                for r in rows:
                    bars.append(Bar(
                        symbol=r['symbol'],
                        timeframe=r['timeframe'],
                        timestamp=datetime.fromisoformat(r['timestamp']),
                        open=r['open'],
                        high=r['high'],
                        low=r['low'],
                        close=r['close'],
                        volume=r['volume']
                    ))
                return bars
            except Exception as e:
                print(f"⚠️ Lỗi đọc Nến từ Supabase: {e}")
                return []
        return await asyncio.to_thread(_get)

    async def save_signal(self, signal: Signal):
        def _insert():
            data = self._to_dict(signal)
            data['timestamp'] = data['timestamp'].isoformat()
            
            # Xử lý type an toàn
            if hasattr(signal, 'type') and signal.type:
                data['type'] = signal.type.value if hasattr(signal.type, 'value') else str(signal.type)
            elif hasattr(signal, 'action') and signal.action:
                data['type'] = signal.action.value if hasattr(signal.action, 'value') else str(signal.action)
            else:
                data['type'] = "BUY"
                
            # Xử lý status an toàn
            if hasattr(signal, 'status') and signal.status:
                data['status'] = signal.status.value if hasattr(signal.status, 'value') else str(signal.status)
            else:
                data['status'] = "NEW"
                
            data['reasons'] = json.dumps(getattr(signal, 'reasons', []))
            
            try:
                supabase.table("signals").insert(data).execute()
            except Exception as e:
                print(f"⚠️ Lỗi lưu Tín hiệu lên Supabase: {e}")
        await asyncio.to_thread(_insert)

    async def get_signals(self, symbol: str = None, limit: int = 100):
        def _get():
            try:
                query = supabase.table("signals").select("*")
                if symbol:
                    query = query.eq("symbol", symbol)
                res = query.order("timestamp", desc=True).limit(limit).execute()
                return res.data
            except Exception as e:
                print(f"⚠️ Lỗi đọc Tín hiệu từ Supabase: {e}")
                return []
        return await asyncio.to_thread(_get)

    async def save_setting(self, key: str, value: str):
        def _save():
            try:
                # Dùng upsert: Đã có thì cập nhật, chưa có thì tạo mới
                supabase.table("app_settings").upsert({"key": key, "value": str(value)}, on_conflict="key").execute()
            except Exception as e:
                print(f"⚠️ Lỗi lưu Setting lên Supabase: {e}")
        await asyncio.to_thread(_save)

    async def get_setting(self, key: str) -> Optional[str]:
        def _get():
            try:
                res = supabase.table("app_settings").select("value").eq("key", key).execute()
                if res.data and len(res.data) > 0:
                    return res.data[0]["value"]
                return None
            except Exception as e:
                return None
        return await asyncio.to_thread(_get)
    # Bổ sung vào src/storage/database.py (trong class Database)
    
    async def save_sentiment(self, symbol: str, score: float, updated_at: float):
        """Lưu hoặc cập nhật điểm số AI của một mã cổ phiếu lên Supabase."""
        def _save():
            try:
                data = {
                    "symbol": symbol.upper(),
                    "score": float(score),
                    "updated_at": float(updated_at)
                }
                # Dùng upsert: Cập nhật nếu symbol đã có, tạo mới nếu chưa
                supabase.table("ai_sentiments").upsert(data, on_conflict="symbol").execute()
            except Exception as e:
                print(f"⚠️ Lỗi lưu AI Sentiment lên Supabase cho {symbol}: {e}")
        await asyncio.to_thread(_save)

    async def load_all_sentiments(self) -> dict:
        """Tải toàn bộ điểm AI từ Supabase lên RAM khi khởi động server."""
        def _get():
            try:
                res = supabase.table("ai_sentiments").select("*").execute()
                sentiments = {}
                if res.data:
                    for row in res.data:
                        sentiments[row["symbol"]] = {
                            "score": float(row["score"]),
                            "updated_at": float(row["updated_at"])
                        }
                return sentiments
            except Exception as e:
                print(f"⚠️ Lỗi đọc AI Sentiments từ Supabase: {e}")
                return {}
        return await asyncio.to_thread(_get)
    
    async def get_all_user_watchlists(self) -> set[str]:
        """Lấy tất cả các mã cổ phiếu độc nhất từ tất cả người dùng."""
        def _get():
            try:
                # Giả sử bảng user_settings có cột config chứa JSONB
                res = supabase.table("user_settings").select("config").execute()
                all_symbols = set()
                if res.data:
                    for row in res.data:
                        config = row.get("config", {})
                        if config and isinstance(config, dict):
                            watchlist = config.get("watchlist", [])
                            for symbol in watchlist:
                                all_symbols.add(symbol.upper())
                return all_symbols
            except Exception as e:
                print(f"⚠️ Lỗi lấy watchlists từ Supabase: {e}")
                return set()
        return await asyncio.to_thread(_get)

    async def get_users_tracking_symbol(self, symbol: str) -> list[dict]:
        """Lấy danh sách người dùng (kèm chat_id) đang theo dõi một mã cụ thể."""
        def _get():
            try:
                # Cần Join giữa bảng user_settings (lấy watchlist) và bảng users (lấy telegram_chat_id)
                # Lưu ý: Truy vấn này phụ thuộc vào cấu trúc schema hiện tại của bạn.
                # Cách đơn giản nhất (nếu lượng user nhỏ) là lấy tất cả rồi lọc bằng Python.
                res_users = supabase.table("users").select("id, telegram_chat_id").execute()
                res_settings = supabase.table("user_settings").select("user_id, config").execute()
                
                if not res_users.data or not res_settings.data:
                    return []
                
                # Tạo map user_id -> telegram_chat_id
                chat_id_map = {u["id"]: u.get("telegram_chat_id") for u in res_users.data if u.get("telegram_chat_id")}
                
                target_users = []
                for row in res_settings.data:
                    user_id = row.get("user_id")
                    config = row.get("config", {})
                    if config and isinstance(config, dict):
                        watchlist = config.get("watchlist", [])
                        if symbol.upper() in [s.upper() for s in watchlist]:
                            chat_id = chat_id_map.get(user_id)
                            if chat_id:
                                target_users.append({
                                    "user_id": user_id,
                                    "chat_id": chat_id,
                                    "config": config # Có thể dùng để tính toán tín hiệu riêng biệt sau này
                                })
                return target_users
            except Exception as e:
                print(f"⚠️ Lỗi lấy danh sách user cho symbol {symbol}: {e}")
                return []
        return await asyncio.to_thread(_get)


# Khởi tạo Singleton DB
db = Database()