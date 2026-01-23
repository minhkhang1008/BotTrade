"""
Bot Trade - DNSE Lightspeed Adapter
Connects to DNSE Market Data via MQTT over WebSocket
"""
import asyncio
import json
import logging
from datetime import datetime
from typing import Callable, Optional, List, Dict, Any
from dataclasses import dataclass
import ssl

import paho.mqtt.client as mqtt

from ..core.models import Bar

logger = logging.getLogger(__name__)


@dataclass
class DNSEConfig:
    """DNSE connection configuration."""
    username: str
    password: str
    mqtt_url: str = "wss://lightspeed.dnse.com.vn/ws"
    client_id: str = "bottrade_client"


class DNSEAdapter:
    """
    DNSE Lightspeed Market Data Adapter.
    
    Connects to DNSE via MQTT over WebSocket and subscribes to OHLC data.
    Topic format: plaintext/quotes/krx/mdds/v2/ohlc/stock/{resolution}/{symbol}
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
        
        # Bar accumulator (for building bars from ticks if needed)
        self._current_bars: Dict[str, Bar] = {}
    
    @property
    def is_connected(self) -> bool:
        return self._connected
    
    def _create_client(self) -> mqtt.Client:
        """Create and configure MQTT client."""
        client = mqtt.Client(
            client_id=self.config.client_id,
            transport="websockets",
            protocol=mqtt.MQTTv311
        )
        
        # Set credentials
        client.username_pw_set(
            self.config.username,
            self.config.password
        )
        
        # TLS for WSS
        client.tls_set(cert_reqs=ssl.CERT_NONE)
        client.tls_insecure_set(True)
        
        # Callbacks
        client.on_connect = self._on_connect
        client.on_disconnect = self._on_disconnect
        client.on_message = self._on_message
        
        return client
    
    def connect(self, symbols: List[str], timeframe: str = "1H"):
        """
        Connect to DNSE and subscribe to symbols.
        
        Args:
            symbols: List of stock symbols to subscribe
            timeframe: Timeframe for OHLC data (default: 1H)
        """
        self._subscribed_symbols = symbols
        self._timeframe = timeframe
        
        self._client = self._create_client()
        
        # Parse URL to get host and port
        # wss://lightspeed.dnse.com.vn/ws -> host, port 443
        url = self.config.mqtt_url
        if url.startswith("wss://"):
            host = url[6:].split("/")[0]
            port = 443
        elif url.startswith("ws://"):
            host = url[5:].split("/")[0]
            port = 80
        else:
            host = url.split("/")[0]
            port = 443
        
        logger.info(f"Connecting to DNSE at {host}:{port}")
        
        try:
            self._client.connect(host, port, keepalive=60)
            self._client.loop_start()
        except Exception as e:
            logger.error(f"Failed to connect to DNSE: {e}")
            raise
    
    def disconnect(self):
        """Disconnect from DNSE."""
        if self._client:
            self._client.loop_stop()
            self._client.disconnect()
            self._client = None
            self._connected = False
            logger.info("Disconnected from DNSE")
    
    def _on_connect(self, client, userdata, flags, rc):
        """Handle connection established."""
        if rc == 0:
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
            logger.error(f"Connection failed with code: {rc}")
    
    def _on_disconnect(self, client, userdata, rc):
        """Handle disconnection."""
        self._connected = False
        logger.warning(f"Disconnected from DNSE (code: {rc})")
        
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
            # Expected fields from DNSE
            # Adjust based on actual DNSE message format
            timestamp_str = data.get("time") or data.get("t")
            
            if isinstance(timestamp_str, str):
                timestamp = datetime.fromisoformat(timestamp_str.replace("Z", "+00:00"))
            elif isinstance(timestamp_str, (int, float)):
                timestamp = datetime.fromtimestamp(timestamp_str)
            else:
                timestamp = datetime.now()
            
            bar = Bar(
                symbol=symbol,
                timeframe=timeframe,
                timestamp=timestamp,
                open=float(data.get("open") or data.get("o", 0)),
                high=float(data.get("high") or data.get("h", 0)),
                low=float(data.get("low") or data.get("l", 0)),
                close=float(data.get("close") or data.get("c", 0)),
                volume=float(data.get("volume") or data.get("v", 0))
            )
            
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
