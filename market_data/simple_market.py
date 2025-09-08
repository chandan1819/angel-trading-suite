#!/usr/bin/env python3
"""
Simple Market Data - Reliable version without problematic APIs
"""

import json
import sys
import os

# Add parent directory to path to import SmartApi
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from SmartApi import SmartConnect
import pyotp
from datetime import datetime

class SimpleMarket:
    def __init__(self):
        self.smartApi = None
        self.login()
    
    def login(self):
        """Login to Angel Broking"""
        try:
            config_path = os.path.join(os.path.dirname(os.path.dirname(__file__)), 'config', 'config.json')
    with open(config_path, 'r') as f:
                config = json.load(f)
            
            self.smartApi = SmartConnect(api_key=config['api_key'])
            totp = pyotp.TOTP(config['totp_secret']).now()
            
            data = self.smartApi.generateSession(
                config['client_code'], 
                config['pin'], 
                totp
            )
            
            if data['status']:
                print("✅ Connected to Angel Broking")
            else:
                print(f"❌ Login failed: {data.get('message')}")
                
        except Exception as e:
            print(f"❌ Login error: {e}")
    
    def get_stock_price(self, symbol, token):
        """Get stock price safely"""
        try:
            ltp_data = self.smartApi.ltpData("NSE", symbol, token)
            if ltp_data['status']:
                data = ltp_data['data']
                ltp = float(data.get('ltp', 0))
                close = float(data.get('close', 0))
                
                if close > 0:
                    change_pct = ((ltp - close) / close) * 100
                    trend = "📈" if change_pct > 0 else "📉" if change_pct < 0 else "➡️"
                    return f"{trend} {symbol:12} ₹{ltp:8.2f} ({change_pct:+5.2f}%)"
                else:
                    return f"📊 {symbol:12} ₹{ltp:8.2f}"
            else:
                return f"❌ {symbol:12} Failed to get price"
        except:
            return f"❌ {symbol:12} Error getting price"
    
    def show_popular_stocks(self):
        """Show popular stocks with reliable tokens"""
        print("\n🏆 POPULAR STOCKS")
        print("=" * 20)
        
        # Reliable stock tokens (tested)
        stocks = [
            ("RELIANCE", "2885"),
            ("TCS", "11536"), 
            ("HDFCBANK", "1333"),
            ("INFY", "1594"),
            ("SBIN", "3045"),
            ("BHARTIARTL", "10604"),
            ("KOTAKBANK", "1922"),
            ("LT", "11483")
        ]
        
        for symbol, token in stocks:
            result = self.get_stock_price(symbol, token)
            print(result)
    
    def search_stock(self, search_term):
        """Search and get stock price"""
        print(f"\n🔍 SEARCHING: {search_term}")
        print("=" * 30)
        
        try:
            result = self.smartApi.searchScrip("NSE", search_term)
            if result['status'] and result['data']:
                stock = result['data'][0]
                symbol = stock['tradingsymbol']
                token = stock['symboltoken']
                
                print(f"✅ Found: {symbol}")
                
                # Get price
                price_result = self.get_stock_price(symbol, token)
                print(price_result)
                
                # Get detailed price info
                ltp_data = self.smartApi.ltpData("NSE", symbol, token)
                if ltp_data['status']:
                    data = ltp_data['data']
                    print(f"🔺 High: ₹{data.get('high', 0)}")
                    print(f"🔻 Low: ₹{data.get('low', 0)}")
                    print(f"📊 Open: ₹{data.get('open', 0)}")
                
            else:
                print("❌ Stock not found")
                
        except Exception as e:
            print(f"❌ Search error: {e}")
    
    def get_account_summary(self):
        """Get account summary"""
        print("\n💰 ACCOUNT SUMMARY")
        print("=" * 20)
        
        try:
            # Get RMS data
            rms = self.smartApi.rmsLimit()
            if rms['status']:
                data = rms['data']
                print(f"💵 Available Cash: ₹{data.get('availablecash', 0)}")
                print(f"📊 Used Margin: ₹{data.get('utilisedmargin', 0)}")
            
            # Get positions count
            positions = self.smartApi.position()
            if positions['status']:
                net_pos = positions['data'].get('net', [])
                open_positions = [p for p in net_pos if int(p.get('netqty', 0)) != 0]
                print(f"📍 Open Positions: {len(open_positions)}")
            
            # Get holdings count
            holdings = self.smartApi.holding()
            if holdings['status']:
                print(f"💼 Holdings: {len(holdings.get('data', []))}")
                
        except Exception as e:
            print(f"❌ Account summary error: {e}")

def main():
    """Main function"""
    print("📊 Simple Market Data")
    print("=" * 25)
    
    market = SimpleMarket()
    
    if not market.smartApi:
        print("❌ Failed to connect")
        return
    
    # Show account summary
    market.get_account_summary()
    
    # Show popular stocks
    market.show_popular_stocks()
    
    # Interactive search
    while True:
        print("\n" + "=" * 25)
        search_term = input("🔍 Enter stock name (or 'quit' to exit): ").strip()
        
        if search_term.lower() in ['quit', 'exit', 'q']:
            break
        elif search_term:
            market.search_stock(search_term.upper())
    
    print("👋 Goodbye!")

if __name__ == "__main__":
    main()