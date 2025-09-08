#!/usr/bin/env python3
"""
Angel Broking Market Data Script
Get live market data, prices, and analysis
"""

import json
import sys
import os

# Add parent directory to path to import SmartApi
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from SmartApi import SmartConnect
import pyotp
from datetime import datetime, timedelta

class MarketData:
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
    
    def get_nifty_data(self):
        """Get NIFTY 50 data"""
        print("\n📊 NIFTY 50 DATA")
        print("=" * 25)
        
        try:
            # NIFTY 50 token
            nifty_data = self.smartApi.ltpData("NSE", "NIFTY", "99926000")
            if nifty_data['status']:
                data = nifty_data['data']
                print(f"📈 NIFTY 50: {data.get('ltp', 0)}")
                print(f"🔺 High: {data.get('high', 0)}")
                print(f"🔻 Low: {data.get('low', 0)}")
                print(f"📊 Open: {data.get('open', 0)}")
                print(f"📉 Previous Close: {data.get('close', 0)}")
                
                # Calculate change
                ltp = float(data.get('ltp', 0))
                close = float(data.get('close', 0))
                if close > 0:
                    change = ltp - close
                    change_pct = (change / close) * 100
                    print(f"📈 Change: {change:.2f} ({change_pct:.2f}%)")
                    
        except Exception as e:
            print(f"❌ Error getting NIFTY data: {e}")
    
    def get_top_stocks_data(self):
        """Get data for popular stocks"""
        print("\n🏆 TOP STOCKS DATA")
        print("=" * 25)
        
        # Popular stocks with their tokens
        stocks = [
            ("RELIANCE", "2885"),
            ("TCS", "11536"),
            ("HDFCBANK", "1333"),
            ("INFY", "1594"),
            ("ICICIBANK", "4963"),
            ("SBIN", "3045"),
            ("BHARTIARTL", "10604"),
            ("ITC", "424"),
            ("KOTAKBANK", "1922"),
            ("LT", "11483")
        ]
        
        try:
            for symbol, token in stocks:
                ltp_data = self.smartApi.ltpData("NSE", symbol, token)
                if ltp_data['status']:
                    data = ltp_data['data']
                    ltp = float(data.get('ltp', 0))
                    close = float(data.get('close', 0))
                    
                    if close > 0:
                        change_pct = ((ltp - close) / close) * 100
                        trend = "📈" if change_pct > 0 else "📉" if change_pct < 0 else "➡️"
                        print(f"{trend} {symbol:12} ₹{ltp:8.2f} ({change_pct:+5.2f}%)")
                    else:
                        print(f"📊 {symbol:12} ₹{ltp:8.2f}")
                        
        except Exception as e:
            print(f"❌ Error getting stocks data: {e}")
    
    def search_and_get_price(self, search_term):
        """Search for a stock and get its price"""
        print(f"\n🔍 SEARCHING: {search_term}")
        print("=" * 30)
        
        try:
            # Search for the stock
            result = self.smartApi.searchScrip("NSE", search_term)
            if result['status'] and result['data']:
                stock = result['data'][0]  # Get first result
                symbol = stock['tradingsymbol']
                token = stock['symboltoken']
                
                print(f"✅ Found: {symbol} (Token: {token})")
                
                # Get price data
                ltp_data = self.smartApi.ltpData("NSE", symbol, token)
                if ltp_data['status']:
                    data = ltp_data['data']
                    ltp = float(data.get('ltp', 0))
                    high = float(data.get('high', 0))
                    low = float(data.get('low', 0))
                    close = float(data.get('close', 0))
                    
                    print(f"💰 Current Price: ₹{ltp}")
                    print(f"🔺 Day High: ₹{high}")
                    print(f"🔻 Day Low: ₹{low}")
                    print(f"📊 Previous Close: ₹{close}")
                    
                    if close > 0:
                        change = ltp - close
                        change_pct = (change / close) * 100
                        trend = "📈 UP" if change > 0 else "📉 DOWN" if change < 0 else "➡️ FLAT"
                        print(f"📈 Change: ₹{change:.2f} ({change_pct:.2f}%) {trend}")
                        
                return stock
            else:
                print("❌ Stock not found")
                return None
                
        except Exception as e:
            print(f"❌ Search error: {e}")
            return None
    
    def get_market_status(self):
        """Check market status"""
        print("\n🕐 MARKET STATUS")
        print("=" * 20)
        
        now = datetime.now()
        current_time = now.time()
        
        # Market hours: 9:15 AM to 3:30 PM
        market_open = datetime.strptime("09:15", "%H:%M").time()
        market_close = datetime.strptime("15:30", "%H:%M").time()
        
        is_weekday = now.weekday() < 5  # Monday = 0, Sunday = 6
        
        if is_weekday and market_open <= current_time <= market_close:
            print("🟢 Market is OPEN")
        else:
            print("🔴 Market is CLOSED")
            
        print(f"🕐 Current Time: {current_time.strftime('%H:%M')}")
        print(f"📅 Date: {now.strftime('%Y-%m-%d %A')}")
        
        if is_weekday:
            if current_time < market_open:
                print(f"⏰ Market opens at 09:15 AM")
            elif current_time > market_close:
                print(f"⏰ Market closed at 03:30 PM")
        else:
            print("📅 Market closed on weekends")
    
    def get_gainers_losers(self):
        """Get top gainers and losers"""
        print("\n📈📉 TOP GAINERS & LOSERS")
        print("=" * 30)
        
        try:
            # Get top gainers
            gainers_params = {
                "datatype": "PercGainers",
                "expirytype": "ALL"
            }
            gainers = self.smartApi.gainersLosers(gainers_params)
            
            if gainers['status'] and gainers['data']:
                print("🏆 TOP GAINERS:")
                for i, stock in enumerate(gainers['data'][:5], 1):
                    symbol = stock.get('tradingsymbol', 'N/A')
                    ltp = stock.get('ltp', 0)
                    change_pct = stock.get('changepercent', 0)
                    print(f"  {i}. {symbol:12} ₹{ltp:8.2f} (+{change_pct:.2f}%)")
            
            # Get top losers
            losers_params = {
                "datatype": "PercLosers", 
                "expirytype": "ALL"
            }
            losers = self.smartApi.gainersLosers(losers_params)
            
            if losers['status'] and losers['data']:
                print("\n📉 TOP LOSERS:")
                for i, stock in enumerate(losers['data'][:5], 1):
                    symbol = stock.get('tradingsymbol', 'N/A')
                    ltp = stock.get('ltp', 0)
                    change_pct = stock.get('changepercent', 0)
                    print(f"  {i}. {symbol:12} ₹{ltp:8.2f} ({change_pct:.2f}%)")
                    
        except Exception as e:
            print(f"❌ Error getting gainers/losers: {e}")

def main():
    """Main function"""
    print("📊 Angel Broking Market Data")
    print("=" * 35)
    
    market = MarketData()
    
    if not market.smartApi:
        print("❌ Failed to connect. Check your config.json")
        return
    
    # Get market status
    market.get_market_status()
    
    # Get NIFTY data
    market.get_nifty_data()
    
    # Get top stocks
    market.get_top_stocks_data()
    
    # Get gainers and losers
    market.get_gainers_losers()
    
    # Interactive search
    print("\n" + "=" * 35)
    search_term = input("🔍 Enter stock name to search (or press Enter to skip): ").strip()
    if search_term:
        market.search_and_get_price(search_term.upper())
    
    print("\n✅ Market data fetch completed!")

if __name__ == "__main__":
    main()