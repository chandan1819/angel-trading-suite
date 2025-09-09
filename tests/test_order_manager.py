"""
Unit tests for the Order Management System.

Tests cover order placement, validation, position monitoring, and error handling.
"""

import pytest
import unittest
from unittest.mock import Mock, MagicMock, patch
from datetime import datetime, time
import threading
import time as time_module

from src.orders.order_manager import OrderManager
from src.orders.order_models import (
    OrderRequest, OrderResponse, OrderStatus, Position, OrderType, 
    OrderAction, OrderValidity, PositionType, OCOOrder
)
from src.orders.order_validator import OrderValidator
from src.orders.position_monitor import PositionMonitor
from src.models.trading_models import Trade, TradeLeg, TradeStatus, OptionType, OrderAction as ModelOrderAction
from src.api.angel_api_client import AngelAPIClient


class TestOrderModels(unittest.TestCase):
    """Test order data models"""
    
    def test_order_request_validation(self):
        """Test OrderRequest validation"""
        # Valid order
        order = OrderRequest(
            symbol="BANKNIFTY2412545000CE",
            token="12345",
            exchange="NFO",
            action=OrderAction.BUY,
            order_type=OrderType.LIMIT,
            quantity=25,
            price=100.0
        )
        self.assertTrue(order.validate())
        
        # Invalid order - missing symbol
        invalid_order = OrderRequest(
            symbol="",
            token="12345",
            exchange="NFO",
            action=OrderAction.BUY,
            order_type=OrderType.LIMIT,
            quantity=25,
            price=100.0
        )
        self.assertFalse(invalid_order.validate())
        
        # Invalid order - zero quantity
        invalid_order2 = OrderRequest(
            symbol="BANKNIFTY2412545000CE",
            token="12345",
            exchange="NFO",
            action=OrderAction.BUY,
            order_type=OrderType.LIMIT,
            quantity=0,
            price=100.0
        )
        self.assertFalse(invalid_order2.validate())
        
        # Invalid order - limit order without price
        invalid_order3 = OrderRequest(
            symbol="BANKNIFTY2412545000CE",
            token="12345",
            exchange="NFO",
            action=OrderAction.BUY,
            order_type=OrderType.LIMIT,
            quantity=25
        )
        self.assertFalse(invalid_order3.validate())
    
    def test_order_request_to_api_params(self):
        """Test conversion to API parameters"""
        order = OrderRequest(
            symbol="BANKNIFTY2412545000CE",
            token="12345",
            exchange="NFO",
            action=OrderAction.BUY,
            order_type=OrderType.LIMIT,
            quantity=25,
            price=100.0,
            validity=OrderValidity.DAY,
            product="MIS"
        )
        
        params = order.to_api_params()
        
        expected_params = {
            "variety": "NORMAL",
            "tradingsymbol": "BANKNIFTY2412545000CE",
            "symboltoken": "12345",
            "transactiontype": "BUY",
            "exchange": "NFO",
            "ordertype": "LIMIT",
            "producttype": "MIS",
            "duration": "DAY",
            "quantity": "25",
            "price": "100.0"
        }
        
        self.assertEqual(params, expected_params)
    
    def test_position_calculations(self):
        """Test position P&L calculations"""
        position = Position(
            symbol="BANKNIFTY2412545000CE",
            token="12345",
            exchange="NFO",
            product="MIS",
            quantity=25,
            average_price=100.0,
            ltp=110.0
        )
        
        # Test unrealized P&L calculation
        expected_pnl = 25 * (110.0 - 100.0)  # 250.0
        self.assertEqual(position.calculate_unrealized_pnl(), expected_pnl)
        
        # Test position type
        self.assertEqual(position.position_type, PositionType.LONG)
        
        # Test market value
        expected_market_value = 25 * 110.0  # 2750.0
        self.assertEqual(position.market_value, expected_market_value)
        
        # Test LTP update
        position.update_ltp(120.0)
        self.assertEqual(position.ltp, 120.0)
        self.assertEqual(position.unrealized_pnl, 25 * (120.0 - 100.0))  # 500.0


