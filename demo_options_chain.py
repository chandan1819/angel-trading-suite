#!/usr/bin/env python3
"""
Demo: Bank Nifty Options Chain API Call and Display
This script shows exactly how the options chain is fetched and displayed.
"""

import os
import sys
import json
import time
from datetime import datetime
from pathlib import Path

# Add src to path
sys.path.insert(0, str(Path(__file__).parent / 'src'))

def demo_options_chain_call():
    """Demonstrate options chain API call and data structure"""
    
    print("🔍 BANK NIFTY OPTIONS CHAIN - API DEMO")
    print("=" * 60)
    
    # Check credentials
    print("1️⃣ Checking API Credentials...")
    api_key = os.getenv('ANGEL_API_KEY')
    client_code = os.getenv('ANGEL_CLIENT_CODE')
    pin = os.getenv('ANGEL_PIN')
    totp_secret = os.getenv('ANGEL_TOTP_SECRET')
    
    if not all([api_key, client_code, pin, totp_secret]):
        print("❌ Missing API credentials!")
        print("Please set environment variables:")
        print("export ANGEL_API_KEY='your_key'")
        print("export ANGEL_CLIENT_CODE='your_code'")
        print("export ANGEL_PIN='your_pin'")
        print("export ANGEL_TOTP_SECRET='your_secret'")
        return False
    
    print(f"✅ API Key: {api_key[:4]}...")
    print(f"✅ Client Code: {client_code}")
    print()
    
    # Import and initialize API client
    print("2️⃣ Initializing Angel Broking API Client...")
    try:
        from config.config_manager import ConfigManager
        from api.angel_api_client import AngelAPIClient
        from api.market_data import MarketDataManager
        
        # Load configuration
        config_manager = ConfigManager()
        config = config_manager.load_config('config/live_trading_config.yaml')
        
        # Initialize API client
        api_client = AngelAPIClient(config.api)
        print("✅ API Client created")
        
        # Authenticate
        print("🔐 Authenticating with Angel Broking...")
        if api_client.initialize():
            print("✅ Authentication successful!")
        else:
            print("❌ Authentication failed!")
            return False
            
    except Exception as e:
        print(f"❌ Error initializing API: {e}")
        return False
    
    print()
    
    # Initialize Market Data Manager
    print("3️⃣ Initializing Market Data Manager...")
    try:
        market_data = MarketDataManager(api_client)
        print("✅ Market Data Manager ready")
    except Exception as e:
        print(f"❌ Error: {e}")
        return False
    
    print()
    
    # Get BANKNIFTY spot price
    print("4️⃣ Fetching BANKNIFTY Spot Price...")
    try:
        spot_price = api_client.get_ltp("NSE", "BANKNIFTY")
        if spot_price:
            print(f"✅ BANKNIFTY Spot: ₹{spot_price:,.2f}")
        else:
            print("❌ Could not fetch spot price")
            spot_price = 45000  # Mock price for demo
            print(f"🔧 Using mock price: ₹{spot_price:,.2f}")
    except Exception as e:
        print(f"⚠️ Error fetching spot price: {e}")
        spot_price = 45000  # Mock price for demo
        print(f"🔧 Using mock price: ₹{spot_price:,.2f}")
    
    print()
    
    # Get Options Chain
    print("5️⃣ Fetching BANKNIFTY Options Chain...")
    print("📡 API Call: get_options_chain('BANKNIFTY')")
    print("⏳ This may take 10-15 seconds...")
    
    try:
        start_time = time.time()
        options_chain = market_data.get_options_chain("BANKNIFTY")
        end_time = time.time()
        
        if options_chain:
            print(f"✅ Options chain fetched in {end_time - start_time:.2f} seconds")
            display_options_chain(options_chain, spot_price)
        else:
            print("❌ Failed to fetch options chain")
            print("🔧 Showing mock options chain structure...")
            display_mock_options_chain(spot_price)
            
    except Exception as e:
        print(f"❌ Error fetching options chain: {e}")
        print("🔧 Showing mock options chain structure...")
        display_mock_options_chain(spot_price)
    
    return True

