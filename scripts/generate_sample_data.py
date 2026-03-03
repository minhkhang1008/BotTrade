#!/usr/bin/env python3
import asyncio
import os
import sys
from datetime import datetime, timedelta

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from src.storage.database import db
from src.core.models import Bar

def create_bar(symbol, timestamp, o, h, l, c):
    return Bar(
        symbol=symbol, timeframe="1H", timestamp=timestamp,
        open=round(o), high=round(h), low=round(l), close=round(c), 
        volume=250000
    )

def next_time(current_time):
    hours = [9, 10, 11, 13, 14]
    try:
        idx = hours.index(current_time.hour)
        if idx < len(hours) - 1:
            return current_time.replace(hour=hours[idx + 1])
    except ValueError:
        pass
    next_day = current_time + timedelta(days=1)
    while next_day.weekday() >= 5:
        next_day += timedelta(days=1)
    return next_day.replace(hour=9)

async def main():
    os.environ["BOT_TRADE_MOCK_MODE"] = "true"
    await db.connect()
    
    symbols = ["VNM", "FPT", "VIC", "VHM", "HPG"]
    all_bars = []
    
    for symbol in symbols:
        bars = []
        current_time = datetime(2024, 1, 1, 9, 0, 0)
        
        def add_bar(o, c, h=None, l=None):
            nonlocal current_time
            if h is None: h = max(o, c) + 10
            if l is None: l = min(o, c) - 10
            bars.append(create_bar(symbol, current_time, o, h, l, c))
            current_time = next_time(current_time)

        # Hàm "đúc" mô hình nến đảo chiều để ép bot nhận diện Pivot
        def make_bearish_engulfing(peak_price):
            add_bar(peak_price - 100, peak_price)  # Nến xanh
            add_bar(peak_price + 10, peak_price - 150) # Nến đỏ bao trùm (-> Pivot High)

        def make_bullish_engulfing(trough_price):
            add_bar(trough_price + 100, trough_price) # Nến đỏ
            add_bar(trough_price - 10, trough_price + 150) # Nến xanh bao trùm (-> Pivot Low)

        # 1. Khởi động: Bơm RSI lên cao (>50)
        price = 50000
        for _ in range(50):
            add_bar(price, price + 100)
            price += 100

        # 2. Xây dựng 4 nhịp sóng (Uptrend: Đỉnh sau cao hơn, Đáy sau cao hơn)
        # Sóng 1
        while price < 56000: add_bar(price, price + 100); price += 100
        make_bearish_engulfing(56000) 
        price = 56000 - 150
        while price > 55500: add_bar(price, price - 100); price -= 100
        make_bullish_engulfing(55500) 
        price = 55500 + 150

        # Sóng 2
        while price < 56500: add_bar(price, price + 100); price += 100
        make_bearish_engulfing(56500) 
        price = 56500 - 150
        while price > 56000: add_bar(price, price - 100); price -= 100
        make_bullish_engulfing(56000) 
        price = 56000 + 150

        # Sóng 3
        while price < 57000: add_bar(price, price + 100); price += 100
        make_bearish_engulfing(57000) 
        price = 57000 - 150
        while price > 56500: add_bar(price, price - 100); price -= 100
        make_bullish_engulfing(56500) 
        price = 56500 + 150

        # Sóng 4 (Chỉ tạo đỉnh rồi rơi từ từ xuống Support)
        while price < 57500: add_bar(price, price + 100); price += 100
        make_bearish_engulfing(57500) 
        price = 57500 - 150
        while price > 57050: add_bar(price, price - 100); price -= 100

        # 3. Kích hoạt tín hiệu (Trigger) bằng NẾN BÚA hoàn hảo
        # Thân nến cực mỏng (10), Râu dưới siêu dài (80), Râu trên cực ngắn (2)
        add_bar(o=57050, c=57060, h=57062, l=56970)
        
        all_bars.extend(bars)
        
    await db.save_bars(all_bars)
    print("✅ Đã tạo kịch bản: 4 Đỉnh, 4 Đáy hoàn hảo, kèm Nến Búa và RSI > 50!")
    await db.disconnect()

if __name__ == "__main__":
    asyncio.run(main())