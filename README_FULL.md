# BotTrade - README Chi Tiết

Tài liệu này tóm tắt cách cài đặt, kiến trúc hạ tầng, và logic toán học của BotTrade.

## 1) Cài đặt & Chạy

### Yêu cầu
- Python 3.11 (đã dùng cho môi trường backend)
- Node.js 18+ (frontend Vite)
- Git, pip, npm (hoặc pnpm/yarn nếu muốn)

### Backend (FastAPI)
```bash
# Tạo virtualenv (macOS/Linux)
python -m venv .venv
source .venv/bin/activate

# Cài dependencies
pip install --upgrade pip
pip install -r requirements.txt

# Tạo file .env ở thư mục gốc (ví dụ)
cat > .env <<'EOF'
DNSE_USERNAME=
DNSE_PASSWORD=
DNSE_ACCOUNT_NO=
WATCHLIST=VNM,FPT,VIC
TIMEFRAME=1H
HOST=0.0.0.0
PORT=8000
AUTO_TRADE_ENABLED=False
EOF

# Chạy mock mode (sử dụng data ảo để xem cách bot chạy)
python -m src.main --mock
# Hoặc production (dùng data từ API DNSE)
python -m src.main
```

### Frontend (React + Vite + Tailwind)
```bash
cd bottrade-ui
npm install
# Chạy mock API/WS cho UI độc lập
npm run mock
npm run dev   # http://localhost:5173
```

### Kết nối UI với backend Python
- Backend mặc định chạy `http://localhost:8000`, WS `ws://localhost:8000/ws/v1/stream`.
- Có thể tạo `bottrade-ui/.env`:
  - `VITE_API_URL=http://localhost:8000`
  - `VITE_WS_URL=ws://localhost:8000/ws/v1/stream`

### Kiểm tra
- Swagger: http://localhost:8000/docs
- Health: http://localhost:8000/api/v1/health
- WS: mở console và thử `new WebSocket('ws://localhost:8000/ws/v1/stream')`.

## 2) Công nghệ & Kiến trúc

- **Backend:** FastAPI + WebSocket, chạy trong `src/api/server.py`; orchestrator ở `src/main.py`. Persistence bằng SQLite qua `aiosqlite` ([src/storage/database.py](src/storage/database.py)).
- **Market data:** MQTT over WSS đến DNSE (topic OHLC) qua adapter [src/adapters/dnse_adapter.py](src/adapters/dnse_adapter.py). Có `MockDNSEAdapter` để phát sinh dữ liệu giả lập.
- **Signal engine:** logic phát hiện tín hiệu ở [src/core](src/core) (indicators, pivots, trend, patterns, signal engine). Mỗi mã cổ phiếu có một `SignalEngine` riêng, nuôi bởi stream nến.
- **Trading:** dịch vụ đặt lệnh DNSE ở [src/adapters/trading_service.py](src/adapters/trading_service.py); cần login → OTP → trading token (hết hạn ~8h). Có thể tắt bằng `AUTO_TRADE_ENABLED=False`.
- **API/WS:** REST endpoints (`/api/v1/health`, `/api/v1/bars`, `/api/v1/signals`, `/api/v1/settings`, …) và WebSocket `/ws/v1/stream` đẩy sự kiện `bar_closed`, `signal`, `system`.
- **DB schema:**
  - `bars(symbol,timeframe,timestamp,open,high,low,close,volume)`
  - `signals(symbol,signal_type,timestamp,entry,stop_loss,take_profit,quantity,status,reason)`
  - `settings(key,value)` để lưu watchlist, default quantity…
- **Frontend:** React + Vite + TypeScript + Tailwind, mã nằm ở `bottrade-ui/src`. Có mock server (`npm run mock`) để demo UI mà không cần backend Python.
- **Scripts:** backtest demo [scripts/run_backtest.py](scripts/run_backtest.py), test API, generate sample data.