def display_options_chain(options_chain, spot_price):
    """Display real options chain data"""
    
    print("\n📊 REAL OPTIONS CHAIN DATA")
    print("=" * 80)
    
    print(f"🎯 Underlying: {options_chain.underlying_symbol}")
    print(f"💹 Spot Price: ₹{options_chain.underlying_price:,.2f}")
    print(f"📅 Expiry Date: {options_chain.expiry_date}")
    print(f"🎯 ATM Strike: {options_chain.atm_strike}")
    print(f"⏰ Data Time: {options_chain.timestamp}")
    print(f"📈 Total Strikes: {len(options_chain.strikes)}")
    
    print("\n📋 OPTIONS CHAIN TABLE")
    print("-" * 80)
    print(f"{'Strike':<8} {'Call LTP':<10} {'Call Vol':<10} {'Call OI':<10} {'Put LTP':<10} {'Put Vol':<10} {'Put OI':<10}")
    print("-" * 80)
    
    # Show strikes around ATM
    atm_strike = options_chain.atm_strike
    strikes_to_show = []
    
    for strike_data in options_chain.strikes:
        strike = strike_data['strike']
        if abs(strike - atm_strike) <= 500:  # Show strikes within 500 points of ATM
            strikes_to_show.append(strike_data)
    
    # Sort by strike
    strikes_to_show.sort(key=lambda x: x['strike'])
    
    for strike_data in strikes_to_show[:10]:  # Show first 10 strikes
        strike = strike_data['strike']
        
        # Call data
        call_data = strike_data.get('call', {})
        call_ltp = call_data.get('ltp', 0)
        call_volume = call_data.get('volume', 0)
        call_oi = call_data.get('open_interest', 0)
        
        # Put data
        put_data = strike_data.get('put', {})
        put_ltp = put_data.get('ltp', 0)
        put_volume = put_data.get('volume', 0)
        put_oi = put_data.get('open_interest', 0)
        
        # Mark ATM strike
        marker = " 🎯" if strike == atm_strike else ""
        
        print(f"{strike:<8.0f} {call_ltp:<10.2f} {call_volume:<10} {call_oi:<10} "
              f"{put_ltp:<10.2f} {put_volume:<10} {put_oi:<10}{marker}")
    
    print("-" * 80)
    
    # Show detailed ATM data
    print(f"\n🎯 ATM STRIKE DETAILS ({atm_strike})")
    print("-" * 40)
    
    atm_data = None
    for strike_data in options_chain.strikes:
        if strike_data['strike'] == atm_strike:
            atm_data = strike_data
            break
    
    if atm_data:
        call_data = atm_data.get('call', {})
        put_data = atm_data.get('put', {})
        
        print("📞 CALL OPTION:")
        print(f"   LTP: ₹{call_data.get('ltp', 0):.2f}")
        print(f"   Bid: ₹{call_data.get('bid', 0):.2f}")
        print(f"   Ask: ₹{call_data.get('ask', 0):.2f}")
        print(f"   Volume: {call_data.get('volume', 0):,}")
        print(f"   Open Interest: {call_data.get('open_interest', 0):,}")
        print(f"   IV: {call_data.get('implied_volatility', 0):.2f}%")
        
        print("\n📞 PUT OPTION:")
        print(f"   LTP: ₹{put_data.get('ltp', 0):.2f}")
        print(f"   Bid: ₹{put_data.get('bid', 0):.2f}")
        print(f"   Ask: ₹{put_data.get('ask', 0):.2f}")
        print(f"   Volume: {put_data.get('volume', 0):,}")
        print(f"   Open Interest: {put_data.get('open_interest', 0):,}")
        print(f"   IV: {put_data.get('implied_volatility', 0):.2f}%")
        
        # Calculate straddle premium
        call_ltp = call_data.get('ltp', 0)
        put_ltp = put_data.get('ltp', 0)
        straddle_premium = call_ltp + put_ltp
        
        print(f"\n🎲 STRADDLE ANALYSIS:")
        print(f"   Total Premium: ₹{straddle_premium:.2f}")
        print(f"   Breakeven High: ₹{atm_strike + straddle_premium:.2f}")
        print(f"   Breakeven Low: ₹{atm_strike - straddle_premium:.2f}")
        print(f"   Max Profit: ₹{straddle_premium:.2f} (if expires at ATM)")

