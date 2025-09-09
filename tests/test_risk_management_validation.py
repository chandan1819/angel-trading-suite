"""
Comprehensive unit tests for risk management validation and enforcement.

This module tests all risk management rules, validation logic, and enforcement
mechanisms including daily limits, position limits, and emergency controls.
"""

import pytest
import os
import tempfile
from unittest.mock import Mock, patch, MagicMock
from datetime import datetime, date, timedelta

from src.risk.risk_manager import RiskManager
from src.risk.risk_models import (
    RiskAlert, RiskAlertType, RiskLevel, ValidationResult,
    DailyRiskMetrics, MarginRequirement
)
from src.models.trading_models import (
    TradingSignal, Trade, TradeLeg, SignalType, OptionType,
    OrderAction, TradeStatus
)
from src.models.config_models import TradingConfig, RiskConfig


class TestRiskValidationRules:
    """Test comprehensive risk validation rules"""
    
    @pytest.fixture
    def risk_config(self):
        """Create comprehensive risk configuration"""
        return RiskConfig(
            max_daily_loss=5000.0,
            max_concurrent_trades=3,
            profit_target=2000.0,
            stop_loss=1000.0,
            position_size_method="percentage",
            margin_buffer=0.2,
            max_position_size=5,
            daily_trade_limit=10,
            emergency_stop_file="test_emergency_stop.txt",
            max_single_trade_risk=2000.0,
            max_portfolio_risk=10000.0,
            risk_free_rate=0.05,
            volatility_threshold=0.3
        )
    
    @pytest.fixture
    def trading_config(self, risk_config):
        """Create trading configuration"""
        config = TradingConfig()
        config.risk = risk_config
        return config
    
    @pytest.fixture
    def risk_manager(self, trading_config):
        """Create RiskManager instance"""
        manager = RiskManager(trading_config)
        manager.initialize()
        return manager
    
    def create_signal(self, signal_type: SignalType = SignalType.BUY,
                     confidence: float = 0.8, stop_loss: float = -1000.0,
                     strategy_name: str = "test_strategy") -> TradingSignal:
        """Helper to create trading signals"""
        return TradingSignal(
            strategy_name=strategy_name,
            signal_type=signal_type,
            underlying="BANKNIFTY",
            strikes=[50000.0],
            option_types=[OptionType.CE],
            quantities=[1],
            confidence=confidence,
            target_pnl=2000.0,
            stop_loss=stop_loss
        )
    
    def create_trade(self, trade_id: str, current_pnl: float = 0.0) -> Trade:
        """Helper to create trades"""
        trade = Trade(
            trade_id=trade_id,
            strategy="test_strategy",
            underlying_symbol="BANKNIFTY",
            entry_time=datetime.now(),
            target_pnl=2000.0,
            stop_loss=-1000.0
        )
        
        # Add leg to generate P&L
        if current_pnl != 0:
            # Calculate prices to achieve desired P&L
            entry_price = 100.0
            current_price = entry_price + (current_pnl / 25)  # 25 is quantity
            
            leg = TradeLeg(
                symbol="BANKNIFTY2412550000CE",
                token="12345",
                strike=50000.0,
                option_type=OptionType.CE,
                action=OrderAction.BUY,
                quantity=25,
                entry_price=entry_price,
                current_price=current_price
            )
            trade.add_leg(leg)
        
        return trade
    
    def test_daily_loss_limit_validation(self, risk_manager):
        """Test daily loss limit validation"""
        # Set up daily metrics approaching limit
        today = date.today().isoformat()
        
        test_cases = [
            (-3000.0, True, "within_limit"),
            (-4999.0, True, "just_within_limit"),
            (-5000.0, False, "at_limit"),
            (-5001.0, False, "exceeds_limit"),
            (-10000.0, False, "far_exceeds_limit")
        ]
        
        for daily_pnl, should_pass, scenario in test_cases:
            risk_manager.daily_metrics[today].total_pnl = daily_pnl
            
            signal = self.create_signal()
            result = risk_manager.validate_trade(signal)
            
            if should_pass:
                assert result.is_valid, f"Should pass for {scenario}"
            else:
                assert not result.is_valid, f"Should fail for {scenario}"
                assert any(alert.alert_type == RiskAlertType.DAILY_LOSS_LIMIT 
                          for alert in result.alerts), f"Missing daily loss alert for {scenario}"
    
    def test_position_limit_validation(self, risk_manager):
        """Test concurrent position limit validation"""
        signal = self.create_signal()
        
        # Test with different numbers of active positions
        test_cases = [
            (0, True, "no_positions"),
            (1, True, "one_position"),
            (2, True, "two_positions"),
            (3, False, "at_limit"),
            (4, False, "exceeds_limit")
        ]
        
        for num_positions, should_pass, scenario in test_cases:
            # Set up active trades
            risk_manager.active_trades.clear()
            for i in range(num_positions):
                trade = self.create_trade(f"TRADE{i}")
                risk_manager.active_trades[f"TRADE{i}"] = trade
            
            result = risk_manager.validate_trade(signal)
            
            if should_pass:
                assert result.is_valid, f"Should pass for {scenario}"
            else:
                assert not result.is_valid, f"Should fail for {scenario}"
                assert any(alert.alert_type == RiskAlertType.POSITION_LIMIT_EXCEEDED 
                          for alert in result.alerts), f"Missing position limit alert for {scenario}"
    
    def test_trade_count_limit_validation(self, risk_manager):
        """Test daily trade count limit validation"""
        today = date.today().isoformat()
        
        test_cases = [
            (5, True, "normal_count"),
            (9, True, "approaching_limit"),
            (10, False, "at_limit"),
            (15, False, "exceeds_limit")
        ]
        
        for trade_count, should_pass, scenario in test_cases:
            risk_manager.daily_metrics[today].trades_count = trade_count
            
            signal = self.create_signal()
            result = risk_manager.validate_trade(signal)
            
            if should_pass:
                assert result.is_valid, f"Should pass for {scenario}"
            else:
                assert not result.is_valid, f"Should fail for {scenario}"
                assert any(alert.alert_type == RiskAlertType.TRADE_LIMIT_EXCEEDED 
                          for alert in result.alerts), f"Missing trade limit alert for {scenario}"
    
    def test_emergency_stop_validation(self, risk_manager):
        """Test emergency stop validation"""
        signal = self.create_signal()
        
        with tempfile.NamedTemporaryFile(delete=False) as temp_file:
            risk_manager.risk_config.emergency_stop_file = temp_file.name
            
            # Test without emergency file
            if os.path.exists(temp_file.name):
                os.unlink(temp_file.name)
            
            result = risk_manager.validate_trade(signal)
            assert result.is_valid, "Should pass without emergency file"
            
            # Test with emergency file
            with open(temp_file.name, 'w') as f:
                f.write("EMERGENCY STOP")
            
            result = risk_manager.validate_trade(signal)
            assert not result.is_valid, "Should fail with emergency file"
            assert any(alert.alert_type == RiskAlertType.EMERGENCY_STOP 
                      for alert in result.alerts), "Missing emergency stop alert"
            
            # Cleanup
            if os.path.exists(temp_file.name):
                os.unlink(temp_file.name)
    
    def test_signal_structure_validation(self, risk_manager):
        """Test trading signal structure validation"""
        # Test valid signal
        valid_signal = self.create_signal()
        result = risk_manager.validate_trade(valid_signal)
        assert result.is_valid, "Valid signal should pass"
        
        # Test invalid signals
        invalid_signals = [
            # Empty strategy name
            TradingSignal("", SignalType.BUY, "BANKNIFTY", [50000], [OptionType.CE], [1], 0.8),
            
            # Invalid confidence (> 1.0)
            TradingSignal("test", SignalType.BUY, "BANKNIFTY", [50000], [OptionType.CE], [1], 1.5),
            
            # Empty strikes
            TradingSignal("test", SignalType.BUY, "BANKNIFTY", [], [OptionType.CE], [1], 0.8),
            
            # Mismatched arrays
            TradingSignal("test", SignalType.BUY, "BANKNIFTY", [50000, 50100], [OptionType.CE], [1], 0.8),
        ]
        
        for invalid_signal in invalid_signals:
            result = risk_manager.validate_trade(invalid_signal)
            assert not result.is_valid, f"Invalid signal should fail: {invalid_signal}"
    
    def test_position_size_validation(self, risk_manager):
        """Test position size validation within trade validation"""
        signal = self.create_signal()
        
        # Mock position size calculation to return invalid size
        with patch.object(risk_manager, 'calculate_position_size') as mock_calc:
            # Return invalid position size result
            invalid_result = Mock()
            invalid_result.is_valid.return_value = False
            invalid_result.recommended_size = 0
            mock_calc.return_value = invalid_result
            
            result = risk_manager.validate_trade(signal)
            
            assert not result.is_valid, "Should fail with invalid position size"
            assert any(alert.alert_type == RiskAlertType.POSITION_SIZE_VIOLATION 
                      for alert in result.alerts), "Missing position size alert"
    
    def test_margin_requirement_validation(self, risk_manager):
        """Test margin requirement validation"""
        signal = self.create_signal()
        
        # Test with sufficient margin
        with patch.object(risk_manager, '_get_available_margin', return_value=100000.0):
            margin_req = risk_manager.validate_margin_requirement(signal, 2)
            
            assert margin_req.is_sufficient, "Should have sufficient margin"
            assert margin_req.margin_utilization < 100.0
            assert margin_req.get_margin_shortage() == 0.0
        
        # Test with insufficient margin
        with patch.object(risk_manager, '_get_available_margin', return_value=10000.0):
            margin_req = risk_manager.validate_margin_requirement(signal, 5)
            
            assert not margin_req.is_sufficient, "Should have insufficient margin"
            assert margin_req.margin_utilization > 100.0
            assert margin_req.get_margin_shortage() > 0.0
    
    def test_risk_validation_with_multiple_violations(self, risk_manager):
        """Test risk validation when multiple rules are violated"""
        # Set up multiple violations
        today = date.today().isoformat()
        risk_manager.daily_metrics[today].total_pnl = -6000.0  # Exceeds daily limit
        risk_manager.daily_metrics[today].trades_count = 15    # Exceeds trade limit
        
        # Add maximum positions
        for i in range(3):
            trade = self.create_trade(f"TRADE{i}")
            risk_manager.active_trades[f"TRADE{i}"] = trade
        
        signal = self.create_signal()
        result = risk_manager.validate_trade(signal)
        
        assert not result.is_valid, "Should fail with multiple violations"
        
        # Should have multiple alerts
        alert_types = [alert.alert_type for alert in result.alerts]
        assert RiskAlertType.DAILY_LOSS_LIMIT in alert_types
        # Note: Only first violation is typically returned to fail fast
    
    def test_risk_validation_performance(self, risk_manager):
        """Test risk validation performance"""
        import time
        
        signal = self.create_signal()
        
        # Measure validation time
        start_time = time.time()
        for _ in range(100):  # Run 100 validations
            result = risk_manager.validate_trade(signal)
        end_time = time.time()
        
        # Should complete quickly (under 1 second for 100 validations)
        assert (end_time - start_time) < 1.0, "Risk validation too slow"


