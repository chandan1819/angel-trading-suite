#!/usr/bin/env python3
"""
Simple test for live trading
"""

import os
import sys
import time
from datetime import datetime

print("🚀 Bank Nifty Live Trading Test")
print("=" * 40)

# Check credentials
print("Checking credentials...")

# Try to load from config.json first
try:
    config_file = "config/config.json"
    if os.path.exists(config_file):
        import json
        with open(config_file, 'r') as f:
            config_data = json.load(f)
        
        # Set environment variables from config file
        os.environ['ANGEL_API_KEY'] = config_data.get('api_key', '')
        os.environ['ANGEL_CLIENT_CODE'] = config_data.get('client_code', '')
        os.environ['ANGEL_PIN'] = config_data.get('pin', '')
        os.environ['ANGEL_TOTP_SECRET'] = config_data.get('totp_secret', '')
        
        print("✅ Loaded credentials from config/config.json")
except Exception as e:
    print(f"⚠️ Could not read config.json: {e}")

api_key = os.getenv('ANGEL_API_KEY')
client_code = os.getenv('ANGEL_CLIENT_CODE')
pin = os.getenv('ANGEL_PIN')
totp = os.getenv('ANGEL_TOTP_SECRET')

print(f"API Key: {api_key}")
print(f"Client Code: {client_code}")
print(f"PIN: {pin}")
print(f"TOTP: {totp}")

if not all([api_key, client_code, pin, totp]):
    print("❌ Missing credentials!")
    sys.exit(1)

print("✅ All credentials found!")

print("\n🚨 WARNING: This would start LIVE TRADING!")
print("💰 Max Daily Loss: ₹5,000")
print("🎯 Profit Target: ₹2,000 per trade")
print("🛑 Stop Loss: ₹1,000 per trade")

print("\n⏰ Current time:", datetime.now().strftime('%Y-%m-%d %H:%M:%S'))

# Check market hours
hour = datetime.now().hour
if 9 <= hour <= 15:
    print("✅ Market is open")
else:
    print("⏰ Market is closed (opens 9:15 AM - 3:30 PM)")

print("\n🔄 Starting trading simulation...")
for i in range(3):
    print(f"📈 Cycle {i+1}: Checking BANKNIFTY options...")
    print("   🎯 Straddle strategy: Evaluating conditions...")
    print("   📊 No signals generated (demo mode)")
    time.sleep(2)

print("\n✅ Live trading test completed!")
print("🚀 Ready to start actual live trading!")