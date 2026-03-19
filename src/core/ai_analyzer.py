"""
Bot Trade - AI News Analyzer (2-Step Pipeline)
Sử dụng API trực tiếp từ Google AI Studio (Gemini 2.0 Flash)

Step 1: Filter titles - batch-send all titles to AI, get back which articles matter.
Step 2: Analyze article - send full article content, AI decides affected stocks and scores.
Step 3: Aggregate - Combine scores safely to avoid noise accumulation.
"""
import json
import logging
import os
import requests

logger = logging.getLogger("crawler")
if not logger.handlers:
    logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

# Tên model chuẩn của Google AI Studio
DEFAULT_MODEL = "gemini-2.0-flash"

class AIAnalyzer:
    def __init__(self, api_key: str = None, model: str = None):
        # Lấy Key từ biến GEMINI_API_KEY thay vì OPENROUTER
        self.api_key = api_key or os.getenv("GEMINI_API_KEY")
        if not self.api_key:
            raise ValueError("Missing GEMINI_API_KEY environment variable. Lấy key tại: https://aistudio.google.com/")

        self.model_name = model or os.getenv("AI_MODEL", DEFAULT_MODEL)
        self.api_url = f"https://generativelanguage.googleapis.com/v1beta/models/{self.model_name}:generateContent?key={self.api_key}"

    def _call_ai(self, system_prompt: str, user_message: str) -> dict | None:
        """Gửi request tới Google Gemini API và nhận về JSON chuẩn."""
        headers = {
            "Content-Type": "application/json",
        }
        
        # Cấu trúc Payload chuẩn của Google API
        payload = {
            "system_instruction": {
                "parts": [{"text": system_prompt}]
            },
            "contents": [
                {
                    "parts": [{"text": user_message}]
                }
            ],
            "generationConfig": {
                "temperature": 0.1,  # Ép AI trả lời logic, không bay bổng
                "response_mime_type": "application/json" # Google hỗ trợ ép xuất JSON natively
            }
        }

        try:
            resp = requests.post(self.api_url, headers=headers, json=payload, timeout=45)
            
            # Bắt lỗi HTTP (VD: sai API key, quá rate limit)
            resp.raise_for_status() 
            result_data = resp.json()
            
            # Kiểm tra xem AI có bị chặn bởi bộ lọc an toàn (safety ratings) không
            if "candidates" not in result_data or not result_data["candidates"]:
                logger.error(f"Gemini API không trả về kết quả (Có thể do lỗi chặn nội dung). Raw: {result_data}")
                return None

            # Rút trích text trực tiếp (chắc chắn là JSON nhờ response_mime_type)
            raw_text = result_data['candidates'][0]['content']['parts'][0]['text']
            return json.loads(raw_text)
                
        except requests.exceptions.RequestException as e:
            logger.error(f"Lỗi kết nối Google API: {e}")
            if hasattr(e, 'response') and e.response is not None:
                logger.error(f"Chi tiết lỗi từ Google: {e.response.text}")
            return None
        except json.JSONDecodeError as e:
            logger.error(f"Lỗi Parse JSON: {e}. Raw Text: {raw_text}")
            return None
        except (KeyError, IndexError) as e:
            logger.error(f"Cấu trúc response từ Google không chuẩn: {e}")
            return None

    # ── Bước 1: Lọc tiêu đề (Filter Titles) ──────────────────────────────

    def filter_titles(self, articles: list[dict]) -> list[dict]:
        if not articles:
            return []

        numbered = "\n".join(
            f"{i+1}. [{a.get('source', 'Unknown')}] {a.get('title', '')}"
            for i, a in enumerate(articles)
        )

        system_prompt = (
            "Bạn là chuyên gia lọc tin tức chứng khoán Việt Nam.\n"
            "Dưới đây là danh sách tiêu đề bài báo. Hãy chọn ra tối đa 8 bài có khả năng "
            "tác động mạnh đến giá cổ phiếu, doanh nghiệp hoặc kinh tế vĩ mô.\n\n"
            "BẮT BUỘC TRẢ VỀ JSON THEO ĐÚNG CẤU TRÚC SAU:\n"
            "{\n"
            '  "selected": [1, 3, 7]\n'
            "}\n"
            "(Trong đó 'selected' chứa số thứ tự các bài được chọn. Nếu không chọn được, để mảng rỗng [])."
        )

        user_message = f"Danh sách tiêu đề:\n{numbered}"

        logger.info(f"Bước 1: AI đang lọc {len(articles)} tiêu đề bài báo...")
        result = self._call_ai(system_prompt, user_message)

        if result and isinstance(result, dict) and "selected" in result:
            selected_indices = result["selected"]
            selected_articles = []
            for idx in selected_indices:
                if isinstance(idx, int) and 1 <= idx <= len(articles):
                    selected_articles.append(articles[idx - 1])
            
            logger.info(f"Bước 1: AI đã giữ lại {len(selected_articles)} bài báo tiềm năng.")
            return selected_articles

        logger.warning("Bước 1: AI thất bại, sử dụng thuật toán lọc dự phòng (fallback).")
        return self._fallback_select(articles)

    def _fallback_select(self, articles: list[dict], limit=5) -> list[dict]:
        priority_order = ["chung-khoan", "vi-mo", "ngan-hang", "kinh-doanh"]
        selected = []
        for source in priority_order:
            for a in articles:
                if a.get("source") == source and a not in selected:
                    selected.append(a)
                    if len(selected) >= limit:
                        return selected
        for a in articles:
            if a not in selected:
                selected.append(a)
                if len(selected) >= limit:
                    break
        return selected

    # ── Bước 2: Phân tích chi tiết (Analyze Article) ────────────────────

    def analyze_article(self, content: str, title: str, watchlist: list[str]) -> dict | None:
        if not content or not watchlist:
            return None

        watchlist_str = ", ".join(watchlist)

        system_prompt = (
            "Bạn là Giám đốc rủi ro quỹ đầu tư chứng khoán Việt Nam cực kỳ khắt khe.\n"
            "Nhiệm vụ: Đánh giá tác động THỰC TẾ của bài báo đến các mã cổ phiếu.\n\n"
            "BẮT BUỘC TRẢ VỀ JSON:\n"
            "{\n"
            '  "impacts": [\n'
            '    {"symbol": "MÃ", "score": 0, "reason": "lý do"}\n'
            '  ]\n'
            "}\n\n"
            "THANG ĐIỂM NGHIÊM NGẶT (-3 đến +3):\n"
            "- Mặc định: 0 điểm (Tin PR, tin chung chung, kế hoạch chưa thực tế, tin đã phản ánh vào giá).\n"
            "- Điểm +/- 1: Tác động nhỏ, có thật (Trúng thầu nhỏ, LN tăng/giảm nhẹ).\n"
            "- Điểm +/- 2: Tác động lớn, CÓ SỐ LIỆU (LN đột biến >50%, dự án lớn, chia cổ tức cao).\n"
            "- Điểm +/- 3: Tác động thay đổi cục diện (Phá sản, M&A lớn, thay đổi chính sách trọng yếu).\n\n"
            "QUY TẮC:\n"
            "- KHÔNG cho điểm cộng với tin 'bánh vẽ'. Hãy nghi ngờ.\n"
            "- CHỈ liệt kê mã có trong danh sách theo dõi và có score KHÁC 0.\n"
            "- Trả về impacts: [] nếu không có tác động rõ rệt."
        )

        user_message = (
            f"Danh sách theo dõi: [{watchlist_str}]\n\n"
            f"Tiêu đề: {title}\n\n"
            f"Nội dung:\n{content}"
        )

        logger.info(f"Bước 2: AI đang phân tích bài: {title[:60]}...")
        result = self._call_ai(system_prompt, user_message)

        if result and isinstance(result, dict) and "impacts" in result:
            valid_impacts = []
            for impact in result.get("impacts", []):
                sym = str(impact.get("symbol", "")).upper()
                score = impact.get("score", 0)
                
                if sym in watchlist and isinstance(score, (int, float)) and score != 0:
                    valid_impacts.append({
                        "symbol": sym,
                        "score": int(score),
                        "reason": str(impact.get("reason", "")),
                    })

            if valid_impacts:
                logger.info(f"  -> Phát hiện tác động: {[(i['symbol'], i['score']) for i in valid_impacts]}")
            else:
                logger.info("  -> Không có tác động đáng kể đến danh mục.")

            return {"impacts": valid_impacts}

        logger.warning(f"Bước 2: Phân tích lỗi hoặc sai định dạng: {title[:60]}")
        return None

    # ── Bước 3: Tổng hợp điểm số (Chống nhiễu) ──────────────────────────

    def aggregate_sentiment(self, impact_scores: list[int], strategy: str = "max_impact") -> float:
        if not impact_scores:
            return 0.0
            
        if strategy == "average":
            return sum(impact_scores) / len(impact_scores)
            
        elif strategy == "max_impact":
            max_positive = max(impact_scores)
            max_negative = min(impact_scores)
            if abs(max_negative) >= abs(max_positive):
                return float(max_negative)
            return float(max_positive)
            
        return 0.0

# ── Code Test Nhanh ─────────────
if __name__ == "__main__":
    os.environ["GEMINI_API_KEY"] = "ĐIỀN_API_KEY_CỦA_BẠN_VÀO_ĐÂY" 
    try:
        analyzer = AIAnalyzer()
        print("Đã khởi tạo AIAnalyzer kết nối với Google API thành công!")
        
        # Test nhẹ Bước 1
        fake_articles = [
            {"title": "VN-Index vượt 1300 điểm", "source": "chung-khoan"},
            {"title": "Quán phở ngon nhất Hà Nội", "source": "doi-song"},
            {"title": "FPT lãi kỷ lục trong quý 3", "source": "kinh-doanh"}
        ]
        res = analyzer.filter_titles(fake_articles)
        print(f"Bài được chọn: {[a['title'] for a in res]}")
        
    except ValueError as e:
        print(f"Lỗi khởi tạo: {e}")