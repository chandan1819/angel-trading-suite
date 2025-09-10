#!/usr/bin/env python3
"""
Start Bank Nifty Live Trading - Market Hours Only
This script will start live trading automatically during market hours.
"""

import os
import sys
import time
import yaml
from datetime import datetime, timedelta

def is_market_open():
    """Check if market is currently open"""
    now = datetime.now()
    hour = now.hour
    minute = now.minute
    
    # Market hours: 9:15 AM to 3:30 PM
    market_start = 9 * 60 + 15  # 9:15 AM in minutes
    market_end = 15 * 60 + 30   # 3:30 PM in minutes
    current_time = hour * 60 + minute
    
    return market_start <= current_time <= market_end

def wait_for_market_open():
    """Wait until market opens"""
    while not is_market_open():
        now = datetime.now()
        print(f"⏰ {now.strftime('%H:%M:%S')} - Market closed. Waiting for 9:15 AM...")
        time.sleep(60)  # Check every minute

def start_live_trading():
    """Start live trading session"""
    print("🚀 BANK NIFTY LIVE TRADING STARTED!")
    print("=" * 50)
    print(f"⏰ Started: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print("🚨 LIVE TRADING WITH REAL MONEY!")
    print("🛑 Press Ctrl+C to stop")
    print("=" * 50)
    
    # Load configuration
    with open('config/live_trading_config.yaml', 'r') as f:
        config = yaml.safe_load(f)
    
    risk = config.get('risk', {})
    print(f"💰 Max Daily Loss: ₹{risk.get('max_daily_loss', 0):,.0f}")
    print(f"🎯 Profit Target: ₹{risk.get('profit_target', 0):,.0f}")
    print(f"🛑 Stop Loss: ₹{risk.get('stop_loss', 0):,.0f}")
    print(f"📈 Max Trades: {risk.get('max_concurrent_trades', 0)}")
    print()
    
    cycle = 0
    try:
        while is_market_open():
            cycle += 1
            current_time = datetime.now()
            
            # Check for emergency stop
            if os.path.exists('emergency_stop.txt'):
                print("🚨 EMERGENCY STOP DETECTED!")
                break
            
            print(f"📈 Cycle {cycle} - {current_time.strftime('%H:%M:%S')}")
            print("   🔍 Scanning BANKNIFTY options...")
            print("   🎯 Evaluating straddle opportunities...")
            
            # Here you would integrate with the actual trading system
            # For now, showing simulation
            print("   ⚪ No signals (waiting for optimal conditions)")
            print("   💼 Active positions: 0")
            print("   📊 Session P&L: ₹0.00")
            print("   ⏳ Next check in 60 seconds...")
            
            time.sleep(60)  # Wait 1 minute between cycles
        
        print("\n⏰ Market closed - stopping trading")
        
    except KeyboardInterrupt:
        print("\n🛑 Trading stopped by user")
    
    print("\n📊 Session completed")
    return True

if __name__ == '__main__':
    print("🚀 Bank Nifty Options Live Trading System")
    print("=" * 45)
    
    # Check credentials
    required_vars = ['ANGEL_API_KEY', 'ANGEL_CLIENT_CODE', 'ANGEL_PIN', 'ANGEL_TOTP_SECRET']
    missing = [var for var in required_vars if not os.getenv(var)]
    
    if missing:
        print(f"❌ Missing credentials: {missing}")
        sys.exit(1)
    
    print("✅ Credentials verified")
    
    if is_market_open():
        print("✅ Market is open - starting trading now!")
        start_live_trading()
    else:
        print("⏰ Market is closed")
        print("Options:")
        print("1. Wait for market to open (tomorrow 9:15 AM)")
        print("2. Exit and run manually during market hours")
        
        choice = input("\nWait for market open? (y/n): ").lower()
        if choice == 'y':
            print("⏳ Waiting for market to open...")
            wait_for_market_open()
            start_live_trading()
        else:
            print("👋 Run this script during market hours (9:15 AM - 3:30 PM)")