"""
Bot Trade - Tests for Indicators
"""
import pytest
from src.core.indicators import (
    calculate_rsi, calculate_macd, calculate_atr,
    check_macd_crossover, MACDResult
)
from src.core.models import Bar
from datetime import datetime


class TestRSI:
    def test_rsi_overbought(self):
        """RSI should be high with consecutive up moves."""
        # 15 bars with increasing closes
        closes = [100 + i * 2 for i in range(15)]
        rsi = calculate_rsi(closes, period=14)
        
        assert rsi is not None
        assert rsi > 70  # Overbought
    
    def test_rsi_oversold(self):
        """RSI should be low with consecutive down moves."""
        closes = [100 - i * 2 for i in range(15)]
        rsi = calculate_rsi(closes, period=14)
        
        assert rsi is not None
        assert rsi < 30  # Oversold
    
    def test_rsi_insufficient_data(self):
        """RSI should return None with insufficient data."""
        closes = [100, 101, 102]
        rsi = calculate_rsi(closes, period=14)
        
        assert rsi is None


class TestMACD:
    def test_macd_calculation(self):
        """MACD should calculate correctly."""
        # Generate 50 bars of data
        closes = [100 + i * 0.5 for i in range(50)]
        
        result = calculate_macd(closes, 12, 26, 9)
        
        assert result is not None
        assert isinstance(result, MACDResult)
        assert result.histogram == result.macd_line - result.signal_line
    
    def test_macd_insufficient_data(self):
        """MACD should return None with insufficient data."""
        closes = [100 + i for i in range(20)]
        
        result = calculate_macd(closes, 12, 26, 9)
        
        assert result is None
    
    def test_macd_crossover(self):
        """Test MACD crossover detection."""
        previous = MACDResult(macd_line=-0.5, signal_line=0.0, histogram=-0.5)
        current = MACDResult(macd_line=0.5, signal_line=0.0, histogram=0.5)
        
        assert check_macd_crossover(current, previous) is True
    
    def test_macd_no_crossover(self):
        """Test when no crossover occurred."""
        previous = MACDResult(macd_line=0.5, signal_line=0.0, histogram=0.5)
        current = MACDResult(macd_line=0.6, signal_line=0.0, histogram=0.6)
        
        assert check_macd_crossover(current, previous) is False


class TestATR:
    def test_atr_calculation(self):
        """ATR should calculate correctly."""
        bars = []
        for i in range(20):
            bars.append(Bar(
                symbol="TEST",
                timeframe="1H",
                timestamp=datetime.now(),
                open=100 + i,
                high=102 + i,
                low=98 + i,
                close=101 + i,
                volume=1000
            ))
        
        atr = calculate_atr(bars, period=14)
        
        assert atr is not None
        assert atr > 0
    
    def test_atr_insufficient_data(self):
        """ATR should return None with insufficient data."""
        bars = [Bar(
            symbol="TEST",
            timeframe="1H",
            timestamp=datetime.now(),
            open=100,
            high=102,
            low=98,
            close=101,
            volume=1000
        )]
        
        atr = calculate_atr(bars, period=14)
        
        assert atr is None
