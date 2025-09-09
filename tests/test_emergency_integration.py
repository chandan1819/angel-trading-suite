"""
Integration tests for emergency controls and safety mechanisms.

Tests the integration between TradingManager, EmergencyController, and SafetyMonitor
to ensure proper emergency handling and safety enforcement.
"""

import unittest
import tempfile
import os
import time
import threading
from datetime import datetime, timedelta
from unittest.mock import Mock, patch, MagicMock

import sys
from pathlib import Path
sys.path.append(str(Path(__file__).parent.parent / "src"))

from models.config_models import TradingConfig, RiskConfig
from models.trading_models import Trade, TradeLeg, TradeStatus, OptionType
from trading.trading_manager import TradingManager
from emergency.emergency_controller import EmergencyController, EmergencyType, EmergencyLevel
from emergency.safety_monitor import SafetyMonitor, SafetyCheckType


class TestEmergencyIntegration(unittest.TestCase):
    """Test emergency controls integration"""
    
    def setUp(self):
        """Set up test environment"""
        self.temp_dir = tempfile.mkdtemp()
        self.emergency_stop_file = os.path.join(self.temp_dir, "emergency_stop.txt")
        
        # Create test configuration
        self.config = TradingConfig()
        self.config.risk = RiskConfig()
        self.config.risk.max_daily_loss = 10000.0
        self.config.risk.max_concurrent_trades = 3
        self.config.risk.profit_target = 2000.0
        self.config.risk.stop_loss = 1000.0
        self.config.risk.emergency_stop_file = self.emergency_stop_file
        
        # Mock API client
        self.mock_api_client = Mock()
        self.mock_api_client.initialize.return_value = True
        
    def tearDown(self):
        """Clean up test environment"""
        # Remove emergency stop file if it exists
        if os.path.exists(self.emergency_stop_file):
            os.remove(self.emergency_stop_file)
        
        # Clean up temp directory
        import shutil
        shutil.rmtree(self.temp_dir, ignore_errors=True)
    
    def test_emergency_stop_file_detection(self):
        """Test emergency stop file detection and handling"""
        # Create emergency controller
        emergency_config = {
            'emergency_stop_file': self.emergency_stop_file,
            'daily_loss_limit': 10000.0,
            'check_interval': 0.1  # Fast checking for tests
        }
        
        emergency_controller = EmergencyController(emergency_config)
        
        # Track emergency events
        emergency_events = []
        def capture_event(event):
            emergency_events.append(event)
        
        emergency_controller.register_emergency_callback(
            EmergencyType.MANUAL_STOP, capture_event
        )
        
        # Start monitoring
        emergency_controller.start_monitoring()
        
        try:
            # Create emergency stop file
            with open(self.emergency_stop_file, 'w') as f:
                f.write("Test emergency stop")
            
            # Wait for detection
            time.sleep(0.5)
            
            # Verify emergency stop was detected
            self.assertTrue(emergency_controller.emergency_stop_active)
            self.assertEqual(len(emergency_events), 1)
            self.assertEqual(emergency_events[0].event_type, EmergencyType.MANUAL_STOP)
            
            # Remove emergency stop file
            os.remove(self.emergency_stop_file)
            time.sleep(0.5)
            
            # Verify emergency stop was deactivated
            self.assertFalse(emergency_controller.emergency_stop_active)
            
        finally:
            emergency_controller.stop_monitoring()
    
    def test_daily_loss_limit_enforcement(self):
        """Test daily loss limit enforcement"""
        emergency_config = {
            'emergency_stop_file': self.emergency_stop_file,
            'daily_loss_limit': 5000.0,
            'check_interval': 0.1
        }
        
        emergency_controller = EmergencyController(emergency_config)
        
        # Track emergency events
        emergency_events = []
        def capture_event(event):
            emergency_events.append(event)
        
        emergency_controller.register_emergency_callback(
            EmergencyType.DAILY_LOSS_LIMIT, capture_event
        )
        
        emergency_controller.start_monitoring()
        
        try:
            # Update daily loss to exceed limit
            emergency_controller.update_daily_loss(6000.0)
            
            # Wait for detection
            time.sleep(0.5)
            
            # Verify daily loss limit breach was detected
            self.assertTrue(emergency_controller.daily_loss_limit_breached)
            self.assertEqual(len(emergency_events), 1)
            self.assertEqual(emergency_events[0].event_type, EmergencyType.DAILY_LOSS_LIMIT)
            
        finally:
            emergency_controller.stop_monitoring()
    
    def test_safety_monitor_position_limits(self):
        """Test safety monitor position limit checking"""
        emergency_controller = EmergencyController({
            'emergency_stop_file': self.emergency_stop_file,
            'daily_loss_limit': 10000.0
        })
        
        safety_config = {
            'check_interval': 0.1,
            'max_concurrent_positions': 2,
            'max_single_position_size': 5000.0,
            'enabled_checks': [SafetyCheckType.POSITION_LIMITS]
        }
        
        safety_monitor = SafetyMonitor(safety_config, emergency_controller)
        
        # Create test trades that exceed limits
        trades = {}
        for i in range(3):  # Exceeds max_concurrent_positions
            trade = Trade(
                trade_id=f"TEST_{i}",
                strategy="test_strategy",
                entry_time=datetime.now(),
                exit_time=None,
                legs=[],
                target_pnl=2000.0,
                stop_loss=-1000.0,
                current_pnl=0.0,
                status=TradeStatus.OPEN,
                underlying_symbol="BANKNIFTY",
                expiry_date="2024-12-26"
            )
            trades[trade.trade_id] = trade
        
        safety_monitor.start_monitoring()
        
        try:
            # Update with trades that exceed limits
            safety_monitor.update_trading_state(trades, 0.0)
            
            # Wait for safety check
            time.sleep(0.5)
            
            # Verify safety violations were recorded
            violations = safety_monitor.get_safety_violations()
            position_violations = [v for v in violations 
                                 if v.check_type == SafetyCheckType.POSITION_LIMITS]
            
            self.assertGreater(len(position_violations), 0)
            
        finally:
            safety_monitor.stop_monitoring()
    
    def test_trading_manager_emergency_integration(self):
        """Test TradingManager integration with emergency controls"""
        with patch('src.api.angel_api_client.AngelAPIClient') as mock_api_class:
            mock_api_class.return_value = self.mock_api_client
            
            with patch('src.data.data_manager.DataManager') as mock_data_manager:
                with patch('src.strategies.strategy_manager.StrategyManager') as mock_strategy_manager:
                    with patch('src.risk.risk_manager.RiskManager') as mock_risk_manager:
                        with patch('src.orders.order_manager.OrderManager') as mock_order_manager:
                            with patch('src.logging.logging_manager.LoggingManager') as mock_logging_manager:
                                
                                # Setup mocks
                                mock_risk_manager.return_value.initialize.return_value = True
                                mock_logging_manager.return_value.initialize.return_value = True
                                
                                # Create trading manager
                                trading_manager = TradingManager(self.config, "paper")
                                
                                # Initialize (should create emergency components)
                                success = trading_manager.initialize()
                                self.assertTrue(success)
                                
                                # Verify emergency components were created
                                self.assertIsNotNone(trading_manager.emergency_controller)
                                self.assertIsNotNone(trading_manager.safety_monitor)
                                
                                # Test emergency stop file creation
                                trading_manager.emergency_controller.create_emergency_stop_file("Test stop")
                                self.assertTrue(os.path.exists(self.emergency_stop_file))
                                
                                # Cleanup
                                trading_manager.cleanup()
    
    def test_emergency_shutdown_procedure(self):
        """Test complete emergency shutdown procedure"""
        emergency_config = {
            'emergency_stop_file': self.emergency_stop_file,
            'daily_loss_limit': 10000.0,
            'shutdown_timeout': 5,  # Short timeout for testing
            'force_close_after_timeout': True
        }
        
        emergency_controller = EmergencyController(emergency_config)
        
        # Create mock trades
        test_trades = {
            'TRADE_1': Trade(
                trade_id='TRADE_1',
                strategy='test',
                entry_time=datetime.now(),
                exit_time=None,
                legs=[],
                target_pnl=2000.0,
                stop_loss=-1000.0,
                current_pnl=-500.0,
                status=TradeStatus.OPEN,
                underlying_symbol="BANKNIFTY",
                expiry_date="2024-12-26"
            )
        }
        
        emergency_controller.update_active_trades(test_trades)
        
        # Track position close calls
        close_calls = []
        def mock_close_position(trade_id, reason, emergency=False):
            close_calls.append((trade_id, reason, emergency))
        
        emergency_controller.register_position_close_callback(mock_close_position)
        
        # Initiate emergency shutdown
        emergency_controller.initiate_emergency_shutdown("Test emergency")
        
        # Wait for shutdown to complete
        time.sleep(1)
        
        # Verify position close was called
        self.assertEqual(len(close_calls), 1)
        self.assertEqual(close_calls[0][0], 'TRADE_1')
        self.assertTrue(close_calls[0][2])  # emergency=True
    
    def test_safety_monitor_system_resources(self):
        """Test safety monitor system resource checking"""
        emergency_controller = EmergencyController({
            'emergency_stop_file': self.emergency_stop_file,
            'daily_loss_limit': 10000.0
        })
        
        safety_config = {
            'check_interval': 0.1,
            'max_cpu_usage': 1.0,  # Very low threshold to trigger violation
            'max_memory_usage': 1.0,  # Very low threshold to trigger violation
            'enabled_checks': [SafetyCheckType.SYSTEM_RESOURCES]
        }
        
        safety_monitor = SafetyMonitor(safety_config, emergency_controller)
        safety_monitor.start_monitoring()
        
        try:
            # Wait for resource check
            time.sleep(0.5)
            
            # Verify resource violations were recorded
            violations = safety_monitor.get_safety_violations()
            resource_violations = [v for v in violations 
                                 if v.check_type == SafetyCheckType.SYSTEM_RESOURCES]
            
            # Should have CPU and/or memory violations due to low thresholds
            self.assertGreater(len(resource_violations), 0)
            
        finally:
            safety_monitor.stop_monitoring()
    
    def test_emergency_status_reporting(self):
        """Test emergency status reporting"""
        emergency_config = {
            'emergency_stop_file': self.emergency_stop_file,
            'daily_loss_limit': 10000.0
        }
        
        emergency_controller = EmergencyController(emergency_config)
        safety_monitor = SafetyMonitor({}, emergency_controller)
        
        # Get initial status
        emergency_status = emergency_controller.get_emergency_status()
        safety_status = safety_monitor.get_safety_status()
        
        # Verify status structure
        self.assertIn('emergency_stop_active', emergency_status)
        self.assertIn('daily_loss_limit_breached', emergency_status)
        self.assertIn('monitoring_active', emergency_status)
        
        self.assertIn('monitoring_active', safety_status)
        self.assertIn('enabled_checks', safety_status)
        self.assertIn('system_resources', safety_status)
        
        # Test with emergency stop active
        emergency_controller.create_emergency_stop_file("Test")
        emergency_controller.start_monitoring()
        
        try:
            time.sleep(0.2)
            
            updated_status = emergency_controller.get_emergency_status()
            self.assertTrue(updated_status['emergency_stop_file_exists'])
            
        finally:
            emergency_controller.stop_monitoring()


