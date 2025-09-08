#!/usr/bin/env python3
"""
Angel Broking Order Management
Place, modify, cancel orders and manage positions
"""

import json
import sys
import os

# Add parent directory to path to import SmartApi
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from SmartApi import SmartConnect
import pyotp
from datetime import datetime

class OrderManager:
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
                return True
            else:
                print(f"❌ Login failed: {data.get('message')}")
                return False
                
        except Exception as e:
            print(f"❌ Login error: {e}")
            return False
    
    def place_buy_order(self, symbol, quantity, price, order_type="LIMIT", product_type="INTRADAY"):
        """Place a BUY order"""
        print(f"\n📝 PLACING BUY ORDER")
        print("=" * 25)
        
        # Get symbol token (you might need to search first)
        search_result = self.smartApi.searchScrip("NSE", symbol)
        if not search_result['status'] or not search_result['data']:
            print(f"❌ Symbol {symbol} not found")
            return None
        
        token = search_result['data'][0]['symboltoken']
        full_symbol = search_result['data'][0]['tradingsymbol']
        
        order_params = {
            "variety": "NORMAL",
            "tradingsymbol": full_symbol,
            "symboltoken": token,
            "transactiontype": "BUY",
            "exchange": "NSE",
            "ordertype": order_type,
            "producttype": product_type,
            "duration": "DAY",
            "price": str(price),
            "squareoff": "0",
            "stoploss": "0",
            "quantity": str(quantity)
        }
        
        print(f"📊 Order Details:")
        print(f"  Symbol: {full_symbol}")
        print(f"  Type: BUY {order_type}")
        print(f"  Quantity: {quantity}")
        print(f"  Price: ₹{price}")
        print(f"  Product: {product_type}")
        
        try:
            # Confirm before placing
            confirm = input("\n⚠️  Confirm order placement? (yes/no): ").lower()
            if confirm != 'yes':
                print("❌ Order cancelled by user")
                return None
            
            order_id = self.smartApi.placeOrder(order_params)
            print(f"✅ BUY order placed successfully!")
            print(f"📋 Order ID: {order_id}")
            return order_id
            
        except Exception as e:
            print(f"❌ Order placement failed: {e}")
            return None
    
    def place_sell_order(self, symbol, quantity, price, order_type="LIMIT", product_type="INTRADAY"):
        """Place a SELL order"""
        print(f"\n📝 PLACING SELL ORDER")
        print("=" * 26)
        
        # Get symbol token
        search_result = self.smartApi.searchScrip("NSE", symbol)
        if not search_result['status'] or not search_result['data']:
            print(f"❌ Symbol {symbol} not found")
            return None
        
        token = search_result['data'][0]['symboltoken']
        full_symbol = search_result['data'][0]['tradingsymbol']
        
        order_params = {
            "variety": "NORMAL",
            "tradingsymbol": full_symbol,
            "symboltoken": token,
            "transactiontype": "SELL",
            "exchange": "NSE",
            "ordertype": order_type,
            "producttype": product_type,
            "duration": "DAY",
            "price": str(price),
            "squareoff": "0",
            "stoploss": "0",
            "quantity": str(quantity)
        }
        
        print(f"📊 Order Details:")
        print(f"  Symbol: {full_symbol}")
        print(f"  Type: SELL {order_type}")
        print(f"  Quantity: {quantity}")
        print(f"  Price: ₹{price}")
        print(f"  Product: {product_type}")
        
        try:
            # Confirm before placing
            confirm = input("\n⚠️  Confirm order placement? (yes/no): ").lower()
            if confirm != 'yes':
                print("❌ Order cancelled by user")
                return None
            
            order_id = self.smartApi.placeOrder(order_params)
            print(f"✅ SELL order placed successfully!")
            print(f"📋 Order ID: {order_id}")
            return order_id
            
        except Exception as e:
            print(f"❌ Order placement failed: {e}")
            return None
    
    def get_order_book(self):
        """Get all orders"""
        print(f"\n📚 ORDER BOOK")
        print("=" * 15)
        
        try:
            orders = self.smartApi.orderBook()
            if orders['status']:
                order_list = orders.get('data', [])
                
                if not order_list:
                    print("📝 No orders found")
                    return []
                
                print(f"📋 Total Orders: {len(order_list)}")
                print()
                
                for i, order in enumerate(order_list, 1):
                    status = order.get('orderstatus', 'N/A')
                    symbol = order.get('tradingsymbol', 'N/A')
                    transaction = order.get('transactiontype', 'N/A')
                    quantity = order.get('quantity', 0)
                    price = order.get('price', 0)
                    order_id = order.get('orderid', 'N/A')
                    
                    status_icon = {
                        'COMPLETE': '✅',
                        'OPEN': '🟡',
                        'CANCELLED': '❌',
                        'REJECTED': '🚫'
                    }.get(status, '❓')
                    
                    print(f"{i:2d}. {status_icon} {symbol} - {transaction}")
                    print(f"     Qty: {quantity}, Price: ₹{price}")
                    print(f"     Status: {status}, ID: {order_id}")
                    print()
                
                return order_list
            else:
                print("❌ Failed to get order book")
                return []
                
        except Exception as e:
            print(f"❌ Error getting order book: {e}")
            return []
    
    def cancel_order(self, order_id):
        """Cancel an order"""
        print(f"\n❌ CANCELLING ORDER: {order_id}")
        print("=" * 30)
        
        try:
            result = self.smartApi.cancelOrder(order_id, "NORMAL")
            if result['status']:
                print(f"✅ Order {order_id} cancelled successfully!")
                return True
            else:
                print(f"❌ Failed to cancel order: {result.get('message')}")
                return False
                
        except Exception as e:
            print(f"❌ Cancel order error: {e}")
            return False
    
    def get_positions(self):
        """Get current positions"""
        print(f"\n📍 CURRENT POSITIONS")
        print("=" * 22)
        
        try:
            positions = self.smartApi.position()
            if positions['status']:
                net_positions = positions['data'].get('net', [])
                
                if not net_positions:
                    print("📝 No open positions")
                    return []
                
                print(f"📋 Total Positions: {len(net_positions)}")
                print()
                
                for i, pos in enumerate(net_positions, 1):
                    symbol = pos.get('tradingsymbol', 'N/A')
                    quantity = int(pos.get('netqty', 0))
                    avg_price = float(pos.get('netvalue', 0)) / quantity if quantity != 0 else 0
                    pnl = float(pos.get('unrealised', 0))
                    
                    if quantity == 0:
                        continue  # Skip closed positions
                    
                    pos_type = "LONG 📈" if quantity > 0 else "SHORT 📉"
                    pnl_icon = "💚" if pnl > 0 else "❤️" if pnl < 0 else "💛"
                    
                    print(f"{i}. {symbol} - {pos_type}")
                    print(f"   Quantity: {abs(quantity)}")
                    print(f"   Avg Price: ₹{avg_price:.2f}")
                    print(f"   P&L: {pnl_icon} ₹{pnl:.2f}")
                    print()
                
                return net_positions
            else:
                print("❌ Failed to get positions")
                return []
                
        except Exception as e:
            print(f"❌ Error getting positions: {e}")
            return []
    
    def get_holdings(self):
        """Get holdings (delivery stocks)"""
        print(f"\n💼 HOLDINGS")
        print("=" * 12)
        
        try:
            holdings = self.smartApi.holding()
            if holdings['status']:
                holding_list = holdings.get('data', [])
                
                if not holding_list:
                    print("📝 No holdings found")
                    return []
                
                print(f"📋 Total Holdings: {len(holding_list)}")
                print()
                
                total_value = 0
                total_pnl = 0
                
                for i, holding in enumerate(holding_list, 1):
                    symbol = holding.get('tradingsymbol', 'N/A')
                    quantity = int(holding.get('quantity', 0))
                    avg_price = float(holding.get('averageprice', 0))
                    ltp = float(holding.get('ltp', 0))
                    
                    current_value = quantity * ltp
                    invested_value = quantity * avg_price
                    pnl = current_value - invested_value
                    pnl_pct = (pnl / invested_value * 100) if invested_value > 0 else 0
                    
                    total_value += current_value
                    total_pnl += pnl
                    
                    pnl_icon = "💚" if pnl > 0 else "❤️" if pnl < 0 else "💛"
                    
                    print(f"{i}. {symbol}")
                    print(f"   Quantity: {quantity}")
                    print(f"   Avg Price: ₹{avg_price:.2f}")
                    print(f"   LTP: ₹{ltp:.2f}")
                    print(f"   Value: ₹{current_value:.2f}")
                    print(f"   P&L: {pnl_icon} ₹{pnl:.2f} ({pnl_pct:+.2f}%)")
                    print()
                
                print(f"💰 Total Portfolio Value: ₹{total_value:.2f}")
                total_pnl_icon = "💚" if total_pnl > 0 else "❤️" if total_pnl < 0 else "💛"
                print(f"📊 Total P&L: {total_pnl_icon} ₹{total_pnl:.2f}")
                
                return holding_list
            else:
                print("❌ Failed to get holdings")
                return []
                
        except Exception as e:
            print(f"❌ Error getting holdings: {e}")
            return []

