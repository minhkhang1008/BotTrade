"""
Bot Trade - Main Entry Point
Orchestrates all components: DNSE adapter, signal engine, trading, and API server
"""
import asyncio
import logging
import sys
from datetime import datetime
from typing import Optional

import uvicorn

from .config import settings
from .storage.database import db
from .adapters.dnse_adapter import DNSEAdapter, DNSEConfig, MockDNSEAdapter
from .adapters.trading_service import TradingService, OrderSide, OrderType
from .core.signal_engine import SignalEngine
from .core.models import Bar, Signal
from .api.server import (
    app, 
    broadcast_bar_closed, 
    broadcast_signal, 
    broadcast_system_status,
    set_dnse_status,
    set_trading_service,
    app_state
)


# Configure logging - less verbose
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    datefmt="%H:%M:%S"
)
logger = logging.getLogger(__name__)

# Reduce noise from third-party libraries
logging.getLogger("httpx").setLevel(logging.WARNING)
logging.getLogger("httpcore").setLevel(logging.WARNING)
logging.getLogger("uvicorn.access").setLevel(logging.WARNING)


class BotTradeApp:
    """
    Main application orchestrator.
    
    Connects all components:
    - DNSE Adapter: Receives market data
    - Signal Engine: Generates trading signals
    - Trading Service: Places orders (optional)
    - API Server: Provides REST/WebSocket API
    - Database: Persists bars and signals
    """
    
    def __init__(self, use_mock: bool = False):
        self.use_mock = use_mock
        self.signal_engines: dict[str, SignalEngine] = {}
        self.dnse_adapter = None
        self.trading_service: Optional[TradingService] = None
        self._running = False
    
    def _create_signal_engine(self, symbol: str) -> SignalEngine:
        """Create a signal engine for a symbol."""
        return SignalEngine(
            zone_width_atr_mult=settings.zone_width_atr_multiplier,
            sl_buffer_atr_mult=settings.sl_buffer_atr_multiplier,
            risk_reward_ratio=settings.risk_reward_ratio,
            default_quantity=settings.default_quantity,
            rsi_period=settings.rsi_period,
            macd_fast=settings.macd_fast,
            macd_slow=settings.macd_slow,
            macd_signal=settings.macd_signal,
            atr_period=settings.atr_period
        )
    
    async def _on_bar_closed(self, bar: Bar):
        """Handle new closed bar from DNSE."""
        logger.info(f"📊 {bar.symbol} | O:{bar.open:.0f} H:{bar.high:.0f} L:{bar.low:.0f} C:{bar.close:.0f}")
        
        try:
            # Save bar to database
            await db.save_bar(bar)
            
            # Broadcast to WebSocket clients
            await broadcast_bar_closed(bar)
            
            # Get or create signal engine for this symbol
            if bar.symbol not in self.signal_engines:
                self.signal_engines[bar.symbol] = self._create_signal_engine(bar.symbol)
                
                # Load historical bars
                historical = await db.get_bars(bar.symbol, settings.timeframe, limit=200)
                if historical:
                    self.signal_engines[bar.symbol].load_bars(historical[:-1])
            
            engine = self.signal_engines[bar.symbol]
            
            # Add bar and check for signal
            result = engine.add_bar(bar)
            
            if result and result.should_signal and result.signal:
                signal = result.signal
                logger.info(f"🔔 SIGNAL: {signal.symbol} BUY @ {signal.entry:,.0f} | SL: {signal.stop_loss:,.0f} | TP: {signal.take_profit:,.0f}")
                
                # Save signal to database
                await db.save_signal(signal)
                
                # Broadcast to WebSocket clients (for UI)
                await broadcast_signal(signal)
                
                # Auto-trade: place order
                if settings.auto_trade_enabled and self.trading_service:
                    await self._execute_trade(signal)
        
        except Exception as e:
            logger.error(f"Error processing bar: {e}")
    
    async def _execute_trade(self, signal: Signal):
        """Execute trade based on signal."""
        if not self.trading_service:
            return
        
        if not self.trading_service.tokens.is_trading_token_valid():
            logger.warning("⚠️ Trading token expired. Need OTP to continue.")
            return
        
        try:
            order = await self.trading_service.place_order(
                symbol=signal.symbol,
                side=OrderSide.BUY,
                quantity=signal.quantity,
                price=signal.entry,
                order_type=OrderType.LO
            )
            
            if order:
                logger.info(f"✅ Order placed: {order.id}")
            else:
                logger.error("❌ Failed to place order")
        
        except Exception as e:
            logger.error(f"Trade error: {e}")
    
    def _on_connected(self):
        """Handle DNSE connected."""
        set_dnse_status(True)
        asyncio.create_task(broadcast_system_status("connected", True))
        logger.info("✅ DNSE connected")
    
    def _on_disconnected(self):
        """Handle DNSE disconnected."""
        set_dnse_status(False)
        asyncio.create_task(broadcast_system_status("disconnected", False))
        logger.warning("❌ DNSE disconnected")
    
    async def start(self):
        """Start the bot application."""
        self._running = True
        
        # Connect to database
        await db.connect()
        logger.info("Database ready")
        
        # Initialize Trading Service (if configured)
        if settings.trading_configured:
            self.trading_service = TradingService(
                username=settings.dnse_username,
                password=settings.dnse_password,
                account_no=settings.dnse_account_no
            )
            if await self.trading_service.initialize():
                logger.info(f"Trading service ready | Account: {settings.dnse_account_no}")
                set_trading_service(self.trading_service)  # Register with API
                if settings.auto_trade_enabled:
                    logger.warning("⚠️ AUTO-TRADE ENABLED - Bot will place real orders!")
        
        # Initialize signal engines for watchlist
        for symbol in settings.watchlist_symbols:
            self.signal_engines[symbol] = self._create_signal_engine(symbol)
            
            # Load historical bars
            historical = await db.get_bars(symbol, settings.timeframe, limit=200)
            if historical:
                self.signal_engines[symbol].load_bars(historical)
                logger.info(f"Loaded {len(historical)} bars for {symbol}")
        
        # Start DNSE adapter
        if self.use_mock:
            logger.info("🧪 Running in MOCK mode (simulated data)")
            self.dnse_adapter = MockDNSEAdapter(
                on_bar_closed=lambda bar: asyncio.create_task(self._on_bar_closed(bar)),
                on_connected=self._on_connected,
                on_disconnected=self._on_disconnected
            )
            await self.dnse_adapter.connect(settings.watchlist_symbols, settings.timeframe)
            asyncio.create_task(self.dnse_adapter.simulate_bars(interval_seconds=10))
        else:
            if settings.dnse_username and settings.dnse_password:
                config = DNSEConfig(
                    username=settings.dnse_username,
                    password=settings.dnse_password,
                    mqtt_url=settings.dnse_mqtt_url
                )
                self.dnse_adapter = DNSEAdapter(
                    config=config,
                    on_bar_closed=lambda bar: asyncio.create_task(self._on_bar_closed(bar)),
                    on_connected=self._on_connected,
                    on_disconnected=self._on_disconnected
                )
                self.dnse_adapter.connect(settings.watchlist_symbols, settings.timeframe)
            else:
                logger.warning("DNSE not configured - API-only mode")
        
        logger.info(f"🚀 Bot Trade started | Symbols: {settings.watchlist_symbols}")
    
    async def stop(self):
        """Stop the bot application."""
        self._running = False
        
        if self.trading_service:
            await self.trading_service.close()
        
        if self.dnse_adapter:
            if isinstance(self.dnse_adapter, MockDNSEAdapter):
                await self.dnse_adapter.disconnect()
            else:
                self.dnse_adapter.disconnect()
        
        await db.disconnect()
        logger.info("Bot Trade stopped")


# Global app instance
bot_app = BotTradeApp()


@app.on_event("startup")
async def on_startup():
    await bot_app.start()


@app.on_event("shutdown")
async def on_shutdown():
    await bot_app.stop()


def main():
    """Main entry point."""
    print("\n" + "="*50)
    print("🤖 BOT TRADE - Trading Signal Assistant")
    print("="*50)
    print(f"Symbols: {settings.watchlist_symbols}")
    print(f"Timeframe: {settings.timeframe}")
    print(f"Auto-trade: {'ON ⚠️' if settings.auto_trade_enabled else 'OFF'}")
    print("="*50 + "\n")
    
    # Check for mock mode
    use_mock = "--mock" in sys.argv
    if use_mock:
        bot_app.use_mock = True
    
    # Run API server
    uvicorn.run(
        "src.main:app",
        host=settings.host,
        port=settings.port,
        reload=False,
        log_level="warning"
    )


if __name__ == "__main__":
    main()
