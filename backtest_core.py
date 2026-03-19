import asyncio
import pandas as pd
import numpy as np
import vectorbt as vbt
from src.storage.database import db

async def run_trailing_optimization():
    print("⏳ Đang kết nối Database và tải dữ liệu...")
    await db.connect()
    symbol = "FPT"
    
    bars = await db.get_bars(symbol, timeframe="1H", limit=1000)
    if not bars:
        return

    df = pd.DataFrame([b.model_dump() if hasattr(b, 'model_dump') else b.__dict__ for b in bars])
    df.set_index('timestamp', inplace=True)
    
    close_price = df['close'].astype(float)
    volume = df['volume'].astype(float)

    print("🧠 Đang chạy AI Scoring Engine...")
    
    rsi = vbt.RSI.run(close_price, window=14)
    macd = vbt.MACD.run(close_price, fast_window=12, slow_window=26, signal_window=9)
    
    vol_ma = volume.rolling(window=20).mean()
    vol_std = volume.rolling(window=20).std()
    vol_zscore = (volume - vol_ma) / vol_std

    # Chấm điểm động 
    scores = pd.Series(0, index=close_price.index, dtype=float)
    scores += np.where(rsi.rsi < 40, 2, 0)
    scores += np.where(rsi.rsi < 30, 1, 0)
    scores += np.where(vol_zscore > 1.5, 1, 0)
    scores += np.where(vol_zscore > 2.5, 1, 0)
    scores += np.where(macd.macd > macd.signal, 2, 0)

    # Chốt cố định Threshold = 4 (Vì nó cho nhiều cơ hội vào lệnh nhất ở bài test trước)
    entries = scores >= 4

    # Thoát lệnh khi MACD cắt xuống hoặc RSI quá mua (Chỉ báo đảo chiều)
    exits = (macd.macd < macd.signal) | (rsi.rsi > 70)

    print("\n" + "="*60)
    print("🚀 TỐI ƯU HÓA TRAILING STOP (CHỐT LỜI ĐUỔI)")
    print("="*60)

    best_return = -999
    best_trail = 0

    # Quét để tìm khoảng cách Trailing Stop hoàn hảo (từ 2% đến 8%)
    for trailing_pct in [0.02, 0.03, 0.04, 0.05, 0.06, 0.07, 0.08]:
        portfolio = vbt.Portfolio.from_signals(
            close_price, 
            entries, 
            exits, 
            init_cash=100000000, 
            fees=0.0015, 
            freq='1h',
            sl_stop=trailing_pct,  # Khai báo khoảng cách Cắt lỗ / Chốt lời đuổi
            sl_trail=True          # KÍCH HOẠT TRAILING STOP
            # LƯU Ý: Đã xóa tp_stop để gồng lãi vô cực
        )
        
        total_return = portfolio.total_return() * 100
        trade_count = portfolio.trades.count()
        win_rate = portfolio.trades.win_rate() * 100 if trade_count > 0 else 0
        
        print(f"Bám đuôi {trailing_pct*100:.0f}% -> Số lệnh: {trade_count:2d} | Win Rate: {win_rate:5.1f}% | Lợi nhuận: {total_return:6.2f}%")
        
        if total_return > best_return and trade_count > 0:
            best_return = total_return
            best_trail = trailing_pct

    print("-" * 60)
    if best_trail > 0:
        print(f"🏆 KẾT LUẬN: Đánh bại thị trường với Trailing Stop {best_trail*100:.0f}% (Lợi nhuận: {best_return:.2f}%)")
    else:
        print("⚠️ Chưa tìm thấy thông số sinh lời.")

if __name__ == "__main__":
    asyncio.run(run_trailing_optimization())