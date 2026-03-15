import os
from dotenv import load_dotenv
from supabase import create_client, Client

load_dotenv()

url: str = os.environ.get("SUPABASE_URL", "")
key: str = os.environ.get("SUPABASE_KEY", "")

if not url or not key:
    raise ValueError("⚠️ LỖI: Chưa tìm thấy SUPABASE_URL hoặc SUPABASE_KEY trong file .env")

supabase: Client = create_client(url, key)