class TestEmergencyScenarios(unittest.TestCase):
    """Test various emergency scenarios"""
    
    def setUp(self):
        """Set up test environment"""
        self.temp_dir = tempfile.mkdtemp()
        self.emergency_stop_file = os.path.join(self.temp_dir, "emergency_stop.txt")
    
    def tearDown(self):
        """Clean up test environment"""
        import shutil
        shutil.rmtree(self.temp_dir, ignore_errors=True)
    
    def test_concurrent_emergency_events(self):
        """Test handling of multiple concurrent emergency events"""
        emergency_config = {
            'emergency_stop_file': self.emergency_stop_file,
            'daily_loss_limit': 5000.0,
            'check_interval': 0.1
        }
        
        emergency_controller = EmergencyController(emergency_config)
        
        # Track all emergency events
        all_events = []
        def capture_all_events(event):
            all_events.append(event)
        
        # Register for multiple event types
        emergency_controller.register_emergency_callback(
            EmergencyType.MANUAL_STOP, capture_all_events
        )
        emergency_controller.register_emergency_callback(
            EmergencyType.DAILY_LOSS_LIMIT, capture_all_events
        )
        
        emergency_controller.start_monitoring()
        
        try:
            # Trigger multiple emergency conditions simultaneously
            emergency_controller.update_daily_loss(6000.0)  # Exceeds limit
            
            with open(self.emergency_stop_file, 'w') as f:
                f.write("Manual stop")
            
            # Wait for both events to be processed
            time.sleep(0.5)
            
            # Verify both events were captured
            self.assertGreaterEqual(len(all_events), 2)
            
            event_types = [event.event_type for event in all_events]
            self.assertIn(EmergencyType.MANUAL_STOP, event_types)
            self.assertIn(EmergencyType.DAILY_LOSS_LIMIT, event_types)
            
        finally:
            emergency_controller.stop_monitoring()
    
    def test_emergency_recovery(self):
        """Test emergency recovery procedures"""
        emergency_config = {
            'emergency_stop_file': self.emergency_stop_file,
            'daily_loss_limit': 10000.0,
            'check_interval': 0.1
        }
        
        emergency_controller = EmergencyController(emergency_config)
        emergency_controller.start_monitoring()
        
        try:
            # Create emergency condition
            with open(self.emergency_stop_file, 'w') as f:
                f.write("Test emergency")
            
            time.sleep(0.2)
            self.assertTrue(emergency_controller.emergency_stop_active)
            
            # Remove emergency condition
            os.remove(self.emergency_stop_file)
            time.sleep(0.2)
            
            # Verify recovery
            self.assertFalse(emergency_controller.emergency_stop_active)
            
            # Check that events are marked as resolved
            events = emergency_controller.get_emergency_events()
            manual_stop_events = [e for e in events if e.event_type == EmergencyType.MANUAL_STOP]
            
            if manual_stop_events:
                # At least one should be resolved
                resolved_events = [e for e in manual_stop_events if e.resolved]
                self.assertGreater(len(resolved_events), 0)
            
        finally:
            emergency_controller.stop_monitoring()


if __name__ == '__main__':
    unittest.main()