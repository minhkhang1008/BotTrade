# Bot Trade - Giải thích Logic Hệ thống

Tài liệu kỹ thuật chi tiết về cách hoạt động của Bot Trade.

---

## Mục lục

1. [Tổng quan hệ thống](#1-tổng-quan-hệ-thống)
2. [Kết nối DNSE Market Data](#2-kết-nối-dnse-market-data)
3. [Cấu trúc dữ liệu Bar (Nến)](#3-cấu-trúc-dữ-liệu-bar-nến)
4. [Chỉ báo kỹ thuật (Indicators)](#4-chỉ-báo-kỹ-thuật-indicators)
5. [Phát hiện Pivot Points](#5-phát-hiện-pivot-points)
6. [Phân tích xu hướng (Trend)](#6-phân-tích-xu-hướng-trend)
7. [Nhận diện nến đảo chiều](#7-nhận-diện-nến-đảo-chiều)
8. [Logic tạo tín hiệu BUY](#8-logic-tạo-tín-hiệu-buy)
9. [Tính Entry/SL/TP](#9-tính-entrystltp)
10. [Trading API (DNSE)](#10-trading-api-dnse)
11. [Backtest Engine](#11-backtest-engine)

---

## 1. Tổng quan hệ thống

```
┌─────────────────┐     ┌─────────────────┐     ┌─────────────────┐
│  DNSE Market    │────▶│   Bot Trade     │────▶│   WebSocket     │
│  Data (MQTT)    │     │   Core Engine   │     │   (to UI)       │
└─────────────────┘     └─────────────────┘     └─────────────────┘
                               │
                               ▼
                        ┌─────────────────┐
                        │  Trading API    │
                        │  (đặt lệnh)     │
                        └─────────────────┘
```

**Flow chính:**
1. Nhận dữ liệu nến (OHLC) từ DNSE qua MQTT
2. Tính toán indicators (RSI, MACD, ATR)
3. Phát hiện pivot points (đỉnh/đáy)
4. Phân tích xu hướng
5. Kiểm tra nến đảo chiều
6. Tạo tín hiệu nếu đủ điều kiện
7. Gửi thông báo qua WebSocket
8. (Optional) Tự động đặt lệnh

---

## 2. Kết nối DNSE Market Data

### MQTT over WebSocket

**URL:** `wss://datafeed-lts-krx.dnse.com.vn/wss`

**Authentication (theo API doc DNSE):**
```
1. Đăng nhập: POST https://api.dnse.com.vn/user-service/api/auth
   -> Lấy JWT token

2. Lấy thông tin user: GET https://api.dnse.com.vn/user-service/api/me
   Header: Authorization: Bearer <JWT token>
   -> Lấy investorId

3. Kết nối MQTT:
   - ClientID: dnse-price-json-mqtt-ws-sub-<investorId>-<random_sequence>
   - Username: <investorId>
   - Password: <JWT token>
```

**Topic format:**
```
plaintext/quotes/krx/mdds/v2/ohlc/stock/{timeframe}/{symbol}
```

Ví dụ: `plaintext/quotes/krx/mdds/v2/ohlc/stock/1H/VNM`

**Timeframe:**
- `1`: Phút
- `1H`: Giờ
- `1D`: Ngày
- `W`: Tuần

**Message format (JSON):**
```json
{
  "time": "2024-01-23T10:00:00",
  "o": 75000,    // Open
  "h": 76000,    // High
  "l": 74500,    // Low
  "c": 75500,    // Close
  "v": 150000   // Volume
}
```

**Xử lý trong code:** `src/adapters/dnse_adapter.py`

---

## 3. Cấu trúc dữ liệu Bar (Nến)

**File:** `src/core/models.py`

```python
@dataclass
class Bar:
    symbol: str      # Mã cổ phiếu (VNM, FPT,...)
    timeframe: str   # Khung thời gian (1H, 4H, D,...)
    timestamp: datetime
    open: float      # Giá mở cửa
    high: float      # Giá cao nhất
    low: float       # Giá thấp nhất
    close: float     # Giá đóng cửa
    volume: float    # Khối lượng
```

**Các thuộc tính tính toán:**
```python
@property
def body_size(self):
    """Kích thước thân nến = |Close - Open|"""
    return abs(self.close - self.open)

@property
def total_range(self):
    """Biên độ nến = High - Low"""
    return self.high - self.low

@property
def upper_shadow(self):
    """Bóng trên = High - max(Open, Close)"""
    return self.high - max(self.open, self.close)

@property
def lower_shadow(self):
    """Bóng dưới = min(Open, Close) - Low"""
    return min(self.open, self.close) - self.low

@property
def is_bullish(self):
    """Nến tăng: Close > Open"""
    return self.close > self.open

@property
def is_bearish(self):
    """Nến giảm: Close < Open"""
    return self.close < self.open
```

---

## 4. Chỉ báo kỹ thuật (Indicators)

**File:** `src/core/indicators.py`

### RSI (Relative Strength Index)

**Công thức:**
```
RSI = 100 - (100 / (1 + RS))
RS = Average Gain / Average Loss (trong N periods)
```

**Tham số:** `period = 14` (mặc định)

**Code:**
```python
def calculate_rsi(closes: List[float], period: int = 14) -> float:
    if len(closes) < period + 1:
        return None
    
    deltas = [closes[i] - closes[i-1] for i in range(1, len(closes))]
    gains = [d if d > 0 else 0 for d in deltas]
    losses = [-d if d < 0 else 0 for d in deltas]
    
    avg_gain = sum(gains[-period:]) / period
    avg_loss = sum(losses[-period:]) / period
    
    if avg_loss == 0:
        return 100.0
    
    rs = avg_gain / avg_loss
    return 100 - (100 / (1 + rs))
```

**Ý nghĩa:**
- RSI > 70: Quá mua (overbought)
- RSI < 30: Quá bán (oversold)
- RSI > 50: Momentum tăng (dùng để xác nhận)

---

### MACD (Moving Average Convergence Divergence)

**Công thức:**
```
MACD Line = EMA(12) - EMA(26)
Signal Line = EMA(9) của MACD Line
Histogram = MACD Line - Signal Line
```

**Tham số:**
- `fast_period = 12`
- `slow_period = 26`
- `signal_period = 9`

**MACD Crossover (tín hiệu xác nhận):**
```python
def check_macd_crossover(current: MACDResult, previous: MACDResult) -> bool:
    """
    Bullish crossover: MACD cắt lên Signal Line
    - Previous: MACD < Signal (histogram < 0)
    - Current: MACD > Signal (histogram > 0)
    """
    if previous is None or current is None:
        return False
    return previous.histogram < 0 and current.histogram > 0
```

---

### ATR (Average True Range)

**Công thức:**
```
True Range = max(
    High - Low,
    |High - Previous Close|,
    |Low - Previous Close|
)
ATR = SMA của True Range trong N periods
```

**Tham số:** `period = 14`

**Ý nghĩa:**
- Đo lường độ biến động của giá
- Dùng để tính support zone width và SL buffer

---

## 5. Phát hiện Pivot Points

**File:** `src/core/pivot_detector.py`

### Pivot Low (Đáy)
```
Điều kiện: Bar[i].low < Bar[i-1].low AND Bar[i].low < Bar[i+1].low
```

Nghĩa là: một bar có giá low thấp hơn cả bar trước và bar sau.

### Pivot High (Đỉnh)
```
Điều kiện: Bar[i].high > Bar[i-1].high AND Bar[i].high > Bar[i+1].high
```

**Cấu trúc Pivot:**
```python
@dataclass
class Pivot:
    timestamp: datetime
    bar_index: int
    price: float           # Giá tại pivot
    pivot_type: PivotType  # HIGH hoặc LOW
```

**Lưu ý:** Pivot được xác nhận SAU 1 bar (cần bar sau để so sánh).

---

## 6. Phân tích xu hướng (Trend)

**File:** `src/core/trend_analyzer.py`

### Điều kiện Uptrend

```
Uptrend = TRUE khi:
  - 4 pivot low liên tiếp tăng dần (Low1 < Low2 < Low3 < Low4) = 3 cặp higher lows
  - VÀ 4 pivot high liên tiếp tăng dần (High1 < High2 < High3 < High4) = 3 cặp higher highs
```

**Minh họa:**
```
         H4
        /  \        H3
       /    \      /  \        H2
      /      \    /    \      /  \
     /        \  /      \    /    \
    /          L3        \  /      \
   /                      L2        \
  H1                                 L1
```

**Code:**
```python
def _count_higher_pairs(self, pivots: List[Pivot]) -> int:
    """Đếm số cặp pivot tăng dần từ cuối"""
    count = 0
    for i in range(len(pivots) - 1, 0, -1):
        if pivots[i].price > pivots[i - 1].price:
            count += 1
        else:
            break
    return count

def analyze(self, pivot_lows, pivot_highs) -> TrendAnalysisResult:
    higher_lows = self._count_higher_pairs(pivot_lows)
    higher_highs = self._count_higher_pairs(pivot_highs)
    
    is_uptrend = (higher_lows >= 3) and (higher_highs >= 3)
    return TrendAnalysisResult(is_uptrend, higher_lows, higher_highs)
```

---

## 7. Nhận diện nến đảo chiều

**File:** `src/core/patterns.py`

### Hammer (Búa)

```
Điều kiện:
1. Thân nến nhỏ (< 30% tổng biên độ)
2. Bóng dưới dài (>= 2x thân nến)
3. Bóng trên nhỏ (< thân nến)
```

```python
def is_hammer(bar: Bar) -> bool:
    body = bar.body_size
    if body / bar.total_range > 0.3:  # Thân > 30%
        return False
    if bar.lower_shadow / body < 2.0:  # Bóng dưới < 2x thân
        return False
    if bar.upper_shadow > body:  # Bóng trên > thân
        return False
    return True
```

**Ý nghĩa:** Xuất hiện ở đáy, báo hiệu đảo chiều tăng.

---

### Bullish Engulfing (Nhấn chìm tăng)

```
Điều kiện:
1. Bar trước đó là nến giảm (bearish)
2. Bar hiện tại là nến tăng (bullish)
3. Thân nến hiện tại "nuốt" hoàn toàn thân nến trước
```

```python
def is_bullish_engulfing(current: Bar, previous: Bar) -> bool:
    if not previous.is_bearish:
        return False
    if not current.is_bullish:
        return False
    
    # Current body engulfs previous body
    curr_low = min(current.open, current.close)
    curr_high = max(current.open, current.close)
    prev_low = min(previous.open, previous.close)
    prev_high = max(previous.open, previous.close)
    
    return curr_low < prev_low and curr_high > prev_high
```

---

## 8. Logic tạo tín hiệu BUY

**File:** `src/core/signal_engine.py`

### 4 Điều kiện (TẤT CẢ phải thỏa)

```
SIGNAL BUY khi:
  ✅ Điều kiện 1: UPTREND (3 higher highs + 3 higher lows)
  ✅ Điều kiện 2: Giá chạm SUPPORT ZONE
  ✅ Điều kiện 3: Có nến ĐẢO CHIỀU (Hammer hoặc Bullish Engulfing)
  ✅ Điều kiện 4: XÁC NHẬN (MACD crossover HOẶC RSI > 50)
```

### Support Zone

```python
def _get_support_zone(self, atr: float) -> SupportZone:
    last_pivot_low = self.pivot_detector.get_last_pivot_low()
    width = 0.2 * atr  # Zone width = 20% ATR
    
    return SupportZone(
        pivot=last_pivot_low,
        zone_low=last_pivot_low.price - width,
        zone_high=last_pivot_low.price + width
    )
```

**Minh họa:**
```
Price
  │
  │     Zone High ─────────────────
  │         │                     │
  │         │   SUPPORT ZONE      │  (±0.2 * ATR)
  │         │                     │
  │     Zone Low ──────────────────
  │
  └──────────────────────────────▶ Time
              ▲
         Pivot Low
```

### Kiểm tra giá trong zone

```python
def contains_price(self, low: float, high: float) -> bool:
    """Kiểm tra giá có chạm zone không"""
    return not (high < self.zone_low or low > self.zone_high)
```

---

## 9. Tính Entry/SL/TP

### Entry
```
Entry = Giá đóng cửa của nến tín hiệu
```

### Stop Loss
```
SL = Previous Pivot Low - (0.05 * ATR)
```

Đặt SL dưới pivot low trước đó một khoảng buffer.

### Take Profit
```
Risk = Entry - SL
TP = Entry + (Risk * Risk_Reward_Ratio)
```

Với `Risk_Reward_Ratio = 2.0`:
```
TP = Entry + 2 * (Entry - SL)
```

**Ví dụ:**
```
Entry = 75,000
SL = 73,500
Risk = 75,000 - 73,500 = 1,500
TP = 75,000 + (2 * 1,500) = 78,000
```

### Trailing Stop (Move to Breakeven)

```python
def should_move_to_breakeven(self, current_high: float) -> bool:
    """Move SL lên Entry khi đạt 1R profit"""
    if self.stop_loss >= self.entry:
        return False  # Đã move rồi
    
    one_r_target = self.entry + self.risk
    return current_high >= one_r_target
```

---

## 10. Trading API (DNSE)

**File:** `src/adapters/trading_service.py`

### Authentication Flow

```
1. Login (username, password)
   └─▶ JWT Token (valid 8 hours)

2. Request OTP
   └─▶ OTP gửi qua email (valid 2 minutes)

3. Exchange OTP
   └─▶ Trading Token (valid 8 hours)
```

### API Endpoints

| Action | Method | URL |
|--------|--------|-----|
| Login | POST | `/auth-service/login` |
| Get OTP | GET | `/auth-service/api/email-otp` |
| Get Trading Token | POST | `/order-service/trading-token` |
| Get Accounts | GET | `/order-service/accounts` |
| Get Balance | GET | `/order-service/account-balances/{id}` |
| Place Order | POST | `/order-service/v2/orders` |
| Cancel Order | DELETE | `/order-service/v2/orders/{id}` |

### Place Order Request

```json
{
  "symbol": "VNM",
  "side": "NB",           // NB = Buy, NS = Sell
  "orderType": "LO",      // LO = Limit Order
  "price": 75000,
  "quantity": 100,
  "accountNo": "1234567890",
  "loanPackageId": 12345
}
```

---

## 11. Backtest Engine

**File:** `src/core/backtest.py`

### Flow

```
1. Load bars từ CSV
2. Replay từng bar qua Signal Engine
3. Khi có signal → mở position
4. Với mỗi bar mới:
   - Kiểm tra SL hit → đóng lỗ
   - Kiểm tra TP hit → đóng lời
   - Kiểm tra breakeven → move SL
5. Tính metrics cuối cùng
```

### CSV Format

```csv
time,open,high,low,close,volume
2024-01-02 09:00:00,75000,76000,74500,75500,150000
```

### Metrics tính toán

```python
@dataclass
class BacktestResult:
    total_trades: int
    winning_trades: int
    losing_trades: int
    
    total_pnl: float          # Tổng lãi/lỗ
    total_pnl_percent: float  # % lãi/lỗ
    
    max_drawdown: float       # Drawdown tối đa
    max_drawdown_percent: float
    
    win_rate: float           # Tỷ lệ thắng (%)
    profit_factor: float      # Tổng lời / Tổng lỗ
    average_win: float        # Trung bình lời
    average_loss: float       # Trung bình lỗ
```

---

## Tóm tắt tham số cấu hình

| Tham số | Mặc định | Mô tả |
|---------|----------|-------|
| RSI_PERIOD | 14 | Số periods tính RSI |
| MACD_FAST | 12 | EMA nhanh |
| MACD_SLOW | 26 | EMA chậm |
| MACD_SIGNAL | 9 | Signal line |
| ATR_PERIOD | 14 | Số periods tính ATR |
| ZONE_WIDTH_ATR_MULT | 0.2 | Độ rộng support zone |
| SL_BUFFER_ATR_MULT | 0.05 | Buffer dưới pivot cho SL |
| RISK_REWARD_RATIO | 2.0 | Tỷ lệ TP/SL |
| REQUIRED_PAIRS | 3 | Số cặp higher high/low cần có |

---

## Flowchart tổng quát

```
┌─────────────────────────────────────────────────────────────┐
│                      NEW BAR CLOSED                         │
└─────────────────────────────────────────────────────────────┘
                              │
                              ▼
┌─────────────────────────────────────────────────────────────┐
│               1. Detect Pivot Points                        │
│    (Kiểm tra bar trước có phải pivot không)                 │
└─────────────────────────────────────────────────────────────┘
                              │
                              ▼
┌─────────────────────────────────────────────────────────────┐
│               2. Calculate Indicators                       │
│              RSI, MACD, ATR từ closes                       │
└─────────────────────────────────────────────────────────────┘
                              │
                              ▼
┌─────────────────────────────────────────────────────────────┐
│               3. Check Conditions                           │
├─────────────────────────────────────────────────────────────┤
│  ✓ Uptrend? (3 higher lows + 3 higher highs)               │
│  ✓ Price in support zone?                                   │
│  ✓ Reversal pattern? (Hammer/Engulfing)                    │
│  ✓ Confirmation? (MACD cross OR RSI > 50)                  │
└─────────────────────────────────────────────────────────────┘
                              │
                    ┌─────────┴─────────┐
                    │                   │
              All TRUE             Any FALSE
                    │                   │
                    ▼                   ▼
        ┌───────────────────┐   ┌───────────────────┐
        │   CREATE SIGNAL   │   │    NO SIGNAL      │
        │                   │   │                   │
        │ Entry = Close     │   │   Log reasons     │
        │ SL = PrevLow-buf  │   │                   │
        │ TP = Entry + 2*R  │   │                   │
        └───────────────────┘   └───────────────────┘
                    │
                    ▼
        ┌───────────────────┐
        │  Save to DB       │
        │  Broadcast WS     │
        │  Auto-trade?      │
        └───────────────────┘
```

---

## Liên hệ

Nếu cần giải thích thêm logic nào, liên hệ backend team.
