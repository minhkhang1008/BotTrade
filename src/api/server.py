"""
Bot Trade - API Server
FastAPI application with REST and WebSocket endpoints
"""
import asyncio
import logging
from contextlib import asynccontextmanager
from datetime import datetime
from typing import List, Optional, Dict, Any, Callable, Awaitable

from fastapi import FastAPI, WebSocket, WebSocketDisconnect, Query, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

from ..config import settings
from ..storage.database import db
from ..core.models import Signal, Bar, SignalStatus, SignalType
from ..adapters.notification_service import get_notification_service

logger = logging.getLogger(__name__)

# Callback for watchlist update (set by main.py)
_watchlist_update_callback: Optional[Callable[[List[str]], Awaitable[None]]] = None

def set_watchlist_update_callback(callback: Callable[[List[str]], Awaitable[None]]):
    """Register callback for watchlist updates."""
    global _watchlist_update_callback
    _watchlist_update_callback = callback


# Callback for forcing a demo signal (set by main.py)
_force_demo_signal_callback: Optional[Callable[[str], Awaitable[Signal]]] = None

def set_force_demo_signal_callback(callback: Callable[[str], Awaitable[Signal]]):
    """Register callback for forcing demo signals."""
    global _force_demo_signal_callback
    _force_demo_signal_callback = callback


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
    # Cache latest signal check data per symbol for new WebSocket clients
    latest_signal_checks: Dict[str, dict] = {}


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
    import json
    watchlist_changed = False
    
    if update.watchlist is not None:
        old_watchlist = app_state.current_settings.get("watchlist", [])
        new_watchlist = update.watchlist
        
        # Check if watchlist actually changed
        if set(old_watchlist) != set(new_watchlist):
            watchlist_changed = True
        
        app_state.current_settings["watchlist"] = new_watchlist
        # Save watchlist to database for persistence
        await db.save_setting("watchlist", json.dumps(new_watchlist))
    
    if update.default_quantity is not None:
        app_state.current_settings["default_quantity"] = update.default_quantity
        # Save default_quantity to database for persistence
        await db.save_setting("default_quantity", str(update.default_quantity))
    
    # Update DNSE subscription if watchlist changed
    if watchlist_changed and _watchlist_update_callback:
        try:
            await _watchlist_update_callback(app_state.current_settings["watchlist"])
            logger.info(f"Watchlist updated and saved to database: {app_state.current_settings['watchlist']}")
        except Exception as e:
            logger.error(f"Failed to update watchlist subscription: {e}")
    
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


class IndicatorResponse(BaseModel):
    """Response model for indicators."""
    symbol: str
    rsi: Optional[float] = None
    macd_line: Optional[float] = None
    macd_signal: Optional[float] = None
    macd_histogram: Optional[float] = None
    atr: Optional[float] = None
    has_macd_crossover: bool = False
    timestamp: str


