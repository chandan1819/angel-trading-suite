#!/usr/bin/env python3
"""
Test New API Key - Fresh script to test the latest API key
"""

import json
import sys
import os

# Add parent directory to path to import SmartApi
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from SmartApi import SmartConnect
import pyotp

def test_both_keys():
    """Test both the short API key and secret key"""
    
    # Load config
    config_path = os.path.join(os.path.dirname(os.path.dirname(__file__)), 'config', 'config.json')
        with open(config_path, 'r') as f:
        config = json.load(f)
    
    # Test keys from your dashboard
    keys_to_test = [
        ("Short API Key", "iiFmL1SI"),
        ("Secret Key", "f04f6a58-a55d-41e7-9245-1392c243839a")
    ]
    
    print("🔑 Testing New API Keys from Dashboard")
    print("=" * 50)
    print(f"📱 Client Code: {config['client_code']}")
    print(f"🔢 Current TOTP: {pyotp.TOTP(config['totp_secret']).now()}")
    print()
    
    for key_name, api_key in keys_to_test:
        print(f"🧪 Testing {key_name}: {api_key}")
        
        try:
            # Create fresh SmartConnect instance
            smartApi = SmartConnect(api_key=api_key)
            totp = pyotp.TOTP(config['totp_secret']).now()
            
            print(f"🔢 Using TOTP: {totp}")
            
            # Attempt login
            response = smartApi.generateSession(
                config['client_code'], 
                config['pin'], 
                totp
            )
            
            if response.get('status'):
                print(f"✅ SUCCESS with {key_name}!")
                print(f"🎫 Auth Token: {response['data']['jwtToken'][:20]}...")
                print(f"🔄 Refresh Token: {response['data']['refreshToken'][:20]}...")
                
                # Update config with working key
                config['api_key'] = api_key
                with open('config.json', 'w') as f:
                    json.dump(config, f, indent=4)
                print(f"✅ Updated config.json with working API key!")
                return True
                
            else:
                print(f"❌ Failed with {key_name}: {response.get('message')}")
                print(f"🔍 Error Code: {response.get('errorcode')}")
                
        except Exception as e:
            print(f"❌ Exception with {key_name}: {e}")
        
        print("-" * 30)
    
    return False

if __name__ == "__main__":
    success = test_both_keys()
    
    if success:
        print("\n🎉 API KEY IS WORKING!")
        print("🎯 You can now run: python3 simple_login.py")
    else:
        print("\n❌ Both API keys failed")
        print("💡 The new API key might need time to activate")
        print("🔄 Try running: python3 api_monitor.py")