class TestOrderValidator(unittest.TestCase):
    """Test order validation logic"""
    
    def setUp(self):
        self.config = {
            'market_hours': {
                'start': time(9, 15),
                'end': time(15, 30)
            },
            'lot_size': 25,
            'max_order_value': 1000000,
            'min_price': 0.05,
            'max_price': 10000,
            'price_tolerance': 0.20
        }
        self.validator = OrderValidator(self.config)
    
    def test_basic_parameter_validation(self):
        """Test basic parameter validation"""
        # Valid order
        order = OrderRequest(
            symbol="BANKNIFTY2412545000CE",
            token="12345",
            exchange="NFO",
            action=OrderAction.BUY,
            order_type=OrderType.LIMIT,
            quantity=25,
            price=100.0
        )
        
        result = self.validator._validate_basic_parameters(order)
        self.assertTrue(result.is_valid)
        
        # Invalid order - missing symbol
        invalid_order = OrderRequest(
            symbol="",
            token="12345",
            exchange="NFO",
            action=OrderAction.BUY,
            order_type=OrderType.LIMIT,
            quantity=25,
            price=100.0
        )
        
        result = self.validator._validate_basic_parameters(invalid_order)
        self.assertFalse(result.is_valid)
    
    def test_price_validation(self):
        """Test price validation against LTP"""
        order = OrderRequest(
            symbol="BANKNIFTY2412545000CE",
            token="12345",
            exchange="NFO",
            action=OrderAction.BUY,
            order_type=OrderType.LIMIT,
            quantity=25,
            price=100.0
        )
        
        # Valid price within tolerance
        result = self.validator._validate_price(order, 95.0)
        self.assertTrue(result.is_valid)
        
        # Invalid price - too far from LTP
        result = self.validator._validate_price(order, 50.0)
        self.assertFalse(result.is_valid)
        
        # Invalid price - below minimum
        order.price = 0.01
        result = self.validator._validate_price(order, 100.0)
        self.assertFalse(result.is_valid)
    
    def test_quantity_validation(self):
        """Test quantity and lot size validation"""
        # Valid quantity (multiple of lot size)
        order = OrderRequest(
            symbol="BANKNIFTY2412545000CE",
            token="12345",
            exchange="NFO",
            action=OrderAction.BUY,
            order_type=OrderType.LIMIT,
            quantity=50,  # 2 lots
            price=100.0
        )
        
        result = self.validator._validate_quantity(order)
        self.assertTrue(result.is_valid)
        
        # Invalid quantity (not multiple of lot size)
        order.quantity = 30
        result = self.validator._validate_quantity(order)
        self.assertFalse(result.is_valid)
    
    def test_oco_validation(self):
        """Test OCO order validation"""
        target_order = OrderRequest(
            symbol="BANKNIFTY2412545000CE",
            token="12345",
            exchange="NFO",
            action=OrderAction.SELL,
            order_type=OrderType.LIMIT,
            quantity=25,
            price=120.0
        )
        
        stop_order = OrderRequest(
            symbol="BANKNIFTY2412545000CE",
            token="12345",
            exchange="NFO",
            action=OrderAction.SELL,
            order_type=OrderType.STOP_LOSS_MARKET,
            quantity=25,
            trigger_price=80.0  # Lower than target for long position
        )
        
        # Valid OCO for long position
        result = self.validator.validate_oco_orders(target_order, stop_order, 25)
        self.assertTrue(result.is_valid)
        
        # Invalid OCO - different symbols
        stop_order.symbol = "DIFFERENT_SYMBOL"
        result = self.validator.validate_oco_orders(target_order, stop_order, 25)
        self.assertFalse(result.is_valid)


