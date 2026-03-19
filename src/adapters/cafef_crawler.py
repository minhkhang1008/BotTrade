import requests
from bs4 import BeautifulSoup

class CafeFAdvancedCrawler:
    def __init__(self):
        self.headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"
        }

    def fetch_homepage_news(self, limit=10):
        """[Mức 2] Cào tin vĩ mô từ RSS Trang chủ"""
        url = "https://cafef.vn/thi-truong-chung-khoan.rss"
        try:
            resp = requests.get(url, headers=self.headers, timeout=10)
            soup = BeautifulSoup(resp.content, "xml")
            items = soup.find_all("item")
            
            news_list = []
            for item in items[:limit]:
                news_list.append({
                    "title": item.title.text if item.title else "",
                    "link": item.link.text if item.link else "",
                    "type": "MACRO"
                })
            return news_list
        except Exception as e:
            print(f"❌ Lỗi cào tin vĩ mô: {e}")
            return []

    def fetch_ticker_news(self, symbol, limit=5):
        """[Mức 1] Cào tin sự kiện/doanh nghiệp đích danh mã cổ phiếu"""
        url = f"https://cafef.vn/du-lieu/hose/{symbol.lower()}-tin-tuc.chn"
        print(f"📡 Đang quét tin tức nội bộ mã {symbol.upper()}...")
        
        try:
            resp = requests.get(url, headers=self.headers, timeout=10)
            soup = BeautifulSoup(resp.content, "html.parser")
            
            # Trích xuất từ Box Tin Doanh nghiệp dựa trên cấu trúc DOM của CafeF
            news_items = soup.select(".list3box .tindn ul li a")
            if not news_items:
                news_items = soup.select("#companyinfo-box .item a")

            results = []
            for item in news_items[:limit]:
                title = item.get_text(strip=True)
                link = item.get("href", "")
                if not link.startswith("http"):
                    link = "https://cafef.vn" + link
                    
                if title and len(title) > 10:
                    results.append({
                        "symbol": symbol.upper(),
                        "title": title,
                        "link": link,
                        "type": "COMPANY_SPECIFIC"
                    })
            return results
        except Exception as e:
            print(f"❌ Lỗi cào tin mã {symbol}: {e}")
            return []

if __name__ == "__main__":
    crawler = CafeFAdvancedCrawler()
    
    print("📰 --- TIN ĐÍCH DANH (VIC) ---")
    for n in crawler.fetch_ticker_news("VIC", limit=3):
        print(f"[{n['symbol']}] {n['title']}")
        
    print("\n🌍 --- TIN VĨ MÔ ---")
    for n in crawler.fetch_homepage_news(limit=3):
        print(f"🗞️ {n['title']}")