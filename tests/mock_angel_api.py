"""
Mock Angel API implementation for realistic API simulation in tests.

This module provides a comprehensive mock implementation of the Angel Broking API
that simulates realistic responses, error conditions, and market data scenarios.
"""

import json
import time
import random
from datetime import datetime, timedelta
from typing import Dict, List, Any, Optional
from unittest.mock import Mock
from dataclasses import dataclass, asdict

from src.models.trading_models import OptionType, OrderAction


@dataclass
class MockInstrument:
    """Mock instrument data structure"""
    token: str
    symbol: str
    name: str
    expiry: str
    strike: str
    lotsize: str
    instrumenttype: str
    exch_seg: str
    tick_size: str


@dataclass
class MockOrderResponse:
    """Mock order response structure"""
    orderid: str
    status: str
    message: str
    data: Optional[Dict] = None


@dataclass
class MockPositionData:
    """Mock position data structure"""
    tradingsymbol: str
    exchange: str
    instrumenttoken: str
    producttype: str
    boardlotqty: str
    netqty: str
    buyqty: str
    sellqty: str
    buyavgprice: str
    sellavgprice: str
    netavgprice: str
    pnl: str
    unrealisedpnl: str
    realisedpnl: str
    ltp: str


class MockAngelAPI:
    """
    Mock implementation of Angel Broking SmartAPI for testing.
    
    Provides realistic simulation of API responses, rate limiting,
    error conditions, and market data scenarios.
    """
    
    def __init__(self, scenario: str = "normal"):
        """
        Initialize mock API with specific scenario.
        
        Args:
            scenario: Test scenario ('normal', 'error', 'rate_limit', 'network_issue')
        """
        self.scenario = scenario
        self.authenticated = False
        self.call_count = 0
        self.rate_limit_calls = 0
        self.rate_limit_window_start = time.time()
        self.max_calls_per_minute = 100
        
        # Mock data storage
        self.instruments_data = self._generate_instruments_data()
        self.orders = {}
        self.positions = {}
        self.order_counter = 1000
        
        # Scenario-specific settings
        self.error_probability = 0.0
        self.network_delay = 0.0
        self.rate_limit_enabled = False
        
        self._configure_scenario(scenario)
    
    def _configure_scenario(self, scenario: str):
        """Configure mock behavior based on scenario"""
        if scenario == "error":
            self.error_probability = 0.3  # 30% chance of errors
        elif scenario == "rate_limit":
            self.rate_limit_enabled = True
            self.max_calls_per_minute = 10  # Very low limit
        elif scenario == "network_issue":
            self.network_delay = 2.0  # 2 second delay
            self.error_probability = 0.1
        elif scenario == "market_closed":
            self.authenticated = True
        elif scenario == "high_volatility":
            self.authenticated = True
        # "normal" scenario uses defaults
    
    def _simulate_network_delay(self):
        """Simulate network delay"""
        if self.network_delay > 0:
            time.sleep(self.network_delay)
    
    def _check_rate_limit(self):
        """Check and enforce rate limiting"""
        if not self.rate_limit_enabled:
            return True
        
        current_time = time.time()
        
        # Reset counter if window expired
        if current_time - self.rate_limit_window_start > 60:
            self.rate_limit_calls = 0
            self.rate_limit_window_start = current_time
        
        self.rate_limit_calls += 1
        
        if self.rate_limit_calls > self.max_calls_per_minute:
            raise Exception("Rate limit exceeded: Too many requests")
        
        return True
    
    def _should_simulate_error(self):
        """Determine if an error should be simulated"""
        return random.random() < self.error_probability
    
    def _increment_call_count(self):
        """Increment API call counter"""
        self.call_count += 1
        self._check_rate_limit()
        self._simulate_network_delay()
        
        if self._should_simulate_error():
            error_types = [
                "Connection timeout",
                "Invalid session",
                "Server error",
                "Data not available"
            ]
            raise Exception(random.choice(error_types))
    
    def _generate_instruments_data(self) -> List[MockInstrument]:
        """Generate realistic instruments data"""
        instruments = []
        
        # Generate BANKNIFTY options for current and next month
        base_date = datetime.now()
        expiry_dates = [
            (base_date + timedelta(days=7)).strftime("%d%b%y").upper(),
            (base_date + timedelta(days=35)).strftime("%d%b%y").upper()
        ]
        
        for expiry in expiry_dates:
            # Generate strikes around 50000 (typical BANKNIFTY level)
            for strike in range(45000, 55100, 100):
                # Call option
                call_symbol = f"BANKNIFTY{expiry}C{strike}"
                instruments.append(MockInstrument(
                    token=f"{strike}1{expiry[2:4]}",
                    symbol=call_symbol,
                    name="BANKNIFTY",
                    expiry=expiry,
                    strike=str(strike),
                    lotsize="25",
                    instrumenttype="OPTIDX",
                    exch_seg="NFO",
                    tick_size="0.05"
                ))
                
                # Put option
                put_symbol = f"BANKNIFTY{expiry}P{strike}"
                instruments.append(MockInstrument(
                    token=f"{strike}2{expiry[2:4]}",
                    symbol=put_symbol,
                    name="BANKNIFTY",
                    expiry=expiry,
                    strike=str(strike),
                    lotsize="25",
                    instrumenttype="OPTIDX",
                    exch_seg="NFO",
                    tick_size="0.05"
                ))
        
        return instruments
    
    def generateSession(self, clientcode: str, password: str, totp: str) -> Dict[str, Any]:
        """Mock session generation"""
        self._increment_call_count()
        
        if self.scenario == "auth_error":
            return {
                "status": False,
                "message": "Invalid credentials",
                "errorcode": "AG8001"
            }
        
        self.authenticated = True
        return {
            "status": True,
            "message": "SUCCESS",
            "data": {
                "jwtToken": "mock_jwt_token_12345",
                "refreshToken": "mock_refresh_token_67890",
                "feedToken": "mock_feed_token_abcde"
            }
        }
    
    def getProfile(self) -> Dict[str, Any]:
        """Mock profile retrieval"""
        self._increment_call_count()
        
        if not self.authenticated:
            raise Exception("Not authenticated")
        
        return {
            "status": True,
            "message": "SUCCESS",
            "data": {
                "clientcode": "TEST123",
                "name": "Test User",
                "email": "test@example.com",
                "mobileno": "9876543210",
                "exchanges": ["NSE", "BSE", "NFO"],
                "products": ["CNC", "MIS", "NRML"],
                "lastlogintime": datetime.now().isoformat()
            }
        }
    
    def searchScrip(self, exchange: str, searchtext: str) -> Dict[str, Any]:
        """Mock scrip search"""
        self._increment_call_count()
        
        if not self.authenticated:
            raise Exception("Not authenticated")
        
        # Filter instruments based on search text
        matching_instruments = []
        for instrument in self.instruments_data:
            if (searchtext.upper() in instrument.symbol.upper() and 
                instrument.exch_seg == exchange):
                matching_instruments.append(asdict(instrument))
        
        return {
            "status": True,
            "message": "SUCCESS",
            "data": matching_instruments[:50]  # Limit results
        }
    
    def getLTP(self, exchange: str, tradingsymbol: str, symboltoken: str) -> Dict[str, Any]:
        """Mock LTP (Last Traded Price) retrieval"""
        self._increment_call_count()
        
        if not self.authenticated:
            raise Exception("Not authenticated")
        
        # Generate realistic option prices based on strike and market conditions
        ltp = self._generate_realistic_option_price(tradingsymbol, symboltoken)
        
        return {
            "status": True,
            "message": "SUCCESS",
            "data": {
                "exchange": exchange,
                "tradingsymbol": tradingsymbol,
                "symboltoken": symboltoken,
                "open": str(ltp * 0.98),
                "high": str(ltp * 1.05),
                "low": str(ltp * 0.95),
                "close": str(ltp * 0.99),
                "ltp": str(ltp)
            }
        }
    
    def getMarketData(self, mode: str, exchangeTokens: Dict[str, List[str]]) -> Dict[str, Any]:
        """Mock market data retrieval"""
        self._increment_call_count()
        
        if not self.authenticated:
            raise Exception("Not authenticated")
        
        market_data = []
        
        for exchange, tokens in exchangeTokens.items():
            for token in tokens:
                # Find corresponding instrument
                instrument = None
                for inst in self.instruments_data:
                    if inst.token == token:
                        instrument = inst
                        break
                
                if instrument:
                    ltp = self._generate_realistic_option_price(instrument.symbol, token)
                    
                    market_data.append({
                        "exchange": exchange,
                        "tradingsymbol": instrument.symbol,
                        "symboltoken": token,
                        "open": ltp * 0.98,
                        "high": ltp * 1.05,
                        "low": ltp * 0.95,
                        "close": ltp * 0.99,
                        "ltp": ltp,
                        "volume": random.randint(1000, 50000),
                        "oi": random.randint(500, 25000),
                        "bid": ltp * 0.995,
                        "ask": ltp * 1.005,
                        "timestamp": datetime.now().isoformat()
                    })
        
        return {
            "status": True,
            "message": "SUCCESS",
            "data": market_data
        }
    
    def placeOrder(self, orderparams: Dict[str, Any]) -> Dict[str, Any]:
        """Mock order placement"""
        self._increment_call_count()
        
        if not self.authenticated:
            raise Exception("Not authenticated")
        
        # Validate order parameters
        required_params = ['variety', 'tradingsymbol', 'symboltoken', 'transactiontype', 
                          'exchange', 'ordertype', 'producttype', 'duration', 'quantity']
        
        for param in required_params:
            if param not in orderparams:
                return {
                    "status": False,
                    "message": f"Missing required parameter: {param}",
                    "errorcode": "AB1001"
                }
        
        # Generate order ID
        order_id = f"ORD{self.order_counter:06d}"
        self.order_counter += 1
        
        # Simulate order rejection scenarios
        if self.scenario == "order_rejection":
            if random.random() < 0.3:  # 30% rejection rate
                return {
                    "status": False,
                    "message": "Order rejected: Insufficient margin",
                    "errorcode": "AB2001"
                }
        
        # Store order
        self.orders[order_id] = {
            **orderparams,
            "orderid": order_id,
            "status": "OPEN",
            "filledshares": "0",
            "unfilledshares": orderparams["quantity"],
            "ordertime": datetime.now().isoformat(),
            "averageprice": "0.00"
        }
        
        # Simulate immediate fill for market orders
        if orderparams.get("ordertype") == "MARKET":
            self._simulate_order_fill(order_id)
        
        return {
            "status": True,
            "message": "SUCCESS",
            "data": {"orderid": order_id}
        }
    
    def modifyOrder(self, orderparams: Dict[str, Any]) -> Dict[str, Any]:
        """Mock order modification"""
        self._increment_call_count()
        
        if not self.authenticated:
            raise Exception("Not authenticated")
        
        order_id = orderparams.get("orderid")
        if order_id not in self.orders:
            return {
                "status": False,
                "message": "Order not found",
                "errorcode": "AB3001"
            }
        
        # Update order
        self.orders[order_id].update(orderparams)
        
        return {
            "status": True,
            "message": "SUCCESS",
            "data": {"orderid": order_id}
        }
    
    def cancelOrder(self, orderid: str, variety: str) -> Dict[str, Any]:
        """Mock order cancellation"""
        self._increment_call_count()
        
        if not self.authenticated:
            raise Exception("Not authenticated")
        
        if orderid not in self.orders:
            return {
                "status": False,
                "message": "Order not found",
                "errorcode": "AB3001"
            }
        
        # Cancel order
        self.orders[orderid]["status"] = "CANCELLED"
        
        return {
            "status": True,
            "message": "SUCCESS",
            "data": {"orderid": orderid}
        }
    
    def orderBook(self) -> Dict[str, Any]:
        """Mock order book retrieval"""
        self._increment_call_count()
        
        if not self.authenticated:
            raise Exception("Not authenticated")
        
        return {
            "status": True,
            "message": "SUCCESS",
            "data": list(self.orders.values())
        }
    
    def position(self) -> Dict[str, Any]:
        """Mock position retrieval"""
        self._increment_call_count()
        
        if not self.authenticated:
            raise Exception("Not authenticated")
        
        return {
            "status": True,
            "message": "SUCCESS",
            "data": list(self.positions.values())
        }
    
    def getHistoricalData(self, historicDataParams: Dict[str, Any]) -> Dict[str, Any]:
        """Mock historical data retrieval"""
        self._increment_call_count()
        
        if not self.authenticated:
            raise Exception("Not authenticated")
        
        # Generate mock historical data
        from_date = datetime.strptime(historicDataParams["fromdate"], "%Y-%m-%d %H:%M")
        to_date = datetime.strptime(historicDataParams["todate"], "%Y-%m-%d %H:%M")
        interval = historicDataParams["interval"]
        
        # Generate realistic OHLC data
        historical_data = self._generate_historical_data(from_date, to_date, interval)
        
        return {
            "status": True,
            "message": "SUCCESS",
            "data": historical_data
        }
    
    def _generate_realistic_option_price(self, symbol: str, token: str) -> float:
        """Generate realistic option prices based on symbol and market conditions"""
        # Extract strike from symbol
        try:
            if 'C' in symbol:
                strike_str = symbol.split('C')[1]
                option_type = 'CE'
            else:
                strike_str = symbol.split('P')[1]
                option_type = 'PE'
            
            strike = float(strike_str)
        except:
            strike = 50000.0
            option_type = 'CE'
        
        # Simulate BANKNIFTY spot price
        base_spot = 50000.0
        if self.scenario == "high_volatility":
            spot_variation = random.uniform(-1000, 1000)
        else:
            spot_variation = random.uniform(-200, 200)
        
        spot_price = base_spot + spot_variation
        
        # Calculate intrinsic value
        if option_type == 'CE':
            intrinsic = max(0, spot_price - strike)
        else:
            intrinsic = max(0, strike - spot_price)
        
        # Add time value (simplified)
        time_value = random.uniform(10, 100)
        
        # Total premium
        premium = intrinsic + time_value
        
        # Ensure minimum premium
        return max(0.05, round(premium, 2))
    
    def _generate_historical_data(self, from_date: datetime, to_date: datetime, 
                                interval: str) -> List[Dict[str, Any]]:
        """Generate mock historical OHLC data"""
        data = []
        current_date = from_date
        
        # Determine interval in minutes
        interval_minutes = {
            "ONE_MINUTE": 1,
            "THREE_MINUTE": 3,
            "FIVE_MINUTE": 5,
            "FIFTEEN_MINUTE": 15,
            "THIRTY_MINUTE": 30,
            "ONE_HOUR": 60,
            "ONE_DAY": 1440
        }.get(interval, 5)
        
        base_price = 50000.0
        current_price = base_price
        
        while current_date <= to_date:
            # Generate OHLC for this interval
            open_price = current_price
            
            # Random price movement
            change_pct = random.uniform(-0.02, 0.02)  # ±2% max change
            close_price = open_price * (1 + change_pct)
            
            high_price = max(open_price, close_price) * random.uniform(1.0, 1.01)
            low_price = min(open_price, close_price) * random.uniform(0.99, 1.0)
            
            volume = random.randint(10000, 100000)
            
            data.append({
                "timestamp": current_date.strftime("%Y-%m-%d %H:%M:%S"),
                "open": round(open_price, 2),
                "high": round(high_price, 2),
                "low": round(low_price, 2),
                "close": round(close_price, 2),
                "volume": volume
            })
            
            current_price = close_price
            current_date += timedelta(minutes=interval_minutes)
        
        return data
    
    def _simulate_order_fill(self, order_id: str):
        """Simulate order fill"""
        if order_id not in self.orders:
            return
        
        order = self.orders[order_id]
        
        # Simulate fill price (slightly different from LTP)
        fill_price_variation = random.uniform(-0.02, 0.02)
        if order.get("price"):
            fill_price = float(order["price"]) * (1 + fill_price_variation)
        else:
            # Market order - use current LTP
            ltp = self._generate_realistic_option_price(order["tradingsymbol"], order["symboltoken"])
            fill_price = ltp * (1 + fill_price_variation)
        
        # Update order status
        order["status"] = "COMPLETE"
        order["filledshares"] = order["quantity"]
        order["unfilledshares"] = "0"
        order["averageprice"] = str(round(fill_price, 2))
        
        # Create position
        position_key = f"{order['tradingsymbol']}_{order['producttype']}"
        
        if position_key in self.positions:
            # Update existing position
            pos = self.positions[position_key]
            existing_qty = int(pos.netqty)
            new_qty = int(order["quantity"])
            
            if order["transactiontype"] == "SELL":
                new_qty = -new_qty
            
            total_qty = existing_qty + new_qty
            pos.netqty = str(total_qty)
        else:
            # Create new position
            qty = int(order["quantity"])
            if order["transactiontype"] == "SELL":
                qty = -qty
            
            self.positions[position_key] = MockPositionData(
                tradingsymbol=order["tradingsymbol"],
                exchange=order["exchange"],
                instrumenttoken=order["symboltoken"],
                producttype=order["producttype"],
                boardlotqty="25",
                netqty=str(qty),
                buyqty=order["quantity"] if order["transactiontype"] == "BUY" else "0",
                sellqty=order["quantity"] if order["transactiontype"] == "SELL" else "0",
                buyavgprice=str(fill_price) if order["transactiontype"] == "BUY" else "0.00",
                sellavgprice=str(fill_price) if order["transactiontype"] == "SELL" else "0.00",
                netavgprice=str(fill_price),
                pnl="0.00",
                unrealisedpnl="0.00",
                realisedpnl="0.00",
                ltp=str(fill_price)
            )
    
    def reset(self):
        """Reset mock API state"""
        self.authenticated = False
        self.call_count = 0
        self.rate_limit_calls = 0
        self.orders.clear()
        self.positions.clear()
        self.order_counter = 1000
    
    def get_call_count(self) -> int:
        """Get total API call count"""
        return self.call_count
    
    def set_scenario(self, scenario: str):
        """Change the mock scenario"""
        self.scenario = scenario
        self._configure_scenario(scenario)


class MockAPIFactory:
    """Factory for creating mock API instances with different scenarios"""
    
    @staticmethod
    def create_normal_api() -> MockAngelAPI:
        """Create mock API with normal behavior"""
        return MockAngelAPI("normal")
    
    @staticmethod
    def create_error_prone_api() -> MockAngelAPI:
        """Create mock API that frequently returns errors"""
        return MockAngelAPI("error")
    
    @staticmethod
    def create_rate_limited_api() -> MockAngelAPI:
        """Create mock API with strict rate limiting"""
        return MockAngelAPI("rate_limit")
    
    @staticmethod
    def create_network_issue_api() -> MockAngelAPI:
        """Create mock API with network issues"""
        return MockAngelAPI("network_issue")
    
    @staticmethod
    def create_market_closed_api() -> MockAngelAPI:
        """Create mock API for market closed scenario"""
        return MockAngelAPI("market_closed")
    
    @staticmethod
    def create_high_volatility_api() -> MockAngelAPI:
        """Create mock API with high market volatility"""
        return MockAngelAPI("high_volatility")