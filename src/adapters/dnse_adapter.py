"""
Bot Trade - DNSE Market Data Adapter
Connects to DNSE Market Data via MQTT over WebSocket

Theo API doc DNSE:
- Host: datafeed-lts-krx.dnse.com.vn
- Port: 443
- Path: /wss
- ClientID: <dnse-price-json-mqtt-ws-sub>-<username>-<random_sequence>
- Username: investorId (lấy từ API /me)
- Password: JWT token (lấy từ API auth)
"""
import asyncio
import json
import logging
import uuid
from datetime import datetime
from typing import Callable, Optional, List, Dict, Any
from dataclasses import dataclass
import ssl

import httpx
import paho.mqtt.client as mqtt

from ..core.models import Bar

logger = logging.getLogger(__name__)

# DNSE API URLs
DNSE_AUTH_URL = "https://api.dnse.com.vn/user-service/api/auth"
DNSE_USER_INFO_URL = "https://api.dnse.com.vn/user-service/api/me"
DNSE_MQTT_HOST = "datafeed-lts-krx.dnse.com.vn"
DNSE_MQTT_PORT = 443
DNSE_MQTT_PATH = "/wss"


@dataclass
class DNSEConfig:
    """DNSE connection configuration."""
    username: str  # Email hoặc Số điện thoại hoặc Số lưu ký
    password: str  # Mật khẩu DNSE
    mqtt_url: str = "wss://datafeed-lts-krx.dnse.com.vn/wss"


@dataclass
class DNSECredentials:
    """DNSE MQTT credentials after authentication."""
    investor_id: str  # Dùng làm username cho MQTT
    jwt_token: str    # Dùng làm password cho MQTT
    client_id: str    # Format: dnse-price-json-mqtt-ws-sub-<investorId>-<random>


class DNSEAuthenticator:
    """
    Handles DNSE authentication flow.
    
    1. Login với username/password -> lấy JWT token
    2. Call /me với JWT -> lấy investorId  
    3. Tạo MQTT credentials
    """
    
    def __init__(self, username: str, password: str):
        self.username = username
        self.password = password
    
    async def authenticate(self) -> DNSECredentials:
        """
        Authenticate with DNSE and get MQTT credentials.
        
        Returns:
            DNSECredentials with investorId, token, and clientId
        """
        async with httpx.AsyncClient() as client:
            # Step 1: Login to get JWT token
            logger.info(f"Authenticating with DNSE as {self.username[:3]}***...")
            
            # Thử POST trước (phổ biến hơn)
            try:
                login_response = await client.post(
                    DNSE_AUTH_URL,
                    json={"username": self.username, "password": self.password},
                    timeout=30.0
                )
            except Exception:
                # Fallback to GET with params (theo doc)
                login_response = await client.get(
                    DNSE_AUTH_URL,
                    params={"username": self.username, "password": self.password},
                    timeout=30.0
                )
            
            if login_response.status_code != 200:
                # Thử endpoint khác
                alt_urls = [
                    "https://services.dnse.com.vn/auth-service/login",
                    "https://api.dnse.com.vn/auth-service/login",
                ]
                
                for alt_url in alt_urls:
                    try:
                        login_response = await client.post(
                            alt_url,
                            json={"username": self.username, "password": self.password},
                            timeout=30.0
                        )
                        if login_response.status_code == 200:
                            logger.info(f"Login successful via {alt_url}")
                            break
                    except Exception as e:
                        logger.debug(f"Failed {alt_url}: {e}")
                        continue
            
            if login_response.status_code != 200:
                raise Exception(f"DNSE login failed: {login_response.status_code} - {login_response.text}")
            
            auth_data = login_response.json()
            jwt_token = auth_data.get("token") or auth_data.get("accessToken") or auth_data.get("access_token")
            
            if not jwt_token:
                raise Exception(f"No token in auth response: {auth_data}")
            
            logger.info("Got JWT token successfully")
            
            # Step 2: Get user info with investorId
            headers = {"Authorization": f"Bearer {jwt_token}"}
            
            try:
                me_response = await client.get(
                    DNSE_USER_INFO_URL,
                    headers=headers,
                    timeout=30.0
                )
            except Exception:
                me_response = await client.get(
                    "https://services.dnse.com.vn/user-service/api/me",
                    headers=headers,
                    timeout=30.0
                )
            
            if me_response.status_code != 200:
                raise Exception(f"Failed to get user info: {me_response.status_code} - {me_response.text}")
            
            user_data = me_response.json()
            investor_id = user_data.get("investorId") or user_data.get("investor_id") or user_data.get("id")
            
            if not investor_id:
                raise Exception(f"No investorId in user info: {user_data}")
            
            logger.info(f"Got investorId: {investor_id}")
            
            # Step 3: Create client ID (format from DNSE doc)
            random_seq = str(uuid.uuid4())[:8]
            client_id = f"dnse-price-json-mqtt-ws-sub-{investor_id}-{random_seq}"
            
            return DNSECredentials(
                investor_id=str(investor_id),
                jwt_token=jwt_token,
                client_id=client_id
            )


