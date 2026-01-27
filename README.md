# BotTrade - README

BotTrade là hệ thống tạo tín hiệu giao dịch theo chiến lược kỹ thuật (H1 mặc định), kết hợp dữ liệu thị trường từ DNSE, xử lý tín hiệu real-time, lưu trữ SQLite và hiển thị qua API/WS + UI React.

---

## 1) Cài đặt & Chạy

### Yêu cầu
- Python 3.11
- Node.js 18+
- Git, pip, npm (hoặc pnpm/yarn)

### Backend (FastAPI)
```bash
# Tạo virtualenv (macOS/Linux)
python -m venv .venv
source .venv/bin/activate

# Cài dependencies
pip install --upgrade pip
pip install -r requirements.txt

# Tạo file .env ở thư mục gốc
cat > .env <<'ENV'
DNSE_USERNAME=
DNSE_PASSWORD=
DNSE_ACCOUNT_NO=
WATCHLIST=VNM,FPT,VIC
TIMEFRAME=1H
HOST=0.0.0.0
PORT=8000
AUTO_TRADE_ENABLED=False
ENV

# Chạy mock mode (dữ liệu giả lập)
python -m src.main --mock

# Hoặc production (dùng data DNSE thật)
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
Tạo `bottrade-ui/.env`:
```
VITE_API_URL=http://localhost:8000
VITE_WS_URL=ws://localhost:8000/ws/v1/stream
```

### Kiểm tra nhanh
- Swagger: http://localhost:8000/docs
- Health: http://localhost:8000/api/v1/health
- WS test: `new WebSocket('ws://localhost:8000/ws/v1/stream')`

---

## 2) Công nghệ & Kiến trúc Hạ tầng

### Tổng quan công nghệ
- **Backend:** FastAPI + WebSocket, chạy trong `src/api/server.py`, entry ở `src/main.py`.
- **Market data:** MQTT over WSS tới DNSE (adapter ở `src/adapters/dnse_adapter.py`).
- **Trading:** DNSE Trading Service (OTP + token 8h) trong `src/adapters/trading_service.py`.
- **Signal engine:** `src/core` (indicators, patterns, pivots, trend, signal engine, backtest).
- **DB:** SQLite qua `aiosqlite` (`src/storage/database.py`).
- **Frontend:** React + Vite + TypeScript + Tailwind (`bottrade-ui/`).

### Luồng dữ liệu chính
1. **DNSE MQTT** → nhận OHLC → chuyển thành `Bar`.
2. **Lưu DB** (`bars`) → phục vụ API và tải lịch sử.
3. **SignalEngine** xử lý theo từng mã cổ phiếu.
4. **Phát tín hiệu** → lưu DB (`signals`) → broadcast qua WebSocket.
5. **Tuỳ chọn đặt lệnh** nếu `AUTO_TRADE_ENABLED=True`.

### Thành phần chính
- `src/main.py`: Orchestrator, quản lý DNSE adapter, signal engines, trading service, broadcast WS.
- `src/api/server.py`: REST API + WebSocket, trả bars/signals/settings, broadcast `bar_closed`, `signal`, `system`, `signal_check`.
- `src/storage/database.py`: SQLite, bảng `bars`, `signals`, `settings`.
- `src/adapters/dnse_adapter.py`:
  - `DNSEAdapter`: auth → MQTT subscribe → OHLC.
  - `MockDNSEAdapter`: tạo chuỗi bar giả lập để demo tín hiệu.
- `src/adapters/trading_service.py`: login, OTP, lấy trading token, place order.

### DB schema
- `bars(symbol,timeframe,timestamp,open,high,low,close,volume)`
- `signals(symbol,signal_type,timestamp,entry,stop_loss,take_profit,quantity,status,reason,original_sl)`
- `settings(key,value)`

---

## 3) Logic toán học (core)

### Mô hình dữ liệu
- `Bar(symbol, timeframe, timestamp, open, high, low, close, volume)`
  - Thuộc tính phụ: `body_size`, `upper_shadow`, `lower_shadow`, `total_range`.
- `Pivot(type=HIGH|LOW, price, timestamp, bar_index, pattern)`.
- `SupportZone(zone_low, zone_high)`.
- `Signal(entry, stop_loss, take_profit, quantity, status, reason)`.
  - `risk`, `reward`, `risk_reward_ratio`, `breakeven_price`.

### Indicators
- **RSI** (mặc định 14 kỳ)
  - Tính trên biến động giá: `RS = AvgGain / AvgLoss`,
  - `RSI = 100 - (100 / (1 + RS))`.
  - Bản tính “latest” dùng trung bình đơn của 14 kỳ gần nhất; series dùng Wilder smoothing.
- **MACD**
  - `MACD = EMA12 - EMA26`
  - `Signal = EMA9(MACD)`
  - `Histogram = MACD - Signal`
  - Bullish crossover: `prev.macd_line <= prev.signal_line` và `current.macd_line > current.signal_line`.
- **ATR** (mặc định 14 kỳ)
  - `TR = max(High-Low, |High-PrevClose|, |Low-PrevClose|)`
  - `ATR = SMA14(TR)` (latest) và Wilder smoothing cho series.

### Mẫu nến đảo chiều
- **Hammer (bullish)**: thân nhỏ (<~35% range), bóng dưới dài (>= 1.8x thân), bóng trên ngắn.
- **Bullish Engulfing**: nến trước đỏ, nến sau xanh và thân nến sau nuốt thân nến trước.
- **Shooting Star (bearish)**, **Bearish Engulfing** dùng để xác định pivot high.

### Pivot & Xu hướng
- **Pivot Low**: xuất hiện khi có bullish reversal (Hammer/Bullish Engulfing).
- **Pivot High**: xuất hiện khi có bearish reversal (Shooting Star/Bearish Engulfing).
- **Uptrend**: cần ít nhất 3 cặp higher lows + 3 cặp higher highs
  - Tương đương tối thiểu 4 pivot lows tăng dần và 4 pivot highs tăng dần.

### Support zone & Điều kiện BUY
- **Support zone** quanh pivot low gần nhất:
  - `zone_width = zone_width_atr_mult * ATR`
  - `zone_low = pivot_low - zone_width`, `zone_high = pivot_low + zone_width`
- **Điều kiện tạo BUY (tất cả phải đúng):**
  1. Uptrend thỏa (>=3 cặp higher lows & higher highs).
  2. Giá chạm support zone.
  3. Có mẫu nến đảo chiều tăng (Hammer hoặc Bullish Engulfing).
  4. Xác nhận: MACD bullish crossover **hoặc** RSI > 50.

### Quản lý lệnh
- **Entry** = giá đóng cửa nến tín hiệu.
- **Stop-loss** = pivot low trước đó − `sl_buffer_atr_mult * ATR` (nếu chưa có pivot trước: dùng low hiện tại − buffer).
- **Take-profit** = `Entry + risk_reward_ratio * (Entry − SL)`.
- **Breakeven**: khi giá đạt `Entry + risk`, dời SL lên Entry.

### Backtest
- Đọc CSV (time/open/high/low/close/volume) → replay qua `SignalEngine`.
- Mỗi mã cổ phiếu một engine riêng, chỉ mở 1 vị thế/mã tại một thời điểm.
- Thoát vị thế khi chạm SL/TP; nếu đạt 1R thì dời SL lên hòa vốn.
- Metric: win rate, profit factor, max drawdown, PnL %, average win/loss.

---

## Thư mục chính
```
BotTrade/
├── src/
│   ├── main.py           # Orchestrator
│   ├── config.py         # Settings
│   ├── adapters/         # DNSE + Trading
│   ├── core/             # Indicators, Signals, Backtest
│   ├── storage/          # SQLite
│   └── api/              # FastAPI + WebSocket
├── bottrade-ui/          # React UI
├── scripts/              # Backtest, test API
├── data/                 # Sample data
└── tests/                # Unit tests
```
