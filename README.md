# BotTrade - README

BotTrade là hệ thống tạo tín hiệu giao dịch theo chiến lược kỹ thuật (H1 mặc định), kết hợp dữ liệu thị trường real-time từ DNSE MQTT, dữ liệu lịch sử từ VNDirect API, xử lý tín hiệu real-time, lưu trữ SQLite và hiển thị qua API/WS + UI React.

---

## 1) Cài đặt & Chạy

### Yêu cầu
- Python 3.11+
- Node.js 18+
- Git, pip, npm (hoặc pnpm/yarn)

### Backend (FastAPI)
```bash
# Tạo virtualenv (macOS/Linux)
python -m venv venv
source venv/bin/activate

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

# Telegram Notification (optional - để nhận thông báo khi có signal)
TELEGRAM_BOT_TOKEN=
TELEGRAM_CHAT_ID=
TELEGRAM_ENABLED=True
ENV

# Chạy mock/demo mode (dữ liệu giả lập, database riêng)
python run.py --mock

# Hoặc production (dùng data DNSE thật)
python run.py
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
- **Backend:** FastAPI + WebSocket, chạy trong `src/api/server.py`, entry point ở `run.py`.
- **Market data (real-time):** MQTT over WSS tới DNSE (adapter ở `src/adapters/dnse_adapter.py`).
- **Market data (lịch sử):** VNDirect Chart API (`https://dchart-api.vndirect.com.vn/dchart/history`).
- **Trading:** DNSE Trading Service (OTP + token 8h) trong `src/adapters/trading_service.py`.
- **Notification:** Telegram Bot API trong `src/adapters/notification_service.py`.
- **Signal engine:** `src/core` (indicators, patterns, pivots, trend, signal engine, backtest).
- **DB:** SQLite qua `aiosqlite` (`src/storage/database.py`).
  - `bottrade.db`: Database cho real mode
  - `bottrade_demo.db`: Database riêng cho demo/mock mode
- **Frontend:** React + Vite + TypeScript + Tailwind (`bottrade-ui/`).

### Luồng dữ liệu chính
1. **Khởi động:** Lấy dữ liệu lịch sử từ VNDirect API (200+ bars).
2. **DNSE MQTT** → nhận OHLC real-time → normalize giá (×1000 nếu cần) → chuyển thành `Bar`.
3. **Lưu DB** (`bars`) → phục vụ API và tải lịch sử.
4. **SignalEngine** xử lý theo từng mã cổ phiếu.
5. **Phát tín hiệu** → lưu DB (`signals`) → broadcast qua WebSocket → gửi Telegram notification.
6. **Tuỳ chọn đặt lệnh** nếu `AUTO_TRADE_ENABLED=True`.

### Thành phần chính
- `run.py`: Entry point chính, tránh double-load module khi dùng uvicorn.
- `src/main.py`: Orchestrator, quản lý DNSE adapter, signal engines, trading service, broadcast WS.
- `src/api/server.py`: REST API + WebSocket, trả bars/signals/settings, broadcast `bar_closed`, `signal`, `system`, `signal_check`.
- `src/storage/database.py`: SQLite, bảng `bars`, `signals`, `settings`. Tự động chọn DB theo mode.
- `src/adapters/dnse_adapter.py`:
  - `DNSEAdapter`: auth → MQTT subscribe → OHLC real-time. Normalize giá (×1000) từ MQTT.
  - `fetch_historical_bars()`: Lấy dữ liệu lịch sử từ VNDirect API (ưu tiên), fallback SSI, TCBS.
  - `MockDNSEAdapter`: tạo chuỗi bar giả lập để demo tín hiệu (deterministic).
- `src/adapters/trading_service.py`: login, OTP, lấy trading token, place order.
- `src/adapters/notification_service.py`: Gửi thông báo qua Telegram khi có signal.

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
  - Sử dụng **Wilder's Smoothing** (chuẩn TradingView).
  - Tính trên biến động giá: `RS = AvgGain / AvgLoss`.
  - `RSI = 100 - (100 / (1 + RS))`.
  - Wilder's formula: `avg = (prev_avg * (period-1) + current) / period`.
