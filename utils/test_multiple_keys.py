#!/usr/bin/env python3
"""
Test Multiple API Keys
This script helps test different API keys quickly
"""

import json
from SmartApi import SmartConnect
import pyotp

def test_api_key(api_key, description=""):
    """Test a single API key"""
    print(f"\n🔑 Testing {description}API Key: {api_key[:8]}...{api_key[-8:]}")
    
    try:
        # Load other config
        with open('config.json', 'r') as f:
            config = json.load(f)
        
        # Initialize with test API key
        smartApi = SmartConnect(api_key=api_key)
        totp = pyotp.TOTP(config['totp_secret']).now()
        
        print(f"🔢 TOTP: {totp}")
        
        # Test login
        response = smartApi.generateSession(
            config['client_code'], 
            config['pin'], 
            totp
        )
        
        if response.get('status'):
            print("✅ SUCCESS! This API key works!")
            print(f"🎫 Auth Token: {response['data']['jwtToken'][:20]}...")
            return True
        else:
            print(f"❌ Failed: {response.get('message')} (Code: {response.get('errorcode')})")
            return False
            
    except Exception as e:
        print(f"❌ Exception: {e}")
        return False

def main():
    """Test multiple API keys"""
    print("🧪 API Key Tester")
    print("=" * 40)
    
    # Current API key from config
    try:
        with open('config.json', 'r') as f:
            config = json.load(f)
        current_key = config['api_key']
        
        print("Testing current API key from config...")
        success = test_api_key(current_key, "Current ")
        
        if success:
            print("\n🎉 Your current API key works! No changes needed.")
            return
            
    except Exception as e:
        print(f"Error loading config: {e}")
        return
    
    print("\n" + "=" * 40)
    print("Current API key failed. Let's try others...")
    
    # Test other potential API keys
    print("\nFrom your Angel Broking dashboard, I saw these ACTIVE APIs:")
    print("1. Trading API")
    print("2. OpenAlgo API")
    
    while True:
        new_key = input("\n🔑 Enter another API key to test (or 'quit' to exit): ").strip()
        
        if new_key.lower() == 'quit':
            break
            
        if len(new_key) < 30:
            print("❌ API key seems too short. Please check.")
            continue
            
        success = test_api_key(new_key, "New ")
        
        if success:
            # Update config with working key
            config['api_key'] = new_key
            with open('config.json', 'w') as f:
                json.dump(config, f, indent=4)
            print("✅ Config updated with working API key!")
            break
    
    print("\n🏁 Testing complete!")

if __name__ == "__main__":
    main()