def main():
    """Main interactive menu"""
    print("📋 Angel Broking Order Management")
    print("=" * 35)
    
    order_mgr = OrderManager()
    
    if not order_mgr.smartApi:
        print("❌ Failed to connect. Check your config.json")
        return
    
    while True:
        print("\n" + "=" * 35)
        print("📋 ORDER MANAGEMENT MENU")
        print("=" * 35)
        print("1. 📚 View Order Book")
        print("2. 📍 View Positions")
        print("3. 💼 View Holdings")
        print("4. 📝 Place BUY Order")
        print("5. 📝 Place SELL Order")
        print("6. ❌ Cancel Order")
        print("7. 🚪 Exit")
        
        choice = input("\n🔢 Enter your choice (1-7): ").strip()
        
        if choice == '1':
            order_mgr.get_order_book()
            
        elif choice == '2':
            order_mgr.get_positions()
            
        elif choice == '3':
            order_mgr.get_holdings()
            
        elif choice == '4':
            print("\n📝 PLACE BUY ORDER")
            symbol = input("Enter symbol (e.g., RELIANCE): ").strip().upper()
            try:
                quantity = int(input("Enter quantity: "))
                price = float(input("Enter price: "))
                order_type = input("Order type (LIMIT/MARKET) [LIMIT]: ").strip().upper() or "LIMIT"
                product_type = input("Product type (INTRADAY/DELIVERY) [INTRADAY]: ").strip().upper() or "INTRADAY"
                
                order_mgr.place_buy_order(symbol, quantity, price, order_type, product_type)
            except ValueError:
                print("❌ Invalid input. Please enter valid numbers.")
                
        elif choice == '5':
            print("\n📝 PLACE SELL ORDER")
            symbol = input("Enter symbol (e.g., RELIANCE): ").strip().upper()
            try:
                quantity = int(input("Enter quantity: "))
                price = float(input("Enter price: "))
                order_type = input("Order type (LIMIT/MARKET) [LIMIT]: ").strip().upper() or "LIMIT"
                product_type = input("Product type (INTRADAY/DELIVERY) [INTRADAY]: ").strip().upper() or "INTRADAY"
                
                order_mgr.place_sell_order(symbol, quantity, price, order_type, product_type)
            except ValueError:
                print("❌ Invalid input. Please enter valid numbers.")
                
        elif choice == '6':
            order_id = input("Enter Order ID to cancel: ").strip()
            if order_id:
                order_mgr.cancel_order(order_id)
            else:
                print("❌ Invalid Order ID")
                
        elif choice == '7':
            print("👋 Goodbye!")
            break
            
        else:
            print("❌ Invalid choice. Please select 1-7.")
        
        input("\n⏸️  Press Enter to continue...")

if __name__ == "__main__":
    main()