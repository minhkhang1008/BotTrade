"""
Bot Trade - Pivot Point Detection
Identifies pivot highs and lows based on reversal patterns
"""
from typing import List, Optional
from datetime import datetime

from .models import Bar, Pivot, PivotType, CandlePattern
from .patterns import detect_bullish_reversal, detect_bearish_reversal


class PivotDetector:
    """
    Detects pivot points based on candlestick reversal patterns.
    
    - Pivot Low: Identified by bullish reversal patterns (Hammer, Bullish Engulfing)
    - Pivot High: Identified by bearish reversal patterns (Shooting Star, Bearish Engulfing)
    """
    
    def __init__(self):
        self.pivot_lows: List[Pivot] = []
        self.pivot_highs: List[Pivot] = []
    
    def process_bar(self, bars: List[Bar], bar_index: int) -> Optional[Pivot]:
        """
        Process new bar and detect any pivot points.
        
        Args:
            bars: List of all bars up to current
            bar_index: Index of the current bar
        
        Returns:
            New Pivot if detected, None otherwise
        """
        if len(bars) < 2:
            return None
        
        current_bar = bars[-1]
        
        # Check for bullish reversal -> Pivot Low
        bullish_pattern = detect_bullish_reversal(bars)
        if bullish_pattern:
            pivot = Pivot(
                type=PivotType.LOW,
                price=current_bar.low,
                timestamp=current_bar.timestamp,
                bar_index=bar_index,
                pattern=bullish_pattern
            )
            self.pivot_lows.append(pivot)
            return pivot
        
        # Check for bearish reversal -> Pivot High
        bearish_pattern = detect_bearish_reversal(bars)
        if bearish_pattern:
            pivot = Pivot(
                type=PivotType.HIGH,
                price=current_bar.high,
                timestamp=current_bar.timestamp,
                bar_index=bar_index,
                pattern=bearish_pattern
            )
            self.pivot_highs.append(pivot)
            return pivot
        
        return None
    
    def get_recent_lows(self, count: int = 4) -> List[Pivot]:
        """Get the most recent pivot lows."""
        return self.pivot_lows[-count:] if len(self.pivot_lows) >= count else self.pivot_lows.copy()
    
    def get_recent_highs(self, count: int = 4) -> List[Pivot]:
        """Get the most recent pivot highs."""
        return self.pivot_highs[-count:] if len(self.pivot_highs) >= count else self.pivot_highs.copy()
    
    def get_last_pivot_low(self) -> Optional[Pivot]:
        """Get the most recent pivot low."""
        return self.pivot_lows[-1] if self.pivot_lows else None
    
    def get_previous_pivot_low(self) -> Optional[Pivot]:
        """Get the second most recent pivot low (for SL calculation)."""
        return self.pivot_lows[-2] if len(self.pivot_lows) >= 2 else None
    
    def get_last_pivot_high(self) -> Optional[Pivot]:
        """Get the most recent pivot high."""
        return self.pivot_highs[-1] if self.pivot_highs else None
    
    def clear(self):
        """Clear all detected pivots."""
        self.pivot_lows.clear()
        self.pivot_highs.clear()
    
    def load_pivots(self, lows: List[Pivot], highs: List[Pivot]):
        """Load existing pivots (e.g., from storage)."""
        self.pivot_lows = lows.copy()
        self.pivot_highs = highs.copy()


def detect_pivots_from_bars(bars: List[Bar]) -> tuple[List[Pivot], List[Pivot]]:
    """
    Scan all bars and detect all pivot points.
    
    Returns:
        Tuple of (pivot_lows, pivot_highs)
    """
    detector = PivotDetector()
    
    for i in range(1, len(bars)):
        bars_window = bars[:i + 1]
        detector.process_bar(bars_window, i)
    
    return detector.pivot_lows.copy(), detector.pivot_highs.copy()
