#!/usr/bin/env python3
"""
Angel Broking SmartAPI Login Example
This script demonstrates how to login using config.json file
"""

import json
import os
import sys

# Add parent directory to path to import SmartApi
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from SmartApi import SmartConnect
import pyotp
from logzero import logger

def load_config():
    """Load configuration from JSON file"""
    try:
        config_path = os.path.join(os.path.dirname(os.path.dirname(__file__)), 'config', 'config.json')
        with open(config_path, 'r') as f:
            config = json.load(f)
        return config
    except FileNotFoundError:
        logger.error(f"Config file not found at config/config.json!")
        return None
    except json.JSONDecodeError:
        logger.error(f"Invalid JSON in config file")
        return None

def login_to_angel_broking():
    """Login to Angel Broking using credentials from config.json"""
    
    # Load configuration
    config = load_config()
    if not config:
        return None
    
    # Extract credentials
    api_key = config.get('api_key')
    client_code = config.get('client_code')
    pin = config.get('pin')
    totp_secret = config.get('totp_secret')
    
    # Validate all required fields are present
    if not all([api_key, client_code, pin, totp_secret]):
        logger.error("Missing required credentials in config.json")
        return None
    
    print("🔐 Initializing Angel Broking SmartAPI connection...")
    print(f"📱 Client Code: {client_code}")
    print(f"🔑 API Key: {api_key[:8]}...{api_key[-8:]}")  # Show partial key for security
    
    try:
        # Initialize SmartConnect
        smartApi = SmartConnect(api_key=api_key)
        
        # Generate TOTP (Time-based One-Time Password)
        print("🔢 Generating TOTP...")
        totp = pyotp.TOTP(totp_secret).now()
        print(f"🔢 Current TOTP: {totp}")
        
        # Attempt login
        print("🚀 Attempting login...")
        login_response = smartApi.generateSession(client_code, pin, totp)
        
        if login_response.get('status') == True:
            print("✅ Login successful!")
            
            # Extract tokens
            auth_token = login_response['data']['jwtToken']
            refresh_token = login_response['data']['refreshToken']
            feed_token = smartApi.getfeedToken()
            
            print("\n📊 Login Details:")
            print(f"🎫 Auth Token: {auth_token[:20]}...")
            print(f"🔄 Refresh Token: {refresh_token[:20]}...")
            print(f"📡 Feed Token: {feed_token}")
            
            # Get user profile
            print("\n👤 Fetching user profile...")
            profile = smartApi.getProfile(refresh_token)
            if profile.get('status'):
                user_data = profile['data']
                print(f"📝 Name: {user_data.get('name', 'N/A')}")
                print(f"📧 Email: {user_data.get('email', 'N/A')}")
                print(f"📞 Mobile: {user_data.get('mobileno', 'N/A')}")
                print(f"🏢 Broker: {user_data.get('broker', 'N/A')}")
                print(f"💼 Client Code: {user_data.get('clientcode', 'N/A')}")
            
            return {
                'smartApi': smartApi,
                'auth_token': auth_token,
                'refresh_token': refresh_token,
                'feed_token': feed_token,
                'profile': profile
            }
            
        else:
            print("❌ Login failed!")
            print(f"Error: {login_response.get('message', 'Unknown error')}")
            return None
            
    except Exception as e:
        logger.error(f"Login error: {e}")
        print(f"❌ Exception during login: {e}")
        return None

def test_api_functionality(login_data):
    """Test basic API functionality after successful login"""
    if not login_data:
        return
    
    smartApi = login_data['smartApi']
    
    print("\n🧪 Testing API functionality...")
    
    try:
        # Test 1: Get RMS Limits
        print("📊 Testing RMS Limits...")
        rms_data = smartApi.rmsLimit()
        if rms_data.get('status'):
            print("✅ RMS Limits retrieved successfully")
        else:
            print("❌ Failed to get RMS Limits")
    
    except Exception as e:
        print(f"❌ RMS Limits test failed: {e}")
    
    try:
        # Test 2: Get Holdings
        print("💼 Testing Holdings...")
        holdings = smartApi.holding()
        if holdings.get('status'):
            print("✅ Holdings retrieved successfully")
            if holdings.get('data'):
                print(f"📈 Number of holdings: {len(holdings['data'])}")
        else:
            print("❌ Failed to get Holdings")
    
    except Exception as e:
        print(f"❌ Holdings test failed: {e}")
    
    try:
        # Test 3: Get Positions
        print("📍 Testing Positions...")
        positions = smartApi.position()
        if positions.get('status'):
            print("✅ Positions retrieved successfully")
        else:
            print("❌ Failed to get Positions")
    
    except Exception as e:
        print(f"❌ Positions test failed: {e}")

def main():
    """Main function"""
    print("🎯 Angel Broking SmartAPI Login Demo")
    print("=" * 50)
    
    # Attempt login
    login_data = login_to_angel_broking()
    
    if login_data:
        print("\n🎉 Login completed successfully!")
        
        # Test some API functionality
        test_api_functionality(login_data)
        
        # Logout
        try:
            print("\n🚪 Logging out...")
            logout_response = login_data['smartApi'].terminateSession(login_data['profile']['data']['clientcode'])
            if logout_response.get('status'):
                print("✅ Logout successful!")
            else:
                print("❌ Logout failed")
        except Exception as e:
            print(f"❌ Logout error: {e}")
    
    else:
        print("\n❌ Login failed. Please check your credentials in config.json")

if __name__ == "__main__":
    main()