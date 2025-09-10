#!/usr/bin/env python3
"""
Show the actual API response structure and data format
"""

import json
from datetime import datetime

def show_angel_api_response_structure():
    """Show what the actual Angel Broking API response looks like"""
    
    print("📡 ANGEL BROKING API - ACTUAL RESPONSE STRUCTURE")
    print("=" * 70)
    
    print("🔍 1. INSTRUMENT SEARCH RESPONSE")
    print("-" * 40)
    
    # Sample instrument search response
    instrument_response = {
        "status": True,
        "message": "SUCCESS",
        "errorcode": "",
        "data": [
            {
                "token": "26009",
                "symbol": "BANKNIFTY09SEP2445200CE",
                "name": "BANKNIFTY",
                "expiry": "09SEP2024",
                "strike": "45200.00",
                "lotsize": "35",
                "instrumenttype": "OPTIDX",
                "exch_seg": "NFO",
                "tick_size": "0.05"
            },
            {
                "token": "26010",
                "symbol": "BANKNIFTY09SEP2445200PE",
                "name": "BANKNIFTY",
                "expiry": "09SEP2024",
                "strike": "45200.00",
                "lotsize": "35",
                "instrumenttype": "OPTIDX",
                "exch_seg": "NFO",
                "tick_size": "0.05"
            }
        ]
    }
    
    print("Sample Response:")
    print(json.dumps(instrument_response, indent=2))
    print()
    
    print("🔍 2. LTP (LAST TRADED PRICE) RESPONSE")
    print("-" * 40)
    
    # Sample LTP response
    ltp_response = {
        "status": True,
        "message": "SUCCESS",
        "errorcode": "",
        "data": {
            "exchange": "NFO",
            "tradingsymbol": "BANKNIFTY09SEP2445200CE",
            "symboltoken": "26009",
            "open": "75.50",
            "high": "82.30",
            "low": "65.20",
            "close": "78.45",
            "ltp": "67.21",
            "volume": "3376",
            "openinterest": "37548"
        }
    }
    
    print("Sample Response:")
    print(json.dumps(ltp_response, indent=2))
    print()
    
    print("🔍 3. BATCH LTP RESPONSE (Multiple Options)")
    print("-" * 40)
    
    # Sample batch LTP response
    batch_ltp_response = {
        "status": True,
        "message": "SUCCESS",
        "errorcode": "",
        "data": [
            {
                "exchange": "NFO",
                "tradingsymbol": "BANKNIFTY09SEP2445200CE",
                "symboltoken": "26009",
                "ltp": "67.21",
                "volume": "3376",
                "openinterest": "37548"
            },
            {
                "exchange": "NFO",
                "tradingsymbol": "BANKNIFTY09SEP2445200PE",
                "symboltoken": "26010",
                "ltp": "115.57",
                "volume": "1654",
                "openinterest": "42039"
            },
            {
                "exchange": "NFO",
                "tradingsymbol": "BANKNIFTY09SEP2445100CE",
                "symboltoken": "26007",
                "ltp": "122.92",
                "volume": "2891",
                "openinterest": "38389"
            },
            {
                "exchange": "NFO",
                "tradingsymbol": "BANKNIFTY09SEP2445100PE",
                "symboltoken": "26008",
                "ltp": "66.36",
                "volume": "3400",
                "openinterest": "19923"
            }
        ]
    }
    
    print("Sample Response:")
    print(json.dumps(batch_ltp_response, indent=2))
    print()
    
    print("🔄 4. HOW THE SYSTEM PROCESSES THIS DATA")
    print("-" * 40)
    
    processed_data = {
        "underlying_symbol": "BANKNIFTY",
        "underlying_price": 45150.75,
        "expiry_date": "2024-09-09",
        "timestamp": datetime.now().isoformat(),
        "atm_strike": 45200,
        "strikes": [
            {
                "strike": 45100,
                "call": {
                    "token": "26007",
                    "symbol": "BANKNIFTY09SEP2445100CE",
                    "ltp": 122.92,
                    "volume": 2891,
                    "open_interest": 38389,
                    "bid": 122.01,
                    "ask": 123.84,
                    "spread": 1.83,
                    "implied_volatility": 19.5
                },
                "put": {
                    "token": "26008",
                    "symbol": "BANKNIFTY09SEP2445100PE",
                    "ltp": 66.36,
                    "volume": 3400,
                    "open_interest": 19923,
                    "bid": 65.58,
                    "ask": 67.14,
                    "spread": 1.56,
                    "implied_volatility": 20.1
                }
            },
            {
                "strike": 45200,
                "call": {
                    "token": "26009",
                    "symbol": "BANKNIFTY09SEP2445200CE",
                    "ltp": 67.21,
                    "volume": 3376,
                    "open_interest": 37548,
                    "bid": 66.23,
                    "ask": 68.20,
                    "spread": 1.97,
                    "implied_volatility": 18.8
                },
                "put": {
                    "token": "26010",
                    "symbol": "BANKNIFTY09SEP2445200PE",
                    "ltp": 115.57,
                    "volume": 1654,
                    "open_interest": 42039,
                    "bid": 114.12,
                    "ask": 117.02,
                    "spread": 2.90,
                    "implied_volatility": 19.2
                }
            }
        ]
    }
    
    print("Processed Options Chain Structure:")
    print(json.dumps(processed_data, indent=2))
    print()
    
    print("🎯 5. STRATEGY EVALUATION PROCESS")
    print("-" * 40)
    
    evaluation_steps = [
        "1. Extract ATM strike data (45200)",
        "2. Check call option liquidity:",
        "   - Volume: 3,376 ≥ 500 ✅",
        "   - Open Interest: 37,548 ≥ 2,000 ✅", 
        "   - Spread: ₹1.97 ≤ ₹3.00 ✅",
        "3. Check put option liquidity:",
        "   - Volume: 1,654 ≥ 500 ✅",
        "   - Open Interest: 42,039 ≥ 2,000 ✅",
        "   - Spread: ₹2.90 ≤ ₹3.00 ✅",
        "4. Calculate IV rank:",
        "   - Current IV: 19.0%",
        "   - 30-day range: 12% - 28%",
        "   - IV Rank: 43.8% < 70% ❌",
        "5. Final decision: NO TRADE (IV too low)"
    ]
    
    for step in evaluation_steps:
        print(f"   {step}")
    
    print()
    
    print("📊 6. WHAT YOU SEE IN LIVE TRADING")
    print("-" * 40)
    
    console_output = """
📈 Cycle 15 - 10:45:30
   🔍 Evaluating market conditions...
   📊 Fetching BANKNIFTY options data...
   💹 BANKNIFTY Spot: 45,150.75 (+0.3%)
   🎯 ATM Strike: 45200
   
   📋 Options Chain Analysis:
   ├── 45200CE: LTP ₹67.21, Vol 3,376, OI 37,548, Spread ₹1.97
   ├── 45200PE: LTP ₹115.57, Vol 1,654, OI 42,039, Spread ₹2.90
   └── Straddle Premium: ₹182.78
   
   📊 Liquidity Check: ✅ PASSED
   ├── Call Volume: 3,376 ≥ 500 ✅
   ├── Put Volume: 1,654 ≥ 500 ✅
   ├── Call Spread: ₹1.97 ≤ ₹3.00 ✅
   └── Put Spread: ₹2.90 ≤ ₹3.00 ✅
   
   📈 IV Analysis: ❌ FAILED
   ├── Current IV Rank: 43.8%
   ├── Required: ≥70%
   └── Status: Too low for entry
   
   ⚪ No trading signals generated (IV rank too low)
   💼 Portfolio: No active positions
   📊 Session P&L: ₹0.00
   ⏳ Next evaluation in 60 seconds...
"""
    
    print(console_output)
    
    print("🔧 7. ACTUAL API CALLS MADE")
    print("-" * 40)
    
    api_calls = [
        "POST /rest/auth/angelbroking/user/v1/loginByPassword",
        "GET /rest/secure/angelbroking/order/v1/getLTP/exchange/NSE/tradingsymbol/BANKNIFTY",
        "POST /rest/secure/angelbroking/order/v1/searchScrip",
        "POST /rest/secure/angelbroking/order/v1/getMarketData",
        "GET /rest/secure/angelbroking/order/v1/getLTP/exchange/NFO/tradingsymbol/BANKNIFTY09SEP2445200CE",
        "GET /rest/secure/angelbroking/order/v1/getLTP/exchange/NFO/tradingsymbol/BANKNIFTY09SEP2445200PE",
        "... (similar calls for all strikes)"
    ]
    
    for i, call in enumerate(api_calls, 1):
        print(f"   {i}. {call}")
    
    print()

if __name__ == '__main__':
    show_angel_api_response_structure()
    
    print("=" * 70)
    print("🎯 SUMMARY:")
    print("• System makes 20-30 API calls per cycle to get complete options chain")
    print("• Each option contract has token, symbol, LTP, volume, and OI data")
    print("• Data is processed into structured format for strategy analysis")
    print("• Liquidity and IV conditions are checked before any trade")
    print("• Most cycles result in NO TRADE due to strict conditions")
    print("• When conditions are met, system executes straddle automatically")
    print("=" * 70)