"""
Bot Trade - Main Entry Point
Orchestrates all components: DNSE adapter, signal engine, notifications, and API server
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
from .adapters.notification_service import init_notification_service, get_notification_service
from .core.signal_engine import SignalEngine
from .core.models import Bar, Signal, SignalType, SignalStatus
from .api.server import (
    app, 
    broadcast_bar_closed, 
    broadcast_signal,
    broadcast_signal_check,
    broadcast_system_status,
    set_dnse_status,
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
    """
    
    def __init__(self, use_mock: bool = False):
        self.use_mock = use_mock
        self.signal_engines: dict[str, SignalEngine] = {}
        self.dnse_adapter = None
        self._main_loop: Optional[asyncio.AbstractEventLoop] = None
        self._running = False
        self._current_symbols: list[str] = []
    
    def _create_signal_engine(self, symbol: str) -> SignalEngine:
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
        if self._main_loop and self._main_loop.is_running():
            self._main_loop.call_soon_threadsafe(
                lambda: asyncio.create_task(self._on_bar_closed(bar))
            )
        else:
            logger.warning(f"No event loop to handle bar: {bar.symbol}")
    
    async def _on_bar_closed(self, bar: Bar):
        logger.info(f"📊 {bar.symbol} | O:{bar.open:.2f} H:{bar.high:.2f} L:{bar.low:.2f} C:{bar.close:.2f} V:{bar.volume:.0f}")
        try:
            await db.save_bar(bar)
            await broadcast_bar_closed(bar)
            
            if bar.symbol not in self.signal_engines:
                self.signal_engines[bar.symbol] = self._create_signal_engine(bar.symbol)
                historical = await db.get_bars(bar.symbol, settings.timeframe, limit=200)
                if historical:
                    self.signal_engines[bar.symbol].load_bars(historical[:-1])
            
            engine = self.signal_engines[bar.symbol]
            result = engine.add_bar(bar)
            
            if result:
                await self._broadcast_signal_check(bar.symbol, engine, bar, result)
            
            if result and result.should_signal and result.signal:
                signal = result.signal
                logger.info(f"🔔 SIGNAL: {signal.symbol} BUY @ {signal.entry:,.0f} | SL: {signal.stop_loss:,.0f} | TP: {signal.take_profit:,.0f}")
                
                await db.save_signal(signal)
                await broadcast_signal(signal)
                
                notifier = get_notification_service()
                if notifier and notifier.is_enabled:
                    # Gọi hàm rải tin nhắn thông minh (nó sẽ tự filter chat_id từ DB)
                    await notifier.send_signal_notification(signal)
        
        except Exception as e:
            logger.error(f"Error processing bar: {e}")
    
    async def _broadcast_signal_check(self, symbol: str, engine, bar: Bar, result=None):
        from .core.indicators import get_all_indicators
        
        if result:
            passed_count = len(result.reasons) if result.reasons else 0
            passed_list = result.reasons or []
            failed_list = result.failed_conditions or []
        else:
            check_result = engine.check_signal()
            passed_count = len(check_result.reasons) if check_result.reasons else 0
            passed_list = check_result.reasons or []
            failed_list = check_result.failed_conditions or []
        
        total_conditions = 4 
        indicators = {}
        analysis_details = {}
        
        if hasattr(engine, 'bars') and len(engine.bars) > 0:
            ind = get_all_indicators(
                engine.bars, engine.rsi_period, engine.macd_fast,
                engine.macd_slow, engine.macd_signal, engine.atr_period
            )
            indicators = {
                "rsi": round(ind.rsi, 2) if ind.rsi else None,
                "macd": round(ind.macd_line, 4) if ind.macd_line else None,
                "macd_signal": round(ind.macd_signal, 4) if ind.macd_signal else None,
                "atr": round(ind.atr, 2) if ind.atr else None,
            }
            
            pivot_lows = [{"price": p.price, "index": p.bar_index} for p in engine.pivot_detector.pivot_lows[-5:]]
            pivot_highs = [{"price": p.price, "index": p.bar_index} for p in engine.pivot_detector.pivot_highs[-5:]]
            
            trend_result = engine.trend_analyzer.analyze(
                engine.pivot_detector.pivot_lows, engine.pivot_detector.pivot_highs
            )
            
            support_zone = None
            if ind.atr and engine.pivot_detector.pivot_lows:
                last_pivot = engine.pivot_detector.pivot_lows[-1]
                zone_width = engine.zone_width_atr_mult * ind.atr
                support_zone = {
                    "pivot_price": last_pivot.price,
                    "zone_low": last_pivot.price - zone_width,
                    "zone_high": last_pivot.price + zone_width,
                }
            
            analysis_details = {
                "pivot_lows": pivot_lows,
                "pivot_highs": pivot_highs,
                "pivot_lows_count": len(engine.pivot_detector.pivot_lows),
                "pivot_highs_count": len(engine.pivot_detector.pivot_highs),
                "higher_lows_count": trend_result.higher_lows_count,
                "higher_highs_count": trend_result.higher_highs_count,
                "is_uptrend": trend_result.is_uptrend,
                "trend_reason": trend_result.reason,
                "support_zone": support_zone,
                "bar_low": bar.low,
                "bar_high": bar.high,
                "total_bars": len(engine.bars),
            }
        
        await broadcast_signal_check(
            symbol=symbol,
            bar_data=bar.to_dict(),
            conditions_passed=passed_count,
            total_conditions=total_conditions,
            passed=passed_list,
            failed=failed_list,
            indicators=indicators,
            analysis_details=analysis_details
        )
    
    async def _broadcast_initial_signal_checks(self):
        for symbol in self._current_symbols:
            engine = self.signal_engines.get(symbol)
            if engine and hasattr(engine, 'bars') and len(engine.bars) >= 2:
                last_bar = engine.bars[-1]
                try:
                    await self._broadcast_signal_check(symbol, engine, last_bar)
                    logger.info(f"📊 Broadcast initial signal check for {symbol}")
                except Exception as e:
                    logger.error(f"Failed to broadcast initial signal check for {symbol}: {e}")
    
    def _on_connected(self):
        set_dnse_status(True)
        logger.info("✅ DNSE connected")
        if self._main_loop and self._main_loop.is_running():
            self._main_loop.call_soon_threadsafe(
                lambda: asyncio.create_task(broadcast_system_status("connected", True))
            )
    
    def _on_disconnected(self):
        set_dnse_status(False)
        logger.warning("❌ DNSE disconnected")
        if self._main_loop and self._main_loop.is_running():
            self._main_loop.call_soon_threadsafe(
                lambda: asyncio.create_task(broadcast_system_status("disconnected", False))
            )

    async def reload_master_watchlist(self):
        """Gom tất cả mã từ mọi user và cập nhật kết nối DNSE."""
        all_symbols_set = await db.get_all_user_watchlists()
        new_symbols = list(all_symbols_set) if all_symbols_set else settings.watchlist_symbols.copy()
        
        old_symbols = self._current_symbols.copy()
        to_add = [s for s in new_symbols if s not in old_symbols]
        to_remove = [s for s in old_symbols if s not in new_symbols]
        
        for symbol in to_remove:
            if self.dnse_adapter and hasattr(self.dnse_adapter, 'unsubscribe'):
                self.dnse_adapter.unsubscribe(symbol)
            if symbol in self.signal_engines:
                del self.signal_engines[symbol]
        
        for symbol in to_add:
            if self.dnse_adapter and hasattr(self.dnse_adapter, 'subscribe'):
                self.dnse_adapter.subscribe(symbol)
            self.signal_engines[symbol] = self._create_signal_engine(symbol)
            historical = await db.get_bars(symbol, settings.timeframe, limit=200)
            if historical:
                self.signal_engines[symbol].load_bars(historical)
                
        self._current_symbols = new_symbols
        logger.info(f"🔄 Đã cập nhật Master Watchlist: {len(new_symbols)} mã ({self._current_symbols})")

    async def update_watchlist(self, new_symbols: list[str] = None):
        """Bỏ qua list API gửi lên, ép backend quét lại toàn bộ DB khi có user đổi Settings."""
        await self.reload_master_watchlist()

    async def start_demo_mode(self):
        if not self.use_mock:
            logger.warning("Demo mode only available in mock mode")
            return
        if not isinstance(self.dnse_adapter, MockDNSEAdapter):
            logger.warning("Demo mode requires MockDNSEAdapter")
            return
        logger.info("🎬 Starting demo mode...")
        for symbol in self._current_symbols:
            if symbol in self.signal_engines:
                self.signal_engines[symbol].reset()
                logger.info(f"🔄 Reset signal engine for {symbol}")
        asyncio.create_task(self.dnse_adapter.generate_demo_signal_scenario())

    async def force_demo_signal(self, symbol: str = None) -> Signal:
        if not symbol:
            symbol = self._current_symbols[0] if self._current_symbols else "VNM"
        symbol = symbol.upper()
        if symbol not in self.signal_engines:
            self.signal_engines[symbol] = self._create_signal_engine(symbol)
        
        engine = self.signal_engines[symbol]
        latest_bars = await db.get_bars(symbol, settings.timeframe, limit=1)
        latest_bar = latest_bars[0] if latest_bars else None
        signal = engine.generate_demo_signal(symbol, latest_bar)
        
        logger.info(f"🔔 DEMO SIGNAL FORCED: {signal.symbol} BUY @ {signal.entry:,.0f} | SL: {signal.stop_loss:,.0f} | TP: {signal.take_profit:,.0f}")
        await db.save_signal(signal)
        await broadcast_signal(signal)
        return signal

    async def start(self):
        self._running = True
        self._main_loop = asyncio.get_running_loop()
        set_watchlist_update_callback(self.update_watchlist)
        
        if self.use_mock:
            set_demo_mode_callback(self.start_demo_mode)
            set_force_demo_signal_callback(self.force_demo_signal)
        
        await db.connect()
        logger.info("Database ready")
        
        # Gom Watchlist tổng
        all_symbols_set = await db.get_all_user_watchlists()
        if all_symbols_set:
            self._current_symbols = list(all_symbols_set)
        else:
            self._current_symbols = settings.watchlist_symbols.copy()
            
        saved_quantity = await db.get_setting("default_quantity")
        app_state.current_settings["default_quantity"] = int(saved_quantity) if saved_quantity else settings.default_quantity
        
        for symbol in self._current_symbols:
            self.signal_engines[symbol] = self._create_signal_engine(symbol)
            historical = await db.get_bars(symbol, settings.timeframe, limit=200)
            if historical:
                self.signal_engines[symbol].load_bars(historical)
        
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
            if settings.dnse_username and settings.dnse_password:
                config = DNSEConfig(username=settings.dnse_username, password=settings.dnse_password, mqtt_url=settings.dnse_mqtt_url)
                self.dnse_adapter = DNSEAdapter(
                    config=config,
                    on_bar_closed=self._handle_bar_from_thread,
                    on_connected=self._on_connected,
                    on_disconnected=self._on_disconnected
                )
                for symbol in self._current_symbols:
                    existing_bars = await db.get_bars(symbol, settings.timeframe, limit=200)
                    if len(existing_bars) < 50:
                        historical_bars = await self.dnse_adapter.fetch_historical_bars(symbol, settings.timeframe, limit=200)
                        if historical_bars:
                            await db.save_bars(historical_bars)
                            if symbol in self.signal_engines:
                                self.signal_engines[symbol].load_bars(historical_bars)
                self.dnse_adapter.connect(self._current_symbols, settings.timeframe)
            else:
                logger.warning("⚠️ DNSE credentials not found - API-only mode")
        
        logger.info(f"🚀 Bot Trade started | Master Watchlist: {self._current_symbols}")
        await self._broadcast_initial_signal_checks()
    
    async def stop(self):
        self._running = False
        if self.dnse_adapter:
            if isinstance(self.dnse_adapter, MockDNSEAdapter):
                await self.dnse_adapter.disconnect()
            else:
                self.dnse_adapter.disconnect()
        await db.disconnect()
        logger.info("Bot Trade stopped")