class DNSEAdapter:
    """
    DNSE Market Data Adapter.
    
    Connects to DNSE via MQTT over WebSocket and subscribes to OHLC data.
    Topic format: plaintext/quotes/krx/mdds/v2/ohlc/stock/{resolution}/{symbol}
    
    Authentication flow:
    1. Login với username/password -> JWT token
    2. Get /me -> investorId
    3. Connect MQTT với username=investorId, password=JWT token
    """
    
    def __init__(
        self,
        config: DNSEConfig,
        on_bar_closed: Optional[Callable[[Bar], None]] = None,
        on_connected: Optional[Callable[[], None]] = None,
        on_disconnected: Optional[Callable[[], None]] = None
    ):
        self.config = config
        self.on_bar_closed = on_bar_closed
        self.on_connected = on_connected
        self.on_disconnected = on_disconnected
        
        self._client: Optional[mqtt.Client] = None
        self._connected = False
        self._subscribed_symbols: List[str] = []
        self._timeframe = "1H"
        self._credentials: Optional[DNSECredentials] = None
        
        # Bar accumulator (for building bars from ticks if needed)
        self._current_bars: Dict[str, Bar] = {}
    
    @property
    def is_connected(self) -> bool:
        return self._connected
    
    async def _authenticate(self) -> DNSECredentials:
        """Authenticate with DNSE and get MQTT credentials."""
        authenticator = DNSEAuthenticator(self.config.username, self.config.password)
        return await authenticator.authenticate()
    
    def _create_client(self, credentials: DNSECredentials) -> mqtt.Client:
        """Create and configure MQTT client with proper credentials."""
        client = mqtt.Client(
            callback_api_version=mqtt.CallbackAPIVersion.VERSION2,
            client_id=credentials.client_id,
            transport="websockets",
            protocol=mqtt.MQTTv311
        )
        
        # Set credentials: username=investorId, password=JWT token
        client.username_pw_set(
            credentials.investor_id,
            credentials.jwt_token
        )
        
        # TLS for WSS
        client.tls_set(cert_reqs=ssl.CERT_NONE)
        client.tls_insecure_set(True)
        
        # Callbacks
        client.on_connect = self._on_connect
        client.on_disconnect = self._on_disconnect
        client.on_message = self._on_message
        
        return client
    
    async def connect_async(self, symbols: List[str], timeframe: str = "1H"):
        """
        Async version: Authenticate and connect to DNSE.
        
        Args:
            symbols: List of stock symbols to subscribe
            timeframe: Timeframe for OHLC data (default: 1H)
        """
        self._subscribed_symbols = symbols
        self._timeframe = timeframe
        
        try:
            # Step 1: Authenticate to get MQTT credentials
            self._credentials = await self._authenticate()
            logger.info(f"Authenticated. ClientID: {self._credentials.client_id}")
            
            # Step 2: Create MQTT client with credentials
            self._client = self._create_client(self._credentials)
            
            # Step 3: Connect to MQTT broker
            logger.info(f"Connecting to DNSE at {DNSE_MQTT_HOST}:{DNSE_MQTT_PORT}{DNSE_MQTT_PATH}")
            
            self._client.ws_set_options(path=DNSE_MQTT_PATH)
            self._client.connect(DNSE_MQTT_HOST, DNSE_MQTT_PORT, keepalive=60)
            self._client.loop_start()
            
            logger.info("DNSE MQTT client started, waiting for connection...")
            
        except Exception as e:
            logger.error(f"Failed to connect to DNSE: {e}")
            if self.on_disconnected:
                self.on_disconnected()
            raise
    
    def _sync_authenticate(self) -> DNSECredentials:
        """
        Synchronous authentication using httpx.Client (not async).
        Use this when an event loop is already running.
        """
        import httpx
        
        logger.info(f"Authenticating with DNSE as {self.config.username[:3]}***...")
        
        with httpx.Client(timeout=30.0) as client:
            # Step 1: Login to get JWT token
            try:
                login_response = client.post(
                    DNSE_AUTH_URL,
                    json={"username": self.config.username, "password": self.config.password}
                )
            except Exception:
                login_response = client.get(
                    DNSE_AUTH_URL,
                    params={"username": self.config.username, "password": self.config.password}
                )
            
            if login_response.status_code != 200:
                # Try alternative endpoints
                alt_urls = [
                    "https://services.dnse.com.vn/auth-service/login",
                    "https://api.dnse.com.vn/auth-service/login",
                ]
                for alt_url in alt_urls:
                    try:
                        login_response = client.post(
                            alt_url,
                            json={"username": self.config.username, "password": self.config.password}
                        )
                        if login_response.status_code == 200:
                            break
                    except Exception:
                        continue
            
            if login_response.status_code != 200:
                raise Exception(f"DNSE login failed: {login_response.status_code}")
            
            auth_data = login_response.json()
            jwt_token = auth_data.get("token") or auth_data.get("accessToken") or auth_data.get("access_token")
            
            if not jwt_token:
                raise Exception(f"No token in auth response")
            
            logger.info("Got JWT token successfully")
            
            # Step 2: Get investorId from /me
            headers = {"Authorization": f"Bearer {jwt_token}"}
            me_response = client.get(DNSE_USER_INFO_URL, headers=headers)
            
            if me_response.status_code != 200:
                me_response = client.get(
                    "https://services.dnse.com.vn/user-service/api/me",
                    headers=headers
                )
            
            if me_response.status_code != 200:
                raise Exception(f"Failed to get user info: {me_response.status_code}")
            
            user_data = me_response.json()
            investor_id = user_data.get("investorId") or user_data.get("investor_id") or user_data.get("id")
            
            if not investor_id:
                raise Exception(f"No investorId in user info")
            
            logger.info(f"Got investorId: {investor_id}")
            
            # Create client ID
            random_seq = str(uuid.uuid4())[:8]
            client_id = f"dnse-price-json-mqtt-ws-sub-{investor_id}-{random_seq}"
            
            return DNSECredentials(
                investor_id=str(investor_id),
                jwt_token=jwt_token,
                client_id=client_id
            )
    
    def connect(self, symbols: List[str], timeframe: str = "1H"):
        """
        Sync version: Connect to DNSE.
        Uses sync HTTP client for auth to avoid event loop conflicts.
        
        Args:
            symbols: List of stock symbols to subscribe
            timeframe: Timeframe for OHLC data (default: 1H)
        """
        self._subscribed_symbols = symbols
        self._timeframe = timeframe
        
        try:
            # Use sync authentication to avoid event loop conflicts
            self._credentials = self._sync_authenticate()
            logger.info(f"Authenticated. ClientID: {self._credentials.client_id}")
        except Exception as e:
            logger.error(f"Authentication failed: {e}")
            raise
        
        self._client = self._create_client(self._credentials)
        
        logger.info(f"Connecting to DNSE at {DNSE_MQTT_HOST}:{DNSE_MQTT_PORT}{DNSE_MQTT_PATH}")
        
        try:
            self._client.ws_set_options(path=DNSE_MQTT_PATH)
            self._client.connect(DNSE_MQTT_HOST, DNSE_MQTT_PORT, keepalive=60)
            self._client.loop_start()
            logger.info("DNSE MQTT client started, waiting for connection...")
        except Exception as e:
            logger.error(f"Failed to connect to DNSE: {e}")
            if self.on_disconnected:
                self.on_disconnected()
            raise
    
    def disconnect(self):
        """Disconnect from DNSE."""
        if self._client:
            self._client.loop_stop()
            self._client.disconnect()
            self._client = None
            self._connected = False
            logger.info("Disconnected from DNSE")
    
    def _on_connect(self, client, userdata, flags, reason_code, properties):
        """Handle connection established."""
        if not reason_code.is_failure:
            self._connected = True
            logger.info("Connected to DNSE Lightspeed")
            
            # Subscribe to OHLC topics for each symbol
            for symbol in self._subscribed_symbols:
                topic = f"plaintext/quotes/krx/mdds/v2/ohlc/stock/{self._timeframe}/{symbol}"
                client.subscribe(topic)
                logger.info(f"Subscribed to {topic}")
            
            if self.on_connected:
                self.on_connected()
        else:
            logger.error(f"Connection failed: {reason_code}")
    
    def _on_disconnect(self, client, userdata, disconnect_flags, reason_code, properties):
        """Handle disconnection."""
        self._connected = False
        logger.warning(f"Disconnected from DNSE: {reason_code}")
        
        if self.on_disconnected:
            self.on_disconnected()
    
    def _on_message(self, client, userdata, msg):
        """Handle incoming MQTT message."""
        try:
            topic = msg.topic
            payload = json.loads(msg.payload.decode())
            
            logger.debug(f"Received message on {topic}: {payload}")
            
            # Parse topic to get symbol
            # plaintext/quotes/krx/mdds/v2/ohlc/stock/1H/VNM
            parts = topic.split("/")
            if len(parts) >= 8:
                symbol = parts[-1]
                timeframe = parts[-2]
                
                # Parse bar data
                bar = self._parse_bar(symbol, timeframe, payload)
                if bar and self.on_bar_closed:
                    self.on_bar_closed(bar)
        
        except json.JSONDecodeError as e:
            logger.error(f"Failed to parse message: {e}")
        except Exception as e:
            logger.error(f"Error processing message: {e}")
    
    def _parse_bar(
        self,
        symbol: str,
        timeframe: str,
        data: Dict[str, Any]
    ) -> Optional[Bar]:
        """Parse DNSE message into Bar object."""
        try:
            # DNSE returns time as Unix timestamp (can be string or int)
            # Example: {'time': '1769151600', 'open': 68.1, ...}
            timestamp_raw = data.get("time") or data.get("t")
            
            if timestamp_raw is None:
                timestamp = datetime.now()
            elif isinstance(timestamp_raw, str):
                # Check if it's a numeric string (Unix timestamp)
                if timestamp_raw.isdigit():
                    timestamp = datetime.fromtimestamp(int(timestamp_raw))
                else:
                    # Try ISO format
                    timestamp = datetime.fromisoformat(timestamp_raw.replace("Z", "+00:00"))
            elif isinstance(timestamp_raw, (int, float)):
                timestamp = datetime.fromtimestamp(timestamp_raw)
            else:
                timestamp = datetime.now()
            
            # Parse OHLCV - DNSE uses full names: 'open', 'high', 'low', 'close', 'volume'
            bar = Bar(
                symbol=data.get("symbol") or symbol,  # DNSE includes symbol in message
                timeframe=timeframe,
                timestamp=timestamp,
                open=float(data.get("open") or data.get("o", 0)),
                high=float(data.get("high") or data.get("h", 0)),
                low=float(data.get("low") or data.get("l", 0)),
                close=float(data.get("close") or data.get("c", 0)),
                volume=float(data.get("volume") or data.get("v", 0))
            )
            
            logger.debug(f"Parsed bar: {bar.symbol} @ {bar.timestamp} | O:{bar.open} H:{bar.high} L:{bar.low} C:{bar.close}")
            return bar
        
        except Exception as e:
            logger.error(f"Failed to parse bar: {e}, data: {data}")
            return None
    
    def subscribe(self, symbol: str):
        """Subscribe to a new symbol."""
        if symbol not in self._subscribed_symbols:
            self._subscribed_symbols.append(symbol)
            if self._connected and self._client:
                topic = f"plaintext/quotes/krx/mdds/v2/ohlc/stock/{self._timeframe}/{symbol}"
                self._client.subscribe(topic)
                logger.info(f"Subscribed to {topic}")
    
    def unsubscribe(self, symbol: str):
        """Unsubscribe from a symbol."""
        if symbol in self._subscribed_symbols:
            self._subscribed_symbols.remove(symbol)
            if self._connected and self._client:
                topic = f"plaintext/quotes/krx/mdds/v2/ohlc/stock/{self._timeframe}/{symbol}"
                self._client.unsubscribe(topic)
                logger.info(f"Unsubscribed from {topic}")


