"""
Bot Trade - Trend Analyzer
Determines uptrend using zig-zag rule (3 higher highs + 3 higher lows)
"""
from typing import List, Optional
from dataclasses import dataclass

from .models import Pivot, PivotType


@dataclass
class TrendAnalysisResult:
    """Result of trend analysis."""
    is_uptrend: bool
    higher_lows_count: int  # Number of consecutive higher lows pairs
    higher_highs_count: int  # Number of consecutive higher highs pairs
    reason: str
    
    def to_dict(self) -> dict:
        return {
            "is_uptrend": self.is_uptrend,
            "higher_lows_count": self.higher_lows_count,
            "higher_highs_count": self.higher_highs_count,
            "reason": self.reason
        }


class TrendAnalyzer:
    """
    Analyzes price trend using zig-zag method.
    
    Uptrend criteria:
    - 4 consecutive pivot lows (Low1 < Low2 < Low3 < Low4) = 3 pairs of higher lows
    - 4 consecutive pivot highs (High1 < High2 < High3 < High4) = 3 pairs of higher highs
    """
    
    REQUIRED_PAIRS = 3  # 3 cặp đỉnh/đáy cao dần = cần 4 pivots
    
    def __init__(self):
        pass
    
    def analyze(
        self,
        pivot_lows: List[Pivot],
        pivot_highs: List[Pivot]
    ) -> TrendAnalysisResult:
        """
        Analyze trend based on pivot points.
        
        Args:
            pivot_lows: List of pivot low points
            pivot_highs: List of pivot high points
        
        Returns:
            TrendAnalysisResult with trend status and details
        """
        # Count consecutive higher lows
        higher_lows = self._count_higher_pairs(pivot_lows)
        
        # Count consecutive higher highs
        higher_highs = self._count_higher_pairs(pivot_highs)
        
        # Check if uptrend criteria met
        is_uptrend = (
            higher_lows >= self.REQUIRED_PAIRS and
            higher_highs >= self.REQUIRED_PAIRS
        )
        
        # Build reason
        if is_uptrend:
            reason = f"Uptrend confirmed: {higher_lows} higher lows + {higher_highs} higher highs"
        else:
            missing = []
            if higher_lows < self.REQUIRED_PAIRS:
                missing.append(f"higher lows ({higher_lows}/{self.REQUIRED_PAIRS})")
            if higher_highs < self.REQUIRED_PAIRS:
                missing.append(f"higher highs ({higher_highs}/{self.REQUIRED_PAIRS})")
            reason = f"No uptrend: insufficient {', '.join(missing)}"
        
        return TrendAnalysisResult(
            is_uptrend=is_uptrend,
            higher_lows_count=higher_lows,
            higher_highs_count=higher_highs,
            reason=reason
        )
    
    def _count_higher_pairs(self, pivots: List[Pivot]) -> int:
        """
        Count consecutive higher pivot pairs from the end.
        
        Example: if pivots are [10, 12, 11, 13, 15]
        We check from end: 15 > 13 (1), 13 > 11 (2), 11 < 12 (stop)
        Returns 2
        """
        if len(pivots) < 2:
            return 0
        
        count = 0
        # Start from the most recent and go backwards
        for i in range(len(pivots) - 1, 0, -1):
            if pivots[i].price > pivots[i - 1].price:
                count += 1
            else:
                break
        
        return count
    
    def is_uptrend(
        self,
        pivot_lows: List[Pivot],
        pivot_highs: List[Pivot]
    ) -> bool:
        """Simple check if market is in uptrend."""
        result = self.analyze(pivot_lows, pivot_highs)
        return result.is_uptrend
    
    def get_trend_strength(
        self,
        pivot_lows: List[Pivot],
        pivot_highs: List[Pivot]
    ) -> float:
        """
        Get trend strength score (0.0 to 1.0).
        
        1.0 = Strong uptrend (3+ pairs of both)
        0.5 = Partial uptrend
        0.0 = No uptrend
        """
        result = self.analyze(pivot_lows, pivot_highs)
        
        if result.is_uptrend:
            # Extra strength for additional pairs
            extra_lows = max(0, result.higher_lows_count - self.REQUIRED_PAIRS)
            extra_highs = max(0, result.higher_highs_count - self.REQUIRED_PAIRS)
            bonus = min(0.2, (extra_lows + extra_highs) * 0.05)
            return min(1.0, 0.8 + bonus)
        else:
            # Partial score
            low_score = min(result.higher_lows_count / self.REQUIRED_PAIRS, 1.0)
            high_score = min(result.higher_highs_count / self.REQUIRED_PAIRS, 1.0)
            return (low_score + high_score) / 2 * 0.5


def check_uptrend(pivot_lows: List[Pivot], pivot_highs: List[Pivot]) -> bool:
    """
    Quick function to check if market is in uptrend.
    
    Requires:
    - 4 consecutive higher lows (3 pairs)
    - 4 consecutive higher highs (3 pairs)
    """
    analyzer = TrendAnalyzer()
    return analyzer.is_uptrend(pivot_lows, pivot_highs)
