"""
Bot Trade - Signal Generation Engine
Main logic for generating BUY signals
"""
from typing import List, Optional
from datetime import datetime
from dataclasses import dataclass
import logging

from .models import (
    Bar, Signal, SignalType, SignalStatus, 
    Pivot, SupportZone, IndicatorValues, CandlePattern
)
from .indicators import (
    get_all_indicators, calculate_macd, check_macd_crossover, MACDResult
)
from .patterns import detect_bullish_reversal
from .pivot_detector import PivotDetector
from .trend_analyzer import TrendAnalyzer, TrendAnalysisResult

logger = logging.getLogger(__name__)


@dataclass
class SignalCheckResult:
    """Result of signal check with detailed reasons."""
    should_signal: bool
    signal: Optional[Signal] = None
    reasons: List[str] = None
    failed_conditions: List[str] = None
    
    def __post_init__(self):
        if self.reasons is None:
            self.reasons = []
        if self.failed_conditions is None:
            self.failed_conditions = []


class SignalEngine:
    """
    Main signal generation engine.
    
    Generates BUY signals when ALL conditions are met:
    1. Uptrend (3 higher highs + 3 higher lows)
    2. Price touches support zone
    3. Bullish reversal pattern detected
    4. Confirmation: MACD crossover OR RSI > 50
    """
    
    def __init__(
        self,
        zone_width_atr_mult: float = 0.2,
        sl_buffer_atr_mult: float = 0.05,
        risk_reward_ratio: float = 2.0,
        default_quantity: int = 1,
        rsi_period: int = 14,
        macd_fast: int = 12,
        macd_slow: int = 26,
        macd_signal: int = 9,
        atr_period: int = 14
    ):
        self.zone_width_atr_mult = zone_width_atr_mult
        self.sl_buffer_atr_mult = sl_buffer_atr_mult
        self.risk_reward_ratio = risk_reward_ratio
        self.default_quantity = default_quantity
        
        # Indicator settings
        self.rsi_period = rsi_period
        self.macd_fast = macd_fast
        self.macd_slow = macd_slow
        self.macd_signal = macd_signal
        self.atr_period = atr_period
        
        # Components
        self.pivot_detector = PivotDetector()
        self.trend_analyzer = TrendAnalyzer()
        
        # State
        self.bars: List[Bar] = []
        self.previous_macd: Optional[MACDResult] = None
    
    def add_bar(self, bar: Bar) -> Optional[SignalCheckResult]:
        """
        Add new bar and check for signals.
        
        Args:
            bar: New closed bar
        
        Returns:
            SignalCheckResult if bar processed, None if error
        """
        self.bars.append(bar)
        bar_index = len(self.bars) - 1
        
        # Detect pivot on this bar
        self.pivot_detector.process_bar(self.bars, bar_index)
        
        # Check for signal
        result = self.check_signal()
        
        # Update previous MACD for next crossover check
        closes = [b.close for b in self.bars]
        current_macd = calculate_macd(
            closes, self.macd_fast, self.macd_slow, self.macd_signal
        )
        self.previous_macd = current_macd
        
        return result
    
    def check_signal(self) -> SignalCheckResult:
        """
        Check all conditions for BUY signal.
        
        Returns:
            SignalCheckResult with signal if conditions met
        """
        reasons = []
        failed = []
        
        if len(self.bars) < 2:
            return SignalCheckResult(
                should_signal=False,
                failed_conditions=["Insufficient data"]
            )
        
        current_bar = self.bars[-1]
        
        # Get indicators
        indicators = get_all_indicators(
            self.bars,
            self.rsi_period,
            self.macd_fast,
            self.macd_slow,
            self.macd_signal,
            self.atr_period
        )
        
        if indicators.atr is None:
            return SignalCheckResult(
                should_signal=False,
                failed_conditions=["ATR not available (need more data)"]
            )
        
        # Condition 1: Check uptrend
        trend_result = self.trend_analyzer.analyze(
            self.pivot_detector.pivot_lows,
            self.pivot_detector.pivot_highs
        )
        
        if not trend_result.is_uptrend:
            failed.append(f"No uptrend: {trend_result.reason}")
        else:
            reasons.append(f"✓ Uptrend: {trend_result.reason}")
        
        # Condition 2: Price touches support zone
        support_zone = self._get_support_zone(indicators.atr)
        if support_zone is None:
            failed.append("No support zone available")
        else:
            if support_zone.contains_price(current_bar.low, current_bar.high):
                reasons.append(
                    f"✓ Price in support zone [{support_zone.zone_low:.2f} - {support_zone.zone_high:.2f}]"
                )
            else:
                failed.append(
                    f"Price not in support zone [{support_zone.zone_low:.2f} - {support_zone.zone_high:.2f}]"
                )
        
        # Condition 3: Bullish reversal pattern
        pattern = detect_bullish_reversal(self.bars)
        if pattern:
            reasons.append(f"✓ Bullish reversal: {pattern.value}")
        else:
            failed.append("No bullish reversal pattern")
        
        # Condition 4: Confirmation (MACD cross OR RSI > 50)
        confirmation = False
        confirmation_reason = ""
        
        # Check MACD crossover
        closes = [b.close for b in self.bars]
        current_macd = calculate_macd(
            closes, self.macd_fast, self.macd_slow, self.macd_signal
        )
        
        if check_macd_crossover(current_macd, self.previous_macd):
            confirmation = True
            confirmation_reason = "MACD bullish crossover"
        elif indicators.rsi is not None and indicators.rsi > 50:
            confirmation = True
            confirmation_reason = f"RSI > 50 ({indicators.rsi:.1f})"
        
        if confirmation:
            reasons.append(f"✓ Confirmation: {confirmation_reason}")
        else:
            rsi_str = f"{indicators.rsi:.1f}" if indicators.rsi else "N/A"
            failed.append(f"No confirmation (MACD no cross, RSI={rsi_str})")
        
        # All conditions must pass
        all_passed = len(failed) == 0 and len(reasons) >= 4
        
        if not all_passed:
            return SignalCheckResult(
                should_signal=False,
                reasons=reasons,
                failed_conditions=failed
            )
        
        # Generate signal
        signal = self._create_signal(
            current_bar,
            indicators.atr,
            pattern,
            reasons
        )
        
        return SignalCheckResult(
            should_signal=True,
            signal=signal,
            reasons=reasons
        )
    
    def _get_support_zone(self, atr: float) -> Optional[SupportZone]:
        """Get the most recent support zone."""
        last_pivot_low = self.pivot_detector.get_last_pivot_low()
        if last_pivot_low is None:
            return None
        
        width = self.zone_width_atr_mult * atr
        return SupportZone(
            pivot=last_pivot_low,
            zone_low=last_pivot_low.price - width,
            zone_high=last_pivot_low.price + width
        )
    
    def _create_signal(
        self,
        bar: Bar,
        atr: float,
        pattern: CandlePattern,
        reasons: List[str]
    ) -> Signal:
        """Create BUY signal with SL/TP."""
        entry = bar.close
        
        # SL below previous pivot low
        prev_pivot = self.pivot_detector.get_previous_pivot_low()
        if prev_pivot:
            sl = prev_pivot.price - (self.sl_buffer_atr_mult * atr)
        else:
            # Fallback: use current bar low
            sl = bar.low - (self.sl_buffer_atr_mult * atr)
        
        # TP based on RR ratio
        risk = entry - sl
        tp = entry + (self.risk_reward_ratio * risk)
        
        reason_text = "\n".join(reasons)
        
        return Signal(
            symbol=bar.symbol,
            signal_type=SignalType.BUY,
            timestamp=bar.timestamp,
            entry=entry,
            stop_loss=sl,
            take_profit=tp,
            quantity=self.default_quantity,
            status=SignalStatus.ACTIVE,
            reason=reason_text
        )
    
    def load_bars(self, bars: List[Bar]):
        """Load historical bars and detect pivots."""
        self.bars = []
        self.pivot_detector.clear()
        
        for bar in bars:
            self.bars.append(bar)
            bar_index = len(self.bars) - 1
            self.pivot_detector.process_bar(self.bars, bar_index)
        
        # Set previous MACD
        if len(self.bars) >= 2:
            closes = [b.close for b in self.bars[:-1]]
            self.previous_macd = calculate_macd(
                closes, self.macd_fast, self.macd_slow, self.macd_signal
            )
    
    def reset(self):
        """Reset engine state."""
        self.bars.clear()
        self.pivot_detector.clear()
        self.previous_macd = None
