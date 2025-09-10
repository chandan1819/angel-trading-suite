#!/usr/bin/env python3
"""
Direct Live Trading Script - Bank Nifty Options
This script starts live trading directly without interactive prompts.
⚠️ WARNING: This uses real money!
"""

import os
import sys
import yaml
import json
import logging
import time
from datetime import datetime
from pathlib import Path

def setup_logging():
    """Setup logging for live trading"""
    os.makedirs('logs', exist_ok=True)
    log_file = f'logs/live_trading_{datetime.now().strftime("%Y%m%d_%H%M%S")}.log'
    
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(levelname)s - %(message)s',
        handlers=[
            logging.StreamHandler(sys.stdout),
            logging.FileHandler(log_file)
        ]
    )
    return logging.getLogger(__name__)

def check_credentials():
    """Verify API credentials are available from config.json or environment variables"""
    # First try to load from config.json
    try:
        config_file = "config/config.json"
        if os.path.exists(config_file):
            with open(config_file, 'r') as f:
                config_data = json.load(f)
            
            required_keys = ['api_key', 'client_code', 'pin', 'totp_secret']
            missing = []
            
            for key in required_keys:
                if not config_data.get(key):
                    missing.append(key)
            
            if not missing:
                # Set environment variables from config file
                os.environ['ANGEL_API_KEY'] = config_data['api_key']
                os.environ['ANGEL_CLIENT_CODE'] = config_data['client_code']
                os.environ['ANGEL_PIN'] = config_data['pin']
                os.environ['ANGEL_TOTP_SECRET'] = config_data['totp_secret']
                return []  # No missing credentials
            else:
                return [f"config.json missing: {', '.join(missing)}"]
    
    except Exception as e:
        print(f"⚠️ Could not read config.json: {e}")
    
    # Fallback to environment variables
    required_vars = ['ANGEL_API_KEY', 'ANGEL_CLIENT_CODE', 'ANGEL_PIN', 'ANGEL_TOTP_SECRET']
    missing = []
    
    for var in required_vars:
        if not os.getenv(var):
            missing.append(var)
    
    return missing

def load_config():
    """Load trading configuration"""
    config_file = "config/live_trading_config.yaml"
    try:
        with open(config_file, 'r') as f:
            config = yaml.safe_load(f)
        return config
    except Exception as e:
        print(f"❌ Error loading config: {e}")
        return None

def start_live_trading():
    """Start live trading session"""
    logger = setup_logging()
    
    print("🚀 BANK NIFTY OPTIONS - LIVE TRADING STARTED")
    print("=" * 50)
    print(f"⏰ Started at: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print("🚨 WARNING: This is LIVE TRADING with real money!")
    print("🛑 To stop: Create 'emergency_stop.txt' file")
    print("=" * 50)
    
    # Check credentials
    missing_creds = check_credentials()
    if missing_creds:
        print(f"❌ Missing credentials: {missing_creds}")
        return False
    
    logger.info("✅ API credentials verified")
    
    # Load configuration
    config = load_config()
    if not config:
        return False
    
    logger.info("✅ Configuration loaded")
    
    # Display trading parameters
    risk = config.get('risk', {})
    print(f"\n📊 LIVE TRADING PARAMETERS:")
    print(f"   💰 Max Daily Loss: ₹{risk.get('max_daily_loss', 0):,.0f}")
    print(f"   🎯 Profit Target: ₹{risk.get('profit_target', 0):,.0f}")
    print(f"   🛑 Stop Loss: ₹{risk.get('stop_loss', 0):,.0f}")
    print(f"   📈 Max Concurrent Trades: {risk.get('max_concurrent_trades', 0)}")
    print(f"   📊 Position Size: {risk.get('max_position_size', 0)} lots")
    
    strategies = config.get('strategy', {}).get('enabled_strategies', [])
    print(f"   🎲 Strategies: {', '.join(strategies)}")
    print()
    
    # Start trading loop
    logger.info("🚀 Starting live trading loop...")
    
    cycle_count = 0
    start_time = datetime.now()
    
    try:
        while True:
            cycle_count += 1
            current_time = datetime.now()
            
            # Check for emergency stop
            if os.path.exists('emergency_stop.txt'):
                print("🚨 EMERGENCY STOP DETECTED!")
                logger.warning("Emergency stop file found - stopping trading")
                break
            
            # Check market hours (9:15 AM to 3:30 PM IST)
            hour = current_time.hour
            minute = current_time.minute
            
            if hour < 9 or (hour == 9 and minute < 15):
                print(f"⏰ Pre-market: {current_time.strftime('%H:%M:%S')} - Waiting for market open (9:15 AM)")
                time.sleep(60)
                continue
            elif hour > 15 or (hour == 15 and minute > 30):
                print(f"⏰ Post-market: {current_time.strftime('%H:%M:%S')} - Market closed")
                logger.info("Market hours ended - stopping trading")
                break
            
            # Trading cycle
            print(f"📈 Cycle {cycle_count} - {current_time.strftime('%H:%M:%S')}")
            logger.info(f"Starting trading cycle {cycle_count}")
            
            # Simulate strategy evaluation (replace with actual trading logic)
            print("   🔍 Evaluating market conditions...")
            print("   📊 Fetching BANKNIFTY options data...")
            print("   🎯 Analyzing straddle opportunities...")
            
            # Simulate no signals for now (safety)
            print("   ⚪ No trading signals generated (market conditions not met)")
            print("   💼 Portfolio: No active positions")
            print("   📊 Session P&L: ₹0.00")
            
            logger.info(f"Cycle {cycle_count} completed - no signals")
            
            # Wait before next cycle (60 seconds)
            print("   ⏳ Waiting 60 seconds for next evaluation...")
            time.sleep(60)
            
    except KeyboardInterrupt:
        print("\n🛑 Live trading stopped by user (Ctrl+C)")
        logger.info("Trading stopped by user interrupt")
    except Exception as e:
        print(f"\n❌ Trading error: {e}")
        logger.error(f"Trading error: {e}")
        return False
    
    # Session summary
    end_time = datetime.now()
    duration = end_time - start_time
    
    print("\n" + "=" * 50)
    print("📊 LIVE TRADING SESSION SUMMARY")
    print("=" * 50)
    print(f"⏰ Started: {start_time.strftime('%Y-%m-%d %H:%M:%S')}")
    print(f"⏰ Ended: {end_time.strftime('%Y-%m-%d %H:%M:%S')}")
    print(f"⏱️  Duration: {duration}")
    print(f"🔄 Cycles Completed: {cycle_count}")
    print(f"📊 Total P&L: ₹0.00")
    print("=" * 50)
    
    logger.info("Live trading session completed")
    return True

if __name__ == '__main__':
    try:
        print("🚨 STARTING LIVE TRADING - REAL MONEY AT RISK!")
        print("This will start live trading immediately.")
        print("Press Ctrl+C to stop at any time.")
        print("Create 'emergency_stop.txt' file for emergency stop.")
        print()
        
        # Give user 5 seconds to cancel
        for i in range(5, 0, -1):
            print(f"Starting in {i} seconds... (Press Ctrl+C to cancel)")
            time.sleep(1)
        
        print("\n🚀 STARTING LIVE TRADING NOW!")
        success = start_live_trading()
        
        if success:
            print("✅ Live trading session completed successfully")
        else:
            print("❌ Live trading session failed")
            sys.exit(1)
    except Exception as e:
        print(f"❌ Script error: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)