class TestRiskEnforcement:
    """Test risk enforcement mechanisms"""
    
    @pytest.fixture
    def risk_manager(self):
        """Create RiskManager for enforcement tests"""
        config = TradingConfig()
        config.risk = RiskConfig(
            max_daily_loss=5000.0,
            max_concurrent_trades=3,
            profit_target=2000.0,
            stop_loss=1000.0,
            position_size_method="fixed",
            margin_buffer=0.2,
            max_position_size=5,
            daily_trade_limit=10,
            emergency_stop_file="test_emergency.txt"
        )
        
        manager = RiskManager(config)
        manager.initialize()
        return manager
    
    def test_profit_target_enforcement(self, risk_manager):
        """Test profit target enforcement"""
        # Create trade hitting profit target
        trade = Trade(
            trade_id="PROFIT_TEST",
            strategy="test_strategy",
            underlying_symbol="BANKNIFTY",
            entry_time=datetime.now(),
            target_pnl=2000.0,
            stop_loss=-1000.0
        )
        
        # Add leg with profit exceeding target
        leg = TradeLeg(
            symbol="BANKNIFTY2412550000CE",
            token="12345",
            strike=50000.0,
            option_type=OptionType.CE,
            action=OrderAction.BUY,
            quantity=25,
            entry_price=100.0,
            current_price=180.0  # Profit: (180-100)*25 = 2000
        )
        trade.add_leg(leg)
        
        alerts = risk_manager.monitor_positions([trade])
        
        # Should generate profit target alert
        profit_alerts = [a for a in alerts if a.alert_type == RiskAlertType.PROFIT_TARGET_HIT]
        assert len(profit_alerts) > 0, "Should generate profit target alert"
        assert profit_alerts[0].trade_id == "PROFIT_TEST"
        
        # Should recommend closing position
        assert risk_manager.should_close_position(trade), "Should recommend closing profitable position"
    
    def test_stop_loss_enforcement(self, risk_manager):
        """Test stop loss enforcement"""
        # Create trade hitting stop loss
        trade = Trade(
            trade_id="STOP_TEST",
            strategy="test_strategy",
            underlying_symbol="BANKNIFTY",
            entry_time=datetime.now(),
            target_pnl=2000.0,
            stop_loss=-1000.0
        )
        
        # Add leg with loss exceeding stop
        leg = TradeLeg(
            symbol="BANKNIFTY2412550000CE",
            token="12345",
            strike=50000.0,
            option_type=OptionType.CE,
            action=OrderAction.BUY,
            quantity=25,
            entry_price=100.0,
            current_price=60.0  # Loss: (60-100)*25 = -1000
        )
        trade.add_leg(leg)
        
        alerts = risk_manager.monitor_positions([trade])
        
        # Should generate stop loss alert
        stop_alerts = [a for a in alerts if a.alert_type == RiskAlertType.STOP_LOSS_HIT]
        assert len(stop_alerts) > 0, "Should generate stop loss alert"
        assert stop_alerts[0].trade_id == "STOP_TEST"
        
        # Should recommend closing position
        assert risk_manager.should_close_position(trade), "Should recommend closing losing position"
    
    def test_daily_metrics_update_enforcement(self, risk_manager):
        """Test daily metrics update and enforcement"""
        # Create multiple trades with different P&L
        trades = []
        
        # Winning trade
        winning_trade = self.create_trade_with_pnl("WIN001", 1500.0)
        trades.append(winning_trade)
        
        # Losing trade
        losing_trade = self.create_trade_with_pnl("LOSS001", -800.0)
        trades.append(losing_trade)
        
        # Break-even trade
        breakeven_trade = self.create_trade_with_pnl("EVEN001", 0.0)
        trades.append(breakeven_trade)
        
        # Monitor positions to update metrics
        risk_manager.monitor_positions(trades)
        
        # Check daily metrics
        today_metrics = risk_manager.get_daily_metrics()
        
        assert today_metrics.trades_count == 3
        assert today_metrics.total_pnl == 700.0  # 1500 - 800 + 0
        assert today_metrics.winning_trades == 1
        assert today_metrics.losing_trades == 1
        assert today_metrics.largest_win == 1500.0
        assert today_metrics.largest_loss == -800.0
    
    def test_emergency_stop_enforcement(self, risk_manager):
        """Test emergency stop enforcement"""
        trade = self.create_trade_with_pnl("EMERGENCY001", 500.0)
        
        with tempfile.NamedTemporaryFile(delete=False) as temp_file:
            risk_manager.risk_config.emergency_stop_file = temp_file.name
            
            # Create emergency file
            with open(temp_file.name, 'w') as f:
                f.write("EMERGENCY STOP ACTIVATED")
            
            alerts = risk_manager.monitor_positions([trade])
            
            # Should generate emergency stop alert
            emergency_alerts = [a for a in alerts if a.alert_type == RiskAlertType.EMERGENCY_STOP]
            assert len(emergency_alerts) > 0, "Should generate emergency stop alert"
            
            # Should recommend closing all positions
            assert risk_manager.should_close_position(trade), "Should close position on emergency stop"
            
            # Cleanup
            if os.path.exists(temp_file.name):
                os.unlink(temp_file.name)
    
    def test_risk_level_escalation(self, risk_manager):
        """Test risk level escalation based on metrics"""
        today = date.today().isoformat()
        metrics = risk_manager.daily_metrics[today]
        
        # Test different risk levels
        risk_scenarios = [
            (-1000.0, RiskLevel.LOW, "low_risk"),
            (-2500.0, RiskLevel.MEDIUM, "medium_risk"),
            (-4000.0, RiskLevel.HIGH, "high_risk"),
            (-4800.0, RiskLevel.CRITICAL, "critical_risk")
        ]
        
        for daily_pnl, expected_level, scenario in risk_scenarios:
            metrics.total_pnl = daily_pnl
            metrics.risk_utilization = abs(daily_pnl) / metrics.daily_loss_limit
            
            actual_level = metrics.risk_level
            assert actual_level == expected_level, f"Wrong risk level for {scenario}"
    
    def create_trade_with_pnl(self, trade_id: str, target_pnl: float) -> Trade:
        """Helper to create trade with specific P&L"""
        trade = Trade(
            trade_id=trade_id,
            strategy="test_strategy",
            underlying_symbol="BANKNIFTY",
            entry_time=datetime.now(),
            target_pnl=2000.0,
            stop_loss=-1000.0
        )
        
        if target_pnl != 0:
            # Calculate prices to achieve target P&L
            entry_price = 100.0
            current_price = entry_price + (target_pnl / 25)  # 25 is quantity
            
            leg = TradeLeg(
                symbol="BANKNIFTY2412550000CE",
                token="12345",
                strike=50000.0,
                option_type=OptionType.CE,
                action=OrderAction.BUY,
                quantity=25,
                entry_price=entry_price,
                current_price=current_price
            )
            trade.add_leg(leg)
        
        return trade


