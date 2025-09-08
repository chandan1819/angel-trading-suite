#!/usr/bin/env python3
"""
Comprehensive Angel Broking Troubleshooting
This script helps identify and fix common issues
"""

import json
import sys
import os

# Add parent directory to path to import SmartApi
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import requests
import time
from SmartApi import SmartConnect
import pyotp

def check_api_key_format(api_key):
    """Check if API key format is correct"""
    print("🔍 Checking API Key Format...")
    
    if not api_key:
        print("❌ API key is empty")
        return False
    
    if len(api_key) != 36:
        print(f"❌ API key length is {len(api_key)}, expected 36")
        return False
    
    if api_key.count('-') != 4:
        print(f"❌ API key has {api_key.count('-')} dashes, expected 4")
        return False
    
    parts = api_key.split('-')
    expected_lengths = [8, 4, 4, 4, 12]
    
    for i, (part, expected_len) in enumerate(zip(parts, expected_lengths)):
        if len(part) != expected_len:
            print(f"❌ Part {i+1} has length {len(part)}, expected {expected_len}")
            return False
    
    print("✅ API key format is correct")
    return True

def test_different_endpoints():
    """Test different API endpoints"""
    print("\n🌐 Testing Different Endpoints...")
    
    endpoints = [
        "https://apiconnect.angelone.in",  # Production
        "https://apiconnect.angelbroking.com",  # Alternative
        "https://openapisuat.angelbroking.com"  # UAT/Sandbox
    ]
    
    for endpoint in endpoints:
        try:
            response = requests.get(endpoint, timeout=5)
            print(f"✅ {endpoint} - Status: {response.status_code}")
        except Exception as e:
            print(f"❌ {endpoint} - Error: {e}")

def test_with_different_endpoints(config):
    """Test login with different API endpoints"""
    print("\n🔄 Testing with Different API Endpoints...")
    
    endpoints = [
        ("Production", "https://apiconnect.angelone.in"),
        ("Alternative", "https://apiconnect.angelbroking.com"),
        ("UAT/Sandbox", "https://openapisuat.angelbroking.com")
    ]
    
    for name, endpoint in endpoints:
        print(f"\n🔗 Testing {name}: {endpoint}")
        
        try:
            # Create SmartConnect with custom endpoint
            smartApi = SmartConnect(api_key=config['api_key'])
            smartApi.root = endpoint  # Override the root URL
            
            totp = pyotp.TOTP(config['totp_secret']).now()
            
            response = smartApi.generateSession(
                config['client_code'], 
                config['pin'], 
                totp
            )
            
            if response.get('status'):
                print(f"✅ SUCCESS with {name}!")
                return True, endpoint
            else:
                print(f"❌ Failed with {name}: {response.get('message')}")
                
        except Exception as e:
            print(f"❌ Exception with {name}: {e}")
    
    return False, None

def check_account_requirements():
    """Check account requirements"""
    print("\n📋 Account Requirements Checklist:")
    print("=" * 40)
    
    requirements = [
        "✓ Angel Broking trading account is active",
        "✓ API trading is enabled in your account",
        "✓ KYC is completed",
        "✓ 2FA (TOTP) is enabled",
        "✓ API key is generated from developer portal",
        "✓ API key has trading permissions",
        "✓ No pending documentation or approvals"
    ]
    
    for req in requirements:
        print(f"  {req}")
    
    print("\n❓ Please verify all the above requirements are met.")

def wait_and_retry_test(config, retries=3, delay=30):
    """Wait and retry login test"""
    print(f"\n⏳ Waiting and Retrying (New API keys may take time to activate)...")
    
    for attempt in range(retries):
        print(f"\n🔄 Attempt {attempt + 1}/{retries}")
        
        if attempt > 0:
            print(f"⏰ Waiting {delay} seconds...")
            time.sleep(delay)
        
        try:
            smartApi = SmartConnect(api_key=config['api_key'])
            totp = pyotp.TOTP(config['totp_secret']).now()
            
            response = smartApi.generateSession(
                config['client_code'], 
                config['pin'], 
                totp
            )
            
            if response.get('status'):
                print("✅ SUCCESS! API key is now working!")
                return True
            else:
                print(f"❌ Still failing: {response.get('message')}")
                
        except Exception as e:
            print(f"❌ Exception: {e}")
    
    return False

def main():
    """Main troubleshooting function"""
    print("🔧 Comprehensive Angel Broking Troubleshooting")
    print("=" * 50)
    
    # Load config
    try:
        config_path = os.path.join(os.path.dirname(os.path.dirname(__file__)), 'config', 'config.json')
        with open(config_path, 'r') as f:
            config = json.load(f)
    except Exception as e:
        print(f"❌ Error loading config: {e}")
        return
    
    api_key = config['api_key']
    print(f"🔑 Testing API Key: {api_key[:8]}...{api_key[-8:]}")
    print(f"📱 Client Code: {config['client_code']}")
    
    # Step 1: Check API key format
    if not check_api_key_format(api_key):
        print("❌ API key format is invalid. Please check your API key.")
        return
    
    # Step 2: Test endpoints
    test_different_endpoints()
    
    # Step 3: Test with different endpoints
    success, working_endpoint = test_with_different_endpoints(config)
    if success:
        print(f"✅ Found working endpoint: {working_endpoint}")
        return
    
    # Step 4: Check account requirements
    check_account_requirements()
    
    # Step 5: Wait and retry (for new API keys)
    print(f"\n🆕 Since you just created this API key: {api_key[:8]}...")
    retry_choice = input("🔄 Try waiting and retrying? (y/n): ").strip().lower()
    
    if retry_choice == 'y':
        success = wait_and_retry_test(config)
        if success:
            return
    
    # Step 6: Final recommendations
    print("\n💡 Final Recommendations:")
    print("=" * 30)
    print("1. 📞 Contact Angel Broking Support:")
    print("   - Email: chdansinha1@hotmail.com")
    print("   - Phone: Check your Angel Broking app for support number")
    print("   - Mention Error Code: AB1053 (Invalid apiKey)")
    
    print("\n2. 🔍 Verify in Angel Broking Portal:")
    print("   - Login to https://smartapi.angelone.in/")
    print("   - Check if API key shows as 'ACTIVE'")
    print("   - Verify all permissions are enabled")
    
    print("\n3. 📋 Account Verification:")
    print("   - Ensure API trading is enabled")
    print("   - Check for any pending KYC or documentation")
    print("   - Verify 2FA is properly configured")

if __name__ == "__main__":
    main()