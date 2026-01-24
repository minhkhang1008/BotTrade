"""
Bot Trade - API Server
FastAPI application with REST and WebSocket endpoints
"""
import asyncio
import logging
from contextlib import asynccontextmanager
from datetime import datetime
from typing import List, Optional, Dict, Any

from fastapi import FastAPI, WebSocket, WebSocketDisconnect, Query, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

from ..config import settings
from ..storage.database import db
from ..core.models import Signal, Bar, SignalStatus

logger = logging.getLogger(__name__)


# ============ Pydantic Models for API ============

class HealthResponse(BaseModel):
    status: str
    dnse_connected: bool
    timestamp: str
    symbols: List[str]


class SettingsResponse(BaseModel):
    watchlist: List[str]
    timeframe: str
    rsi_period: int
    macd_fast: int
    macd_slow: int
    macd_signal: int
    atr_period: int
    zone_width_atr_multiplier: float
    sl_buffer_atr_multiplier: float
    risk_reward_ratio: float
    default_quantity: int


class SettingsUpdate(BaseModel):
    watchlist: Optional[List[str]] = None
    default_quantity: Optional[int] = None


class SignalResponse(BaseModel):
    id: int
    symbol: str
    signal_type: str
    timestamp: str
    entry: float
    stop_loss: float
    take_profit: float
    quantity: int
    status: str
    reason: str
    risk: float
    reward: float
    risk_reward_ratio: float


class BarResponse(BaseModel):
    symbol: str
    timeframe: str
    timestamp: str
    open: float
    high: float
    low: float
    close: float
    volume: float


# ============ WebSocket Manager ============

class ConnectionManager:
    """Manages WebSocket connections for realtime updates."""
    
    def __init__(self):
        self.active_connections: List[WebSocket] = []
    
    async def connect(self, websocket: WebSocket):
        await websocket.accept()
        self.active_connections.append(websocket)
        logger.info(f"WebSocket connected. Total: {len(self.active_connections)}")
    
    def disconnect(self, websocket: WebSocket):
        self.active_connections.remove(websocket)
        logger.info(f"WebSocket disconnected. Total: {len(self.active_connections)}")
    
    async def broadcast(self, event: str, data: dict):
        """Send event to all connected clients."""
        message = {"event": event, "data": data}
        disconnected = []
        
        for connection in self.active_connections:
            try:
                await connection.send_json(message)
            except Exception:
                disconnected.append(connection)
        
        for conn in disconnected:
            self.active_connections.remove(conn)
    
    async def send_personal(self, websocket: WebSocket, event: str, data: dict):
        """Send event to specific client."""
        await websocket.send_json({"event": event, "data": data})


manager = ConnectionManager()


# ============ Application State ============

class AppState:
    """Global application state."""
    dnse_connected: bool = False
    current_settings: Dict[str, Any] = {}


app_state = AppState()


# ============ Lifespan ============

