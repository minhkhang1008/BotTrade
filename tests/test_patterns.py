"""
Bot Trade - Tests for Candlestick Patterns
"""
import pytest
from datetime import datetime
from src.core.models import Bar, CandlePattern
from src.core.patterns import (
    is_hammer, is_bullish_engulfing,
    is_shooting_star, is_bearish_engulfing,
    detect_bullish_reversal, detect_bearish_reversal
)


def make_bar(open_: float, high: float, low: float, close: float) -> Bar:
    """Helper to create test bars."""
    return Bar(
        symbol="TEST",
        timeframe="1H",
        timestamp=datetime.now(),
        open=open_,
        high=high,
        low=low,
        close=close,
        volume=1000
    )


class TestHammer:
    def test_valid_hammer(self):
        """Test valid hammer pattern."""
        # Small body at top, long lower shadow
        bar = make_bar(open_=100, high=101, low=95, close=100.5)
        assert is_hammer(bar) is True
    
    def test_invalid_hammer_no_lower_shadow(self):
        """Hammer needs long lower shadow."""
        bar = make_bar(open_=100, high=102, low=99.5, close=100.5)
        assert is_hammer(bar) is False
    
    def test_invalid_hammer_large_body(self):
        """Hammer needs small body."""
        bar = make_bar(open_=100, high=105, low=95, close=104)
        assert is_hammer(bar) is False


class TestBullishEngulfing:
    def test_valid_bullish_engulfing(self):
        """Test valid bullish engulfing."""
        prev = make_bar(open_=102, high=103, low=100, close=100.5)  # Bearish
        curr = make_bar(open_=99, high=104, low=98, close=103)     # Bullish engulfs
        
        assert is_bullish_engulfing(curr, prev) is True
    
    def test_invalid_prev_not_bearish(self):
        """Previous bar must be bearish."""
        prev = make_bar(open_=100, high=103, low=99, close=102)    # Bullish
        curr = make_bar(open_=99, high=104, low=98, close=103)
        
        assert is_bullish_engulfing(curr, prev) is False
    
    def test_invalid_curr_not_engulfing(self):
        """Current bar must engulf previous."""
        prev = make_bar(open_=102, high=103, low=100, close=100.5)
        curr = make_bar(open_=100.2, high=103, low=100, close=101)  # Doesn't engulf
        
        assert is_bullish_engulfing(curr, prev) is False


class TestShootingStar:
    def test_valid_shooting_star(self):
        """Test valid shooting star pattern."""
        # Small body at bottom, long upper shadow, minimal lower shadow
        # open=100, high=110, low=99.9, close=100.1
        # body = 0.1, upper_shadow = 9.9, lower_shadow = 0.1
        bar = make_bar(open_=100, high=110, low=99.9, close=100.1)
        assert is_shooting_star(bar) is True
    
    def test_invalid_shooting_star_no_upper_shadow(self):
        """Shooting star needs long upper shadow."""
        bar = make_bar(open_=100, high=100.5, low=95, close=99.8)
        assert is_shooting_star(bar) is False


class TestBearishEngulfing:
    def test_valid_bearish_engulfing(self):
        """Test valid bearish engulfing."""
        prev = make_bar(open_=100, high=103, low=99, close=102)    # Bullish
        curr = make_bar(open_=103, high=104, low=98, close=99)     # Bearish engulfs
        
        assert is_bearish_engulfing(curr, prev) is True


class TestPatternDetection:
    def test_detect_bullish_reversal_hammer(self):
        """Detect hammer as bullish reversal."""
        bars = [
            make_bar(100, 102, 98, 99),   # Some previous bar
            make_bar(99, 100, 93, 99.5)   # Hammer
        ]
        
        pattern = detect_bullish_reversal(bars)
        assert pattern == CandlePattern.HAMMER
    
    def test_detect_bullish_reversal_engulfing(self):
        """Detect engulfing as bullish reversal."""
        bars = [
            make_bar(102, 103, 100, 100.5),  # Bearish
            make_bar(99, 104, 98, 103)       # Bullish engulfing
        ]
        
        pattern = detect_bullish_reversal(bars)
        assert pattern == CandlePattern.BULLISH_ENGULFING
    
    def test_detect_no_pattern(self):
        """No pattern detected."""
        bars = [
            make_bar(100, 102, 99, 101),
            make_bar(101, 103, 100, 102)
        ]
        
        pattern = detect_bullish_reversal(bars)
        assert pattern is None
