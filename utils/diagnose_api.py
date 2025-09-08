#!/usr/bin/env python3
"""
Angel Broking API Diagnostics
This script helps diagnose API connection issues
"""

import json
import sys
import os

# Add parent directory to path to import SmartApi
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import requests
from SmartApi import SmartConnect
import pyotp

def load_config():
    """Load config and validate"""
    try:
        config_path = os.path.join(os.path.dirname(os.path.dirname(__file__)), 'config', 'config.json')
        with open(config_path, 'r') as f:
            config = json.load(f)
        return config
    except Exception as e:
        print(f"❌ Error loading config: {e}")
        return None

def validate_config(config):
    """Validate configuration"""
    print("🔍 Validating configuration...")
    
    required_fields = ['api_key', 'client_code', 'pin', 'totp_secret']
    missing_fields = []
    
    for field in required_fields:
        if not config.get(field):
            missing_fields.append(field)
    
    if missing_fields:
        print(f"❌ Missing fields: {missing_fields}")
        return False
    
    # Validate field formats
    api_key = config['api_key']
    client_code = config['client_code']
    pin = config['pin']
    totp_secret = config['totp_secret']
    
    print(f"✅ API Key: {api_key[:8]}...{api_key[-8:]} (Length: {len(api_key)})")
    print(f"✅ Client Code: {client_code}")
    print(f"✅ PIN: {'*' * len(pin)} (Length: {len(pin)})")
    print(f"✅ TOTP Secret: {totp_secret[:4]}...{totp_secret[-4:]} (Length: {len(totp_secret)})")
    
    # Test TOTP generation
    try:
        totp = pyotp.TOTP(totp_secret).now()
        print(f"✅ TOTP Generated: {totp}")
        return True
    except Exception as e:
        print(f"❌ TOTP Generation Failed: {e}")
        return False

def test_api_connectivity():
    """Test basic API connectivity"""
    print("\n🌐 Testing API connectivity...")
    
    try:
        # Test Angel One API endpoint
        response = requests.get("https://apiconnect.angelone.in", timeout=10)
        print(f"✅ Angel One API reachable (Status: {response.status_code})")
        return True
    except Exception as e:
        print(f"❌ API connectivity failed: {e}")
        return False

def test_login_with_details(config):
    """Test login with detailed error reporting"""
    print("\n🔐 Testing login with detailed reporting...")
    
    try:
        smartApi = SmartConnect(api_key=config['api_key'])
        totp = pyotp.TOTP(config['totp_secret']).now()
        
        print(f"🔢 Using TOTP: {totp}")
        print(f"📱 Client Code: {config['client_code']}")
        print(f"🔑 API Key: {config['api_key'][:8]}...")
        
        # Attempt login
        response = smartApi.generateSession(
            config['client_code'], 
            config['pin'], 
            totp
        )
        
        print(f"\n📋 Full Response:")
        print(json.dumps(response, indent=2))
        
        if response.get('status'):
            print("✅ Login successful!")
            return True
        else:
            print(f"❌ Login failed: {response.get('message')}")
            print(f"🔍 Error Code: {response.get('errorcode')}")
            return False
            
    except Exception as e:
        print(f"❌ Login exception: {e}")
        return False

def provide_solutions(config):
    """Provide potential solutions based on the error"""
    print("\n💡 Potential Solutions:")
    print("=" * 50)
    
    print("1. 🔑 API Key Issues:")
    print("   - Verify your API key is active in Angel Broking developer portal")
    print("   - Check if you're using the correct environment (prod vs sandbox)")
    print("   - Ensure API key hasn't expired")
    print("   - Contact Angel Broking support to verify API key status")
    
    print("\n2. 📱 Account Issues:")
    print("   - Verify your client code is correct")
    print("   - Ensure your account has API trading enabled")
    print("   - Check if 2FA is properly configured")
    
    print("\n3. 🔢 TOTP Issues:")
    print("   - Verify TOTP secret is correct")
    print("   - Check system time is synchronized")
    print("   - Try generating a new TOTP secret")
    
    print("\n4. 🌐 Network Issues:")
    print("   - Check internet connection")
    print("   - Verify firewall isn't blocking API calls")
    print("   - Try from a different network")
    
    print(f"\n📞 Angel Broking Support:")
    print("   - Email: smartapi.sdk@gmail.com")
    print("   - Developer Portal: https://smartapi.angelone.in/")

def main():
    """Main diagnostic function"""
    print("🔧 Angel Broking API Diagnostics")
    print("=" * 50)
    
    # Load and validate config
    config = load_config()
    if not config:
        return
    
    config_valid = validate_config(config)
    if not config_valid:
        return
    
    # Test connectivity
    connectivity_ok = test_api_connectivity()
    if not connectivity_ok:
        print("❌ Basic connectivity failed. Check your internet connection.")
        return
    
    # Test login
    login_success = test_login_with_details(config)
    
    if not login_success:
        provide_solutions(config)
    
    print("\n" + "=" * 50)
    print("🏁 Diagnostics complete!")

if __name__ == "__main__":
    main()