@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application lifespan handler."""
    # Startup
    await db.connect()
    app_state.current_settings = {
        "watchlist": settings.watchlist_symbols,
        "timeframe": settings.timeframe,
        "default_quantity": settings.default_quantity
    }
    logger.info("Bot Trade API started")
    
    yield
    
    # Shutdown
    await db.disconnect()
    logger.info("Bot Trade API stopped")


# ============ FastAPI App ============
# Note: lifespan is handled in main.py via on_event decorators

app = FastAPI(
    title="Bot Trade API",
    description="Trading signal bot API with REST and WebSocket support",
    version="0.1.0"
    # lifespan is NOT set here - handled by main.py
)

# CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # Cho phép tất cả origins (chỉ dev)
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# ============ REST Endpoints ============

@app.get("/", include_in_schema=False)
async def root():
    """Redirect root to API docs."""
    from fastapi.responses import RedirectResponse
    return RedirectResponse(url="/docs")


@app.get("/api/v1/health", response_model=HealthResponse)
async def health_check():
    """Check API health and DNSE connection status."""
    return HealthResponse(
        status="ok",
        dnse_connected=app_state.dnse_connected,
        timestamp=datetime.now().isoformat(),
        symbols=app_state.current_settings.get("watchlist", [])
    )


@app.get("/api/v1/symbols", response_model=List[str])
async def get_symbols():
    """Get list of watched symbols."""
    return app_state.current_settings.get("watchlist", settings.watchlist_symbols)


@app.get("/api/v1/settings", response_model=SettingsResponse)
async def get_settings():
    """Get current settings."""
    return SettingsResponse(
        watchlist=app_state.current_settings.get("watchlist", settings.watchlist_symbols),
        timeframe=settings.timeframe,
        rsi_period=settings.rsi_period,
        macd_fast=settings.macd_fast,
        macd_slow=settings.macd_slow,
        macd_signal=settings.macd_signal,
        atr_period=settings.atr_period,
        zone_width_atr_multiplier=settings.zone_width_atr_multiplier,
        sl_buffer_atr_multiplier=settings.sl_buffer_atr_multiplier,
        risk_reward_ratio=settings.risk_reward_ratio,
        default_quantity=app_state.current_settings.get(
            "default_quantity", settings.default_quantity
        )
    )


@app.put("/api/v1/settings", response_model=SettingsResponse)
async def update_settings(update: SettingsUpdate):
    """Update settings."""
    if update.watchlist is not None:
        app_state.current_settings["watchlist"] = update.watchlist
    
    if update.default_quantity is not None:
        app_state.current_settings["default_quantity"] = update.default_quantity
    
    # Broadcast settings update
    await manager.broadcast("settings_updated", app_state.current_settings)
    
    return await get_settings()


@app.get("/api/v1/signals", response_model=List[SignalResponse])
async def get_signals(
    symbol: Optional[str] = Query(None, description="Filter by symbol"),
    limit: int = Query(50, ge=1, le=500, description="Max number of signals")
):
    """Get signal history."""
    signals = await db.get_signals(symbol=symbol, limit=limit)
    
    return [
        SignalResponse(
            id=s.id,
            symbol=s.symbol,
            signal_type=s.signal_type.value,
            timestamp=s.timestamp.isoformat(),
            entry=s.entry,
            stop_loss=s.stop_loss,
            take_profit=s.take_profit,
            quantity=s.quantity,
            status=s.status.value,
            reason=s.reason,
            risk=s.risk,
            reward=s.reward,
            risk_reward_ratio=s.risk_reward_ratio
        )
        for s in signals
    ]


@app.get("/api/v1/signals/{signal_id}", response_model=SignalResponse)
async def get_signal(signal_id: int):
    """Get signal by ID."""
    signal = await db.get_signal_by_id(signal_id)
    if not signal:
        raise HTTPException(status_code=404, detail="Signal not found")
    
    return SignalResponse(
        id=signal.id,
        symbol=signal.symbol,
        signal_type=signal.signal_type.value,
        timestamp=signal.timestamp.isoformat(),
        entry=signal.entry,
        stop_loss=signal.stop_loss,
        take_profit=signal.take_profit,
        quantity=signal.quantity,
        status=signal.status.value,
        reason=signal.reason,
        risk=signal.risk,
        reward=signal.reward,
        risk_reward_ratio=signal.risk_reward_ratio
    )


@app.get("/api/v1/bars", response_model=List[BarResponse])
async def get_bars(
    symbol: str = Query(..., description="Stock symbol"),
    limit: int = Query(100, ge=1, le=1000, description="Max number of bars")
):
    """Get bar history for a symbol."""
    bars = await db.get_bars(symbol=symbol, limit=limit)
    
    return [
        BarResponse(
            symbol=b.symbol,
            timeframe=b.timeframe,
            timestamp=b.timestamp.isoformat(),
            open=b.open,
            high=b.high,
            low=b.low,
            close=b.close,
            volume=b.volume
        )
        for b in bars
    ]


# ============ WebSocket Endpoint ============

@app.websocket("/ws/v1/stream")
async def websocket_endpoint(websocket: WebSocket):
    """
    WebSocket endpoint for realtime updates.
    
    Events:
    - system: Connection status updates
    - bar_closed: New closed bar
    - signal: New trading signal
    """
    await manager.connect(websocket)
    
    # Send initial status
    await manager.send_personal(websocket, "system", {
        "status": "connected",
        "dnse_connected": app_state.dnse_connected,
        "timestamp": datetime.now().isoformat()
    })
    
    try:
        while True:
            # Keep connection alive, handle incoming messages if needed
            data = await websocket.receive_text()
            
            # Echo or handle client messages if needed
            logger.debug(f"Received from client: {data}")
    
    except WebSocketDisconnect:
        manager.disconnect(websocket)


# ============ Event Broadcasting Functions ============

async def broadcast_bar_closed(bar: Bar):
    """Broadcast bar closed event."""
    await manager.broadcast("bar_closed", bar.to_dict())


async def broadcast_signal(signal: Signal):
    """Broadcast new signal event."""
    await manager.broadcast("signal", signal.to_dict())


async def broadcast_system_status(status: str, dnse_connected: bool):
    """Broadcast system status update."""
    await manager.broadcast("system", {
        "status": status,
        "dnse_connected": dnse_connected,
        "timestamp": datetime.now().isoformat()
    })


def set_dnse_status(connected: bool):
    """Update DNSE connection status."""
    app_state.dnse_connected = connected


# ============ Trading Endpoints ============

# Reference to trading service (set by main.py)
_trading_service = None


def set_trading_service(service):
    """Set trading service reference."""
    global _trading_service
    _trading_service = service


class OTPRequest(BaseModel):
    otp: Optional[str] = None
    smart_otp: Optional[str] = None


class TradingStatusResponse(BaseModel):
    trading_enabled: bool
    auto_trade_enabled: bool
    trading_token_valid: bool
    account_no: str


class OrderRequest(BaseModel):
    symbol: str
    quantity: int
    price: float


@app.get("/api/v1/trading/status", response_model=TradingStatusResponse)
async def get_trading_status():
    """Get trading service status."""
    if not _trading_service:
        return TradingStatusResponse(
            trading_enabled=False,
            auto_trade_enabled=False,
            trading_token_valid=False,
            account_no=""
        )
    
    return TradingStatusResponse(
        trading_enabled=True,
        auto_trade_enabled=settings.auto_trade_enabled,
        trading_token_valid=_trading_service.tokens.is_trading_token_valid(),
        account_no=_trading_service.account_no or ""
    )


@app.post("/api/v1/trading/request-otp")
async def request_otp():
    """Request OTP to be sent via email."""
    if not _trading_service:
        raise HTTPException(status_code=503, detail="Trading service not configured")
    
    success = await _trading_service.request_email_otp()
    if success:
        return {"message": "OTP sent to your email"}
    else:
        raise HTTPException(status_code=500, detail="Failed to send OTP")


@app.post("/api/v1/trading/authenticate")
async def authenticate_trading(request: OTPRequest):
    """Authenticate with OTP to get trading token."""
    if not _trading_service:
        raise HTTPException(status_code=503, detail="Trading service not configured")
    
    if not request.otp and not request.smart_otp:
        raise HTTPException(status_code=400, detail="Must provide otp or smart_otp")
    
    success = await _trading_service.get_trading_token(
        otp=request.otp,
        smart_otp=request.smart_otp
    )
    
    if success:
        return {"message": "Trading token obtained", "valid_hours": 8}
    else:
        raise HTTPException(status_code=401, detail="Invalid OTP")


@app.get("/api/v1/trading/balance")
async def get_balance():
    """Get account balance."""
    if not _trading_service:
        raise HTTPException(status_code=503, detail="Trading service not configured")
    
    balance = await _trading_service.get_balance()
    if balance:
        return {
            "account_no": balance.account_no,
            "cash_balance": balance.cash_balance,
            "buying_power": balance.buying_power,
            "withdrawable": balance.withdrawable
        }
    else:
        raise HTTPException(status_code=500, detail="Failed to get balance")


@app.get("/api/v1/trading/orders")
async def get_orders():
    """Get list of orders."""
    if not _trading_service:
        raise HTTPException(status_code=503, detail="Trading service not configured")
    
    orders = await _trading_service.get_orders()
    return [
        {
            "id": o.id,
            "symbol": o.symbol,
            "side": o.side.value,
            "price": o.price,
            "quantity": o.quantity,
            "filled_quantity": o.filled_quantity,
            "status": o.status
        }
        for o in orders
    ]


@app.post("/api/v1/trading/orders")
async def place_order(request: OrderRequest):
    """Place a BUY order manually."""
    if not _trading_service:
        raise HTTPException(status_code=503, detail="Trading service not configured")
    
    if not _trading_service.tokens.is_trading_token_valid():
        raise HTTPException(status_code=401, detail="Trading token not valid. Please authenticate with OTP first.")
    
    from ..adapters.trading_service import OrderSide, OrderType
    
    order = await _trading_service.place_order(
        symbol=request.symbol,
        side=OrderSide.BUY,
        quantity=request.quantity,
        price=request.price,
        order_type=OrderType.LO
    )
    
    if order:
        return {"order_id": order.id, "status": order.status}
    else:
        raise HTTPException(status_code=500, detail="Failed to place order")


@app.delete("/api/v1/trading/orders/{order_id}")
async def cancel_order(order_id: str):
    """Cancel an order."""
    if not _trading_service:
        raise HTTPException(status_code=503, detail="Trading service not configured")
    
    if not _trading_service.tokens.is_trading_token_valid():
        raise HTTPException(status_code=401, detail="Trading token not valid")
    
    success = await _trading_service.cancel_order(order_id)
    if success:
        return {"message": "Order cancelled"}
    else:
        raise HTTPException(status_code=500, detail="Failed to cancel order")

