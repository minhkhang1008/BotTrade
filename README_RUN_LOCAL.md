# Running BotTrade locally (backend + frontend)

This document explains how to run the BotTrade backend (FastAPI) and frontend (Vite) on your local Windows machine.

IMPORTANT: Do NOT commit secrets. Put real credentials only in `BotTrade/.env` on your local machine and never push it.

Recommended approach (Windows): use Miniconda/Anaconda to avoid building heavy wheels (numpy/pandas).

## **Hướng dẫn chạy BotTrade (Backend + Frontend) — Windows PowerShell**

- **Mục tiêu**: Sau khi clone repo, người khác chỉ cần làm theo các bước dưới đây để cài đặt và chạy local (backend FastAPI + frontend Vite). Hướng dẫn tập trung cho Windows PowerShell.

**Yêu cầu trước khi bắt đầu**
- **Python**: 3.11 (khuyến nghị) — dùng `py -3.11` nếu có nhiều phiên bản.
- **Node.js & npm**: Node 18+ (hiện tại Node 24 hoạt động). Kiểm tra `node -v` và `npm -v`.
- **Git**
- **(Tùy chọn nhưng khuyến nghị)**: Miniconda/Anaconda — giúp cài `numpy`/`pandas` nhanh và tránh phải build từ source trên Windows.

**Tổng quan luồng chạy**
- Backend (FastAPI) nằm ở `BotTrade/src` và dùng SQLite local (`bottrade.db`).
- Frontend (React + Vite) nằm ở `BotTrade/bottrade-ui`.
- Có một mock API/WS server trong `bottrade-ui/mock-server.js` để chạy UI mà không cần backend Python.

---

## **1) Cách nhanh (khuyến nghị): dùng Miniconda)**
Nếu bạn có Miniconda, làm theo các bước sau:

```powershell
# 1. Clone repo (nếu chưa)
# git clone <repo-url>
# cd <repo-folder>/BotTrade

conda create -n bottrade python=3.11 -y
conda activate bottrade

# Tùy chọn: cài numpy/pandas bằng conda (nếu bạn muốn dùng pandas trong dev)
conda install -c conda-forge pandas numpy -y

# Cài các package pip của backend
pip install --upgrade pip
pip install -r requirements.txt

# Frontend: cài npm deps
cd bottrade-ui
npm install
cd ..

# Khởi backend ở chế độ MOCK (an toàn, không cần credentials)
# dùng python module (đảm bảo đang ở thư mục BotTrade)
python -m src.main --mock

# Khởi frontend (vào folder bottrade-ui)
cd bottrade-ui
npm run mock   # khởi mock API/WS (port mặc định 8001)
npm run dev    # khởi Vite dev server (http://localhost:5173)
```

Ghi chú: script `start-dev.ps1` (nếu có) có thể tự động hóa một số bước.

---

## **2) Cách không dùng conda — tạo virtualenv (PowerShell)**
```powershell
cd D:\...\BotTrade

# Tạo virtualenv (Python 3.11 được cài sẵn trên máy)
py -3.11 -m venv .venv
Set-ExecutionPolicy -Scope Process -ExecutionPolicy Bypass -Force
& .\.venv\Scripts\Activate.ps1
pip install --upgrade pip

# Nếu pip cố build numpy/pandas trên Windows sẽ tốn thời gian/cần công cụ biên dịch.
# Nếu muốn tránh việc build này, cài pandas/numpy bằng Miniconda, hoặc comment chúng trong requirements.txt.
pip install -r requirements.txt

# Chạy backend (mock):
python -m src.main --mock

# Hoặc chạy uvicorn trực tiếp:
python -m uvicorn src.main:app --app-dir D:\path\to\BotTrade --host 127.0.0.1 --port 8001

# Frontend (mở terminal mới):
cd bottrade-ui
npm install
npm run mock
npm run dev
```

---

## **3) Chạy chỉ frontend (dùng mock API)**
Nếu bạn chỉ muốn chạy giao diện mà không phụ thuộc backend Python, frontend có sẵn mock server.

```powershell
cd BotTrade\bottrade-ui
npm install
npm run mock   # mock API + WS (port 8001)
npm run dev

# Mở browser: http://localhost:5173
```

---

## **4) Biến môi trường (env files)**
- Backend: tạo file `BotTrade/.env` (không commit) để đặt các biến sau (ví dụ):

```
DNSE_USERNAME=
DNSE_PASSWORD=
DNSE_ACCOUNT_NO=
WATCHLIST=VNM,FPT,VIC
TIMEFRAME=1H
HOST=0.0.0.0
PORT=8001
AUTO_TRADE_ENABLED=False
```

- Frontend: nếu cần tùy chỉnh endpoint, tạo `bottrade-ui/.env` và dùng tiền tố `VITE_`:

```
VITE_API_URL=http://localhost:8001
VITE_WS_URL=ws://localhost:8001/ws/v1/stream
```

---

## **5) Kiểm tra sau khi chạy**
- Frontend: `http://localhost:5173` (hoặc port Vite báo ra)
- Mock API (nếu dùng): `http://localhost:8001`
- Backend (uvicorn): `http://127.0.0.1:8001/docs` — Swagger UI

---

## **6) Chạy test (backend)**
```powershell
cd BotTrade
& .\.venv\Scripts\Activate.ps1   # hoặc activate conda env
pytest -q
```

---

## **7) Vấn đề thường gặp & cách khắc phục**
- **Lỗi khi pip cài `pydantic-core` trên Python quá mới (cần Rust/Cargo hoặc wheel)**: dùng Python 3.11 hoặc cài Rust + Visual C++ Build Tools. Khuyến nghị: dùng Python 3.11 để có wheel prebuilt.
- **Lỗi build `numpy`/`pandas` trên Windows**: cài `numpy`/`pandas` bằng `conda install -c conda-forge numpy pandas` hoặc cài Visual C++ Build Tools (khó hơn).
- **Port đã bị chiếm**: kiểm tra `Get-NetTCPConnection -LocalPort 8001` và dừng tiến trình chiếm cổng.
- **WebSocket không kết nối**: kiểm tra URL WS trong `bottrade-ui/src/useWebSocket.ts` hoặc `VITE_WS_URL` và kiểm tra CORS/backend chạy.

---

## **8) Lưu ý về Auto-trade / bảo mật**
- Mặc định `AUTO_TRADE_ENABLED` = `False`. Không bật trên môi trường local nếu bạn không muốn bot đặt lệnh thật.
- Nếu bật Auto-trade, cần cung cấp `DNSE_USERNAME`, `DNSE_PASSWORD`, `DNSE_ACCOUNT_NO` trong `BotTrade/.env`.

---

Nếu bạn muốn, tôi có thể (chọn một):
- cập nhật `README.md` gốc bằng phiên bản ngắn gọn này,
- hoặc tạo một script PowerShell `start-dev.ps1` tự động hóa các bước (venv/conda, cài deps, khởi backend/frontend).

Chỉ định lựa chọn bạn muốn tôi làm tiếp — hoặc tôi có thể commit file README vừa tạo và gửi hướng dẫn push lên GitHub cho bạn.
