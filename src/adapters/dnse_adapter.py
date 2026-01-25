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
        
        # Calculate 'from' based on timeframe and limit
        if timeframe == "1H":
            from_time = now - (limit * 60 * 60)
        elif timeframe == "4H":
            from_time = now - (limit * 4 * 60 * 60)
        elif timeframe == "1D":
            from_time = now - (limit * 24 * 60 * 60)
        elif timeframe == "1W":
            from_time = now - (limit * 7 * 24 * 60 * 60)
        else:
            from_time = now - (limit * 60 * 60)
        
        # List of chart APIs to try (in order)
        chart_apis = [
            # SSI iBoard (usually works)
            f"https://iboard.ssi.com.vn/dchart/api/history?symbol={symbol}&resolution={resolution}&from={from_time}&to={now}",
            # Fireant
            f"https://restv2.fireant.vn/symbols/{symbol}/historical-quotes?startDate={(datetime.now() - __import__('datetime').timedelta(days=limit)).strftime('%Y-%m-%d')}&endDate={datetime.now().strftime('%Y-%m-%d')}&offset=0&limit={limit}",
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
    Mock adapter for testing without DNSE connection.
    Simulates bar data for development.
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
        """Generate simulated bars for testing. These are realistic bars that can trigger signals."""
        import random
        
        self._running = True
        base_prices = {symbol: 50000 + random.random() * 50000 for symbol in self._symbols}
        trend_direction = {symbol: 1 for symbol in self._symbols}  # 1 = up, -1 = down
        trend_bars = {symbol: 0 for symbol in self._symbols}  # Counter for trend
        
        while self._running:
            for symbol in self._symbols:
                # Initialize price for new symbols
                if symbol not in base_prices:
                    base_prices[symbol] = 50000 + random.random() * 50000
                    trend_direction[symbol] = 1
                    trend_bars[symbol] = 0
                
                self._bar_count += 1
                base = base_prices[symbol]
                trend_bars[symbol] += 1
                
                # Create trending price movement with occasional pullbacks
                # This creates a more realistic pattern that can satisfy signal conditions
                
                # Every 15-20 bars, potentially create a pattern that could trigger signal
                if trend_bars[symbol] >= 15 and random.random() > 0.7:
                    # Create a hammer pattern (bullish reversal)
                    # Hammer: small body at top, long lower wick
                    open_price = base * (1 + random.uniform(0.001, 0.003))
                    close = open_price * (1 + random.uniform(0.001, 0.005))  # Close near/above open
                    low = open_price * (1 - random.uniform(0.015, 0.025))  # Long lower wick
                    high = max(open_price, close) * (1 + random.uniform(0.001, 0.003))  # Small upper wick
                    logger.info(f"🎯 MockDNSE: Generated potential hammer pattern for {symbol}")
                elif trend_direction[symbol] == 1:
                    # Uptrend bar
                    change = random.uniform(0.002, 0.012) * base
                    open_price = base
                    close = base + change
                    high = close * (1 + random.uniform(0.001, 0.005))
                    low = open_price * (1 - random.uniform(0.001, 0.003))
                else:
                    # Pullback bar
                    change = random.uniform(0.002, 0.008) * base
                    open_price = base
                    close = base - change
                    high = open_price * (1 + random.uniform(0.001, 0.003))
                    low = close * (1 - random.uniform(0.001, 0.005))
                
                # Switch trend direction periodically
                if trend_bars[symbol] > 8 and random.random() > 0.85:
                    trend_direction[symbol] = -trend_direction[symbol]
                    trend_bars[symbol] = 0
                
                bar = Bar(
                    symbol=symbol,
                    timeframe="1H",
                    timestamp=datetime.now(),
                    open=open_price,
                    high=high,
                    low=low,
                    close=close,
                    volume=random.randint(100000, 1000000)
                )
                
                base_prices[symbol] = close
                
                if self.on_bar_closed:
                    self.on_bar_closed(bar)
            
            await asyncio.sleep(interval_seconds)
    
    def subscribe(self, symbol: str):
        """Subscribe to a new symbol (mock)."""
        if symbol not in self._symbols:
            self._symbols.append(symbol)
            logger.info(f"Mock: Subscribed to {symbol}")
    
    def unsubscribe(self, symbol: str):
        """Unsubscribe from a symbol (mock)."""
        if symbol in self._symbols:
            self._symbols.remove(symbol)
            logger.info(f"Mock: Unsubscribed from {symbol}")

    async def generate_demo_signal_scenario(self):
        """
        Generate a sequence of bars that will trigger a BUY signal.
        
        The signal engine requires ALL of these conditions:
        1. Uptrend: 4 consecutive higher pivot lows + 4 consecutive higher pivot highs
        2. Price touches support zone (near last pivot low)
        3. Bullish reversal pattern (Hammer or Bullish Engulfing)
        4. Confirmation: MACD crossover OR RSI > 50
        
        Strategy:
        - Generate bars with clear hammer/engulfing patterns at key points
        - Create rising lows and rising highs
        - End with a pullback to support + hammer pattern
        """
        import random
        from datetime import timedelta
        
        if not self._symbols:
            logger.warning("No symbols to generate demo for")
            return
        
        self._demo_mode_active = True
        symbol = self._symbols[0]
        base_price = 50000.0
        
        logger.info(f"🎬 Demo: Starting signal scenario for {symbol}")
        logger.info(f"🎬 Demo: Generating uptrend with pivot patterns...")
        
        # ============ PHASE 1: Build uptrend with CLEAR pivot patterns ============
        # We need to create bars that will be detected as pivot highs and lows
        # Pivot Low = Hammer or Bullish Engulfing pattern
        # Pivot High = Shooting Star or Bearish Engulfing pattern
        
        bars_generated = []
        price = base_price
        pivot_low_prices = []
        pivot_high_prices = []
        
        # Generate a realistic uptrend with 5 clear pivot lows and 5 clear pivot highs
        for wave in range(5):
            # --- Downswing (creates PIVOT LOW at bottom) ---
            # 2-3 bearish bars going down
            for i in range(random.randint(2, 3)):
                open_p = price
                close_p = price * (1 - random.uniform(0.005, 0.012))
                high_p = open_p * (1 + random.uniform(0.001, 0.003))
                low_p = close_p * (1 - random.uniform(0.002, 0.005))
                
                bar = Bar(symbol=symbol, timeframe="1H", timestamp=datetime.now() - timedelta(hours=50-len(bars_generated)),
                         open=open_p, high=high_p, low=low_p, close=close_p, volume=random.randint(200000, 500000))
                bars_generated.append(bar)
                price = close_p
                
                if self.on_bar_closed:
                    self.on_bar_closed(bar)
                await asyncio.sleep(0.2)
            
            # --- HAMMER pattern (creates PIVOT LOW) ---
            # Hammer: small body at top, long lower wick (lower_wick > 2 * body)
            pivot_low_price = price * (1 - random.uniform(0.01, 0.015))  # New low
            open_p = pivot_low_price * 1.005
            close_p = open_p * (1 + random.uniform(0.002, 0.005))  # Bullish close
            body_size = close_p - open_p
            low_p = open_p - (body_size * random.uniform(2.5, 4))  # Long lower wick
            high_p = close_p * (1 + random.uniform(0.001, 0.002))  # Small upper wick
            
            bar = Bar(symbol=symbol, timeframe="1H", timestamp=datetime.now() - timedelta(hours=50-len(bars_generated)),
                     open=open_p, high=high_p, low=low_p, close=close_p, volume=random.randint(400000, 800000))
            bars_generated.append(bar)
            pivot_low_prices.append(bar.low)
            price = close_p
            
            logger.info(f"🎬 Demo: Created pivot low #{wave+1} at {bar.low:.0f} (Hammer)")
            
            if self.on_bar_closed:
                self.on_bar_closed(bar)
            await asyncio.sleep(0.3)
            
            # --- Upswing (creates PIVOT HIGH at top) ---
            # 3-4 bullish bars going up
            for i in range(random.randint(3, 4)):
                open_p = price
                close_p = price * (1 + random.uniform(0.008, 0.015))
                high_p = close_p * (1 + random.uniform(0.002, 0.005))
                low_p = open_p * (1 - random.uniform(0.001, 0.003))
                
                bar = Bar(symbol=symbol, timeframe="1H", timestamp=datetime.now() - timedelta(hours=50-len(bars_generated)),
                         open=open_p, high=high_p, low=low_p, close=close_p, volume=random.randint(250000, 600000))
                bars_generated.append(bar)
                price = close_p
                
                if self.on_bar_closed:
                    self.on_bar_closed(bar)
                await asyncio.sleep(0.2)
            
            # --- SHOOTING STAR pattern (creates PIVOT HIGH) ---
            # Shooting Star: small body at bottom, long upper wick
            open_p = price
            close_p = price * (1 - random.uniform(0.002, 0.005))  # Bearish close
            body_size = open_p - close_p
            high_p = open_p + (body_size * random.uniform(2.5, 4))  # Long upper wick
            low_p = close_p * (1 - random.uniform(0.001, 0.002))  # Small lower wick
            
            bar = Bar(symbol=symbol, timeframe="1H", timestamp=datetime.now() - timedelta(hours=50-len(bars_generated)),
                     open=open_p, high=high_p, low=low_p, close=close_p, volume=random.randint(350000, 700000))
            bars_generated.append(bar)
            pivot_high_prices.append(bar.high)
            price = close_p
            
            logger.info(f"🎬 Demo: Created pivot high #{wave+1} at {bar.high:.0f} (Shooting Star)")
            
            if self.on_bar_closed:
                self.on_bar_closed(bar)
            await asyncio.sleep(0.3)
        
        # Check if we have higher highs and higher lows
        logger.info(f"🎬 Demo: Pivot lows: {[f'{p:.0f}' for p in pivot_low_prices]}")
        logger.info(f"🎬 Demo: Pivot highs: {[f'{p:.0f}' for p in pivot_high_prices]}")
        
        # ============ PHASE 2: Pullback to support zone ============
        logger.info(f"🎬 Demo: Creating pullback to support zone...")
        
        support_zone = pivot_low_prices[-1]  # Last pivot low
        target_price = support_zone * 1.01  # Just above support
        
        # Small pullback
        for i in range(3):
            open_p = price
            close_p = price * (1 - random.uniform(0.005, 0.01))
            high_p = open_p * (1 + random.uniform(0.001, 0.003))
            low_p = close_p * (1 - random.uniform(0.002, 0.004))
            
            bar = Bar(symbol=symbol, timeframe="1H", timestamp=datetime.now() - timedelta(hours=5-i),
                     open=open_p, high=high_p, low=low_p, close=close_p, volume=random.randint(200000, 450000))
            bars_generated.append(bar)
            price = close_p
            
            if self.on_bar_closed:
                self.on_bar_closed(bar)
            await asyncio.sleep(0.4)
        
        # ============ PHASE 3: Final HAMMER at support (TRIGGER) ============
        logger.info(f"🎬 Demo: Creating trigger bar (Hammer at support)...")
        
        # Create a clear hammer pattern at support zone
        open_p = price
        close_p = price * 1.008  # Bullish close
        body_size = close_p - open_p
        low_p = support_zone * 0.995  # Touch into support zone
        high_p = close_p * 1.002  # Small upper wick
        
        bar = Bar(
            symbol=symbol, 
            timeframe="1H", 
            timestamp=datetime.now(),
            open=open_p, 
            high=high_p, 
            low=low_p, 
            close=close_p, 
            volume=random.randint(500000, 900000)
        )
        
        logger.info(f"🎬 Demo: TRIGGER BAR - O:{open_p:.0f} H:{high_p:.0f} L:{low_p:.0f} C:{close_p:.0f}")
        logger.info(f"🎬 Demo: Support zone around: {support_zone:.0f}")
        
        if self.on_bar_closed:
            self.on_bar_closed(bar)
        
        logger.info(f"🎬 Demo: Signal scenario complete! Check for BUY signal 🔔")
        self._demo_mode_active = False
