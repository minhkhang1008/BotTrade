# Bot Trade - Trading Signal Assistant

Bot theo dõi biểu đồ H1 và báo tín hiệu mua dựa trên:
- Xu hướng tăng (3 cặp đỉnh/đáy cao dần)
- Giá chạm vùng đỡ + nến đảo chiều
- Xác nhận MACD/RSI

---

## 🚀 Cài đặt

```bash
# 1. Tạo virtual environment
python -m venv venv
source venv/bin/activate  # Mac/Linux

# 2. Cài dependencies
pip install -r requirements.txt

# 3. Copy và sửa config
cp .env.example .env
# Sửa DNSE_USERNAME, DNSE_PASSWORD, WATCHLIST
```

---

## 🧪 Chạy Bot

### Mock Mode (test với data giả lập)
```bash
python -m src.main --mock
```

### Production (với DNSE thật)
```bash
python -m src.main
```

Server chạy tại: `http://localhost:8000`

---

## 📡 API cho UI

| Endpoint | Mô tả |
|----------|-------|
| `GET /api/v1/health` | Trạng thái hệ thống |
| `GET /api/v1/symbols` | Danh sách mã |
| `GET /api/v1/signals` | Lịch sử tín hiệu |
| `GET /api/v1/bars?symbol=VNM` | Lịch sử nến |
| `GET /api/v1/trading/status` | Trạng thái trading |
| `GET /docs` | API documentation |

### WebSocket
```javascript
const ws = new WebSocket('ws://localhost:8000/ws/v1/stream');
ws.onmessage = (e) => {
  const { event, data } = JSON.parse(e.data);
  // event: 'bar_closed' | 'signal' | 'system'
};
```

---

## 📊 Backtest

```bash
# Chạy demo backtest
python scripts/run_backtest.py
```

Hoặc tự viết:
```python
from src.core.backtest import BacktestEngine, load_bars_from_csv

bars = load_bars_from_csv("data/VNM_1H.csv", "VNM")
engine = BacktestEngine(initial_capital=100_000_000)
result = engine.run(bars)
result.print_report()
```

---

## 🤖 Auto-trade

```bash
# 1. Config
AUTO_TRADE_ENABLED=true
DNSE_ACCOUNT_NO=your_account

# 2. Chạy bot
python -m src.main

# 3. Xác thực OTP (valid 8 giờ)
curl -X POST http://localhost:8000/api/v1/trading/request-otp
curl -X POST http://localhost:8000/api/v1/trading/authenticate \
  -H "Content-Type: application/json" \
  -d '{"otp": "123456"}'
```

---

## 🧪 Scripts tiện ích

```bash
# Test API
python scripts/test_api.py

# Backtest demo
python scripts/run_backtest.py

# Unit tests
PYTHONPATH=. pytest tests/ -v
```

---

## 📁 Cấu trúc

```
BotTrade/
├── src/
│   ├── main.py           # Entry point
│   ├── config.py         # Settings
│   ├── adapters/         # DNSE, Trading
│   ├── core/             # Indicators, Signals, Backtest
│   ├── storage/          # SQLite
│   └── api/              # FastAPI + WebSocket
├── scripts/              # Demo scripts
├── data/                 # Sample data
└── tests/                # Unit tests
```