import os
_use_mock_mode = os.environ.get("BOT_TRADE_MOCK_MODE", "false").lower() == "true"

bot_app: Optional[BotTradeApp] = None
_started = False

@app.on_event("startup")
async def on_startup():
    global bot_app, _started
    if _started:
        return
    _started = True
    
    notifier = init_notification_service(
        bot_token=settings.telegram_bot_token,
        chat_id=settings.telegram_chat_id
    )
    if notifier.is_enabled:
        logger.info(f"📱 Telegram notifications: ENABLED")
    else:
        logger.info(f"📱 Telegram notifications: DISABLED")
    
    bot_app = BotTradeApp(use_mock=_use_mock_mode)
    await bot_app.start()

@app.on_event("shutdown")
async def on_shutdown():
    global bot_app, _started
    if bot_app:
        await bot_app.stop()
    _started = False

def main():
    print("\n⚠️  Please use 'python run.py' instead of 'python -m src.main'")
    print("   This avoids the double startup issue.\n")
    print("="*50)
    print("🤖 BOT TRADE - Trading Signal Assistant")
    print("="*50)
    
    use_mock = "--mock" in sys.argv
    if use_mock:
        os.environ["BOT_TRADE_MOCK_MODE"] = "true"
        print("🧪 MOCK MODE ENABLED")
    
    uvicorn.run("src.main:app", host=settings.host, port=settings.port, reload=False, log_level="info")

if __name__ == "__main__":
    main()