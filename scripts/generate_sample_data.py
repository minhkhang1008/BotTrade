#!/usr/bin/env python3
import asyncio
import os
import sys
from datetime import datetime, timedelta
import random

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from src.storage.database import db
from src.core.models import Bar
from src.core.signal_engine import SignalEngine
from src.config import settings

async def main():
    os.environ["BOT_TRADE_MOCK_MODE"] = "true"
    await db.connect()
    
    symbol = "VNM"
    price = 70000.0
    start_date = datetime(2024, 1, 2, 9, 0, 0)
    bars = []
    
    for i in range(150):
        hours = [9, 10, 11, 13, 14]
        hour_idx = i % 5
        day_offset = i // 5
        
        date = start_date + timedelta(days=day_offset)
        while date.weekday() >= 5:
            day_offset += 1
            date = start_date + timedelta(days=day_offset)
            
        timestamp = date.replace(hour=hours[hour_idx], minute=0, second=0)
        
        move = random.uniform(-0.005, 0.008)
        open_price = price
        close_price = open_price * (1 + move)
        
        cycle_pos = i % 18
        if cycle_pos == 17:
            close_price = open_price + abs(move) * price
            low_price = open_price - 0.015 * price
            high_price = max(open_price, close_price) + 0.002 * price
        else:
            high_price = max(open_price, close_price) * (1 + random.uniform(0, 0.003))
            low_price = min(open_price, close_price) * (1 - random.uniform(0, 0.003))
            
        bar = Bar(
            symbol=symbol,
            timeframe="1H",
            timestamp=timestamp,
            open=round(open_price),
            high=round(high_price),
            low=round(low_price),
            close=round(close_price),
            volume=int(100000 * random.uniform(0.8, 1.5))
        )
        bars.append(bar)
        price = close_price
        
    await db.save_bars(bars)
    
    engine = SignalEngine(
        zone_width_atr_mult=settings.zone_width_atr_multiplier,
        sl_buffer_atr_mult=settings.sl_buffer_atr_multiplier,
        risk_reward_ratio=settings.risk_reward_ratio,
        default_quantity=settings.default_quantity
    )
    
    for bar in bars:
        res = engine.add_bar(bar)
        if res and res.should_signal and res.signal:
            await db.save_signal(res.signal)
            
    await db.disconnect()

if __name__ == "__main__":
    asyncio.run(main())