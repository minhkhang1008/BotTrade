"""
Bot Trade - Backtest Engine
Simulates trading strategy on historical data
"""
import logging
from datetime import datetime
from typing import List, Optional, Dict, Any
from dataclasses import dataclass, field
from pathlib import Path
import csv

from .models import Bar, Signal, SignalType, SignalStatus
from .signal_engine import SignalEngine

logger = logging.getLogger(__name__)


@dataclass
class Trade:
    """Completed trade record."""
    signal: Signal
    entry_time: datetime
    exit_time: datetime
    entry_price: float
    exit_price: float
    quantity: int
    pnl: float
    pnl_percent: float
    exit_reason: str  # TP, SL, BREAKEVEN


@dataclass
class BacktestResult:
    """Backtest performance report."""
    start_date: datetime
    end_date: datetime
    initial_capital: float
    final_capital: float
    
    total_trades: int = 0
    winning_trades: int = 0
    losing_trades: int = 0
    
    total_pnl: float = 0.0
    total_pnl_percent: float = 0.0
    
    max_drawdown: float = 0.0
    max_drawdown_percent: float = 0.0
    
    win_rate: float = 0.0
    profit_factor: float = 0.0
    average_win: float = 0.0
    average_loss: float = 0.0
    
    trades: List[Trade] = field(default_factory=list)
    
    def calculate_metrics(self):
        """Calculate performance metrics from trades."""
        if not self.trades:
            return
        
        self.total_trades = len(self.trades)
        wins = [t for t in self.trades if t.pnl > 0]
        losses = [t for t in self.trades if t.pnl <= 0]
        
        self.winning_trades = len(wins)
        self.losing_trades = len(losses)
        
        self.win_rate = self.winning_trades / self.total_trades * 100 if self.total_trades > 0 else 0
        
        total_wins = sum(t.pnl for t in wins)
        total_losses = abs(sum(t.pnl for t in losses))
        
        self.profit_factor = total_wins / total_losses if total_losses > 0 else float('inf')
        
        self.average_win = total_wins / len(wins) if wins else 0
        self.average_loss = total_losses / len(losses) if losses else 0
    
    def to_dict(self) -> dict:
        """Convert to dictionary."""
        return {
            "period": f"{self.start_date.date()} to {self.end_date.date()}",
            "initial_capital": self.initial_capital,
            "final_capital": self.final_capital,
            "total_pnl": self.total_pnl,
            "total_pnl_percent": f"{self.total_pnl_percent:.2f}%",
            "total_trades": self.total_trades,
            "winning_trades": self.winning_trades,
            "losing_trades": self.losing_trades,
            "win_rate": f"{self.win_rate:.1f}%",
            "profit_factor": f"{self.profit_factor:.2f}",
            "max_drawdown": f"{self.max_drawdown_percent:.2f}%",
            "average_win": self.average_win,
            "average_loss": self.average_loss
        }
    
    def print_report(self):
        """Print formatted report."""
        print("\n" + "="*50)
        print("📊 BACKTEST REPORT")
        print("="*50)
        print(f"Period: {self.start_date.date()} → {self.end_date.date()}")
        print(f"Initial Capital: {self.initial_capital:,.0f}")
        print(f"Final Capital: {self.final_capital:,.0f}")
        print("-"*50)
        print(f"Total PnL: {self.total_pnl:,.0f} ({self.total_pnl_percent:.2f}%)")
        print(f"Max Drawdown: {self.max_drawdown_percent:.2f}%")
        print("-"*50)
        print(f"Total Trades: {self.total_trades}")
        print(f"Win Rate: {self.win_rate:.1f}%")
        print(f"Profit Factor: {self.profit_factor:.2f}")
        print(f"Avg Win: {self.average_win:,.0f}")
        print(f"Avg Loss: {self.average_loss:,.0f}")
        print("="*50 + "\n")


