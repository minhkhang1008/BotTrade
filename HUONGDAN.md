# Hướng dẫn cho UI Developer

Tài liệu này hướng dẫn cách tích hợp giao diện web với Bot Trade API.

---

## 🚀 Khởi động Backend

```bash
cd BotTrade
source venv/bin/activate
python -m src.main --mock   # Test mode
# hoặc
python -m src.main          # Production với DNSE thật
```

**Base URL:** `http://localhost:8001`

---

## 📡 API Endpoints

### Health Check
```http
GET /api/v1/health
```
Response:
```json
{
  "status": "ok",
  "dnse_connected": true,
  "timestamp": "2024-01-23T09:00:00",
  "symbols": ["VNM", "FPT", "VIC"]
}
```

---

### Danh sách mã theo dõi
```http
GET /api/v1/symbols
```
Response:
```json
["VNM", "FPT", "VIC", "VHM", "HPG"]
```

---

### Cài đặt
```http
GET /api/v1/settings
```
Response:
```json
{
  "watchlist": ["VNM", "FPT"],
  "timeframe": "1H",
  "rsi_period": 14,
  "macd_fast": 12,
  "macd_slow": 26,
  "macd_signal": 9,
  "atr_period": 14,
  "zone_width_atr_multiplier": 0.2,
  "sl_buffer_atr_multiplier": 0.05,
  "risk_reward_ratio": 2.0,
  "default_quantity": 100
}
```

---

### Lịch sử tín hiệu
```http
GET /api/v1/signals
GET /api/v1/signals?symbol=VNM&limit=20
```
Response:
```json
[
  {
    "id": 1,
    "symbol": "VNM",
    "signal_type": "BUY",
    "timestamp": "2024-01-23T10:00:00",
    "entry": 75000,
    "stop_loss": 73500,
    "take_profit": 78000,
    "quantity": 100,
    "status": "ACTIVE",
    "reason": "Uptrend + Support zone + Hammer",
    "risk": 1500,
    "reward": 3000,
    "risk_reward_ratio": 2.0
  }
]
```

**Signal statuses:** `ACTIVE`, `TP_HIT`, `SL_HIT`, `CANCELLED`, `BREAKEVEN`

---

### Lịch sử nến (OHLC)
```http
GET /api/v1/bars?symbol=VNM&limit=100
```
Response:
```json
[
  {
    "symbol": "VNM",
    "timeframe": "1H",
    "timestamp": "2024-01-23T09:00:00",
    "open": 75000,
    "high": 76000,
    "low": 74500,
    "close": 75500,
    "volume": 150000
  }
]
```

---

### Trading Status
```http
GET /api/v1/trading/status
```
Response:
```json
{
  "trading_enabled": true,
  "auto_trade_enabled": false,
  "trading_token_valid": false,
  "account_no": "1234567890"
}
```

---

## 🔌 WebSocket (Realtime)

```javascript
const ws = new WebSocket('ws://localhost:8001/ws/v1/stream');

ws.onopen = () => {
  console.log('Connected to Bot Trade');
};

ws.onmessage = (event) => {
  const { event: eventName, data } = JSON.parse(event.data);
  
  switch(eventName) {
    case 'system':
      // Trạng thái kết nối
      // data: { status, dnse_connected, timestamp }
      console.log('System:', data.status);
      break;
      
    case 'bar_closed':
      // Nến mới đóng - cập nhật chart
      // data: { symbol, timeframe, timestamp, open, high, low, close, volume }
      updateChart(data);
      break;
      
    case 'signal':
      // Tín hiệu mới - hiển thị alert
      // data: { symbol, signal_type, entry, stop_loss, take_profit, ... }
      showSignalAlert(data);
      break;
  }
};

ws.onerror = (error) => {
  console.error('WebSocket error:', error);
};

ws.onclose = () => {
  console.log('Disconnected - reconnecting...');
  // Auto reconnect logic
};
```

---

## 🎨 Gợi ý UI Components

### 1. Dashboard
- **Connection Status** - Hiển thị trạng thái DNSE (từ `/health`)
- **Watchlist** - Danh sách mã đang theo dõi
- **Latest Signal** - Tín hiệu mới nhất

### 2. Chart View
- **Candlestick Chart** - Dữ liệu từ `/bars`
- **Indicators** - RSI, MACD (optional - backend đã tính)
- **Entry/SL/TP markers** - Khi có signal

### 3. Signals List
- **Table** với các cột: Symbol, Type, Entry, SL, TP, Status, Time
- **Filter** theo symbol, status
- **Pagination** với limit param

### 4. Settings Panel
- **Watchlist editor** - Thêm/bỏ mã
- **Trading toggle** - Bật/tắt auto-trade

---

## 📦 Example Code (React)

```jsx
// hooks/useSignals.js
import { useState, useEffect } from 'react';

export function useSignals() {
  const [signals, setSignals] = useState([]);
  
  useEffect(() => {
    fetch('http://localhost:8001/api/v1/signals')
      .then(res => res.json())
      .then(setSignals);
  }, []);
  
  return signals;
}

// hooks/useWebSocket.js
export function useWebSocket(onMessage) {
  useEffect(() => {
    const ws = new WebSocket('ws://localhost:8001/ws/v1/stream');
    ws.onmessage = (e) => onMessage(JSON.parse(e.data));
    return () => ws.close();
  }, []);
}
```

---

## ⚠️ Lưu ý

1. **CORS** - Backend đã cho phép tất cả origins (dev mode)
2. **WebSocket** - Tự động nhận sự kiện, không cần polling
3. **Mock mode** - Dùng `--mock` để test không cần DNSE thật
4. **API Docs** - Xem chi tiết tại `http://localhost:8001/docs`

---

## 📞 Liên hệ

Nếu cần thêm endpoint hoặc thay đổi format, liên hệ backend team.
