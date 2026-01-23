#!/usr/bin/env python3
"""
Demo script to test API endpoints.
Usage: python scripts/test_api.py
"""
import requests
import json

BASE_URL = "http://localhost:8000"


def test_endpoint(method, path, data=None):
    """Test an API endpoint."""
    url = f"{BASE_URL}{path}"
    try:
        if method == "GET":
            resp = requests.get(url, timeout=5)
        elif method == "POST":
            resp = requests.post(url, json=data, timeout=5)
        elif method == "PUT":
            resp = requests.put(url, json=data, timeout=5)
        elif method == "DELETE":
            resp = requests.delete(url, timeout=5)
        
        print(f"\n{'='*50}")
        print(f"📡 {method} {path}")
        print(f"Status: {resp.status_code}")
        
        try:
            print(json.dumps(resp.json(), indent=2, ensure_ascii=False))
        except:
            print(resp.text[:200])
        
        return resp.status_code == 200
    except requests.exceptions.ConnectionError:
        print(f"❌ Cannot connect to {BASE_URL}")
        print("   Make sure the server is running: python -m src.main --mock")
        return False


def main():
    print("\n" + "="*50)
    print("🧪 BOT TRADE - API TEST")
    print("="*50)
    
    tests = [
        ("GET", "/api/v1/health"),
        ("GET", "/api/v1/symbols"),
        ("GET", "/api/v1/settings"),
        ("GET", "/api/v1/signals"),
        ("GET", "/api/v1/trading/status"),
    ]
    
    passed = 0
    for method, path in tests:
        if test_endpoint(method, path):
            passed += 1
    
    print("\n" + "="*50)
    print(f"✅ Passed: {passed}/{len(tests)}")
    print("="*50 + "\n")


if __name__ == "__main__":
    main()
