"""
Script để debug kết nối DNSE Market Data
Theo API doc DNSE:
- Host: datafeed-lts-krx.dnse.com.vn
- Port: 443
- Path: /wss
- ClientID: dnse-price-json-mqtt-ws-sub-<investorId>-<random_sequence>
- Username: investorId (lấy từ API /me)
- Password: JWT token (lấy từ API auth)

Chạy: python scripts/test_dnse_connection.py
"""
import ssl
import time
import json
import uuid
import httpx
import paho.mqtt.client as mqtt
from dotenv import load_dotenv
import os

# Load environment variables
load_dotenv()

DNSE_USERNAME = os.getenv("DNSE_USERNAME")
DNSE_PASSWORD = os.getenv("DNSE_PASSWORD")

# Đúng theo doc DNSE
DNSE_MQTT_HOST = "datafeed-lts-krx.dnse.com.vn"
DNSE_MQTT_PORT = 443
DNSE_MQTT_PATH = "/wss"

# Auth URLs
AUTH_URLS = [
    "https://api.dnse.com.vn/user-service/api/auth",
    "https://services.dnse.com.vn/auth-service/login",
    "https://api.dnse.com.vn/auth-service/login",
]

USER_INFO_URLS = [
    "https://api.dnse.com.vn/user-service/api/me",
    "https://services.dnse.com.vn/user-service/api/me",
]

print("="*60)
print("🔍 DNSE Market Data Connection Debug")
print("="*60)
print(f"📡 MQTT Target: wss://{DNSE_MQTT_HOST}:{DNSE_MQTT_PORT}{DNSE_MQTT_PATH}")
print(f"👤 Username: {DNSE_USERNAME[:3] + '***' if DNSE_USERNAME else 'NOT SET'}")
print("="*60)


def authenticate_dnse(username: str, password: str):
    """
    Authenticate with DNSE và lấy MQTT credentials.
    
    Returns:
        tuple: (investor_id, jwt_token) hoặc (None, None) nếu lỗi
    """
    print("\n📝 Bước 1: Đăng nhập lấy JWT token...")
    
    jwt_token = None
    
    with httpx.Client(timeout=30.0) as client:
        # Try each auth URL
        for auth_url in AUTH_URLS:
            print(f"   Thử: {auth_url}")
            try:
                # Try POST first (common pattern)
                resp = client.post(auth_url, json={
                    "username": username,
                    "password": password
                })
                
                if resp.status_code == 405:  # Method not allowed, try GET
                    resp = client.get(auth_url, params={
                        "username": username,
                        "password": password
                    })
                
                if resp.status_code == 200:
                    data = resp.json()
                    jwt_token = data.get("token") or data.get("accessToken") or data.get("access_token")
                    if jwt_token:
                        print(f"   ✅ Đăng nhập thành công! Token: {jwt_token[:20]}...")
                        break
                    else:
                        print(f"   ⚠️ Response không có token: {list(data.keys())}")
                else:
                    print(f"   ❌ HTTP {resp.status_code}: {resp.text[:100]}")
            except Exception as e:
                print(f"   ❌ Lỗi: {e}")
        
        if not jwt_token:
            print("   ❌ Không thể đăng nhập với tất cả endpoints")
            return None, None
        
        # Step 2: Get investorId from /me
        print("\n📝 Bước 2: Lấy investorId từ /me...")
        
        headers = {"Authorization": f"Bearer {jwt_token}"}
        
        for me_url in USER_INFO_URLS:
            print(f"   Thử: {me_url}")
            try:
                resp = client.get(me_url, headers=headers)
                if resp.status_code == 200:
                    data = resp.json()
                    investor_id = data.get("investorId") or data.get("investor_id") or data.get("id")
                    if investor_id:
                        print(f"   ✅ Lấy được investorId: {investor_id}")
                        return str(investor_id), jwt_token
                    else:
                        print(f"   ⚠️ Response không có investorId: {list(data.keys())}")
                else:
                    print(f"   ❌ HTTP {resp.status_code}: {resp.text[:100]}")
            except Exception as e:
                print(f"   ❌ Lỗi: {e}")
        
        print("   ❌ Không thể lấy investorId")
        return None, jwt_token