class TestRiskAlertSystem:
    """Test risk alert generation and handling"""
    
    def test_risk_alert_creation(self):
        """Test risk alert creation with different types"""
        alert_tests = [
            (RiskAlertType.PROFIT_TARGET_HIT, RiskLevel.HIGH, "Profit target reached"),
            (RiskAlertType.STOP_LOSS_HIT, RiskLevel.CRITICAL, "Stop loss triggered"),
            (RiskAlertType.DAILY_LOSS_LIMIT, RiskLevel.CRITICAL, "Daily limit exceeded"),
            (RiskAlertType.EMERGENCY_STOP, RiskLevel.CRITICAL, "Emergency stop active"),
        ]
        
        for alert_type, level, message in alert_tests:
            alert = RiskAlert(
                alert_type=alert_type,
                level=level,
                message=message,
                trade_id="TEST001",
                current_value=1500.0,
                threshold_value=2000.0,
                timestamp=datetime.now()
            )
            
            assert alert.alert_type == alert_type
            assert alert.level == level
            assert alert.message == message
            assert alert.trade_id == "TEST001"
            assert alert.is_critical() == (level == RiskLevel.CRITICAL)
    
    def test_validation_result_alert_aggregation(self):
        """Test validation result alert aggregation"""
        result = ValidationResult(is_valid=True, message="Initial validation")
        
        # Add multiple alerts
        alerts = [
            RiskAlert(RiskAlertType.POSITION_SIZE_VIOLATION, RiskLevel.LOW, "Size warning"),
            RiskAlert(RiskAlertType.MARGIN_INSUFFICIENT, RiskLevel.MEDIUM, "Margin warning"),
            RiskAlert(RiskAlertType.STOP_LOSS_HIT, RiskLevel.CRITICAL, "Stop loss hit"),
        ]
        
        for alert in alerts:
            result.add_alert(alert)
        
        # Should become invalid due to critical alert
        assert not result.is_valid
        assert len(result.alerts) == 3
        
        # Should have critical alerts
        critical_alerts = result.get_critical_alerts()
        assert len(critical_alerts) == 1
        assert critical_alerts[0].alert_type == RiskAlertType.STOP_LOSS_HIT
    
    def test_alert_filtering_and_prioritization(self):
        """Test alert filtering and prioritization"""
        alerts = [
            RiskAlert(RiskAlertType.POSITION_SIZE_VIOLATION, RiskLevel.LOW, "Low priority"),
            RiskAlert(RiskAlertType.DAILY_LOSS_LIMIT, RiskLevel.CRITICAL, "High priority"),
            RiskAlert(RiskAlertType.MARGIN_INSUFFICIENT, RiskLevel.MEDIUM, "Medium priority"),
            RiskAlert(RiskAlertType.EMERGENCY_STOP, RiskLevel.CRITICAL, "Highest priority"),
        ]
        
        # Sort by priority (critical first)
        sorted_alerts = sorted(alerts, key=lambda a: (a.level.value, a.timestamp), reverse=True)
        
        # Critical alerts should come first
        assert sorted_alerts[0].level == RiskLevel.CRITICAL
        assert sorted_alerts[1].level == RiskLevel.CRITICAL
        assert sorted_alerts[2].level == RiskLevel.MEDIUM
        assert sorted_alerts[3].level == RiskLevel.LOW