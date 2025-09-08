#!/usr/bin/env python3
"""
Simple Angel Broking Login Example
A minimal example showing how to login and place a test order
"""

import json
import sys
import os

# Add parent directory to path to import SmartApi
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from SmartApi import SmartConnect
import pyotp

def simple_login():
    """Simple login function"""
    
    # Load config from config folder
    config_path = os.path.join(os.path.dirname(os.path.dirname(__file__)), 'config', 'config.json')
    
    try:
        with open(config_path, 'r') as f:
            config = json.load(f)
    except FileNotFoundError:
        print("❌ Config file not found. Make sure config/config.json exists.")
        return None, None
    
    # Initialize API
    smartApi = SmartConnect(api_key=config['api_key'])
    
    # Generate TOTP and login
    totp = pyotp.TOTP(config['totp_secret']).now()
    data = smartApi.generateSession(config['client_code'], config['pin'], totp)
    
    if data['status']:
        print("✅ Login successful!")
        
        # Get tokens
        auth_token = data['data']['jwtToken']
        refresh_token = data['data']['refreshToken']
        feed_token = smartApi.getfeedToken()
        
        print(f"Auth Token: {auth_token[:20]}...")
        print(f"Feed Token: {feed_token}")
        
        return smartApi, data
    else:
        print("❌ Login failed:", data.get('message'))
        return None, None

def get_account_info(smartApi, login_data):
    """Get basic account information"""
    try:
        refresh_token = login_data['data']['refreshToken']
        profile = smartApi.getProfile(refresh_token)
        
        if profile['status']:
            user = profile['data']
            print(f"\n👤 Account Info:")
            print(f"Name: {user.get('name')}")
            print(f"Client Code: {user.get('clientcode')}")
            print(f"Email: {user.get('email')}")
            
        # Get RMS limits
        rms = smartApi.rmsLimit()
        if rms['status']:
            print(f"\n💰 Available Cash: ₹{rms['data'].get('availablecash', 0)}")
            
    except Exception as e:
        print(f"Error getting account info: {e}")

if __name__ == "__main__":
    print("🚀 Simple Angel Broking Login")
    print("-" * 30)
    
    smartApi, login_data = simple_login()
    
    if smartApi:
        get_account_info(smartApi, login_data)
        
        # Logout
        client_code = login_data['data']['clientcode']
        logout = smartApi.terminateSession(client_code)
        print(f"\n🚪 Logout: {'✅ Success' if logout.get('status') else '❌ Failed'}")