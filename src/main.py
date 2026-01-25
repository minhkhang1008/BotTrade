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
from .core.models import Bar, Signal, SignalType, SignalStatus
from .api.server import (
    app, 
    broadcast_bar_closed, 
    broadcast_signal, 
    broadcast_system_status,
    set_dnse_status,
    set_trading_service,
    set_watchlist_update_callback,
    set_demo_mode_callback,
    set_force_demo_signal_callback,
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
        self._main_loop: Optional[asyncio.AbstractEventLoop] = None
        self._running = False
        self._current_symbols: list[str] = []
    
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
    
    def _handle_bar_from_thread(self, bar: Bar):
        """
        Thread-safe callback for handling bars from MQTT thread.
        Schedules the async handler in the main event loop.
        """
        if self._main_loop and self._main_loop.is_running():
            self._main_loop.call_soon_threadsafe(
                lambda: asyncio.create_task(self._on_bar_closed(bar))
            )
        else:
            logger.warning(f"No event loop to handle bar: {bar.symbol}")
    
    async def _on_bar_closed(self, bar: Bar):
        """Handle new closed bar from DNSE."""
        logger.info(f"📊 {bar.symbol} | O:{bar.open:.2f} H:{bar.high:.2f} L:{bar.low:.2f} C:{bar.close:.2f} V:{bar.volume:.0f}")
        
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
        """Handle DNSE connected (called from MQTT thread)."""
        set_dnse_status(True)
        logger.info("✅ DNSE connected")
        
        # Schedule async broadcast in the main event loop (thread-safe)
        if self._main_loop and self._main_loop.is_running():
            self._main_loop.call_soon_threadsafe(
                lambda: asyncio.create_task(broadcast_system_status("connected", True))
            )
    
    def _on_disconnected(self):
        """Handle DNSE disconnected (called from MQTT thread)."""
        set_dnse_status(False)
        logger.warning("❌ DNSE disconnected")
        
        # Schedule async broadcast in the main event loop (thread-safe)
        if self._main_loop and self._main_loop.is_running():
            self._main_loop.call_soon_threadsafe(
                lambda: asyncio.create_task(broadcast_system_status("disconnected", False))
            )
    
    async def update_watchlist(self, new_symbols: list[str]):
        """
        Update the watchlist dynamically.
        Subscribes to new symbols and unsubscribes from removed ones.
        """
        new_symbols = [s.upper() for s in new_symbols]
        old_symbols = self._current_symbols.copy()
        
        # Find symbols to add and remove
        to_add = [s for s in new_symbols if s not in old_symbols]
        to_remove = [s for s in old_symbols if s not in new_symbols]
        
        # Unsubscribe from removed symbols
        for symbol in to_remove:
            if self.dnse_adapter:
                if hasattr(self.dnse_adapter, 'unsubscribe'):
                    self.dnse_adapter.unsubscribe(symbol)
            if symbol in self.signal_engines:
                del self.signal_engines[symbol]
            logger.info(f"📤 Removed {symbol} from watchlist")
        
        # Subscribe to new symbols
        for symbol in to_add:
            if self.dnse_adapter:
                if hasattr(self.dnse_adapter, 'subscribe'):
                    self.dnse_adapter.subscribe(symbol)
            
            # Create signal engine for new symbol
            self.signal_engines[symbol] = self._create_signal_engine(symbol)
            
            # Load historical bars if available
            historical = await db.get_bars(symbol, settings.timeframe, limit=200)
            if historical:
                self.signal_engines[symbol].load_bars(historical)
                logger.info(f"Loaded {len(historical)} bars for {symbol}")
            
            logger.info(f"📥 Added {symbol} to watchlist")
        
        self._current_symbols = new_symbols
        logger.info(f"📊 Watchlist updated: {new_symbols}")

    async def start_demo_mode(self):
        """
        Start demo mode - generates mock bars that lead to signals.
        This is for presentation purposes.
        
        In demo mode:
        1. Reset signal engines (clear old bars/pivots)
        2. Generate bars that will trigger a BUY signal
        """
        if not self.use_mock:
            logger.warning("Demo mode only available in mock mode")
            return
        
        if not isinstance(self.dnse_adapter, MockDNSEAdapter):
            logger.warning("Demo mode requires MockDNSEAdapter")
            return
        
        logger.info("🎬 Starting demo mode...")
        
        # Reset signal engines for demo (clear old data to start fresh)
        for symbol in self._current_symbols:
            if symbol in self.signal_engines:
                self.signal_engines[symbol].reset()
                logger.info(f"🔄 Reset signal engine for {symbol}")
        
        # Start generating demo bars that will trigger a signal
        asyncio.create_task(self.dnse_adapter.generate_demo_signal_scenario())

    async def force_demo_signal(self, symbol: str = None) -> Signal:
        """
        Force generate a demo signal immediately.
        This bypasses all normal signal conditions for testing/demo purposes.
        
        Args:
            symbol: Optional symbol to generate signal for. Uses first watchlist symbol if None.
        
        Returns:
            The generated Signal object
        """
        if not symbol:
            symbol = self._current_symbols[0] if self._current_symbols else "VNM"
        
        symbol = symbol.upper()
        
        # Get or create signal engine
        if symbol not in self.signal_engines:
            self.signal_engines[symbol] = self._create_signal_engine(symbol)
        
        engine = self.signal_engines[symbol]
        
        # Get the latest bar for realistic prices (if available)
        latest_bars = await db.get_bars(symbol, settings.timeframe, limit=1)
        latest_bar = latest_bars[0] if latest_bars else None
        
        # Generate demo signal
        signal = engine.generate_demo_signal(symbol, latest_bar)
        
        logger.info(f"🔔 DEMO SIGNAL FORCED: {signal.symbol} BUY @ {signal.entry:,.0f} | SL: {signal.stop_loss:,.0f} | TP: {signal.take_profit:,.0f}")
        
        # Save signal to database
        await db.save_signal(signal)
        
        # Broadcast to WebSocket clients
        await broadcast_signal(signal)
        
        return signal

    async def start(self):
        """Start the bot application."""
        self._running = True
        
        # Save reference to main event loop for thread-safe callbacks
        self._main_loop = asyncio.get_running_loop()
        
        # Register callback for watchlist updates from API
        set_watchlist_update_callback(self.update_watchlist)
        
        # Register demo mode callbacks (only works in mock mode)
        if self.use_mock:
            set_demo_mode_callback(self.start_demo_mode)
            set_force_demo_signal_callback(self.force_demo_signal)
        
        # Connect to database
        await db.connect()
        logger.info("Database ready")
        
        # Load watchlist from database (if exists), otherwise use .env settings
        saved_watchlist = await db.get_setting("watchlist")
        if saved_watchlist:
            import json
            try:
                watchlist_from_db = json.loads(saved_watchlist)
                if watchlist_from_db:
                    logger.info(f"Loaded watchlist from database: {watchlist_from_db}")
                    # Update app_state so API returns correct data
                    app_state.current_settings["watchlist"] = watchlist_from_db
                    self._current_symbols = watchlist_from_db
            except json.JSONDecodeError:
                logger.warning("Invalid watchlist in database, using .env")
                self._current_symbols = settings.watchlist_symbols.copy()
                app_state.current_settings["watchlist"] = self._current_symbols
        else:
            logger.info("No saved watchlist in database, using .env settings")
            self._current_symbols = settings.watchlist_symbols.copy()
            app_state.current_settings["watchlist"] = self._current_symbols
        
        # Load default_quantity from database if exists
        saved_quantity = await db.get_setting("default_quantity")
        if saved_quantity:
            try:
                app_state.current_settings["default_quantity"] = int(saved_quantity)
            except ValueError:
                app_state.current_settings["default_quantity"] = settings.default_quantity
        else:
            app_state.current_settings["default_quantity"] = settings.default_quantity
        
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
        
        # Initialize signal engines for watchlist (use loaded symbols from DB or .env)
        for symbol in self._current_symbols:
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
            await self.dnse_adapter.connect(self._current_symbols, settings.timeframe)
            asyncio.create_task(self.dnse_adapter.simulate_bars(interval_seconds=10))
        else:
            # Debug: print settings to see if env is loaded
            logger.info(f"DNSE Config check - username: '{settings.dnse_username[:3] if settings.dnse_username else 'EMPTY'}***', mqtt_url: '{settings.dnse_mqtt_url}'")
            
            if settings.dnse_username and settings.dnse_password:
                logger.info("✅ DNSE credentials found, initializing adapter...")
                config = DNSEConfig(
                    username=settings.dnse_username,
                    password=settings.dnse_password,
                    mqtt_url=settings.dnse_mqtt_url
                )
                self.dnse_adapter = DNSEAdapter(
                    config=config,
                    # Use thread-safe callback for MQTT thread
                    on_bar_closed=self._handle_bar_from_thread,
                    on_connected=self._on_connected,
                    on_disconnected=self._on_disconnected
                )
                
                # Fetch historical data for all symbols before connecting to live feed
                logger.info("📊 Fetching historical data for signal analysis...")
                for symbol in self._current_symbols:
                    # Check if we already have enough bars
                    existing_bars = await db.get_bars(symbol, settings.timeframe, limit=200)
                    if len(existing_bars) < 50:
                        # Fetch historical from DNSE
                        historical_bars = await self.dnse_adapter.fetch_historical_bars(
                            symbol, settings.timeframe, limit=200
                        )
                        if historical_bars:
                            await db.save_bars(historical_bars)
                            # Load into signal engine
                            if symbol in self.signal_engines:
                                self.signal_engines[symbol].load_bars(historical_bars)
                            logger.info(f"✅ Fetched and saved {len(historical_bars)} bars for {symbol}")
                    else:
                        logger.info(f"Using {len(existing_bars)} cached bars for {symbol}")
                
                # Now connect to live feed
                self.dnse_adapter.connect(self._current_symbols, settings.timeframe)
            else:
                logger.warning("⚠️ DNSE credentials not found - API-only mode (set DNSE_USERNAME and DNSE_PASSWORD in .env)")
        
        logger.info(f"🚀 Bot Trade started | Symbols: {self._current_symbols}")
    
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


# Check for mock mode from environment or command line args
import os
_use_mock_mode = os.environ.get("BOT_TRADE_MOCK_MODE", "false").lower() == "true"

# Global app instance
bot_app = BotTradeApp(use_mock=_use_mock_mode)


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
    
    # Check for mock mode from command line
    use_mock = "--mock" in sys.argv
    
    # Set environment variable so child process also knows about mock mode
    if use_mock:
        os.environ["BOT_TRADE_MOCK_MODE"] = "true"
        print("🧪 MOCK MODE ENABLED")
    
    # Run API server
    uvicorn.run(
        "src.main:app",
        host=settings.host,
        port=settings.port,
        reload=False,
        log_level="info"
    )


if __name__ == "__main__":
    main()