def display_mock_options_chain(spot_price):
    """Display mock options chain structure for demo"""
    
    print("\n📊 MOCK OPTIONS CHAIN STRUCTURE")
    print("=" * 80)
    print("(This shows what the real data would look like)")
    
    print(f"🎯 Underlying: BANKNIFTY")
    print(f"💹 Spot Price: ₹{spot_price:,.2f}")
    print(f"📅 Expiry Date: {datetime.now().strftime('%Y-%m-%d')}")
    
    # Calculate ATM strike
    atm_strike = round(spot_price / 100) * 100
    print(f"🎯 ATM Strike: {atm_strike}")
    
    print("\n📋 SAMPLE OPTIONS CHAIN")
    print("-" * 80)
    print(f"{'Strike':<8} {'Call LTP':<10} {'Call Vol':<10} {'Call OI':<10} {'Put LTP':<10} {'Put Vol':<10} {'Put OI':<10}")
    print("-" * 80)
    
    # Generate mock data for strikes around ATM
    import random
    
    for i in range(-5, 6):  # 11 strikes around ATM
        strike = atm_strike + (i * 100)
        
        # Mock call data (ITM calls more expensive)
        if strike < spot_price:  # ITM call
            call_ltp = abs(spot_price - strike) + random.uniform(20, 50)
        else:  # OTM call
            call_ltp = max(5, random.uniform(10, 100) - abs(strike - spot_price) * 0.3)
        
        # Mock put data (ITM puts more expensive)
        if strike > spot_price:  # ITM put
            put_ltp = abs(strike - spot_price) + random.uniform(20, 50)
        else:  # OTM put
            put_ltp = max(5, random.uniform(10, 100) - abs(spot_price - strike) * 0.3)
        
        # Mock volume and OI
        call_volume = random.randint(100, 5000)
        call_oi = random.randint(1000, 50000)
        put_volume = random.randint(100, 5000)
        put_oi = random.randint(1000, 50000)
        
        # Mark ATM
        marker = " 🎯" if strike == atm_strike else ""
        
        print(f"{strike:<8.0f} {call_ltp:<10.2f} {call_volume:<10} {call_oi:<10} "
              f"{put_ltp:<10.2f} {put_volume:<10} {put_oi:<10}{marker}")
    
    print("-" * 80)
    
    # Show what the API call structure looks like
    print(f"\n🔧 API CALL STRUCTURE:")
    print("=" * 40)
    print("1. api_client.authenticate()")
    print("2. market_data.get_options_chain('BANKNIFTY')")
    print("3. API searches for BANKNIFTY options instruments")
    print("4. Fetches LTP for each option contract")
    print("5. Processes and structures the data")
    print("6. Returns OptionsChainData object")
    
    print(f"\n📊 DATA STRUCTURE:")
    print("=" * 40)
    sample_structure = {
        "underlying_symbol": "BANKNIFTY",
        "underlying_price": spot_price,
        "expiry_date": "2024-09-12",
        "atm_strike": atm_strike,
        "strikes": [
            {
                "strike": atm_strike,
                "call": {
                    "ltp": 150.0,
                    "bid": 148.0,
                    "ask": 152.0,
                    "volume": 2500,
                    "open_interest": 25000,
                    "implied_volatility": 18.5
                },
                "put": {
                    "ltp": 145.0,
                    "bid": 143.0,
                    "ask": 147.0,
                    "volume": 2200,
                    "open_interest": 22000,
                    "implied_volatility": 19.2
                }
            }
        ]
    }
    
    print(json.dumps(sample_structure, indent=2))

def main():
    """Main function"""
    print("🚀 Bank Nifty Options Chain Demo")
    print("This demo shows how the system fetches and processes options chain data")
    print()
    
    success = demo_options_chain_call()
    
    if success:
        print("\n✅ Demo completed successfully!")
        print("\n📋 Key Points:")
        print("• The system fetches live options chain data every 60 seconds")
        print("• It analyzes all strikes around ATM for liquidity and pricing")
        print("• ATM strike is calculated based on current spot price")
        print("• Each option shows LTP, volume, open interest, and IV")
        print("• This data is used to make straddle trading decisions")
    else:
        print("\n❌ Demo failed - check your API credentials")
    
    print("\n🎯 Next Steps:")
    print("• Set up your Angel Broking API credentials")
    print("• Run this demo during market hours for live data")
    print("• Use the live trading system to see this in action")

if __name__ == '__main__':
    main()