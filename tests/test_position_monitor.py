"""
Unit tests for the Position Monitor module.

Tests real-time position monitoring, alert generation, and automatic position closure.
"""

import pytest
import time
import threading
from datetime import datetime, timedelta
from unittest.mock import Mock, patch

from src.risk.position_monitor import PositionMonitor, MonitoringConfig
from src.risk.risk_models import RiskAlert, RiskAlertType, RiskLevel, PositionRisk
from src.models.trading_models import (
    Trade, TradeLeg, OptionType, OrderAction, TradeStatus
)
from src.models.config_models import TradingConfig


class TestPositionMonitor:
    """Test cases for PositionMonitor class"""
    
    @pytest.fixture
    def trading_config(self):
        """Create test trading configuration"""
        return TradingConfig()
    
    @pytest.fixture
    def position_monitor(self, trading_config):
        """Create PositionMonitor instance"""
        monitor = PositionMonitor(trading_config)
        monitor.initialize()
        return monitor
    
    @pytest.fixture
    def sample_trade(self):
        """Create sample trade for testing"""
        trade = Trade(
            trade_id="TEST001",
            strategy="test_strategy",
            underlying_symbol="BANKNIFTY",
            entry_time=datetime.now(),
            target_pnl=2000.0,
            stop_loss=-1000.0,
            status=TradeStatus.OPEN
        )
        
        # Add a trade leg
        leg = TradeLeg(
            symbol="BANKNIFTY2412550000CE",
            token="12345",
            strike=50000.0,
            option_type=OptionType.CE,
            action=OrderAction.SELL,
            quantity=1,
            entry_price=150.0,
            current_price=130.0
        )
        trade.add_leg(leg)
        return trade
    
    @pytest.fixture
    def profitable_trade(self):
        """Create profitable trade that hits target"""
        trade = Trade(
            trade_id="PROFIT001",
            strategy="test_strategy",
            underlying_symbol="BANKNIFTY",
            entry_time=datetime.now(),
            target_pnl=2000.0,
            stop_loss=-1000.0,
            status=TradeStatus.OPEN
        )
        
        # Add profitable leg (short position with price drop)
        leg = TradeLeg(
            symbol="BANKNIFTY2412550000CE",
            token="12345",
            strike=50000.0,
            option_type=OptionType.CE,
            action=OrderAction.SELL,
            quantity=25,  # Full lot
            entry_price=150.0,
            current_price=70.0  # Significant profit
        )
        trade.add_leg(leg)
        return trade
    
    @pytest.fixture
    def losing_trade(self):
        """Create losing trade that hits stop loss"""
        trade = Trade(
            trade_id="LOSS001",
            strategy="test_strategy",
            underlying_symbol="BANKNIFTY",
            entry_time=datetime.now(),
            target_pnl=2000.0,
            stop_loss=-1000.0,
            status=TradeStatus.OPEN
        )
        
        # Add losing leg (short position with price rise)
        leg = TradeLeg(
            symbol="BANKNIFTY2412550000CE",
            token="12345",
            strike=50000.0,
            option_type=OptionType.CE,
            action=OrderAction.SELL,
            quantity=25,  # Full lot
            entry_price=150.0,
            current_price=190.0  # Significant loss
        )
        trade.add_leg(leg)
        return trade
    
    def test_initialization(self, position_monitor):
        """Test position monitor initialization"""
        assert position_monitor.is_initialized()
        assert not position_monitor.monitoring_active
        assert len(position_monitor.active_positions) == 0
        assert len(position_monitor.position_risks) == 0
    
    def test_add_position(self, position_monitor, sample_trade):
        """Test adding position to monitoring"""
        position_monitor.add_position(sample_trade)
        
        assert sample_trade.trade_id in position_monitor.active_positions
        assert sample_trade.trade_id in position_monitor.position_risks
        
        # Check position risk was created
        risk = position_monitor.get_position_risk(sample_trade.trade_id)
        assert risk is not None
        assert risk.trade_id == sample_trade.trade_id
        assert risk.current_pnl == sample_trade.current_pnl
    
    def test_remove_position(self, position_monitor, sample_trade):
        """Test removing position from monitoring"""
        # Add position first
        position_monitor.add_position(sample_trade)
        assert sample_trade.trade_id in position_monitor.active_positions
        
        # Remove position
        position_monitor.remove_position(sample_trade.trade_id)
        assert sample_trade.trade_id not in position_monitor.active_positions
        assert sample_trade.trade_id not in position_monitor.position_risks
    
    def test_update_position(self, position_monitor, sample_trade):
        """Test updating position data"""
        # Add position first
        position_monitor.add_position(sample_trade)
        original_price = sample_trade.legs[0].current_price
        
        # Update position
        sample_trade.legs[0].current_price = 140.0
        position_monitor.update_position(sample_trade)
        
        # Check position was updated
        updated_trade = position_monitor.active_positions[sample_trade.trade_id]
        assert updated_trade.legs[0].current_price == 140.0
        assert updated_trade.legs[0].current_price != original_price
    
    def test_get_position_risk(self, position_monitor, sample_trade):
        """Test getting position risk metrics"""
        position_monitor.add_position(sample_trade)
        
        risk = position_monitor.get_position_risk(sample_trade.trade_id)
        
        assert risk is not None
        assert isinstance(risk, PositionRisk)
        assert risk.trade_id == sample_trade.trade_id
        assert risk.profit_target == sample_trade.target_pnl
        assert risk.stop_loss == sample_trade.stop_loss
        assert risk.position_size > 0
        assert risk.margin_used > 0
    
    def test_get_all_position_risks(self, position_monitor, sample_trade):
        """Test getting all position risks"""
        position_monitor.add_position(sample_trade)
        
        all_risks = position_monitor.get_all_position_risks()
        
        assert len(all_risks) == 1
        assert sample_trade.trade_id in all_risks
        assert isinstance(all_risks[sample_trade.trade_id], PositionRisk)
    
    def test_alert_callback_registration(self, position_monitor):
        """Test alert callback registration and triggering"""
        alerts_received = []
        
        def alert_callback(alert):
            alerts_received.append(alert)
        
        position_monitor.add_alert_callback(alert_callback)
        
        # Create and trigger an alert
        test_alert = RiskAlert(
            alert_type=RiskAlertType.PROFIT_TARGET_HIT,
            level=RiskLevel.HIGH,
            message="Test alert"
        )
        
        position_monitor._trigger_alert(test_alert)
        
        assert len(alerts_received) == 1
        assert alerts_received[0] == test_alert
    
    def test_position_close_callback_registration(self, position_monitor, sample_trade):
        """Test position close callback registration and triggering"""
        close_calls = []
        
        def close_callback(trade, reason):
            close_calls.append((trade.trade_id, reason))
        
        position_monitor.add_position_close_callback(close_callback)
        
        # Trigger position close
        position_monitor._trigger_position_close(sample_trade, "Test close")
        
        assert len(close_calls) == 1
        assert close_calls[0][0] == sample_trade.trade_id
        assert close_calls[0][1] == "Test close"
    
    def test_force_close_all_positions(self, position_monitor, sample_trade):
        """Test force closing all positions"""
        close_calls = []
        
        def close_callback(trade, reason):
            close_calls.append((trade.trade_id, reason))
        
        position_monitor.add_position_close_callback(close_callback)
        position_monitor.add_position(sample_trade)
        
        closed_positions = position_monitor.force_close_all_positions("Emergency")
        
        assert len(closed_positions) == 1
        assert sample_trade.trade_id in closed_positions
        assert len(close_calls) == 1
        assert close_calls[0][1] == "Emergency"
    
    def test_get_monitoring_status(self, position_monitor, sample_trade):
        """Test getting monitoring status"""
        position_monitor.add_position(sample_trade)
        
        status = position_monitor.get_monitoring_status()
        
        assert isinstance(status, dict)
        assert 'monitoring_active' in status
        assert 'active_positions_count' in status
        assert 'monitored_positions' in status
        assert 'check_interval' in status
        assert 'last_check' in status
        
        assert status['active_positions_count'] == 1
        assert sample_trade.trade_id in status['monitored_positions']
    
    def test_start_stop_monitoring(self, position_monitor):
        """Test starting and stopping monitoring"""
        # Initially not monitoring
        assert not position_monitor.monitoring_active
        
        # Start monitoring
        success = position_monitor.start_monitoring()
        assert success
        assert position_monitor.monitoring_active
        assert position_monitor.monitor_thread is not None
        
        # Give thread time to start
        time.sleep(0.1)
        assert position_monitor.monitor_thread.is_alive()
        
        # Stop monitoring
        position_monitor.stop_monitoring()
        assert not position_monitor.monitoring_active
        
        # Give thread time to stop
        time.sleep(0.1)
        if position_monitor.monitor_thread:
            assert not position_monitor.monitor_thread.is_alive()
    
    def test_monitoring_loop_profit_target(self, position_monitor, profitable_trade):
        """Test monitoring loop detects profit target"""
        alerts_received = []
        close_calls = []
        
        def alert_callback(alert):
            alerts_received.append(alert)
        
        def close_callback(trade, reason):
            close_calls.append((trade.trade_id, reason))
        
        position_monitor.add_alert_callback(alert_callback)
        position_monitor.add_position_close_callback(close_callback)
        position_monitor.add_position(profitable_trade)
        
        # Manually trigger position check
        position_monitor._check_all_positions()
        
        # Should have profit target alert and close call
        profit_alerts = [a for a in alerts_received if a.alert_type == RiskAlertType.PROFIT_TARGET_HIT]
        assert len(profit_alerts) > 0
        assert len(close_calls) > 0
        assert "profit target" in close_calls[0][1].lower()
    
    def test_monitoring_loop_stop_loss(self, position_monitor, losing_trade):
        """Test monitoring loop detects stop loss"""
        alerts_received = []
        close_calls = []
        
        def alert_callback(alert):
            alerts_received.append(alert)
        
        def close_callback(trade, reason):
            close_calls.append((trade.trade_id, reason))
        
        position_monitor.add_alert_callback(alert_callback)
        position_monitor.add_position_close_callback(close_callback)
        position_monitor.add_position(losing_trade)
        
        # Manually trigger position check
        position_monitor._check_all_positions()
        
        # Should have stop loss alert and close call
        stop_alerts = [a for a in alerts_received if a.alert_type == RiskAlertType.STOP_LOSS_HIT]
        assert len(stop_alerts) > 0
        assert len(close_calls) > 0
        assert "stop loss" in close_calls[0][1].lower()
    
    def test_position_timeout_detection(self, position_monitor):
        """Test position timeout detection"""
        # Create old trade
        old_trade = Trade(
            trade_id="OLD001",
            strategy="test_strategy",
            underlying_symbol="BANKNIFTY",
            entry_time=datetime.now() - timedelta(hours=2),  # 2 hours ago
            target_pnl=2000.0,
            stop_loss=-1000.0,
            status=TradeStatus.OPEN
        )
        
        leg = TradeLeg(
            symbol="BANKNIFTY2412550000CE",
            token="12345",
            strike=50000.0,
            option_type=OptionType.CE,
            action=OrderAction.SELL,
            quantity=1,
            entry_price=150.0,
            current_price=150.0
        )
        old_trade.add_leg(leg)
        
        alerts_received = []
        
        def alert_callback(alert):
            alerts_received.append(alert)
        
        position_monitor.add_alert_callback(alert_callback)
        position_monitor.add_position(old_trade)
        
        # Set short timeout for testing
        position_monitor.monitoring_config.position_timeout = 3600  # 1 hour
        
        # Check if timeout is detected
        is_timed_out = position_monitor._is_position_timed_out(old_trade, datetime.now())
        assert is_timed_out
    
    def test_closed_position_removal(self, position_monitor, sample_trade):
        """Test that closed positions are removed from monitoring"""
        position_monitor.add_position(sample_trade)
        assert sample_trade.trade_id in position_monitor.active_positions
        
        # Close the trade
        sample_trade.status = TradeStatus.CLOSED
        
        # Manually trigger position check
        position_monitor._check_all_positions()
        
        # Position should be removed
        assert sample_trade.trade_id not in position_monitor.active_positions
    
    def test_position_risk_calculations(self, position_monitor, sample_trade):
        """Test position risk metric calculations"""
        position_monitor.add_position(sample_trade)
        
        risk = position_monitor.get_position_risk(sample_trade.trade_id)
        
        # Test risk level calculation
        assert risk.get_risk_level() in [RiskLevel.LOW, RiskLevel.MEDIUM, RiskLevel.HIGH, RiskLevel.CRITICAL]
        
        # Test distance calculations
        assert risk.profit_distance == risk.profit_target - risk.current_pnl
        assert risk.loss_distance == risk.current_pnl - risk.stop_loss
        
        # Test risk-reward ratio
        if risk.loss_distance > 0:
            expected_ratio = risk.profit_distance / risk.loss_distance
            assert abs(risk.risk_reward_ratio - expected_ratio) < 0.01
    
    def test_greeks_estimation(self, position_monitor, sample_trade):
        """Test Greeks estimation for position risk"""
        position_monitor.add_position(sample_trade)
        
        risk = position_monitor.get_position_risk(sample_trade.trade_id)
        
        # Check that Greeks are estimated (non-zero values)
        assert risk.delta_exposure != 0
        assert risk.time_decay_risk >= 0
        assert risk.volatility_risk >= 0
        assert risk.gamma_exposure != 0
    
    def test_monitoring_with_multiple_positions(self, position_monitor, sample_trade, profitable_trade):
        """Test monitoring multiple positions simultaneously"""
        position_monitor.add_position(sample_trade)
        position_monitor.add_position(profitable_trade)
        
        assert len(position_monitor.active_positions) == 2
        assert len(position_monitor.position_risks) == 2
        
        # Check all positions
        position_monitor._check_all_positions()
        
        # Both positions should still be tracked
        all_risks = position_monitor.get_all_position_risks()
        assert len(all_risks) == 2
    
    def test_cleanup(self, position_monitor, sample_trade):
        """Test position monitor cleanup"""
        # Add position and start monitoring
        position_monitor.add_position(sample_trade)
        position_monitor.start_monitoring()
        
        # Cleanup
        position_monitor.cleanup()
        
        assert not position_monitor.is_initialized()
        assert not position_monitor.monitoring_active
        assert len(position_monitor.active_positions) == 0
        assert len(position_monitor.position_risks) == 0
        assert len(position_monitor.alert_callbacks) == 0
        assert len(position_monitor.position_close_callbacks) == 0
    
    def test_error_handling_in_monitoring(self, position_monitor):
        """Test error handling in monitoring loop"""
        # Create invalid trade that might cause errors
        invalid_trade = Trade(
            trade_id="INVALID001",
            strategy="test_strategy",
            underlying_symbol="BANKNIFTY",
            entry_time=datetime.now(),
            target_pnl=2000.0,
            stop_loss=-1000.0,
            status=TradeStatus.OPEN
        )
        # Don't add legs to make it invalid
        
        position_monitor.add_position(invalid_trade)
        
        # This should not crash even with invalid trade
        position_monitor._check_all_positions()
        
        # Monitor should still be functional
        assert position_monitor.is_initialized()
    
    def test_concurrent_monitoring_operations(self, position_monitor, sample_trade):
        """Test concurrent operations during monitoring"""
        position_monitor.start_monitoring()
        
        # Add position while monitoring is active
        position_monitor.add_position(sample_trade)
        
        # Update position while monitoring is active
        sample_trade.legs[0].current_price = 140.0
        position_monitor.update_position(sample_trade)
        
        # Remove position while monitoring is active
        position_monitor.remove_position(sample_trade.trade_id)
        
        position_monitor.stop_monitoring()
        
        # Should complete without errors
        assert not position_monitor.monitoring_active


class TestMonitoringConfig:
    """Test cases for MonitoringConfig"""
    
    def test_default_config(self):
        """Test default monitoring configuration"""
        config = MonitoringConfig()
        
        assert config.check_interval == 30
        assert config.price_update_interval == 10
        assert config.emergency_check_interval == 5
        assert config.max_monitoring_threads == 5
        assert config.position_timeout == 3600
    
    def test_custom_config(self):
        """Test custom monitoring configuration"""
        config = MonitoringConfig(
            check_interval=60,
            price_update_interval=20,
            emergency_check_interval=10,
            max_monitoring_threads=10,
            position_timeout=7200
        )
        
        assert config.check_interval == 60
        assert config.price_update_interval == 20
        assert config.emergency_check_interval == 10
        assert config.max_monitoring_threads == 10
        assert config.position_timeout == 7200


if __name__ == "__main__":
    pytest.main([__file__])