class BacktestEngine:
    """
    Backtest engine for trading strategy.
    
    Replays historical bars through the signal engine and simulates trades.
    """
    
    def __init__(
        self,
        initial_capital: float = 100_000_000,  # 100M VND default
        position_size_percent: float = 10.0,    # Use 10% per trade
        **signal_engine_kwargs
    ):
        self.initial_capital = initial_capital
        self.position_size_percent = position_size_percent
        self.signal_engine_kwargs = signal_engine_kwargs
        
        self.capital = initial_capital
        self.peak_capital = initial_capital
        self.max_drawdown = 0.0
        
        self.active_positions: Dict[str, Signal] = {}
        self.trades: List[Trade] = []
        self.equity_curve: List[tuple] = []  # (timestamp, equity)
    
    def run(self, bars: List[Bar]) -> BacktestResult:
        """
        Run backtest on historical bars.
        
        Args:
            bars: List of historical bars (sorted by time)
        
        Returns:
            BacktestResult with performance metrics
        """
        if not bars:
            return BacktestResult(
                start_date=datetime.now(),
                end_date=datetime.now(),
                initial_capital=self.initial_capital,
                final_capital=self.initial_capital
            )
        
        # Group bars by symbol
        bars_by_symbol = self._group_bars_by_symbol(bars)
        
        # Create signal engine for each symbol
        engines: Dict[str, SignalEngine] = {}
        for symbol in bars_by_symbol:
            engines[symbol] = SignalEngine(**self.signal_engine_kwargs)
        
        # Sort all bars by timestamp
        all_bars = sorted(bars, key=lambda b: b.timestamp)
        
        logger.info(f"Starting backtest with {len(all_bars)} bars across {len(bars_by_symbol)} symbols")
        
        for bar in all_bars:
            # Check existing positions first
            self._check_positions(bar)
            
            # Process bar through signal engine
            engine = engines[bar.symbol]
            result = engine.add_bar(bar)
            
            if result and result.should_signal and result.signal:
                self._handle_signal(result.signal, bar)
            
            # Track equity
            self.equity_curve.append((bar.timestamp, self.capital))
            
            # Update drawdown
            if self.capital > self.peak_capital:
                self.peak_capital = self.capital
            
            current_dd = (self.peak_capital - self.capital) / self.peak_capital
            if current_dd > self.max_drawdown:
                self.max_drawdown = current_dd
        
        # Build result
        result = BacktestResult(
            start_date=all_bars[0].timestamp,
            end_date=all_bars[-1].timestamp,
            initial_capital=self.initial_capital,
            final_capital=self.capital,
            total_pnl=self.capital - self.initial_capital,
            total_pnl_percent=(self.capital - self.initial_capital) / self.initial_capital * 100,
            max_drawdown=self.max_drawdown * self.initial_capital,
            max_drawdown_percent=self.max_drawdown * 100,
            trades=self.trades
        )
        result.calculate_metrics()
        
        return result
    
    def _group_bars_by_symbol(self, bars: List[Bar]) -> Dict[str, List[Bar]]:
        """Group bars by symbol."""
        result = {}
        for bar in bars:
            if bar.symbol not in result:
                result[bar.symbol] = []
            result[bar.symbol].append(bar)
        return result
    
    def _handle_signal(self, signal: Signal, bar: Bar):
        """Handle new trading signal."""
        # Skip if already have position in this symbol
        if signal.symbol in self.active_positions:
            return
        
        # Calculate position size
        position_value = self.capital * (self.position_size_percent / 100)
        quantity = int(position_value / signal.entry)
        
        if quantity <= 0:
            return
        
        # "Open" position
        signal.quantity = quantity
        self.active_positions[signal.symbol] = signal
        
        logger.debug(f"Opened position: {signal.symbol} {quantity} @ {signal.entry}")
    
    def _check_positions(self, bar: Bar):
        """Check active positions against current bar for exits."""
        if bar.symbol not in self.active_positions:
            return
        
        signal = self.active_positions[bar.symbol]
        exit_price = None
        exit_reason = ""
        
        # Check stop loss
        if bar.low <= signal.stop_loss:
            exit_price = signal.stop_loss
            exit_reason = "SL"
        
        # Check take profit
        elif bar.high >= signal.take_profit:
            exit_price = signal.take_profit
            exit_reason = "TP"
        
        # Check breakeven
        elif signal.should_move_to_breakeven(bar.high):
            signal.move_to_breakeven()
            logger.debug(f"Moved SL to breakeven for {signal.symbol}")
        
        # Exit position
        if exit_price:
            pnl = (exit_price - signal.entry) * signal.quantity
            pnl_percent = (exit_price - signal.entry) / signal.entry * 100
            
            trade = Trade(
                signal=signal,
                entry_time=signal.timestamp,
                exit_time=bar.timestamp,
                entry_price=signal.entry,
                exit_price=exit_price,
                quantity=signal.quantity,
                pnl=pnl,
                pnl_percent=pnl_percent,
                exit_reason=exit_reason
            )
            
            self.trades.append(trade)
            self.capital += pnl
            
            del self.active_positions[bar.symbol]
            
            logger.debug(f"Closed position: {signal.symbol} @ {exit_price} ({exit_reason}) PnL: {pnl:,.0f}")
    
    def reset(self):
        """Reset backtest state."""
        self.capital = self.initial_capital
        self.peak_capital = self.initial_capital
        self.max_drawdown = 0.0
        self.active_positions.clear()
        self.trades.clear()
        self.equity_curve.clear()


def load_bars_from_csv(filepath: str, symbol: str, timeframe: str = "1H") -> List[Bar]:
    """
    Load bars from CSV file.
    
    Expected columns: time/date, open, high, low, close, volume
    
    Args:
        filepath: Path to CSV file
        symbol: Stock symbol
        timeframe: Timeframe label
    
    Returns:
        List of Bar objects
    """
    bars = []
    path = Path(filepath)
    
    if not path.exists():
        logger.error(f"File not found: {filepath}")
        return bars
    
    with open(path, 'r', encoding='utf-8') as f:
        reader = csv.DictReader(f)
        
        for row in reader:
            try:
                # Try different column names
                time_str = row.get('time') or row.get('date') or row.get('datetime') or row.get('Time')
                
                # Parse timestamp
                timestamp = None
                for fmt in [
                    "%Y-%m-%d %H:%M:%S",
                    "%Y-%m-%d",
                    "%d/%m/%Y %H:%M:%S",
                    "%d/%m/%Y"
                ]:
                    try:
                        timestamp = datetime.strptime(time_str, fmt)
                        break
                    except ValueError:
                        continue
                
                if not timestamp:
                    continue
                
                bar = Bar(
                    symbol=symbol,
                    timeframe=timeframe,
                    timestamp=timestamp,
                    open=float(row.get('open') or row.get('Open', 0)),
                    high=float(row.get('high') or row.get('High', 0)),
                    low=float(row.get('low') or row.get('Low', 0)),
                    close=float(row.get('close') or row.get('Close', 0)),
                    volume=float(row.get('volume') or row.get('Volume', 0))
                )
                bars.append(bar)
            
            except Exception as e:
                logger.warning(f"Error parsing row: {e}")
                continue
    
    logger.info(f"Loaded {len(bars)} bars from {filepath}")
    return bars
