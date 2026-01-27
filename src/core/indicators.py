"""
Bot Trade - Technical Indicators
RSI, MACD, ATR implementations
"""
from typing import List, Optional, Tuple
from dataclasses import dataclass
import math

# Lightweight numpy-free implementations for indicators to avoid heavy native deps

def _mean(values: List[float]) -> float:
    return sum(values) / len(values) if values else 0.0

def _diff(values: List[float]) -> List[float]:
    return [values[i+1] - values[i] for i in range(len(values)-1)]

def _where_positive(values: List[float]) -> List[float]:
    return [v if v > 0 else 0.0 for v in values]

def _where_negative_abs(values: List[float]) -> List[float]:
    return [(-v) if v < 0 else 0.0 for v in values]

from .models import Bar, IndicatorValues


def calculate_rsi(closes: List[float], period: int = 14) -> Optional[float]:
    """
    Calculate RSI (Relative Strength Index) using Wilder's smoothing method.
    
    This is the standard RSI calculation used by TradingView and most platforms.
    
    Args:
        closes: List of closing prices
        period: RSI period (default 14)
    
    Returns:
        RSI value (0-100) or None if not enough data
    """
    if len(closes) < period + 1:
        return None
    
    # Calculate price changes
    deltas = _diff(closes)
    
    # Separate gains and losses
    gains = _where_positive(deltas)
    losses = _where_negative_abs(deltas)
    
    # Initial average using SMA for first period
    avg_gain = _mean(gains[:period])
    avg_loss = _mean(losses[:period])
    
    # Apply Wilder's smoothing for remaining values
    # Formula: avg = (prev_avg * (period-1) + current) / period
    for i in range(period, len(gains)):
        avg_gain = (avg_gain * (period - 1) + gains[i]) / period
        avg_loss = (avg_loss * (period - 1) + losses[i]) / period
    
    if avg_loss == 0:
        return 100.0
    
    rs = avg_gain / avg_loss
    rsi = 100 - (100 / (1 + rs))
    
    return round(float(rsi), 2)


def calculate_rsi_series(closes: List[float], period: int = 14) -> List[Optional[float]]:
    """
    Calculate RSI series for all bars.
    
    Returns:
        List of RSI values (None for first 'period' bars)
    """
    result = [None] * len(closes)
    
    if len(closes) < period + 1:
        return result
    
    deltas = _diff(closes)
    gains = _where_positive(deltas)
    losses = _where_negative_abs(deltas)
    
    # Initial SMA
    avg_gain = _mean(gains[:period])
    avg_loss = _mean(losses[:period])
    
    for i in range(period, len(closes)):
        if avg_loss == 0:
            result[i] = 100.0
        else:
            rs = avg_gain / avg_loss
            result[i] = 100 - (100 / (1 + rs))
        
        if i < len(closes) - 1:
            # EMA smoothing
            avg_gain = (avg_gain * (period - 1) + gains[i]) / period
            avg_loss = (avg_loss * (period - 1) + losses[i]) / period
    
    return result


@dataclass
class MACDResult:
    """MACD calculation result."""
    macd_line: float
    signal_line: float
    histogram: float


def calculate_ema(values: List[float], period: int) -> List[float]:
    """Calculate Exponential Moving Average."""
    if len(values) < period:
        return []

    multiplier = 2 / (period + 1)
    ema = [_mean(values[:period])]  # Start with SMA

    for i in range(period, len(values)):
        ema.append(values[i] * multiplier + ema[-1] * (1 - multiplier))

    return ema


def calculate_macd(
    closes: List[float],
    fast_period: int = 12,
    slow_period: int = 26,
    signal_period: int = 9
) -> Optional[MACDResult]:
    """
    Calculate MACD (Moving Average Convergence Divergence).
    
    Args:
        closes: List of closing prices
        fast_period: Fast EMA period (default 12)
        slow_period: Slow EMA period (default 26)
        signal_period: Signal line period (default 9)
    
    Returns:
        MACDResult or None if not enough data
    """
    min_periods = slow_period + signal_period
    if len(closes) < min_periods:
        return None
    
    # Calculate EMAs
    fast_ema = calculate_ema(closes, fast_period)
    slow_ema = calculate_ema(closes, slow_period)
    
    if not fast_ema or not slow_ema:
        return None
    
    # Align EMAs (slow starts later)
    offset = slow_period - fast_period
    macd_line_values = [
        fast_ema[i + offset] - slow_ema[i]
        for i in range(len(slow_ema))
    ]
    
    if len(macd_line_values) < signal_period:
        return None
    
    # Calculate signal line (EMA of MACD line)
    signal_ema = calculate_ema(macd_line_values, signal_period)
    
    if not signal_ema:
        return None
    
    # Get raw values
    macd_line = macd_line_values[-1]
    signal_line = signal_ema[-1]
    histogram = macd_line - signal_line
    
    # Normalize to thousands (like TradingView displays)
    # This makes values comparable: -0.23 instead of -230
    macd_line = macd_line / 1000
    signal_line = signal_line / 1000
    histogram = histogram / 1000
    
    return MACDResult(
        macd_line=macd_line,
        signal_line=signal_line,
        histogram=histogram
    )


