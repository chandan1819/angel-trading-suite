#!/usr/bin/env python3
"""
Angel Broking Trading Demo
This script demonstrates various trading operations
"""

import json
import sys
import os

# Add parent directory to path to import SmartApi
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from SmartApi import SmartConnect
import pyotp
from datetime import datetime, timedelta

class AngelTradingDemo:
    def __init__(self):
        self.smartApi = None
        self.load_config_and_login()
    
    def load_config_and_login(self):
        """Load config and login"""
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
                print("✅ Login successful!")
                return True
            else:
                print(f"❌ Login failed: {data.get('message')}")
                return False
                
        except Exception as e:
            print(f"❌ Login error: {e}")
            return False
    
    def get_account_info(self):
        """Get account information"""
        print("\n📊 ACCOUNT INFORMATION")
        print("=" * 30)
        
        try:
            # Get RMS (Risk Management System) data
            rms = self.smartApi.rmsLimit()
            if rms['status']:
                data = rms['data']
                print(f"💰 Available Cash: ₹{data.get('availablecash', 0)}")
                print(f"📈 Used Margin: ₹{data.get('utilisedmargin', 0)}")
                print(f"🔒 Available Margin: ₹{data.get('availablemargin', 0)}")
            
            # Get Holdings
            holdings = self.smartApi.holding()
            if holdings['status']:
                print(f"💼 Total Holdings: {len(holdings.get('data', []))}")
                
                if holdings['data']:
                    print("\n📋 Your Holdings:")
                    for holding in holdings['data'][:5]:  # Show first 5
                        print(f"  • {holding.get('tradingsymbol', 'N/A')}: {holding.get('quantity', 0)} shares")
            
            # Get Positions
            positions = self.smartApi.position()
            if positions['status']:
                net_positions = positions['data'].get('net', [])
                print(f"📍 Open Positions: {len(net_positions)}")
                
        except Exception as e:
            print(f"❌ Error getting account info: {e}")
    
    def search_stocks(self, search_term="RELIANCE"):
        """Search for stocks"""
        print(f"\n🔍 SEARCHING FOR: {search_term}")
        print("=" * 30)
        
        try:
            result = self.smartApi.searchScrip("NSE", search_term)
            if result['status'] and result['data']:
                print(f"✅ Found {len(result['data'])} results:")
                
                for i, stock in enumerate(result['data'][:5], 1):
                    print(f"{i}. {stock['tradingsymbol']} (Token: {stock['symboltoken']})")
                    print(f"   Exchange: {stock['exchange']}")
                
                return result['data'][0] if result['data'] else None
            else:
                print("❌ No results found")
                return None
                
        except Exception as e:
            print(f"❌ Search error: {e}")
            return None
    
    def get_live_price(self, symbol="RELIANCE", token="2885"):
        """Get live price of a stock"""
        print(f"\n💹 LIVE PRICE: {symbol}")
        print("=" * 30)
        
        try:
            ltp_data = self.smartApi.ltpData("NSE", symbol, token)
            if ltp_data['status']:
                data = ltp_data['data']
                print(f"📊 Symbol: {data.get('tradingsymbol', symbol)}")
                print(f"💰 LTP (Last Traded Price): ₹{data.get('ltp', 0)}")
                print(f"📈 Open: ₹{data.get('open', 0)}")
                print(f"📉 Close: ₹{data.get('close', 0)}")
                print(f"🔺 High: ₹{data.get('high', 0)}")
                print(f"🔻 Low: ₹{data.get('low', 0)}")
                return data
            else:
                print("❌ Failed to get price data")
                return None
                
        except Exception as e:
            print(f"❌ Price fetch error: {e}")
            return None
    
    def place_sample_order(self, demo_mode=True):
        """Place a sample order (DEMO - will not execute unless demo_mode=False)"""
        print(f"\n📝 SAMPLE ORDER {'(DEMO MODE)' if demo_mode else '(LIVE MODE)'}")
        print("=" * 40)
        
        if demo_mode:
            print("⚠️  This is DEMO mode - no actual order will be placed")
            print("⚠️  Set demo_mode=False to place real orders")
        
        # Sample order parameters
        order_params = {
            "variety": "NORMAL",
            "tradingsymbol": "RELIANCE-EQ",
            "symboltoken": "2885",
            "transactiontype": "BUY",
            "exchange": "NSE",
            "ordertype": "LIMIT",
            "producttype": "INTRADAY",
            "duration": "DAY",
            "price": "2500",  # Set a reasonable price
            "squareoff": "0",
            "stoploss": "0",
            "quantity": "1"
        }
        
        print("📋 Order Details:")
        for key, value in order_params.items():
            print(f"  {key}: {value}")
        
        if not demo_mode:
            try:
                order_id = self.smartApi.placeOrder(order_params)
                print(f"✅ Order placed successfully! Order ID: {order_id}")
                return order_id
            except Exception as e:
                print(f"❌ Order placement failed: {e}")
                return None
        else:
            print("✅ Demo order prepared (not executed)")
            return "DEMO_ORDER_ID"
    
    def get_order_book(self):
        """Get order book"""
        print("\n📚 ORDER BOOK")
        print("=" * 20)
        
        try:
            orders = self.smartApi.orderBook()
            if orders['status']:
                order_list = orders.get('data', [])
                print(f"📋 Total Orders: {len(order_list)}")
                
                if order_list:
                    print("\n🔍 Recent Orders:")
                    for order in order_list[-5:]:  # Show last 5 orders
                        print(f"  • {order.get('tradingsymbol', 'N/A')} - {order.get('transactiontype', 'N/A')}")
                        print(f"    Status: {order.get('orderstatus', 'N/A')}")
                        print(f"    Quantity: {order.get('quantity', 0)}")
                        print()
                else:
                    print("📝 No orders found")
                    
        except Exception as e:
            print(f"❌ Error getting order book: {e}")
    
    def get_historical_data(self, symbol="RELIANCE", token="2885"):
        """Get historical data"""
        print(f"\n📈 HISTORICAL DATA: {symbol}")
        print("=" * 30)
        
        try:
            # Get data for last 5 days
            to_date = datetime.now()
            from_date = to_date - timedelta(days=5)
            
            hist_params = {
                "exchange": "NSE",
                "symboltoken": token,
                "interval": "ONE_DAY",
                "fromdate": from_date.strftime("%Y-%m-%d 09:00"),
                "todate": to_date.strftime("%Y-%m-%d 15:30")
            }
            
            hist_data = self.smartApi.getCandleData(hist_params)
            if hist_data['status']:
                data = hist_data['data']
                print(f"📊 Got {len(data)} data points")
                
                if data:
                    print("\n📋 Recent Data (Date, Open, High, Low, Close, Volume):")
                    for candle in data[-3:]:  # Show last 3 days
                        date = candle[0]
                        open_price = candle[1]
                        high = candle[2]
                        low = candle[3]
                        close = candle[4]
                        volume = candle[5]
                        print(f"  {date}: O:{open_price} H:{high} L:{low} C:{close} V:{volume}")
                        
        except Exception as e:
            print(f"❌ Historical data error: {e}")

def main():
    """Main demo function"""
    print("🚀 Angel Broking Trading Demo")
    print("=" * 40)
    
    # Initialize trading demo
    demo = AngelTradingDemo()
    
    if not demo.smartApi:
        print("❌ Failed to initialize. Check your config.json")
        return
    
    # Run demo functions
    demo.get_account_info()
    
    # Search for a stock
    stock_data = demo.search_stocks("RELIANCE")
    
    # Get live price
    if stock_data:
        demo.get_live_price(stock_data['tradingsymbol'], stock_data['symboltoken'])
    else:
        demo.get_live_price()  # Use default RELIANCE
    
    # Show order book
    demo.get_order_book()
    
    # Get historical data
    demo.get_historical_data()
    
    # Demo order (safe - won't execute)
    demo.place_sample_order(demo_mode=True)
    
    print("\n🎉 Demo completed!")
    print("💡 To place real orders, modify the demo_mode parameter")

if __name__ == "__main__":
    main()