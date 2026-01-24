#!/usr/bin/env python3
"""
Quick test for DNSE adapter connection.
"""
import logging
import time

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s"
)

from src.config import settings
from src.adapters.dnse_adapter import DNSEAdapter, DNSEConfig

bars_received = []

def on_bar(bar):
    print(f'📊 BAR: {bar.symbol} | Time: {bar.timestamp} | O:{bar.open} H:{bar.high} L:{bar.low} C:{bar.close} V:{bar.volume}')
    bars_received.append(bar)

def main():
    config = DNSEConfig(
        username=settings.dnse_username,
        password=settings.dnse_password,
        mqtt_url=settings.dnse_mqtt_url
    )

    adapter = DNSEAdapter(
        config=config,
        on_bar_closed=on_bar,
        on_connected=lambda: print('✅ CONNECTED to DNSE!'),
        on_disconnected=lambda: print('❌ DISCONNECTED from DNSE!')
    )

    print('🔄 Connecting to DNSE...')
    adapter.connect(['VNM', 'FPT'], '1H')

    for i in range(10):
        time.sleep(1)
        print(f'⏳ Waiting... {i+1}/10, connected={adapter.is_connected}, bars_received={len(bars_received)}')
        if len(bars_received) >= 2:
            break

    adapter.disconnect()
    print(f'✅ Done! Received {len(bars_received)} bars')

if __name__ == "__main__":
    main()