- **MACD**
  - `MACD = EMA12 - EMA26`
  - `Signal = EMA9(MACD)`
  - `Histogram = MACD - Signal`
  - Cần tối thiểu 35 bars (26 slow + 9 signal).
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
├── run.py                # Entry point chính (khuyên dùng)
├── src/
│   ├── main.py           # Orchestrator
│   ├── config.py         # Settings
│   ├── adapters/         # DNSE MQTT + Trading Service
│   ├── core/             # Indicators, Signals, Backtest
│   ├── storage/          # SQLite (bottrade.db / bottrade_demo.db)
│   └── api/              # FastAPI + WebSocket
├── bottrade-ui/          # React UI
├── scripts/              # Backtest, test API
├── data/                 # Sample data
└── tests/                # Unit tests
```

---

## Lưu ý kỹ thuật

### Price Normalization
- DNSE MQTT trả giá theo đơn vị **nghìn đồng** (VD: 68.9 = 68,900 VND).
- VNDirect API trả giá theo **VND** (VD: 68900).
- Hệ thống tự động detect và normalize: nếu giá < 1000 thì nhân 1000.

### Historical Data
- Sử dụng VNDirect Chart API làm nguồn chính.
- Fallback: SSI iBoard, TCBS.
- Lấy 60+ ngày lịch sử để đảm bảo đủ 200+ bars cho MACD (cần 35 bars minimum).

### Database Separation
- **Real mode:** `bottrade.db`
- **Demo/mock mode:** `bottrade_demo.db` (tách riêng để không lẫn dữ liệu)

---

## 4) Telegram Notification

Bot có thể gửi thông báo đến Telegram khi có tín hiệu mới. Hoạt động kể cả khi tắt web.

### Setup Telegram Bot

1. **Tạo Bot:**
   - Mở Telegram, tìm `@BotFather`
   - Gửi `/newbot` và làm theo hướng dẫn
   - Lưu lại **Bot Token** (dạng: `123456789:ABCdefGHIjklMNOpqrsTUVwxyz`)

2. **Lấy Chat ID:**
   - Mở chat với bot vừa tạo, gửi `/start`
   - Truy cập: `https://api.telegram.org/bot<YOUR_BOT_TOKEN>/getUpdates`
   - Tìm `"chat":{"id":123456789}` - đây là **Chat ID** của bạn
   - Hoặc dùng `@userinfobot` để lấy Chat ID

3. **Cấu hình .env:**
   ```
   TELEGRAM_BOT_TOKEN=123456789:ABCdefGHIjklMNOpqrsTUVwxyz
   TELEGRAM_CHAT_ID=123456789
   TELEGRAM_ENABLED=True
   ```

4. **Test notification:**
   ```bash
   curl -X POST http://localhost:8000/api/v1/notification/test
   ```

### API Endpoints

| Method | Endpoint | Mô tả |
|--------|----------|-------|
| GET | `/api/v1/notification/status` | Kiểm tra trạng thái notification |
| POST | `/api/v1/notification/test` | Gửi test notification |
| POST | `/api/v1/notification/configure` | Cấu hình runtime (không lưu vào .env) |

### Nội dung thông báo

Khi có signal, bot sẽ gửi tin nhắn dạng:
```
🟢 TÍN HIỆU MUA 🟢

Mã: VNM
Giá vào: 68,500 VND
Stop Loss: 67,800 VND
Take Profit: 69,900 VND

📊 Chi tiết:
• Risk: 700 VND (1.02%)
• Reward: 1,400 VND (2.04%)
• R:R = 1:2.0
• Số lượng: 100 cổ phiếu

🕐 14:30:00 27/01/2026

Lý do: Hammer + RSI > 50
```
