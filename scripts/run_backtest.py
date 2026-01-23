#!/usr/bin/env python3
"""
Demo script to run backtest on sample data.
Usage: python scripts/run_backtest.py
"""
import sys
sys.path.insert(0, '.')

from src.core.backtest import BacktestEngine, load_bars_from_csv


def main():
    print("\n" + "="*50)
    print("🔬 BOT TRADE - BACKTEST DEMO")
    print("="*50 + "\n")
    
    # Load sample data
    bars = load_bars_from_csv("data/VNM_1H.csv", "VNM", "1H")
    
    if not bars:
        print("❌ No data found. Make sure data/VNM_1H.csv exists.")
        return
    
    print(f"📊 Loaded {len(bars)} bars")
    print(f"   From: {bars[0].timestamp}")
    print(f"   To:   {bars[-1].timestamp}")
    print()
    
    # Run backtest
    engine = BacktestEngine(
        initial_capital=100_000_000,  # 100M VND
        position_size_percent=10.0     # 10% per trade
    )
    
    result = engine.run(bars)
    
    # Print report
    result.print_report()
    
    # Show trades
    if result.trades:
        print("\n📝 TRADES:")
        print("-"*70)
        for i, trade in enumerate(result.trades, 1):
            emoji = "✅" if trade.pnl > 0 else "❌"
            print(f"{i}. {emoji} {trade.signal.symbol} | "
                  f"Entry: {trade.entry_price:,.0f} → Exit: {trade.exit_price:,.0f} | "
                  f"PnL: {trade.pnl:+,.0f} ({trade.pnl_percent:+.1f}%) | "
                  f"{trade.exit_reason}")
    else:
        print("\n📝 No trades generated (not enough signals)")
        print("   Tip: Add more historical data with clear uptrend patterns")


if __name__ == "__main__":
    main()
