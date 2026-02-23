#!/usr/bin/env python3
"""
Bot Trade - Entry Point
Run this file to start the trading bot.

Usage:
    python run.py          # Normal mode
    python run.py --mock   # Demo/mock mode
"""
import sys
import os

# Add project root to path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))


def main():
    """Main entry point."""
    import uvicorn
    from src.config import settings
    
    print("\n" + "="*50)
    print("🤖 BOT TRADE - Trading Signal Assistant")
    print("="*50)
    print(f"Symbols: {settings.watchlist_symbols}")
    print(f"Timeframe: {settings.timeframe}")
    print("="*50 + "\n")
    
    # Check for mock mode from command line
    use_mock = "--mock" in sys.argv
    
    # Set environment variable so the app knows about mock mode
    if use_mock:
        os.environ["BOT_TRADE_MOCK_MODE"] = "true"
        print("🧪 MOCK MODE ENABLED")
        print("📁 Using separate database: bottrade_demo.db")
    
    # Run API server - import the app from src.main
    # This way src.main is only loaded once by uvicorn
    uvicorn.run(
        "src.main:app",
        host=settings.host,
        port=settings.port,
        reload=False,
        log_level="info"
    )


if __name__ == "__main__":
    main()
