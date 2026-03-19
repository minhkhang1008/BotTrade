"""
Bot Trade - Signal Generation Engine (AI & Scoring Integrated)
Main logic for generating BUY signals based on Technical + AI Sentiment
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
    total_score: float = 0.0
    tech_score: float = 0.0
    ai_sentiment: int = 0
    
    def __post_init__(self):
        if self.reasons is None:
            self.reasons = []
        if self.failed_conditions is None:
            self.failed_conditions = []


class SignalEngine:
    """
    Main signal generation engine with AI Scoring System.
    
    Generates BUY signals when Total Score >= TRIGGER_THRESHOLD
    Total Score = Technical Score + AI Sentiment Score
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
        atr_period: int = 14,
        trigger_threshold: int = 5  # Ngưỡng điểm kích hoạt lệnh Mua
    ):
        self.zone_width_atr_mult = zone_width_atr_mult
        self.sl_buffer_atr_mult = sl_buffer_atr_mult
        self.risk_reward_ratio = risk_reward_ratio
        self.default_quantity = default_quantity
        self.trigger_threshold = trigger_threshold
        
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
    
    def add_bar(self, bar: Bar, ai_sentiment: int = 0) -> Optional[SignalCheckResult]:
        """
        Add new bar, apply AI sentiment, and check for signals.
        
        Args:
            bar: New closed bar
            ai_sentiment: Sentiment score from AI (-3 to +3)
        """
        self.bars.append(bar)
        bar_index = len(self.bars) - 1
        
        # Detect pivot on this bar
        self.pivot_detector.process_bar(self.bars, bar_index)
        
        # Check for signal (Truyền điểm AI vào hàm check)
        result = self.check_signal(ai_sentiment=ai_sentiment)
        
        # Update previous MACD for next crossover check
        closes = [b.close for b in self.bars]
        current_macd = calculate_macd(
            closes, self.macd_fast, self.macd_slow, self.macd_signal
        )
        self.previous_macd = current_macd
        
        return result
    
    def check_signal(self, ai_sentiment: int = 0) -> SignalCheckResult:
        """
        Check conditions using the FreqAI Scoring concept.
        """
        reasons = []
        failed = []
        tech_score = 0
        
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
        
        # --- TECHNICAL SCORING (Max 7 points) ---
        
        # 1. Trend Analysis (+2 Points)
        trend_result = self.trend_analyzer.analyze(
            self.pivot_detector.pivot_lows,
            self.pivot_detector.pivot_highs
        )
        if trend_result.is_uptrend:
            tech_score += 2
            reasons.append(f"✓ Xu hướng tăng rõ ràng (+2 điểm)")
        else:
            failed.append(f"Chưa có xu hướng tăng: {trend_result.reason}")
            
        # 2. Support Zone (+2 Points)
        support_zone = self._get_support_zone(indicators.atr)
        if support_zone and support_zone.contains_price(current_bar.low, current_bar.high):
            tech_score += 2
            reasons.append(f"✓ Giá chạm vùng hỗ trợ an toàn (+2 điểm)")
        else:
            failed.append("Giá không nằm trong vùng hỗ trợ")

        # 3. Reversal Pattern (+1 Point)
        pattern = detect_bullish_reversal(self.bars)
        if pattern:
            tech_score += 1
            reasons.append(f"✓ Nến đảo chiều {pattern.value} (+1 điểm)")
        else:
            failed.append("Không có mẫu hình nến đảo chiều")
            
        # 4. Momentum / Confirmation (+2 Points for MACD, +1 for RSI)
        closes = [b.close for b in self.bars]
        current_macd = calculate_macd(closes, self.macd_fast, self.macd_slow, self.macd_signal)
        
        if check_macd_crossover(current_macd, self.previous_macd):
            tech_score += 2
            reasons.append(f"✓ Động lượng mạnh: MACD cắt lên (+2 điểm)")
        elif indicators.rsi is not None and indicators.rsi > 50:
            tech_score += 1
            reasons.append(f"✓ RSI > 50 xác nhận đà tăng (+1 điểm)")
        else:
            failed.append("Chưa có xác nhận từ MACD/RSI")

        # --- TỔNG HỢP ĐIỂM SỐ (Total Score) ---
        total_score = tech_score + ai_sentiment
        
        # Log AI Effect
        if ai_sentiment != 0:
            ai_emoji = "🔥" if ai_sentiment > 0 else "🧊"
            reasons.append(f"{ai_emoji} AI Sentiment: Vĩ mô tác động ({'+' if ai_sentiment > 0 else ''}{ai_sentiment} điểm)")
            logger.info(f"🧠 [AI SCORING] {current_bar.symbol}: Kỹ thuật ({tech_score}) + AI ({ai_sentiment}) = Tổng {total_score}")

        # --- RA QUYẾT ĐỊNH ---
        is_triggered = total_score >= self.trigger_threshold
        
        if not is_triggered:
            return SignalCheckResult(
                should_signal=False,
                reasons=reasons,
                failed_conditions=failed,
                total_score=total_score,
                tech_score=tech_score,
                ai_sentiment=ai_sentiment
            )
        
        # Nếu đủ điểm -> Phát tín hiệu Mua
        logger.info(f"🚀 [SIGNAL TRIGGERED] {current_bar.symbol} đạt {total_score}/{self.trigger_threshold} điểm!")
        reasons.insert(0, f"🎯 TỔNG ĐIỂM ĐÁNH GIÁ: {total_score}/{self.trigger_threshold}")
        
        signal = self._create_signal(
            current_bar,
            indicators.atr,
            pattern,
            reasons
        )
        
        return SignalCheckResult(
            should_signal=True,
            signal=signal,
            reasons=reasons,
            total_score=total_score,
            tech_score=tech_score,
            ai_sentiment=ai_sentiment
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
        """Create BUY signal with SL/TP based on ATR."""
        entry = bar.close
        
        # SL below previous pivot low
        prev_pivot = self.pivot_detector.get_previous_pivot_low()
        if prev_pivot:
            sl = prev_pivot.price - (self.sl_buffer_atr_mult * atr)
        else:
            sl = bar.low - (self.sl_buffer_atr_mult * atr)
        
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
    
    def generate_demo_signal(self, symbol: str, bar: Optional[Bar] = None) -> Signal:
        """Generate a demo BUY signal."""
        import random
        
        if bar:
            entry = bar.close
            base_price = bar.close
        else:
            base_price = 50000 + random.uniform(-5000, 10000)
            entry = base_price
        
        atr = base_price * 0.02
        sl = entry - (atr * 1.5)
        risk = entry - sl
        tp = entry + (self.risk_reward_ratio * risk)
        
        demo_reasons = [
            "🎯 TỔNG ĐIỂM ĐÁNH GIÁ: 6/5",
            "✓ Kỹ thuật: Xu hướng tăng + Hỗ trợ (+4 điểm)",
            "🔥 AI Sentiment: Tích cực từ CafeF (+2 điểm)",
            "📊 DEMO MODE - Signal for presentation"
        ]
        
        return Signal(
            symbol=symbol,
            signal_type=SignalType.BUY,
            timestamp=datetime.now(),
            entry=entry,
            stop_loss=sl,
            take_profit=tp,
            quantity=self.default_quantity,
            status=SignalStatus.ACTIVE,
            reason="\n".join(demo_reasons)
        )