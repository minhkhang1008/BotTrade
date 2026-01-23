"""
Bot Trade - Candlestick Pattern Recognition
Identifies reversal patterns for pivot detection
"""
from typing import Optional, List
from .models import Bar, CandlePattern


def is_hammer(bar: Bar, body_ratio: float = 0.3, shadow_ratio: float = 2.0) -> bool:
    """
    Check if bar is a Hammer pattern (bullish reversal).
    
    Hammer characteristics:
    - Small body at the top of the range
    - Long lower shadow (at least 2x body)
    - Little or no upper shadow
    
    Args:
        bar: The bar to analyze
        body_ratio: Maximum body size as ratio of total range (default 0.3)
        shadow_ratio: Minimum lower shadow to body ratio (default 2.0)
    
    Returns:
        True if pattern matches
    """
    if bar.total_range == 0:
        return False
    
    body = bar.body_size
    lower_shadow = bar.lower_shadow
    upper_shadow = bar.upper_shadow
    
    # Body should be small relative to total range
    if body / bar.total_range > body_ratio:
        return False
    
    # Lower shadow should be long (at least 2x body)
    if body > 0 and lower_shadow / body < shadow_ratio:
        return False
    
    # Upper shadow should be small
    if body > 0 and upper_shadow > body:
        return False
    
    # For zero-body case, lower shadow should be significant
    if body == 0 and lower_shadow < bar.total_range * 0.6:
        return False
    
    return True


def is_bullish_engulfing(current: Bar, previous: Bar) -> bool:
    """
    Check if current and previous bars form Bullish Engulfing pattern.
    
    Bullish Engulfing characteristics:
    - Previous bar is bearish (red)
    - Current bar is bullish (green)
    - Current body engulfs previous body
    
    Returns:
        True if pattern matches
    """
    if not previous.is_bearish:
        return False
    
    if not current.is_bullish:
        return False
    
    # Current open below previous close, current close above previous open
    current_body_low = min(current.open, current.close)
    current_body_high = max(current.open, current.close)
    prev_body_low = min(previous.open, previous.close)
    prev_body_high = max(previous.open, previous.close)
    
    return current_body_low < prev_body_low and current_body_high > prev_body_high


def is_shooting_star(bar: Bar, body_ratio: float = 0.3, shadow_ratio: float = 2.0) -> bool:
    """
    Check if bar is a Shooting Star pattern (bearish reversal).
    
    Shooting Star characteristics:
    - Small body at the bottom of the range
    - Long upper shadow (at least 2x body)
    - Little or no lower shadow
    
    Returns:
        True if pattern matches
    """
    if bar.total_range == 0:
        return False
    
    body = bar.body_size
    lower_shadow = bar.lower_shadow
    upper_shadow = bar.upper_shadow
    
    # Body should be small relative to total range
    if body / bar.total_range > body_ratio:
        return False
    
    # Upper shadow should be long (at least 2x body)
    if body > 0 and upper_shadow / body < shadow_ratio:
        return False
    
    # Lower shadow should be small
    if body > 0 and lower_shadow > body:
        return False
    
    # For zero-body case, upper shadow should be significant
    if body == 0 and upper_shadow < bar.total_range * 0.6:
        return False
    
    return True


def is_bearish_engulfing(current: Bar, previous: Bar) -> bool:
    """
    Check if current and previous bars form Bearish Engulfing pattern.
    
    Bearish Engulfing characteristics:
    - Previous bar is bullish (green)
    - Current bar is bearish (red)
    - Current body engulfs previous body
    
    Returns:
        True if pattern matches
    """
    if not previous.is_bullish:
        return False
    
    if not current.is_bearish:
        return False
    
    current_body_low = min(current.open, current.close)
    current_body_high = max(current.open, current.close)
    prev_body_low = min(previous.open, previous.close)
    prev_body_high = max(previous.open, previous.close)
    
    return current_body_low < prev_body_low and current_body_high > prev_body_high


def detect_bullish_reversal(bars: List[Bar]) -> Optional[CandlePattern]:
    """
    Detect bullish reversal pattern at the end of bars list.
    
    Checks for:
    - Hammer (single bar)
    - Bullish Engulfing (two bars)
    
    Returns:
        CandlePattern if found, None otherwise
    """
    if len(bars) < 1:
        return None
    
    current = bars[-1]
    
    # Check Hammer first (single bar pattern)
    if is_hammer(current):
        return CandlePattern.HAMMER
    
    # Check Bullish Engulfing (needs 2 bars)
    if len(bars) >= 2:
        previous = bars[-2]
        if is_bullish_engulfing(current, previous):
            return CandlePattern.BULLISH_ENGULFING
    
    return None


def detect_bearish_reversal(bars: List[Bar]) -> Optional[CandlePattern]:
    """
    Detect bearish reversal pattern at the end of bars list.
    
    Checks for:
    - Shooting Star (single bar)
    - Bearish Engulfing (two bars)
    
    Returns:
        CandlePattern if found, None otherwise
    """
    if len(bars) < 1:
        return None
    
    current = bars[-1]
    
    # Check Shooting Star first (single bar pattern)
    if is_shooting_star(current):
        return CandlePattern.SHOOTING_STAR
    
    # Check Bearish Engulfing (needs 2 bars)
    if len(bars) >= 2:
        previous = bars[-2]
        if is_bearish_engulfing(current, previous):
            return CandlePattern.BEARISH_ENGULFING
    
    return None
