# 🚀 Hướng dẫn Cài đặt và Sử dụng BotTrade


## 🛠 I. Cài đặt Hệ thống

### Bước 1: Tải mã nguồn dự án

Mở terminal và chạy lệnh sau để tải toàn bộ mã nguồn về máy:

```bash
git clone https://github.com/minhkhang1008/BotTrade.git
cd BotTrade

```

### Bước 2: Cài đặt Backend (Python)

Hệ thống yêu cầu tạo môi trường ảo (virtual environment) để cài đặt các thư viện cần thiết.

```bash
# 1. Tạo môi trường ảo
python3 -m venv venv

# 2. Kích hoạt môi trường ảo
# Đối với macOS/Linux:
source venv/bin/activate

# Đối với Windows (Command Prompt / PowerShell):
# venv\Scripts\activate hoặc .\venv\Scripts\Activate.ps1

# 3. Cài đặt các thư viện phụ thuộc
pip install -r requirements.txt

```

### Bước 3: Cấu hình Biến môi trường

Bạn cần tạo file `.env` từ file mẫu để cấu hình các thông số cho bot.

```bash
# Đối với macOS/Linux:
cp .env.example .env

# Đối với Windows:
copy .env.example .env

```

👉 **Lưu ý:** Mở file `.env` vừa tạo và điền/chỉnh sửa các thông tin tài khoản, cấu hình cần thiết trước khi chạy bot.

### Bước 4: Khởi chạy Backend

Khởi động máy chủ xử lý tín hiệu:

```bash
python run.py

```

### Bước 5: Cài đặt và Khởi chạy Frontend (Giao diện người dùng)

Mở một **Terminal (Cửa sổ dòng lệnh) mới**, di chuyển vào thư mục giao diện và tiến hành cài đặt:

```bash
# 1. Di chuyển vào thư mục UI
cd bottrade-ui

# 2. Cài đặt các thư viện Node.js
npm install

# 3. Khởi chạy giao diện web
npm run dev

```

🎉 **Hoàn tất cài đặt!** Mở trình duyệt và truy cập vào đường dẫn: [http://localhost:5173/](https://www.google.com/search?q=http://localhost:5173/) để xem giao diện.

---

## ⚙️ II. Hướng dẫn Cấu hình trên Giao diện

Để bot bắt đầu theo dõi thị trường, bạn cần thiết lập danh sách mã cổ phiếu:

1. Tại giao diện web, truy cập vào mục **Settings (Cài đặt)**.
2. Tìm đến phần **Watchlist**, nhập tên các mã cổ phiếu bạn muốn bot theo dõi (Ví dụ: `VIC`, `VNM`, `FPT`).
* *Lưu ý: Bot hiện tại chỉ hỗ trợ dữ liệu từ các sàn chứng khoán Việt Nam.*


3. Bấm **Save Changes** để lưu cấu hình. Bot sẽ tự động cập nhật và bắt đầu quét dữ liệu.

---

## 🧪 III. Chế độ Mô phỏng (Mock Mode)

Nếu bạn muốn trải nghiệm, test thử UI hoặc xem cụ thể mọi quy trình bot hoạt động sinh ra tín hiệu như thế nào mà không cần chờ đợi thị trường thật, hãy sử dụng chế độ Mô phỏng:

1. Dừng Backend hiện tại (Bấm `Ctrl + C` tại terminal đang chạy Python).
2. Khởi chạy lại Backend với cờ `--mock`:
```bash
python run.py --mock

```


3. Mở giao diện web, truy cập mục **Settings**.
4. Mở tính năng **Demo Scenario** để kích hoạt các kịch bản thị trường giả lập, cho phép bạn quan sát bot tính toán và ra lệnh trực quan nhất.

--- 

## 🔗 IV. Lấy các thông tin cấu hình .env ở đâu

1. DNSE_USERNAME & DNSE_PASSWORD: Đăng ký sử dụng Lightspeed API tại: [https://entradex.dnse.com.vn/thong-tin-ca-nhan/light-speed](https://entradex.dnse.com.vn/thong-tin-ca-nhan/light-speed) và sử dụng username (email/sđt) và password đăng nhập EntradeX
2. Telegram BotID: Tạo bot mới tại [@BotFather](https://web.telegram.org/a/#93372553), gõ lệnh /token, chọn Bot vừa tạo và copy token 
3. Telegram ChatID: Sử dụng bot [@userinfobot](https://web.telegram.org/a/#52504489) và gõ lệnh /start sau đó copy phần id
