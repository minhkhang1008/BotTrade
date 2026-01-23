#!/usr/bin/env python3
"""
Generate sample data with candlestick patterns for backtest.
This creates data that includes:
- Uptrend structure (higher highs, higher lows)
- Hammer patterns at support zones
- Engulfing patterns
"""
import csv
from datetime import datetime, timedelta
import random


def generate_bars(symbol: str, start_date: datetime, num_bars: int = 100):
    """Generate sample OHLC data with patterns."""
    bars = []
    
    # Starting price
    price = 70000
    base_volume = 100000
    
    # Generate uptrend with pullbacks
    for i in range(num_bars):
        # Trading hours: 9, 10, 11, 13, 14
        hours = [9, 10, 11, 13, 14]
        hour_idx = i % 5
        day_offset = i // 5
        
        # Skip weekends
        date = start_date + timedelta(days=day_offset)
        while date.weekday() >= 5:  # Saturday or Sunday
            day_offset += 1
            date = start_date + timedelta(days=day_offset)
        
        timestamp = date.replace(hour=hours[hour_idx], minute=0, second=0)
        
        # Trend bias (upward)
        trend = 0.001  # 0.1% per bar on average
        
        # Add pullback cycles every 15-20 bars
        cycle_pos = i % 18
        if cycle_pos < 12:
            # Uptrend phase
            move = random.uniform(0, 0.008) + trend
        else:
            # Pullback phase
            move = random.uniform(-0.006, 0.002)
        
        # Generate OHLC
        open_price = price
        
        # Determine if bullish or bearish
        is_bullish = move > 0
        
        # Check for pattern opportunities at pullback bottoms
        is_hammer = False
        is_engulfing = False
        
        if cycle_pos == 17 and len(bars) > 0:  # End of pullback
            # Create Hammer pattern
            is_hammer = True
            close_price = open_price + abs(move) * price
            low_price = open_price - 0.015 * price  # Long lower shadow
            high_price = max(open_price, close_price) + 0.002 * price
        elif cycle_pos == 16 and len(bars) > 0:
            # Create bearish bar before hammer
            close_price = open_price - 0.004 * price
            low_price = close_price - 0.002 * price
            high_price = open_price + 0.002 * price
        else:
            # Normal bar
            change = move * price
            if is_bullish:
                close_price = open_price + abs(change)
                high_price = close_price + random.uniform(0, 0.003) * price
                low_price = open_price - random.uniform(0, 0.002) * price
            else:
                close_price = open_price - abs(change)
                high_price = open_price + random.uniform(0, 0.002) * price
                low_price = close_price - random.uniform(0, 0.003) * price
        
        volume = base_volume * random.uniform(0.8, 1.5)
        
        bars.append({
            'time': timestamp.strftime('%Y-%m-%d %H:%M:%S'),
            'open': round(open_price),
            'high': round(high_price),
            'low': round(low_price),
            'close': round(close_price),
            'volume': int(volume)
        })
        
        # Update price for next bar
        price = close_price
    
    return bars


def main():
    print("Generating sample data with patterns...")
    
    start = datetime(2024, 1, 2)
    bars = generate_bars("VNM", start, num_bars=150)
    
    # Save to CSV
    output_file = "data/VNM_1H.csv"
    with open(output_file, 'w', newline='') as f:
        writer = csv.DictWriter(f, fieldnames=['time', 'open', 'high', 'low', 'close', 'volume'])
        writer.writeheader()
        writer.writerows(bars)
    
    print(f"✅ Generated {len(bars)} bars")
    print(f"   Saved to: {output_file}")
    print(f"   Price range: {bars[0]['open']:,} → {bars[-1]['close']:,}")


if __name__ == "__main__":
    main()