class MockDNSEAdapter:
    """
    Mock adapter for testing without DNSE connection.
    Simulates bar data for development.
    """
    
    def __init__(
        self,
        on_bar_closed: Optional[Callable[[Bar], None]] = None,
        on_connected: Optional[Callable[[], None]] = None,
        on_disconnected: Optional[Callable[[], None]] = None
    ):
        self.on_bar_closed = on_bar_closed
        self.on_connected = on_connected
        self.on_disconnected = on_disconnected
        
        self._connected = False
        self._running = False
        self._symbols: List[str] = []
        self._task: Optional[asyncio.Task] = None
    
    @property
    def is_connected(self) -> bool:
        return self._connected
    
    async def connect(self, symbols: List[str], timeframe: str = "1H"):
        """Simulate connection."""
        self._symbols = symbols
        self._connected = True
        
        if self.on_connected:
            self.on_connected()
        
        logger.info("Mock DNSE adapter connected")
    
    async def disconnect(self):
        """Simulate disconnection."""
        self._running = False
        self._connected = False
        
        if self._task:
            self._task.cancel()
        
        if self.on_disconnected:
            self.on_disconnected()
        
        logger.info("Mock DNSE adapter disconnected")
    
    async def simulate_bars(self, interval_seconds: float = 5.0):
        """Generate simulated bars for testing."""
        import random
        
        self._running = True
        base_prices = {symbol: 50000 + random.random() * 50000 for symbol in self._symbols}
        
        while self._running:
            for symbol in self._symbols:
                base = base_prices[symbol]
                change = (random.random() - 0.5) * base * 0.02
                
                open_price = base + change
                high = open_price + random.random() * base * 0.01
                low = open_price - random.random() * base * 0.01
                close = low + random.random() * (high - low)
                
                bar = Bar(
                    symbol=symbol,
                    timeframe="1H",
                    timestamp=datetime.now(),
                    open=open_price,
                    high=high,
                    low=low,
                    close=close,
                    volume=random.randint(10000, 1000000)
                )
                
                base_prices[symbol] = close
                
                if self.on_bar_closed:
                    self.on_bar_closed(bar)
            
            await asyncio.sleep(interval_seconds)