Luồng tổng quát: DNSE MQTT → chuyển thành `Bar` → lưu DB → `SignalEngine` tính toán → phát hiện tín hiệu → lưu DB → broadcast WS → (tuỳ chọn) gọi trading API.

## 3) Logic toán học (core)

### Mô hình dữ liệu
- `Bar(symbol, timeframe, timestamp, open, high, low, close, volume)` cùng các thuộc tính phụ `body_size`, `upper_shadow`, `lower_shadow`, `total_range` ([src/core/models.py](src/core/models.py)).
- `Pivot(type=HIGH|LOW, price, timestamp, bar_index, pattern)` và `SupportZone(zone_low, zone_high)`.
- `Signal(entry, stop_loss, take_profit, quantity, status, reason)` chứa `risk`, `reward`, `risk_reward_ratio`, `breakeven_price`.

### Chỉ báo
- **RSI** $RSI = 100 - \frac{100}{1 + RS}$ với $RS = \frac{\text{Avg Gain}}{\text{Avg Loss}}$ (mặc định 14 kỳ) ([src/core/indicators.py](src/core/indicators.py)).
- **MACD** $MACD = EMA_{12} - EMA_{26}$, $Signal = EMA_{9}(MACD)$, $Histogram = MACD - Signal$; xác nhận giao cắt bullish khi histogram đổi dấu âm→dương.
- **ATR** $ATR = SMA_{14}(TR)$ với $TR = \max(High-Low, |High-PrevClose|, |Low-PrevClose|)$.

### Mẫu nến đảo chiều ([src/core/patterns.py](src/core/patterns.py))
- Hammer: thân nhỏ (<~35% range), bóng dưới dài (≥1.8× thân), bóng trên ngắn.
- Bullish Engulfing: nến trước đỏ, nến sau xanh và thân nến sau nuốt thân nến trước.
- (Có thêm Shooting Star, Bearish Engulfing cho pivot high nhưng chiến lược hiện tại tập trung BUY).

### Pivot & Xu hướng
- Pivot Low xuất hiện khi có bullish reversal; Pivot High khi bearish reversal ([src/core/pivot_detector.py](src/core/pivot_detector.py)).
- Uptrend yêu cầu ≥3 cặp higher lows và ≥3 cặp higher highs liên tiếp (cần 4 pivot lows + 4 pivot highs) ([src/core/trend_analyzer.py](src/core/trend_analyzer.py)).

### Vùng đỡ & Tín hiệu BUY ([src/core/signal_engine.py](src/core/signal_engine.py))
- **Support zone:** quanh pivot low gần nhất, biên độ `zone_width_atr_mult * ATR` (mặc định 0.2 * ATR).
- **Điều kiện tạo BUY (tất cả phải đúng):**
  1. Uptrend thỏa (3 higher lows + 3 higher highs).
  2. Giá chạm support zone.
  3. Có mẫu nến đảo chiều tăng (Hammer hoặc Bullish Engulfing).
  4. Xác nhận: MACD bullish crossover **hoặc** RSI > 50.
- **Đặt lệnh:**
  - Entry = giá đóng cửa nến tín hiệu.
  - Stop-loss = pivot low trước đó − `sl_buffer_atr_mult * ATR` (mặc định 0.05 * ATR).
  - Take-profit = Entry + `risk_reward_ratio * (Entry − SL)` (mặc định R:R = 2.0).
  - Khi giá đạt 1R, dời SL lên hòa vốn (`breakeven_price`).

### Backtest ([src/core/backtest.py](src/core/backtest.py))
- Replay dữ liệu CSV (cột time/open/high/low/close/volume) qua `SignalEngine` cho từng bar.
- Quản lý vị thế: mở theo signal, đóng khi chạm SL/TP, dời SL lên hòa vốn.
- Tính toán các metric: win rate, profit factor, max drawdown, PnL %, average win/loss; in báo cáo.