class TestOrderManager(unittest.TestCase):
    """Test OrderManager functionality"""
    
    def setUp(self):
        self.mock_api_client = Mock(spec=AngelAPIClient)
        self.config = {
            'validation': {
                'lot_size': 25,
                'max_order_value': 1000000,
                'min_volume': 0,  # Disable volume check for tests
                'min_open_interest': 0  # Disable OI check for tests
            },
            'retry': {
                'max_attempts': 3,
                'base_delay': 0.1,  # Short delay for tests
                'max_delay': 1.0,
                'backoff_multiplier': 2.0
            },
            'monitoring_interval': 1  # Short interval for tests
        }
        self.order_manager = OrderManager(self.mock_api_client, self.config, mode="paper")
    
    def test_paper_order_placement(self):
        """Test paper trading order placement"""
        order = OrderRequest(
            symbol="BANKNIFTY2412545000CE",
            token="12345",
            exchange="NFO",
            action=OrderAction.BUY,
            order_type=OrderType.MARKET,
            quantity=25
        )
        
        # Mock LTP for validation
        self.mock_api_client.get_ltp.return_value = 100.0
        
        response = self.order_manager.place_order(order)
        
        self.assertTrue(response.is_success)
        self.assertIsNotNone(response.order_id)
        self.assertTrue(response.order_id.startswith("PAPER_"))
        self.assertEqual(response.status, OrderStatus.COMPLETE)
    
    def test_live_order_placement(self):
        """Test live trading order placement"""
        self.order_manager.mode = "live"
        
        order = OrderRequest(
            symbol="BANKNIFTY2412545000CE",
            token="12345",
            exchange="NFO",
            action=OrderAction.BUY,
            order_type=OrderType.LIMIT,
            quantity=25,
            price=100.0
        )
        
        # Mock API responses
        self.mock_api_client.get_ltp.return_value = 100.0
        self.mock_api_client.place_order.return_value = {
            'status': True,
            'data': {'orderid': 'LIVE_12345'}
        }
        
        response = self.order_manager.place_order(order)
        
        self.assertTrue(response.is_success)
        self.assertEqual(response.order_id, 'LIVE_12345')
        self.assertEqual(response.status, OrderStatus.PENDING)
    
    def test_order_validation_failure(self):
        """Test order placement with validation failure"""
        # Invalid order - zero quantity
        order = OrderRequest(
            symbol="BANKNIFTY2412545000CE",
            token="12345",
            exchange="NFO",
            action=OrderAction.BUY,
            order_type=OrderType.LIMIT,
            quantity=0,  # Invalid
            price=100.0
        )
        
        response = self.order_manager.place_order(order)
        
        self.assertFalse(response.is_success)
        self.assertEqual(response.status, OrderStatus.REJECTED)
        self.assertIn("Validation failed", response.message)
    
    def test_paper_position_tracking(self):
        """Test paper trading position tracking"""
        # Place buy order
        buy_order = OrderRequest(
            symbol="BANKNIFTY2412545000CE",
            token="12345",
            exchange="NFO",
            action=OrderAction.BUY,
            order_type=OrderType.MARKET,
            quantity=25
        )
        
        self.mock_api_client.get_ltp.return_value = 100.0
        buy_response = self.order_manager.place_order(buy_order)
        self.assertTrue(buy_response.is_success)
        
        # Check position
        positions = self.order_manager.get_positions()
        self.assertEqual(len(positions), 1)
        
        position = positions[0]
        self.assertEqual(position.symbol, "BANKNIFTY2412545000CE")
        self.assertEqual(position.quantity, 25)
        self.assertGreater(position.average_price, 0)
        
        # Place sell order to close position
        sell_order = OrderRequest(
            symbol="BANKNIFTY2412545000CE",
            token="12345",
            exchange="NFO",
            action=OrderAction.SELL,
            order_type=OrderType.MARKET,
            quantity=25
        )
        
        sell_response = self.order_manager.place_order(sell_order)
        self.assertTrue(sell_response.is_success)
        
        # Position should be closed
        positions = self.order_manager.get_positions()
        self.assertEqual(len(positions), 0)
    
    def test_oco_order_placement(self):
        """Test OCO order placement"""
        # Create a position first
        position = Position(
            symbol="BANKNIFTY2412545000CE",
            token="12345",
            exchange="NFO",
            product="MIS",
            quantity=25,
            average_price=100.0
        )
        
        # Mock order placement
        self.mock_api_client.get_ltp.return_value = 100.0
        self.mock_api_client.place_order.side_effect = [
            {'status': True, 'data': {'orderid': 'TARGET_123'}},
            {'status': True, 'data': {'orderid': 'STOP_456'}}
        ]
        
        success = self.order_manager.place_oco_orders(position, 120.0, 80.0)
        
        self.assertTrue(success)
        self.assertEqual(len(self.order_manager.oco_orders), 1)
    
    def test_order_cancellation(self):
        """Test order cancellation"""
        # Place order first
        order = OrderRequest(
            symbol="BANKNIFTY2412545000CE",
            token="12345",
            exchange="NFO",
            action=OrderAction.BUY,
            order_type=OrderType.LIMIT,
            quantity=25,
            price=100.0
        )
        
        self.mock_api_client.get_ltp.return_value = 100.0
        response = self.order_manager.place_order(order)
        self.assertTrue(response.is_success)
        
        # Cancel order
        success = self.order_manager.cancel_order(response.order_id)
        self.assertTrue(success)
        
        # Check status
        status = self.order_manager.get_order_status(response.order_id)
        self.assertEqual(status, OrderStatus.CANCELLED)
    
    def test_retry_mechanism(self):
        """Test retry mechanism for failed operations"""
        self.order_manager.mode = "live"
        
        order = OrderRequest(
            symbol="BANKNIFTY2412545000CE",
            token="12345",
            exchange="NFO",
            action=OrderAction.BUY,
            order_type=OrderType.LIMIT,
            quantity=25,
            price=100.0
        )
        
        # Mock API to fail twice then succeed
        self.mock_api_client.get_ltp.return_value = 100.0
        self.mock_api_client.place_order.side_effect = [
            Exception("Network error"),
            Exception("Timeout"),
            {'status': True, 'data': {'orderid': 'RETRY_SUCCESS'}}
        ]
        
        response = self.order_manager.place_order(order)
        
        self.assertTrue(response.is_success)
        self.assertEqual(response.order_id, 'RETRY_SUCCESS')
        self.assertEqual(self.mock_api_client.place_order.call_count, 3)


