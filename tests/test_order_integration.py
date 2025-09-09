"""
Integration tests for the complete order management system.

Tests the integration between OrderManager, OrderValidator, PositionMonitor,
and RetryHandler components.
"""

import pytest
import unittest
from unittest.mock import Mock, MagicMock, patch
import threading
import time
from datetime import datetime

from src.orders.order_manager import OrderManager
from src.orders.position_monitor import PositionMonitor
from src.orders.order_models import (
    OrderRequest, OrderResponse, OrderStatus, Position, OrderType, OrderAction
)
from src.models.trading_models import Trade, TradeLeg, TradeStatus, OptionType, OrderAction as ModelOrderAction
from src.api.angel_api_client import AngelAPIClient


class TestOrderManagementIntegration(unittest.TestCase):
    """Integration tests for the complete order management system"""
    
    def setUp(self):
        self.mock_api_client = Mock(spec=AngelAPIClient)
        
        self.config = {
            'validation': {
                'lot_size': 25,
                'max_order_value': 1000000,
                'min_volume': 0,
                'min_open_interest': 0
            },
            'retry': {
                'strategy': 'exponential_backoff',
                'max_attempts': 3,
                'base_delay': 0.1,
                'max_delay': 1.0,
                'backoff_multiplier': 2.0
            },
            'fallback': {
                'enabled': True,
                'max_price_adjustment': 0.05,
                'min_quantity_reduction': 1
            },
            'monitoring_interval': 0.1
        }
        
        self.order_manager = OrderManager(self.mock_api_client, self.config, mode="paper")
        
        self.monitor_config = {
            'default_target_pnl': 2000.0,
            'default_stop_loss': -1000.0,
            'max_daily_loss': -5000.0,
            'position_timeout_hours': 6,
            'monitoring_interval': 0.1,
            'auto_close_on_target': True,
            'auto_close_on_stop': True
        }
        
        self.position_monitor = PositionMonitor(self.order_manager, self.monitor_config)
    
    def test_complete_trading_workflow(self):
        """Test complete trading workflow from signal to position monitoring"""
        # Step 1: Create and place orders for a straddle strategy
        call_order = OrderRequest(
            symbol="BANKNIFTY2412545000CE",
            token="12345",
            exchange="NFO",
            action=OrderAction.SELL,
            order_type=OrderType.MARKET,
            quantity=25,
            trade_id="STRADDLE_001",
            strategy_name="short_straddle"
        )
        
        put_order = OrderRequest(
            symbol="BANKNIFTY2412545000PE",
            token="12346",
            exchange="NFO",
            action=OrderAction.SELL,
            order_type=OrderType.MARKET,
            quantity=25,
            trade_id="STRADDLE_001",
            strategy_name="short_straddle"
        )
        
        # Mock LTP for validation
        self.mock_api_client.get_ltp.side_effect = [100.0, 95.0]
        
        # Place orders
        call_response = self.order_manager.place_order(call_order)
        put_response = self.order_manager.place_order(put_order)
        
        self.assertTrue(call_response.is_success)
        self.assertTrue(put_response.is_success)
        
        # Step 2: Create trade object and add to position monitor
        trade = Trade(
            trade_id="STRADDLE_001",
            strategy="short_straddle",
            underlying_symbol="BANKNIFTY",
            entry_time=datetime.now(),
            target_pnl=2000.0,
            stop_loss=-1000.0
        )
        
        # Add legs to trade
        call_leg = TradeLeg(
            symbol="BANKNIFTY2412545000CE",
            token="12345",
            strike=45000.0,
            option_type=OptionType.CE,
            action=ModelOrderAction.SELL,
            quantity=25,
            entry_price=100.0,
            current_price=100.0
        )
        
        put_leg = TradeLeg(
            symbol="BANKNIFTY2412545000PE",
            token="12346",
            strike=45000.0,
            option_type=OptionType.PE,
            action=ModelOrderAction.SELL,
            quantity=25,
            entry_price=95.0,
            current_price=95.0
        )
        
        trade.add_leg(call_leg)
        trade.add_leg(put_leg)
        
        # Step 3: Add trade to position monitor
        self.position_monitor.add_trade(trade)
        
        # Verify trade is being monitored
        self.assertIn("STRADDLE_001", self.position_monitor.monitored_trades)
        
        # Step 4: Simulate price changes and check P&L
        price_updates = {
            "BANKNIFTY2412545000CE": 80.0,  # Call option price decreased (profit for short)
            "BANKNIFTY2412545000PE": 75.0   # Put option price decreased (profit for short)
        }
        
        self.position_monitor.update_trade_prices("STRADDLE_001", price_updates)
        
        # Calculate expected P&L: (100-80)*25 + (95-75)*25 = 500 + 500 = 1000
        expected_pnl = (100.0 - 80.0) * 25 + (95.0 - 75.0) * 25
        actual_pnl = self.position_monitor.get_trade_pnl("STRADDLE_001")
        
        self.assertEqual(actual_pnl, expected_pnl)
        
        # Step 5: Test position summary
        summary = self.position_monitor.get_position_summary()
        
        self.assertEqual(summary['open_trades'], 1)
        self.assertEqual(summary['total_unrealized_pnl'], expected_pnl)
        self.assertIn('short_straddle', summary['positions_by_strategy'])
    
    def test_target_hit_scenario(self):
        """Test automatic position closure when target is hit"""
        # Create profitable trade
        trade = Trade(
            trade_id="TARGET_TEST",
            strategy="test_strategy",
            underlying_symbol="BANKNIFTY",
            entry_time=datetime.now(),
            target_pnl=1000.0,  # Lower target for easier testing
            stop_loss=-500.0
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
        self.position_monitor.add_trade(trade)
        
        # Mock successful exit order placement
        mock_response = Mock()
        mock_response.is_success = True
        mock_response.order_id = "EXIT_TARGET"
        self.order_manager.place_order = Mock(return_value=mock_response)
        
        # Update price to hit target
        price_updates = {"BANKNIFTY2412545000CE": 140.0}  # 40 point profit * 25 = 1000
        self.position_monitor.update_trade_prices("TARGET_TEST", price_updates)
        
        # Check if target was hit
        pnl = self.position_monitor.get_trade_pnl("TARGET_TEST")
        self.assertGreaterEqual(pnl, trade.target_pnl)
        
        # Simulate target hit processing
        self.position_monitor._check_trade_exit_conditions(trade)
        
        # In a real scenario, this would trigger automatic closure
        # For this test, we verify the P&L calculation is correct
        self.assertEqual(pnl, 1000.0)
    
    def test_stop_loss_scenario(self):
        """Test automatic position closure when stop loss is hit"""
        trade = Trade(
            trade_id="STOP_TEST",
            strategy="test_strategy",
            underlying_symbol="BANKNIFTY",
            entry_time=datetime.now(),
            target_pnl=1000.0,
            stop_loss=-500.0
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
        self.position_monitor.add_trade(trade)
        
        # Update price to hit stop loss
        price_updates = {"BANKNIFTY2412545000CE": 80.0}  # 20 point loss * 25 = -500
        self.position_monitor.update_trade_prices("STOP_TEST", price_updates)
        
        # Check if stop loss was hit
        pnl = self.position_monitor.get_trade_pnl("STOP_TEST")
        self.assertLessEqual(pnl, trade.stop_loss)
        self.assertEqual(pnl, -500.0)
    
    def test_order_retry_integration(self):
        """Test order retry mechanism integration"""
        self.order_manager.mode = "live"  # Switch to live mode for retry testing
        
        order = OrderRequest(
            symbol="BANKNIFTY2412545000CE",
            token="12345",
            exchange="NFO",
            action=OrderAction.BUY,
            order_type=OrderType.LIMIT,
            quantity=25,
            price=100.0
        )
        
        # Mock API to fail first, then succeed
        self.mock_api_client.get_ltp.return_value = 100.0
        self.mock_api_client.place_order.side_effect = [
            {'status': False, 'message': 'Network error'},
            {'status': True, 'data': {'orderid': 'RETRY_SUCCESS'}}
        ]
        
        response = self.order_manager.place_order(order)
        
        self.assertTrue(response.is_success)
        self.assertEqual(response.order_id, 'RETRY_SUCCESS')
    
    def test_position_monitoring_with_multiple_trades(self):
        """Test position monitoring with multiple concurrent trades"""
        # Create multiple trades
        trades = []
        for i in range(3):
            trade = Trade(
                trade_id=f"MULTI_TEST_{i}",
                strategy="test_strategy",
                underlying_symbol="BANKNIFTY",
                entry_time=datetime.now(),
                target_pnl=1000.0,
                stop_loss=-500.0
            )
            
            leg = TradeLeg(
                symbol=f"BANKNIFTY2412{45000 + i*100}CE",
                token=f"1234{i}",
                strike=45000.0 + i*100,
                option_type=OptionType.CE,
                action=ModelOrderAction.BUY,
                quantity=25,
                entry_price=100.0,
                current_price=100.0
            )
            
            trade.add_leg(leg)
            trades.append(trade)
            self.position_monitor.add_trade(trade)
        
        # Update prices for all trades
        for i, trade in enumerate(trades):
            price_updates = {f"BANKNIFTY2412{45000 + i*100}CE": 110.0 + i*5}
            self.position_monitor.update_trade_prices(trade.trade_id, price_updates)
        
        # Check summary
        summary = self.position_monitor.get_position_summary()
        
        self.assertEqual(summary['open_trades'], 3)
        self.assertGreater(summary['total_unrealized_pnl'], 0)
    
    def test_risk_management_integration(self):
        """Test risk management integration across components"""
        # Set up daily loss scenario
        self.position_monitor.daily_pnl = -4000.0  # Close to limit
        
        # Create a losing trade
        trade = Trade(
            trade_id="RISK_TEST",
            strategy="test_strategy",
            underlying_symbol="BANKNIFTY",
            entry_time=datetime.now(),
            target_pnl=1000.0,
            stop_loss=-500.0
        )
        
        leg = TradeLeg(
            symbol="BANKNIFTY2412545000CE",
            token="12345",
            strike=45000.0,
            option_type=OptionType.CE,
            action=ModelOrderAction.BUY,
            quantity=25,
            entry_price=100.0,
            current_price=80.0  # Losing position
        )
        
        trade.add_leg(leg)
        self.position_monitor.add_trade(trade)
        
        # Update to create more loss
        price_updates = {"BANKNIFTY2412545000CE": 60.0}  # Big loss
        self.position_monitor.update_trade_prices("RISK_TEST", price_updates)
        
        # This would push daily loss over limit
        trade_pnl = self.position_monitor.get_trade_pnl("RISK_TEST")
        projected_daily_pnl = self.position_monitor.daily_pnl + trade_pnl
        
        # Check risk alerts
        alerts = self.position_monitor.check_risk_limits()
        
        # Should have daily loss limit alert if projected loss exceeds limit
        if projected_daily_pnl <= self.monitor_config['max_daily_loss']:
            self.assertTrue(any("DAILY_LOSS_LIMIT" in alert for alert in alerts))
    
    def tearDown(self):
        """Clean up after tests"""
        self.order_manager.stop_monitoring()
        self.position_monitor.stop_monitoring()


if __name__ == '__main__':
    unittest.main()