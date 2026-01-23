"""
Bot Trade - Data Models
"""
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Optional, List
import json


class SignalType(str, Enum):
    """Signal type enumeration."""
    BUY = "BUY"
    SELL = "SELL"


class SignalStatus(str, Enum):
    """Signal status enumeration."""
    ACTIVE = "ACTIVE"
    TP_HIT = "TP_HIT"
    SL_HIT = "SL_HIT"
    CANCELLED = "CANCELLED"
    BREAKEVEN = "BREAKEVEN"


class PivotType(str, Enum):
    """Pivot point type."""
    HIGH = "HIGH"
    LOW = "LOW"


class CandlePattern(str, Enum):
    """Candlestick pattern types."""
    HAMMER = "HAMMER"
    BULLISH_ENGULFING = "BULLISH_ENGULFING"
    SHOOTING_STAR = "SHOOTING_STAR"
    BEARISH_ENGULFING = "BEARISH_ENGULFING"


@dataclass
class Bar:
    """OHLCV Bar data model."""
    symbol: str
    timeframe: str
    timestamp: datetime
    open: float
    high: float
    low: float
    close: float
    volume: float = 0.0
    
    @property
    def is_bullish(self) -> bool:
        """Check if bar is bullish (green)."""
        return self.close > self.open
    
    @property
    def is_bearish(self) -> bool:
        """Check if bar is bearish (red)."""
        return self.close < self.open
    
    @property
    def body_size(self) -> float:
        """Get the absolute body size."""
        return abs(self.close - self.open)
    
    @property
    def upper_shadow(self) -> float:
        """Get upper shadow length."""
        return self.high - max(self.open, self.close)
    
    @property
    def lower_shadow(self) -> float:
        """Get lower shadow length."""
        return min(self.open, self.close) - self.low
    
    @property
    def total_range(self) -> float:
        """Get total bar range (high - low)."""
        return self.high - self.low
    
    def to_dict(self) -> dict:
        """Convert to dictionary."""
        return {
            "symbol": self.symbol,
            "timeframe": self.timeframe,
            "timestamp": self.timestamp.isoformat(),
            "open": self.open,
            "high": self.high,
            "low": self.low,
            "close": self.close,
            "volume": self.volume
        }
    
    @classmethod
    def from_dict(cls, data: dict) -> "Bar":
        """Create Bar from dictionary."""
        return cls(
            symbol=data["symbol"],
            timeframe=data["timeframe"],
            timestamp=datetime.fromisoformat(data["timestamp"]),
            open=float(data["open"]),
            high=float(data["high"]),
            low=float(data["low"]),
            close=float(data["close"]),
            volume=float(data.get("volume", 0))
        )


@dataclass
class Pivot:
    """Pivot point data model."""
    type: PivotType
    price: float
    timestamp: datetime
    bar_index: int
    pattern: CandlePattern
    
    def to_dict(self) -> dict:
        """Convert to dictionary."""
        return {
            "type": self.type.value,
            "price": self.price,
            "timestamp": self.timestamp.isoformat(),
            "bar_index": self.bar_index,
            "pattern": self.pattern.value
        }


@dataclass
class SupportZone:
    """Support zone around a pivot low."""
    pivot: Pivot
    zone_low: float
    zone_high: float
    
    def contains_price(self, low: float, high: float) -> bool:
        """Check if price range touches this zone."""
        return low <= self.zone_high and high >= self.zone_low
    
    def to_dict(self) -> dict:
        """Convert to dictionary."""
        return {
            "pivot": self.pivot.to_dict(),
            "zone_low": self.zone_low,
            "zone_high": self.zone_high
        }


@dataclass
class Signal:
    """Trading signal data model."""
    id: Optional[int] = None
    symbol: str = ""
    signal_type: SignalType = SignalType.BUY
    timestamp: datetime = field(default_factory=datetime.now)
    entry: float = 0.0
    stop_loss: float = 0.0
    take_profit: float = 0.0
    quantity: int = 1
    status: SignalStatus = SignalStatus.ACTIVE
    reason: str = ""
    original_sl: float = 0.0  # For tracking breakeven move
    
    def __post_init__(self):
        if self.original_sl == 0.0:
            self.original_sl = self.stop_loss
    
    @property
    def risk(self) -> float:
        """Calculate risk per unit."""
        return abs(self.entry - self.stop_loss)
    
    @property
    def reward(self) -> float:
        """Calculate potential reward per unit."""
        return abs(self.take_profit - self.entry)
    
    @property
    def risk_reward_ratio(self) -> float:
        """Calculate R:R ratio."""
        if self.risk == 0:
            return 0
        return self.reward / self.risk
    
    @property
    def breakeven_price(self) -> float:
        """Price at which to move SL to breakeven (1R profit)."""
        return self.entry + self.risk
    
    def should_move_to_breakeven(self, current_price: float) -> bool:
        """Check if SL should be moved to breakeven."""
        if self.status != SignalStatus.ACTIVE:
            return False
        if self.stop_loss >= self.entry:  # Already at breakeven
            return False
        return current_price >= self.breakeven_price
    
    def move_to_breakeven(self):
        """Move stop loss to entry (breakeven)."""
        self.stop_loss = self.entry
        self.status = SignalStatus.BREAKEVEN
    
    def to_dict(self) -> dict:
        """Convert to dictionary."""
        return {
            "id": self.id,
            "symbol": self.symbol,
            "signal_type": self.signal_type.value,
            "timestamp": self.timestamp.isoformat(),
            "entry": self.entry,
            "stop_loss": self.stop_loss,
            "take_profit": self.take_profit,
            "quantity": self.quantity,
            "status": self.status.value,
            "reason": self.reason,
            "risk": self.risk,
            "reward": self.reward,
            "risk_reward_ratio": self.risk_reward_ratio
        }
    
    @classmethod
    def from_dict(cls, data: dict) -> "Signal":
        """Create Signal from dictionary."""
        return cls(
            id=data.get("id"),
            symbol=data["symbol"],
            signal_type=SignalType(data["signal_type"]),
            timestamp=datetime.fromisoformat(data["timestamp"]),
            entry=float(data["entry"]),
            stop_loss=float(data["stop_loss"]),
            take_profit=float(data["take_profit"]),
            quantity=int(data.get("quantity", 1)),
            status=SignalStatus(data.get("status", "ACTIVE")),
            reason=data.get("reason", ""),
            original_sl=float(data.get("original_sl", data["stop_loss"]))
        )


@dataclass
class IndicatorValues:
    """Container for indicator values at a specific bar."""
    rsi: Optional[float] = None
    macd_line: Optional[float] = None
    macd_signal: Optional[float] = None
    macd_histogram: Optional[float] = None
    atr: Optional[float] = None
    
    @property
    def macd_crossed_up(self) -> bool:
        """Check if MACD line crossed above signal line."""
        # This needs previous values to determine, 
        # so it will be calculated in the indicator module
        return False
    
    @property
    def rsi_above_50(self) -> bool:
        """Check if RSI is above 50."""
        return self.rsi is not None and self.rsi > 50
    
    def to_dict(self) -> dict:
        """Convert to dictionary."""
        return {
            "rsi": self.rsi,
            "macd_line": self.macd_line,
            "macd_signal": self.macd_signal,
            "macd_histogram": self.macd_histogram,
            "atr": self.atr
        }