@app.get("/api/v1/indicators/{symbol}", response_model=IndicatorResponse)
async def get_indicators(symbol: str):
    """Get current indicator values for a symbol."""
    from ..core.indicators import get_all_indicators, calculate_macd, check_macd_crossover
    from ..core.models import Bar
    
    # Get bars for this symbol
    bars = await db.get_bars(symbol=symbol, limit=200)
    
    if not bars or len(bars) < 20:
        return IndicatorResponse(
            symbol=symbol,
            timestamp=datetime.now().isoformat()
        )
    
    # Get settings for indicator periods
    rsi_period = settings.rsi_period
    macd_fast = settings.macd_fast
    macd_slow = settings.macd_slow
    macd_signal = settings.macd_signal
    atr_period = settings.atr_period
    
    # Calculate indicators
    indicators = get_all_indicators(
        bars, rsi_period, macd_fast, macd_slow, macd_signal, atr_period
    )
    
    # Calculate MACD for crossover check
    closes = [b.close for b in bars]
    current_macd = calculate_macd(closes, macd_fast, macd_slow, macd_signal)
    
    # Check crossover (need previous MACD)
    has_crossover = False
    if len(bars) > 1:
        prev_closes = closes[:-1]
        prev_macd = calculate_macd(prev_closes, macd_fast, macd_slow, macd_signal)
        if current_macd and prev_macd:
            has_crossover = check_macd_crossover(current_macd, prev_macd)
    
    return IndicatorResponse(
        symbol=symbol,
        rsi=indicators.rsi,
        macd_line=current_macd.macd_line if current_macd else None,
        macd_signal=current_macd.signal_line if current_macd else None,
        macd_histogram=current_macd.histogram if current_macd else None,
        atr=indicators.atr,
        has_macd_crossover=has_crossover,
        timestamp=datetime.now().isoformat()
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
    
    # Send cached signal check data so new clients see analysis immediately
    for symbol, check_data in app_state.latest_signal_checks.items():
        try:
            await manager.send_personal(websocket, "signal_check", check_data)
        except Exception:
            pass
    
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


async def broadcast_signal_check(symbol: str, bar_data: dict, conditions_passed: int, 
                                  total_conditions: int, passed: list, failed: list,
                                  indicators: dict = None, analysis_details: dict = None):
    """Broadcast signal check progress for UI visualization."""
    data = {
        "symbol": symbol,
        "bar": bar_data,
        "conditions_passed": conditions_passed,
        "total_conditions": total_conditions,
        "passed": passed,
        "failed": failed,
        "indicators": indicators or {},
        "analysis": analysis_details or {},
        "timestamp": datetime.now().isoformat()
    }
    # Cache for new WebSocket clients
    app_state.latest_signal_checks[symbol] = data
    await manager.broadcast("signal_check", data)


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


# ============ Demo Mode Endpoint ============

# Callback for demo mode (set by main.py)
_demo_mode_callback: Optional[Callable[[], Awaitable[None]]] = None


def set_demo_mode_callback(callback: Callable[[], Awaitable[None]]):
    """Register callback for demo mode activation."""
    global _demo_mode_callback
    _demo_mode_callback = callback


@app.post("/api/v1/demo/start")
async def start_demo_mode():
    """
    Start demo mode - generates mock data with signals for presentation.
    This will generate a sequence of bars that leads to a BUY signal.
    """
    if _demo_mode_callback:
        try:
            await _demo_mode_callback()
            return {"message": "Demo mode started - signals will be generated shortly"}
        except Exception as e:
            logger.error(f"Failed to start demo mode: {e}")
            raise HTTPException(status_code=500, detail=str(e))
    else:
        raise HTTPException(status_code=503, detail="Demo mode not available - bot not running in mock mode")


class ForceDemoSignalRequest(BaseModel):
    symbol: Optional[str] = None


@app.post("/api/v1/demo/force-signal")
async def force_demo_signal(request: ForceDemoSignalRequest = None):
    """
    Force generate a demo BUY signal immediately for testing/presentation.
    This bypasses all normal signal conditions and creates a signal directly.
    
    Useful for:
    - Testing the UI signal display
    - Demo presentations
    - Testing notification flow
    """
    if _force_demo_signal_callback:
        try:
            symbol = request.symbol if request and request.symbol else None
            signal = await _force_demo_signal_callback(symbol)
            return {
                "message": "Demo signal generated",
                "signal": signal.to_dict()
            }
        except Exception as e:
            logger.error(f"Failed to force demo signal: {e}")
            raise HTTPException(status_code=500, detail=str(e))
    else:
        raise HTTPException(status_code=503, detail="Force signal not available - bot not running in mock mode")


# ============ Notification Endpoints ============

@app.get("/api/v1/notification/status")
async def get_notification_status():
    """Get current notification configuration status."""
    notifier = get_notification_service()
    return {
        "enabled": notifier.is_enabled if notifier else False,
        "configured": settings.notification_configured,
        "telegram_chat_id": settings.telegram_chat_id[:4] + "***" if settings.telegram_chat_id else None
    }


class NotificationConfigRequest(BaseModel):
    bot_token: str
    chat_id: str


@app.post("/api/v1/notification/configure")
async def configure_notification(request: NotificationConfigRequest):
    """Configure Telegram notification (runtime only, not persisted to .env)."""
    notifier = get_notification_service()
    if not notifier:
        raise HTTPException(status_code=503, detail="Notification service not initialized")
    
    notifier.configure(request.bot_token, request.chat_id)
    
    return {
        "message": "Notification configured successfully",
        "enabled": notifier.is_enabled
    }


@app.post("/api/v1/notification/test")
async def test_notification():
    """Send a test notification to verify Telegram setup."""
    notifier = get_notification_service()
    
    if not notifier:
        raise HTTPException(status_code=503, detail="Notification service not initialized")
    
    if not notifier.is_enabled:
        raise HTTPException(
            status_code=400, 
            detail="Telegram not configured. Set TELEGRAM_BOT_TOKEN and TELEGRAM_CHAT_ID in .env"
        )
    
    success = await notifier.send_test_notification()
    
    if success:
        return {"message": "Test notification sent successfully! Check your Telegram."}
    else:
        raise HTTPException(status_code=500, detail="Failed to send test notification. Check bot token and chat ID.")