class TestPositionMonitor(unittest.TestCase):
    """Test PositionMonitor functionality"""
    
    def setUp(self):
        self.mock_order_manager = Mock(spec=OrderManager)
        self.config = {
            'default_target_pnl': 2000.0,
            'default_stop_loss': -1000.0,
            'max_daily_loss': -5000.0,
            'position_timeout_hours': 6,
            'monitoring_interval': 0.1,  # Short interval for tests
            'auto_close_on_target': True,
            'auto_close_on_stop': True
        }
        self.monitor = PositionMonitor(self.mock_order_manager, self.config)
    
    def test_add_remove_trade(self):
        """Test adding and removing trades for monitoring"""
        trade = Trade(
            trade_id="TEST_001",
            strategy="test_strategy",
            underlying_symbol="BANKNIFTY",
            entry_time=datetime.now(),
            target_pnl=2000.0,
            stop_loss=-1000.0
        )
        
        # Add trade
        self.monitor.add_trade(trade)
        self.assertIn("TEST_001", self.monitor.monitored_trades)
        
        # Remove trade
        self.monitor.remove_trade("TEST_001")
        self.assertNotIn("TEST_001", self.monitor.monitored_trades)
    
    def test_pnl_calculation(self):
        """Test P&L calculation for trades"""
        # Create trade with legs
        trade = Trade(
            trade_id="TEST_002",
            strategy="test_strategy",
            underlying_symbol="BANKNIFTY",
            entry_time=datetime.now(),
            target_pnl=2000.0,
            stop_loss=-1000.0
        )
        
        leg = TradeLeg(
            symbol="BANKNIFTY2412545000CE",
            token="12345",
            strike=45000.0,
            option_type=OptionType.CE,
            action=ModelOrderAction.BUY,
            quantity=25,
            entry_price=100.0,
            current_price=110.0
        )
        
        trade.add_leg(leg)
        self.monitor.add_trade(trade)
        
        # Update prices
        price_updates = {"BANKNIFTY2412545000CE": 120.0}
        self.monitor.update_trade_prices("TEST_002", price_updates)
        
        # Check P&L
        pnl = self.monitor.get_trade_pnl("TEST_002")
        expected_pnl = 25 * (120.0 - 100.0)  # 500.0
        self.assertEqual(pnl, expected_pnl)
    
    def test_risk_limit_checking(self):
        """Test risk limit checking"""
        # Set daily loss
        self.monitor.daily_pnl = -6000.0  # Exceeds limit
        
        alerts = self.monitor.check_risk_limits()
        
        self.assertTrue(any("DAILY_LOSS_LIMIT_BREACHED" in alert for alert in alerts))
    
    def test_position_summary(self):
        """Test position summary generation"""
        # Add a trade
        trade = Trade(
            trade_id="TEST_003",
            strategy="test_strategy",
            underlying_symbol="BANKNIFTY",
            entry_time=datetime.now(),
            target_pnl=2000.0,
            stop_loss=-1000.0,
            status=TradeStatus.OPEN
        )
        
        leg = TradeLeg(
            symbol="BANKNIFTY2412545000CE",
            token="12345",
            strike=45000.0,
            option_type=OptionType.CE,
            action=ModelOrderAction.BUY,
            quantity=25,
            entry_price=100.0,
            current_price=110.0
        )
        
        trade.add_leg(leg)
        self.monitor.add_trade(trade)
        
        summary = self.monitor.get_position_summary()
        
        self.assertEqual(summary['open_trades'], 1)
        self.assertGreater(summary['total_unrealized_pnl'], 0)
        self.assertIn('test_strategy', summary['positions_by_strategy'])
    
    def test_trade_closing(self):
        """Test automatic trade closing"""
        trade = Trade(
            trade_id="TEST_004",
            strategy="test_strategy",
            underlying_symbol="BANKNIFTY",
            entry_time=datetime.now(),
            target_pnl=2000.0,
            stop_loss=-1000.0,
            status=TradeStatus.OPEN
        )
        
        leg = TradeLeg(
            symbol="BANKNIFTY2412545000CE",
            token="12345",
            strike=45000.0,
            option_type=OptionType.CE,
            action=ModelOrderAction.BUY,
            quantity=25,
            entry_price=100.0,
            current_price=100.0
        )
        
        trade.add_leg(leg)
        self.monitor.add_trade(trade)
        
        # Mock successful order placement
        mock_response = Mock()
        mock_response.is_success = True
        mock_response.order_id = "EXIT_123"
        self.mock_order_manager.place_order.return_value = mock_response
        
        # Close trade
        success = self.monitor.close_trade("TEST_004", "MANUAL")
        
        self.assertTrue(success)
        self.assertEqual(trade.status, TradeStatus.CLOSED)
        self.mock_order_manager.place_order.assert_called_once()


if __name__ == '__main__':
    unittest.main()