def test_mqtt_connection(mqtt_username: str, mqtt_password: str, description: str):
    """Test MQTT connection với credentials cho trước."""
    
    print(f"\n🧪 Test MQTT: {description}")
    print(f"   Host: {DNSE_MQTT_HOST}:{DNSE_MQTT_PORT}{DNSE_MQTT_PATH}")
    print(f"   Username: {mqtt_username[:10] if mqtt_username else 'None'}...")
    print(f"   Password: {mqtt_password[:10] if mqtt_password else 'None'}...")
    
    connection_result = {'connected': False, 'reason': None, 'messages': []}
    
    def on_connect(client, userdata, flags, reason_code, properties):
        connection_result['reason'] = str(reason_code)
        if not reason_code.is_failure:
            print(f"   ✅ CONNECTED! Reason: {reason_code}")
            connection_result['connected'] = True
            
            # Subscribe to test topic
            topic = "plaintext/quotes/krx/mdds/v2/ohlc/stock/1H/VNM"
            client.subscribe(topic)
            print(f"   📡 Subscribed to: {topic}")
        else:
            print(f"   ❌ FAILED! Reason: {reason_code}")
    
    def on_message(client, userdata, msg):
        print(f"   📨 Message received on {msg.topic}")
        try:
            payload = json.loads(msg.payload.decode())
            connection_result['messages'].append(payload)
            print(f"   📊 Data: {json.dumps(payload, indent=2)[:200]}...")
        except:
            print(f"   📊 Raw: {msg.payload[:100]}")
    
    def on_disconnect(client, userdata, disconnect_flags, reason_code, properties):
        print(f"   🔌 Disconnected: {reason_code}")
    
    # Create ClientID theo format DNSE
    random_seq = uuid.uuid4().hex[:8]
    client_id = f"dnse-price-json-mqtt-ws-sub-{mqtt_username or 'test'}-{random_seq}"
    
    print(f"   ClientID: {client_id}")
    
    # Create MQTT client
    client = mqtt.Client(
        callback_api_version=mqtt.CallbackAPIVersion.VERSION2,
        client_id=client_id,
        transport="websockets",
        protocol=mqtt.MQTTv311
    )
    
    if mqtt_username:
        client.username_pw_set(mqtt_username, mqtt_password or "")
    
    # TLS setup
    client.tls_set(cert_reqs=ssl.CERT_NONE)
    client.tls_insecure_set(True)
    
    # Set callbacks
    client.on_connect = on_connect
    client.on_message = on_message
    client.on_disconnect = on_disconnect
    
    # Set WebSocket path
    client.ws_set_options(path=DNSE_MQTT_PATH)
    
    try:
        client.connect(DNSE_MQTT_HOST, DNSE_MQTT_PORT, keepalive=60)
        client.loop_start()
        
        # Wait for connection and messages
        print("   ⏳ Đợi kết nối (tối đa 10 giây)...")
        for i in range(10):
            time.sleep(1)
            if connection_result['connected']:
                print(f"   ⏳ Đợi nhận data... ({i+1}/10)")
                if connection_result['messages']:
                    break
        
        client.loop_stop()
        client.disconnect()
        
        return connection_result['connected'], connection_result['messages']
    
    except Exception as e:
        print(f"   ❌ Exception: {e}")
        return False, []


# ============ MAIN TEST FLOW ============

if not DNSE_USERNAME or not DNSE_PASSWORD:
    print("\n❌ ERROR: Chưa cấu hình DNSE_USERNAME và DNSE_PASSWORD trong .env")
    print("   Hãy copy .env.example thành .env và điền thông tin đăng nhập DNSE")
    exit(1)

# Test 1: Anonymous connection (thường không được)
print("\n" + "="*60)
print("🔄 Test 1: Thử kết nối Anonymous...")
print("="*60)
connected, messages = test_mqtt_connection(None, None, "Anonymous (no auth)")
if connected:
    print("\n✅ Anonymous connection THÀNH CÔNG!")
    if messages:
        print(f"   Nhận được {len(messages)} messages")
    exit(0)

# Test 2: Full authentication flow
print("\n" + "="*60)
print("🔄 Test 2: Authentication flow theo doc DNSE...")
print("="*60)

investor_id, jwt_token = authenticate_dnse(DNSE_USERNAME, DNSE_PASSWORD)

if investor_id and jwt_token:
    # Test với credentials đúng: username=investorId, password=token
    connected, messages = test_mqtt_connection(
        investor_id, 
        jwt_token, 
        f"investorId + JWT Token"
    )
    if connected:
        print("\n" + "="*60)
        print("✅ KẾT NỐI THÀNH CÔNG!")
        print("="*60)
        print(f"   MQTT Username: {investor_id}")
        print(f"   MQTT Password: JWT Token (từ đăng nhập)")
        if messages:
            print(f"   📊 Nhận được {len(messages)} messages")
        exit(0)

# Test 3: Fallback - try direct credentials
print("\n" + "="*60)
print("🔄 Test 3: Fallback - thử với credentials gốc...")
print("="*60)

connected, messages = test_mqtt_connection(
    DNSE_USERNAME, 
    DNSE_PASSWORD, 
    "Original Username + Password"
)
if connected:
    print("\n✅ Direct credentials THÀNH CÔNG!")
    exit(0)

# Test 4: Try with token only (nếu có)
if jwt_token:
    print("\n" + "="*60)
    print("🔄 Test 4: Thử các biến thể khác...")
    print("="*60)
    
    # Token as both user and password
    connected, _ = test_mqtt_connection(jwt_token, jwt_token, "Token as User & Password")
    if connected:
        print("\n✅ Token as credentials THÀNH CÔNG!")
        exit(0)
    
    # Token as password only
    connected, _ = test_mqtt_connection(DNSE_USERNAME, jwt_token, "Username + Token")
    if connected:
        print("\n✅ Username + Token THÀNH CÔNG!")
        exit(0)

print("\n" + "="*60)
print("❌ TẤT CẢ CÁC PHƯƠNG PHÁP ĐỀU THẤT BẠI")
print("="*60)
print("""
Gợi ý:
1. Kiểm tra lại thông tin đăng nhập DNSE trong file .env
2. Đảm bảo tài khoản DNSE đã được kích hoạt để nhận market data
3. Liên hệ DNSE support để xác nhận quyền truy cập API

Chi tiết API DNSE Market Data:
- Host: datafeed-lts-krx.dnse.com.vn
- Port: 443  
- Path: /wss
- Auth: Username=investorId, Password=JWT token
""")
