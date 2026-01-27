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
            # DNSE MQTT returns prices in thousands (68.9 = 68,900 VND)
            # We normalize to actual VND to match chart API data
            raw_open = float(data.get("open") or data.get("o", 0))
            raw_high = float(data.get("high") or data.get("h", 0))
            raw_low = float(data.get("low") or data.get("l", 0))
            raw_close = float(data.get("close") or data.get("c", 0))
            
            # If price is less than 1000, it's in thousands - multiply by 1000
            price_mult = 1000 if raw_close < 1000 else 1
            
            bar = Bar(
                symbol=data.get("symbol") or symbol,  # DNSE includes symbol in message
                timeframe=timeframe,
                timestamp=timestamp,
                open=raw_open * price_mult,
                high=raw_high * price_mult,
                low=raw_low * price_mult,
                close=raw_close * price_mult,
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

    async def fetch_historical_bars(
        self,
        symbol: str,
        timeframe: str = "1H",
        limit: int = 200
    ) -> List[Bar]:
        """
        Fetch historical OHLC data from API.
        Uses Entrade (SSI) chart API which is public.
        
        Args:
            symbol: Stock symbol (e.g., VNM, FPT)
            timeframe: Timeframe (1H, 4H, 1D, 1W)
            limit: Number of bars to fetch
            
        Returns:
            List of Bar objects in chronological order
        """
        import time
        
        # Map timeframe to resolution
        resolution_map = {
            "1H": "60",     # 60 minutes
            "4H": "240",    # 240 minutes
            "1D": "1D",     # Daily
            "1W": "1W",     # Weekly
        }
        resolution = resolution_map.get(timeframe, "60")
        
        # Calculate time range
        now = int(time.time())
        
        # For hourly data, we need enough calendar time to get desired bars
        # Trading hours: ~5 bars per day (9:30-14:30 with breaks)
        # So for 200 hourly bars, we need at least 40 trading days = ~60 calendar days
        if timeframe == "1H":
            # Request more days to ensure we get enough hourly bars
            days_needed = max(60, limit // 4)  # At least 60 days or limit/4
            from_time = now - (days_needed * 24 * 60 * 60)
        elif timeframe == "4H":
            from_time = now - (limit * 4 * 60 * 60)
        elif timeframe == "1D":
            from_time = now - (limit * 24 * 60 * 60)
        elif timeframe == "1W":
            from_time = now - (limit * 7 * 24 * 60 * 60)
        else:
            from_time = now - (60 * 24 * 60 * 60)  # Default 60 days
        
        # List of chart APIs to try (in order of reliability)
        chart_apis = [
            # VNDirect (most reliable as of 2026)
            f"https://dchart-api.vndirect.com.vn/dchart/history?symbol={symbol}&resolution={resolution}&from={from_time}&to={now}",
            # SSI iBoard (backup)
            f"https://iboard.ssi.com.vn/dchart/api/history?symbol={symbol}&resolution={resolution}&from={from_time}&to={now}",
            # TCBS (backup)
            f"https://apipubaws.tcbs.com.vn/stock-insight/v1/stock/bars-long-term?ticker={symbol}&type=stock&resolution={resolution}&from={from_time}&to={now}",
        ]
        
        try:
            async with httpx.AsyncClient() as client:
                # Try SSI first
                for api_url in chart_apis:
                    try:
                        response = await client.get(
                            api_url,
                            headers={
                                "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"
                            },
                            timeout=30.0
                        )
                        
                        if response.status_code != 200:
                            continue
                        
                        data = response.json()
                        
                        # SSI/VNDirect format: {s: "ok", t: [...], o: [...], h: [...], l: [...], c: [...], v: [...]}
                        if "t" in data and "c" in data:
                            timestamps = data.get("t", [])
                            opens = data.get("o", [])
                            highs = data.get("h", [])
                            lows = data.get("l", [])
                            closes = data.get("c", [])
                            volumes = data.get("v", [])
                            
                            bars = []
                            for i in range(len(timestamps)):
                                # Check if prices are in thousands (< 1000) or actual (> 1000)
                                price_mult = 1000 if float(closes[i]) < 1000 else 1
                                bar = Bar(
                                    symbol=symbol,
                                    timeframe=timeframe,
                                    timestamp=datetime.fromtimestamp(timestamps[i]),
                                    open=float(opens[i]) * price_mult,
                                    high=float(highs[i]) * price_mult,
                                    low=float(lows[i]) * price_mult,
                                    close=float(closes[i]) * price_mult,
                                    volume=float(volumes[i])
                                )
                                bars.append(bar)
                            
                            if bars:
                                logger.info(f"Fetched {len(bars)} historical bars for {symbol}")
                                return bars
                        
                        # TCBS format: {data: [{...}]}
                        elif "data" in data and isinstance(data["data"], list):
                            bars = []
                            for item in data["data"]:
                                bar = Bar(
                                    symbol=symbol,
                                    timeframe=timeframe,
                                    timestamp=datetime.fromisoformat(item.get("tradingDate", "").replace("Z", "")),
                                    open=float(item.get("open", 0)) * 1000,
                                    high=float(item.get("high", 0)) * 1000,
                                    low=float(item.get("low", 0)) * 1000,
                                    close=float(item.get("close", 0)) * 1000,
                                    volume=float(item.get("volume", 0))
                                )
                                bars.append(bar)
                            
                            if bars:
                                logger.info(f"Fetched {len(bars)} historical bars for {symbol}")
                                return bars
                                
                    except Exception as e:
                        logger.debug(f"API {api_url[:50]}... failed: {e}")
                        continue
                
                logger.warning(f"All chart APIs failed for {symbol}")
                return []
                
        except Exception as e:
            logger.error(f"Error fetching historical data for {symbol}: {e}")
            return []


class MockDNSEAdapter:
    """
    Mock adapter for testing/demo without DNSE connection.
    Generates a deterministic sequence of bars that WILL trigger BUY signals.
    
    Signal conditions required:
    1. Uptrend: 4 pivot lows increasing + 4 pivot highs increasing
    2. Price in support zone (near last pivot low)
    3. Bullish reversal pattern (Hammer)
    4. Confirmation: RSI > 50
    """
    
    def __init__(
        self,
        on_bar_closed: Optional[Callable[[Bar], None]] = None,
        on_connected: Optional[Callable[[], None]] = None,
        on_disconnected: Optional[Callable[[], None]] = None,
        on_demo_signal: Optional[Callable] = None  # Callback to force signal in demo mode
    ):
        self.on_bar_closed = on_bar_closed
        self.on_connected = on_connected
        self.on_disconnected = on_disconnected
        self.on_demo_signal = on_demo_signal  # For forcing signals in demo
        
        self._connected = False
        self._running = False
        self._symbols: List[str] = []
        self._task: Optional[asyncio.Task] = None
        self._demo_mode_active = False
        self._bar_count = 0  # Track number of bars generated
        self._demo_phase = {}  # Track demo phase per symbol
        self._demo_bars_in_phase = {}  # Bars generated in current phase
    
    @property
    def is_connected(self) -> bool:
        return self._connected
    
    async def connect(self, symbols: List[str], timeframe: str = "1H"):
        """Simulate connection."""
        self._symbols = symbols
        self._connected = True
        
        # Initialize demo tracking for each symbol
        for symbol in symbols:
            self._demo_phase[symbol] = 0
            self._demo_bars_in_phase[symbol] = 0
        
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
    
    def _create_hammer(self, base_price: float, make_higher_low: bool = True, prev_low: float = 0) -> dict:
        """
        Create a perfect Hammer pattern bar.
        Hammer: small body at top, long lower wick (lower > 2x body), small upper wick.
        """
        import random
        
        # Ensure higher low if needed
        if make_higher_low and prev_low > 0:
            low = prev_low * (1 + random.uniform(0.005, 0.015))  # Higher than previous low
        else:
            low = base_price * (1 - random.uniform(0.02, 0.035))
        
        # Small body at top - bullish close
        body_size = base_price * random.uniform(0.003, 0.006)
        open_price = low + (base_price - low) * 0.85  # Open near the top
        close = open_price + body_size  # Close slightly above open (bullish)
        
        # Long lower wick (must be > 2x body for hammer detection)
        lower_wick = open_price - low  # This should be >> body_size
        
        # Small upper wick (< body size)
        high = close + body_size * random.uniform(0.2, 0.5)
        
        return {
            'open': open_price,
            'high': high,
            'low': low,
            'close': close
        }
    
    def _create_shooting_star(self, base_price: float, make_higher_high: bool = True, prev_high: float = 0) -> dict:
        """
        Create a perfect Shooting Star pattern bar.
        Shooting Star: small body at bottom, long upper wick (upper > 2x body), small lower wick.
        """
        import random
        
        # Ensure higher high if needed
        if make_higher_high and prev_high > 0:
            high = prev_high * (1 + random.uniform(0.008, 0.02))  # Higher than previous high
        else:
            high = base_price * (1 + random.uniform(0.025, 0.04))
        
        # Small body at bottom - bearish close
        body_size = base_price * random.uniform(0.003, 0.006)
        close = base_price - body_size * 0.5  # Close below open (bearish)
        open_price = close + body_size
        
        # Small lower wick
        low = close - body_size * random.uniform(0.2, 0.5)
        
        return {
            'open': open_price,
            'high': high,
            'low': low,
            'close': close
        }
    
    def _create_bullish_bar(self, base_price: float) -> dict:
        """Create a simple bullish (green) bar."""
        import random
        change = base_price * random.uniform(0.008, 0.018)
        open_price = base_price
        close = base_price + change
        high = close * (1 + random.uniform(0.002, 0.005))
        low = open_price * (1 - random.uniform(0.002, 0.005))
        return {'open': open_price, 'high': high, 'low': low, 'close': close}
    
    def _create_bearish_bar(self, base_price: float) -> dict:
        """Create a simple bearish (red) bar."""
        import random
        change = base_price * random.uniform(0.005, 0.012)
        open_price = base_price
        close = base_price - change
        high = open_price * (1 + random.uniform(0.002, 0.004))
        low = close * (1 - random.uniform(0.002, 0.005))
        return {'open': open_price, 'high': high, 'low': low, 'close': close}

    async def simulate_bars(self, interval_seconds: float = 2.0):
        """
        Generate a DETERMINISTIC sequence of bars that WILL trigger a BUY signal.
        
        FAST DEMO MODE (~60 seconds):
        - Only runs 1 symbol (first in watchlist) for faster demo
        - 4 waves × ~4 bars = 16 bars for pivots
        - 2 init bars + 3 pre-trigger bars = 5 bars
        - Total: ~21 bars × 2 seconds = ~42 seconds per signal
        """
        import random
        
        self._running = True
        
        # DEMO MODE: Only use FIRST symbol for faster demo
        demo_symbols = [self._symbols[0]] if self._symbols else []
        if not demo_symbols:
            logger.warning("🎬 Demo: No symbols in watchlist!")
            return
        
        logger.info(f"🎬 Demo: Running with 1 symbol only: {demo_symbols[0]} (full watchlist: {self._symbols})")
        
        # Initialize state for demo symbol only
        symbol_state = {}
        for symbol in demo_symbols:
            base_price = 50000 + random.random() * 30000
            symbol_state[symbol] = {
                'price': base_price,
                'phase': 'init',  # init, upwave, pivot_high, downwave, pivot_low, pre_trigger, trigger
                'wave': 0,
                'bar_in_wave': 0,
                'pivot_lows': [],  # Track pivot low prices
                'pivot_highs': [],  # Track pivot high prices
                'last_low': 0,
                'last_high': 0,
                'bars_generated': 0,
            }
        
        logger.info(f"🎬 Demo: Starting FAST signal sequence (~1 min) for {demo_symbols[0]}")
        
        while self._running:
            for symbol in demo_symbols:
                state = symbol_state[symbol]
                price = state['price']
                phase = state['phase']
                wave = state['wave']
                bar_in_wave = state['bar_in_wave']
                
                bar_data = None
                
                # ============ PHASE: INIT - Just 2 bullish bars to start ============
                if phase == 'init':
                    bar_data = self._create_bullish_bar(price)
                    state['bar_in_wave'] += 1
                    if state['bar_in_wave'] >= 2:  # Reduced from 3
                        state['phase'] = 'upwave'
                        state['wave'] = 1
                        state['bar_in_wave'] = 0
                        logger.info(f"🎬 {symbol}: Starting wave 1 of uptrend")
                
                # ============ PHASE: UPWAVE - Just 1-2 bullish bars ============
                elif phase == 'upwave':
                    bar_data = self._create_bullish_bar(price)
                    state['bar_in_wave'] += 1
                    
                    # After 1-2 bullish bars, create shooting star (pivot high)
                    if state['bar_in_wave'] >= random.randint(1, 2):  # Reduced from 2-3
                        state['phase'] = 'pivot_high'
                        state['bar_in_wave'] = 0
                
                # ============ PHASE: PIVOT_HIGH - Create Shooting Star ============
                elif phase == 'pivot_high':
                    bar_data = self._create_shooting_star(
                        price, 
                        make_higher_high=True, 
                        prev_high=state['last_high']
                    )
                    state['pivot_highs'].append(bar_data['high'])
                    state['last_high'] = bar_data['high']
                    logger.info(f"🎬 {symbol}: Pivot HIGH #{len(state['pivot_highs'])} at {bar_data['high']:.0f}")
                    
                    state['phase'] = 'downwave'
                    state['bar_in_wave'] = 0
                
                # ============ PHASE: DOWNWAVE - Just 1 bearish bar ============
                elif phase == 'downwave':
                    bar_data = self._create_bearish_bar(price)
                    state['bar_in_wave'] += 1
                    
                    # After just 1 bearish bar, create hammer (pivot low) - faster!
                    if state['bar_in_wave'] >= 1:  # Reduced from 2
                        state['phase'] = 'pivot_low'
                        state['bar_in_wave'] = 0
                
                # ============ PHASE: PIVOT_LOW - Create Hammer ============
                elif phase == 'pivot_low':
                    bar_data = self._create_hammer(
                        price,
                        make_higher_low=True,
                        prev_low=state['last_low']
                    )
                    state['pivot_lows'].append(bar_data['low'])
                    state['last_low'] = bar_data['low']
                    logger.info(f"🎬 {symbol}: Pivot LOW #{len(state['pivot_lows'])} at {bar_data['low']:.0f}")
                    
                    state['wave'] += 1
                    
                    # Check if we have enough pivots (need 4 of each)
                    if len(state['pivot_lows']) >= 4 and len(state['pivot_highs']) >= 4:
                        state['phase'] = 'pre_trigger'  # Add RSI boost phase
                        state['bar_in_wave'] = 0
                        logger.info(f"🎬 {symbol}: Uptrend complete! Preparing for signal...")
                    else:
                        state['phase'] = 'upwave'
                        state['bar_in_wave'] = 0
                
                # ============ PHASE: PRE_TRIGGER - Just 3 bullish bars to boost RSI ============
                elif phase == 'pre_trigger':
                    # Generate strong bullish bars to ensure RSI > 50
                    bar_data = self._create_bullish_bar(price)
                    # Make it extra bullish
                    bar_data['close'] = bar_data['close'] * 1.008  # Stronger bullish
                    bar_data['high'] = bar_data['close'] * 1.003
                    state['bar_in_wave'] += 1
                    
                    # After just 3 bullish bars, RSI should be > 50, then trigger
                    if state['bar_in_wave'] >= 3:  # Reduced from 4
                        state['phase'] = 'trigger'
                        state['bar_in_wave'] = 0
                        logger.info(f"🎬 {symbol}: RSI boosted! Creating trigger bar...")
                
                # ============ PHASE: TRIGGER - Final Hammer at support ============
                elif phase == 'trigger':
                    # Create hammer with LONG LOWER WICK that reaches support zone
                    # The body stays high (preserving RSI), but the wick touches support
                    support_price = state['pivot_lows'][-1]
                    
                    # Calculate ATR-like zone width (about 1.5% of price)
                    zone_width = support_price * 0.015
                    
                    # Hammer: body at top, long lower wick reaching into support zone
                    # Open and close near current price (high)
                    open_price = price * 0.998  # Slight dip at open
                    close = price * 1.003  # Close higher (bullish)
                    body_size = close - open_price
                    
                    # Lower wick reaches down to support zone
                    # This is the key - long wick touches support but body stays high
                    low = support_price * random.uniform(0.998, 1.002)  # In support zone
                    
                    # Small upper wick
                    high = close * 1.001
                    
                    bar_data = {
                        'open': open_price,
                        'high': high,
                        'low': low,
                        'close': close
                    }
                    
                    # Check hammer criteria: lower_wick > 2 * body, upper_wick < body
                    lower_wick = open_price - low
                    upper_wick = high - close
                    logger.info(f"🎯 {symbol}: TRIGGER BAR!")
                    logger.info(f"🎯 {symbol}: O:{open_price:.0f} H:{high:.0f} L:{low:.0f} C:{close:.0f}")
                    logger.info(f"🎯 {symbol}: Body:{body_size:.0f} LowerWick:{lower_wick:.0f} (>{body_size*2:.0f}?) UpperWick:{upper_wick:.0f}")
                    logger.info(f"🎯 {symbol}: Support zone: {support_price:.0f} ± {zone_width:.0f}")
                    logger.info(f"🎯 {symbol}: Pivot Lows: {[f'{p:.0f}' for p in state['pivot_lows']]}")
                    logger.info(f"🎯 {symbol}: Pivot Highs: {[f'{p:.0f}' for p in state['pivot_highs']]}")
                    
                    # Reset for next cycle
                    state['phase'] = 'init'
                    state['wave'] = 0
                    state['bar_in_wave'] = 0
                    state['pivot_lows'] = []
                    state['pivot_highs'] = []
                    state['last_low'] = 0
                    state['last_high'] = 0
                    # Keep price for continuity
                
                # Create and emit bar
                if bar_data:
                    bar = Bar(
                        symbol=symbol,
                        timeframe="1H",
                        timestamp=datetime.now(),
                        open=bar_data['open'],
                        high=bar_data['high'],
                        low=bar_data['low'],
                        close=bar_data['close'],
                        volume=random.randint(200000, 800000)
                    )
                    
                    state['price'] = bar_data['close']
                    state['bars_generated'] += 1
                    
                    if self.on_bar_closed:
                        self.on_bar_closed(bar)
            
            await asyncio.sleep(interval_seconds)
    
    def subscribe(self, symbol: str):
        """Subscribe to a new symbol (mock)."""
        if symbol not in self._symbols:
            self._symbols.append(symbol)
            # Initialize demo tracking
            self._demo_phase[symbol] = 0
            self._demo_bars_in_phase[symbol] = 0
            logger.info(f"Mock: Subscribed to {symbol}")
    
    def unsubscribe(self, symbol: str):
        """Unsubscribe from a symbol (mock)."""
        if symbol in self._symbols:
            self._symbols.remove(symbol)
            logger.info(f"Mock: Unsubscribed from {symbol}")

    async def generate_demo_signal_scenario(self):
        """
        Legacy method - now simulate_bars automatically generates signal scenarios.
        This is kept for backwards compatibility.
        """
        logger.info("🎬 Demo mode is now automatic in simulate_bars()")
        logger.info("🎬 Signal will be generated after ~25-30 bars per symbol")
