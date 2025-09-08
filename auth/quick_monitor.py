#!/usr/bin/env python3
"""
Quick API Monitor - Simple version for immediate testing
"""

import json
import sys
import os

# Add parent directory to path to import SmartApi
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import time
import datetime
from SmartApi import SmartConnect
import pyotp

def quick_test():
    """Quick API test"""
    config_path = os.path.join(os.path.dirname(os.path.dirname(__file__)), 'config', 'config.json')
        with open(config_path, 'r') as f:
        config = json.load(f)
    
    try:
        smartApi = SmartConnect(api_key=config['api_key'])
        totp = pyotp.TOTP(config['totp_secret']).now()
        response = smartApi.generateSession(config['client_code'], config['pin'], totp)
        
        return response.get('status', False), response.get('message', 'Unknown')
    except Exception as e:
        return False, str(e)

def main():
    """Quick monitoring loop"""
    print("🚀 Quick API Monitor - Testing every 30 seconds")
    print("🛑 Press Ctrl+C to stop")
    print("-" * 40)
    
    test_count = 0
    
    try:
        while True:
            test_count += 1
            current_time = datetime.datetime.now().strftime('%H:%M:%S')
            
            success, message = quick_test()
            
            if success:
                print(f"\n🎉 SUCCESS at {current_time}! API key is working!")
                print("🎯 Run: python3 simple_login.py")
                break
            else:
                print(f"❌ Test #{test_count} at {current_time}: {message}")
            
            time.sleep(30)  # Wait 30 seconds
            
    except KeyboardInterrupt:
        print(f"\n👋 Stopped after {test_count} tests")

if __name__ == "__main__":
    main()