def calculate_macd_series(
    closes: List[float],
    fast_period: int = 12,
    slow_period: int = 26,
    signal_period: int = 9
) -> List[Optional[MACDResult]]:
    """Calculate MACD series for all bars."""
    result = [None] * len(closes)
    min_periods = slow_period + signal_period
    
    if len(closes) < min_periods:
        return result
    
    # Calculate full EMAs
    fast_ema = calculate_ema(closes, fast_period)
    slow_ema = calculate_ema(closes, slow_period)
    
    # Calculate MACD line
    offset = slow_period - fast_period
    macd_line_values = []
    for i in range(len(slow_ema)):
        macd_line_values.append(fast_ema[i + offset] - slow_ema[i])
    
    # Calculate signal line
    signal_ema = calculate_ema(macd_line_values, signal_period)
    
    # Fill results
    start_idx = slow_period + signal_period - 1
    for i, sig_idx in enumerate(range(signal_period - 1, len(signal_ema))):
        bar_idx = start_idx + i
        if bar_idx < len(result):
            macd_line = macd_line_values[sig_idx + signal_period - 1]
            signal_line = signal_ema[sig_idx]
            histogram = macd_line - signal_line
            
            # Normalize to thousands (like TradingView displays)
            result[bar_idx] = MACDResult(
                macd_line=macd_line / 1000,
                signal_line=signal_line / 1000,
                histogram=histogram / 1000
            )
    
    return result


def calculate_atr(bars: List[Bar], period: int = 14) -> Optional[float]:
    """
    Calculate ATR (Average True Range).
    
    Args:
        bars: List of Bar objects
        period: ATR period (default 14)
    
    Returns:
        ATR value or None if not enough data
    """
    if len(bars) < period + 1:
        return None
    
    true_ranges = []
    for i in range(1, len(bars)):
        high = bars[i].high
        low = bars[i].low
        prev_close = bars[i - 1].close
        
        tr = max(
            high - low,
            abs(high - prev_close),
            abs(low - prev_close)
        )
        true_ranges.append(tr)
    
    # Use simple average for ATR
    atr = _mean(true_ranges[-period:])
    return float(atr)


def calculate_atr_series(bars: List[Bar], period: int = 14) -> List[Optional[float]]:
    """Calculate ATR series for all bars."""
    result = [None] * len(bars)
    
    if len(bars) < period + 1:
        return result
    
    true_ranges = []
    for i in range(1, len(bars)):
        high = bars[i].high
        low = bars[i].low
        prev_close = bars[i - 1].close
        
        tr = max(
            high - low,
            abs(high - prev_close),
            abs(low - prev_close)
        )
        true_ranges.append(tr)
    
    # Calculate ATR using SMA then EMA
    for i in range(period, len(bars)):
        if i == period:
            result[i] = float(_mean(true_ranges[:period]))
        else:
            # Wilder's smoothing
            prev_atr = result[i - 1]
            result[i] = (prev_atr * (period - 1) + true_ranges[i - 1]) / period
    
    return result


def check_macd_crossover(
    current: Optional[MACDResult],
    previous: Optional[MACDResult]
) -> bool:
    """
    Check if MACD line crossed above signal line.
    
    Returns:
        True if bullish crossover occurred
    """
    if current is None or previous is None:
        return False
    
    # Previous: MACD below signal, Current: MACD above signal
    return (
        previous.macd_line <= previous.signal_line and
        current.macd_line > current.signal_line
    )


def get_all_indicators(
    bars: List[Bar],
    rsi_period: int = 14,
    macd_fast: int = 12,
    macd_slow: int = 26,
    macd_signal: int = 9,
    atr_period: int = 14
) -> IndicatorValues:
    """
    Calculate all indicators for the latest bar.
    
    Returns:
        IndicatorValues with all calculated values
    """
    closes = [bar.close for bar in bars]
    
    rsi = calculate_rsi(closes, rsi_period)
    macd = calculate_macd(closes, macd_fast, macd_slow, macd_signal)
    atr = calculate_atr(bars, atr_period)
    
    return IndicatorValues(
        rsi=rsi,
        macd_line=macd.macd_line if macd else None,
        macd_signal=macd.signal_line if macd else None,
        macd_histogram=macd.histogram if macd else None,
        atr=atr
    )
