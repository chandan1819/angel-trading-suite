#!/usr/bin/env python3
"""
Update API Key in config.json
This script helps you update your API key safely
"""

import json
import os

def update_api_key():
    """Update API key in config.json"""
    
    print("🔑 API Key Updater")
    print("=" * 30)
    
    # Load current config
    try:
        config_path = os.path.join(os.path.dirname(os.path.dirname(__file__)), 'config', 'config.json')
        with open(config_path, 'r') as f:
            config = json.load(f)
        print("✅ Current config loaded")
        print(f"📱 Client Code: {config.get('client_code')}")
        print(f"🔑 Current API Key: {config.get('api_key', 'Not set')[:8]}...")
    except Exception as e:
        print(f"❌ Error loading config: {e}")
        return
    
    # Get new API key
    print("\n🔍 From your Angel Broking dashboard, I can see you have ACTIVE API keys.")
    print("Please click on one of the ACTIVE trading APIs to get the full API key.")
    print("\nVisible ACTIVE APIs:")
    print("- Trading API (dcc87f1A...)")
    print("- OpenAlgo API (AgDFJ31...)")
    
    new_api_key = input("\n🔑 Enter your ACTIVE API key: ").strip()
    
    if not new_api_key:
        print("❌ No API key entered. Exiting.")
        return
    
    if len(new_api_key) < 10:
        print("❌ API key seems too short. Please check and try again.")
        return
    
    # Update config
    config['api_key'] = new_api_key
    
    # Backup old config
    if os.path.exists('config.json'):
        with open('config.json.backup', 'w') as f:
            json.dump(config, f, indent=4)
        print("✅ Backup created: config.json.backup")
    
    # Save new config
    try:
        with open('config.json', 'w') as f:
            json.dump(config, f, indent=4)
        print("✅ Config updated successfully!")
        print(f"🔑 New API Key: {new_api_key[:8]}...{new_api_key[-8:]}")
        
        # Test the new API key
        test_choice = input("\n🧪 Test the new API key now? (y/n): ").strip().lower()
        if test_choice == 'y':
            print("\n🚀 Testing new API key...")
            os.system("python3 simple_login.py")
            
    except Exception as e:
        print(f"❌ Error saving config: {e}")

if __name__ == "__main__":
    update_api_key()