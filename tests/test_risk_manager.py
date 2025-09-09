"""
Unit tests for the Risk Manager module.

Tests position sizing, margin validation, daily limits, and risk monitoring.
"""

import pytest
import os
import tempfile
from datetime import datetime, date
from unittest.mock import Mock, patch

from src.risk.risk_manager import RiskManager
from src.risk.risk_models import (
    RiskAlert, RiskAlertType, RiskLevel, ValidationResult,
    PositionSizeResult, MarginRequirement, DailyRiskMetrics
)
from src.models.trading_models import (
    TradingSignal, Trade, TradeLeg, SignalType, OptionType, 
    OrderAction, TradeStatus
)
from src.models.config_models import TradingConfig, RiskConfig


class TestRiskManager:
    """Test cases for RiskManager class"""
    
    @pytest.fixture
    def risk_config(self):
        """Create test risk configuration"""
        return RiskConfig(
            max_daily_loss=5000.0,
            max_concurrent_trades=3,
            profit_target=2000.0,
            stop_loss=1000.0,
            position_size_method="fixed",
            margin_buffer=0.2,
            max_position_size=5,
            daily_trade_limit=10,
            emergency_stop_file="test_emergency_stop.txt"
        )
    
    @pytest.fixture
    def trading_config(self, risk_config):
        """Create test trading configuration"""
        config = TradingConfig()
        config.risk = risk_config
        return config
    
    @pytest.fixture
    def risk_manager(self, trading_config):
        """Create RiskManager instance"""
        manager = RiskManager(trading_config)
        manager.initialize()
        return manager
    
    @pytest.fixture
    def sample_signal(self):
        """Create sample trading signal"""
        return TradingSignal(
            strategy_name="test_strategy",
            signal_type=SignalType.STRADDLE,
            underlying="BANKNIFTY",
            strikes=[50000.0],
            option_types=[OptionType.CE],
            quantities=[1],
            confidence=0.8,
            target_pnl=2000.0,
            stop_loss=-1000.0
        )
    
    @pytest.fixture
    def sample_trade(self):
        """Create sample trade"""
        trade = Trade(
            trade_id="TEST001",
            strategy="test_strategy",
            underlying_symbol="BANKNIFTY",
            entry_time=datetime.now(),
            target_pnl=2000.0,
            stop_loss=-1000.0
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
            current_price=120.0
        )
        trade.add_leg(leg)
        return trade
    
    def test_initialization(self, risk_manager):
        """Test risk manager initialization"""
        assert risk_manager.is_initialized()
        assert risk_manager.risk_config.max_daily_loss == 5000.0
        assert len(risk_manager.daily_metrics) > 0
    
    def test_validate_trade_success(self, risk_manager, sample_signal):
        """Test successful trade validation"""
        result = risk_manager.validate_trade(sample_signal)
        
        assert result.is_valid
        assert "validation passed" in result.message.lower()
        assert len(result.alerts) == 0
        assert 'position_size' in result.metadata
    
    def test_validate_trade_emergency_stop(self, risk_manager, sample_signal, tmp_path):
        """Test trade validation with emergency stop active"""
        # Create emergency stop file
        emergency_file = tmp_path / "test_emergency_stop.txt"
        emergency_file.write_text("STOP")
        
        # Update config to use temp file
        risk_manager.risk_config.emergency_stop_file = str(emergency_file)
        
        result = risk_manager.validate_trade(sample_signal)
        
        assert not result.is_valid
        assert "emergency stop" in result.message.lower()
        assert len(result.alerts) > 0
        assert result.alerts[0].alert_type == RiskAlertType.EMERGENCY_STOP
    
    def test_validate_trade_daily_limit_exceeded(self, risk_manager, sample_signal):
        """Test trade validation with daily limit exceeded"""
        # Set up daily metrics to exceed limit
        today = date.today().isoformat()
        risk_manager.daily_metrics[today].total_pnl = -6000.0  # Exceeds 5000 limit
        
        result = risk_manager.validate_trade(sample_signal)
        
        assert not result.is_valid
        assert "daily loss limit" in result.message.lower()
        assert len(result.alerts) > 0
        assert result.alerts[0].alert_type == RiskAlertType.DAILY_LOSS_LIMIT
    
    def test_validate_trade_position_limit_exceeded(self, risk_manager, sample_signal):
        """Test trade validation with position limit exceeded"""
        # Add mock active trades to exceed limit
        for i in range(3):  # Max is 3, so this should exceed
            trade = Mock()
            trade.trade_id = f"TRADE{i}"
            risk_manager.active_trades[f"TRADE{i}"] = trade
        
        result = risk_manager.validate_trade(sample_signal)
        
        assert not result.is_valid
        assert "position limit" in result.message.lower()
        assert len(result.alerts) > 0
        assert result.alerts[0].alert_type == RiskAlertType.POSITION_LIMIT_EXCEEDED
    
    def test_calculate_position_size_fixed(self, risk_manager, sample_signal):
        """Test position size calculation with fixed method"""
        result = risk_manager.calculate_position_size(sample_signal)
        
        assert result.is_valid()
        assert result.recommended_size == 1  # Fixed method should return 1
        assert result.calculation_method == "fixed"
        assert result.confidence_factor == 0.8
        assert result.margin_required > 0
    
    def test_calculate_position_size_percentage(self, risk_manager, sample_signal):
        """Test position size calculation with percentage method"""
        risk_manager.risk_config.position_size_method = "percentage"
        
        result = risk_manager.calculate_position_size(sample_signal)
        
        assert result.is_valid()
        assert result.recommended_size >= 1
        assert result.calculation_method == "percentage"
        assert result.margin_required > 0
    
    def test_calculate_position_size_kelly(self, risk_manager, sample_signal):
        """Test position size calculation with Kelly method"""
        risk_manager.risk_config.position_size_method = "kelly"
        
        result = risk_manager.calculate_position_size(sample_signal)
        
        assert result.is_valid()
        assert result.recommended_size >= 1
        assert result.calculation_method == "kelly"
        assert result.margin_required > 0
    
    def test_calculate_position_size_max_limit(self, risk_manager, sample_signal):
        """Test position size calculation respects maximum limit"""
        # Set very high confidence and low premium to trigger large size
        sample_signal.confidence = 1.0
        risk_manager.risk_config.position_size_method = "percentage"
        risk_manager.risk_config.max_position_size = 2  # Low limit
        
        result = risk_manager.calculate_position_size(sample_signal)
        
        assert result.is_valid()
        assert result.recommended_size <= 2  # Should be capped at max
        assert len(result.warnings) > 0  # Should have warning about capping
    
    def test_check_daily_limits_within_limits(self, risk_manager):
        """Test daily limits check when within limits"""
        # Set P&L within limits
        today = date.today().isoformat()
        risk_manager.daily_metrics[today].total_pnl = -2000.0  # Within 5000 limit
        
        assert risk_manager.check_daily_limits()
    
    def test_check_daily_limits_exceeded(self, risk_manager):
        """Test daily limits check when limits exceeded"""
        # Set P&L exceeding limits
        today = date.today().isoformat()
        risk_manager.daily_metrics[today].total_pnl = -6000.0  # Exceeds 5000 limit
        
        assert not risk_manager.check_daily_limits()
    
    def test_monitor_positions_profit_target(self, risk_manager, sample_trade):
        """Test position monitoring with profit target hit"""
        # Set trade P&L to hit profit target (need 2000 profit for short position)
        # For short position: profit = (entry_price - current_price) * quantity
        # Need: (150 - current_price) * 1 >= 2000, so current_price <= -1850
        # But price can't be negative, so let's increase quantity to 25 (full lot)
        sample_trade.legs[0].quantity = 25
        sample_trade.legs[0].current_price = 70.0  # Profit: (150-70)*25 = 2000
        
        alerts = risk_manager.monitor_positions([sample_trade])
        
        assert len(alerts) > 0
        profit_alerts = [a for a in alerts if a.alert_type == RiskAlertType.PROFIT_TARGET_HIT]
        assert len(profit_alerts) > 0
        assert profit_alerts[0].trade_id == "TEST001"
    
    def test_monitor_positions_stop_loss(self, risk_manager, sample_trade):
        """Test position monitoring with stop loss hit"""
        # Set trade P&L to hit stop loss (need -1000 loss for short position)
        # For short position: loss = (entry_price - current_price) * quantity
        # Need: (150 - current_price) * 25 <= -1000, so current_price >= 190
        sample_trade.legs[0].quantity = 25
        sample_trade.legs[0].current_price = 190.0  # Loss: (150-190)*25 = -1000
        
        alerts = risk_manager.monitor_positions([sample_trade])
        
        assert len(alerts) > 0
        stop_alerts = [a for a in alerts if a.alert_type == RiskAlertType.STOP_LOSS_HIT]
        assert len(stop_alerts) > 0
        assert stop_alerts[0].trade_id == "TEST001"
    
    def test_should_close_position_profit_target(self, risk_manager, sample_trade):
        """Test should close position when profit target hit"""
        # Set trade P&L to hit profit target
        sample_trade.legs[0].quantity = 25
        sample_trade.legs[0].current_price = 70.0  # Profit: (150-70)*25 = 2000
        
        assert risk_manager.should_close_position(sample_trade)
    
    def test_should_close_position_stop_loss(self, risk_manager, sample_trade):
        """Test should close position when stop loss hit"""
        # Set trade P&L to hit stop loss
        sample_trade.legs[0].quantity = 25
        sample_trade.legs[0].current_price = 190.0  # Loss: (150-190)*25 = -1000
        
        assert risk_manager.should_close_position(sample_trade)
    
    def test_should_close_position_emergency_stop(self, risk_manager, sample_trade, tmp_path):
        """Test should close position when emergency stop active"""
        # Create emergency stop file
        emergency_file = tmp_path / "test_emergency_stop.txt"
        emergency_file.write_text("STOP")
        risk_manager.risk_config.emergency_stop_file = str(emergency_file)
        
        assert risk_manager.should_close_position(sample_trade)
    
    def test_should_close_position_daily_limit(self, risk_manager, sample_trade):
        """Test should close position when daily limit exceeded"""
        # Set daily P&L to exceed limit
        today = date.today().isoformat()
        risk_manager.daily_metrics[today].total_pnl = -6000.0
        
        assert risk_manager.should_close_position(sample_trade)
    
    def test_get_daily_metrics(self, risk_manager):
        """Test getting daily metrics"""
        today = date.today().isoformat()
        metrics = risk_manager.get_daily_metrics(today)
        
        assert metrics.date == today
        assert metrics.daily_loss_limit == 5000.0
        assert metrics.total_pnl == 0.0
        assert metrics.trades_count == 0
    
    def test_validate_margin_requirement(self, risk_manager, sample_signal):
        """Test margin requirement validation"""
        margin_req = risk_manager.validate_margin_requirement(sample_signal, 2)
        
        assert margin_req.total_margin > 0
        assert margin_req.span_margin > 0
        assert margin_req.exposure_margin > 0
        assert margin_req.available_margin > 0
        assert margin_req.margin_utilization >= 0
        assert isinstance(margin_req.is_sufficient, bool)
    
    def test_validate_margin_insufficient(self, risk_manager, sample_signal):
        """Test margin requirement validation with insufficient margin"""
        # Mock insufficient margin
        with patch.object(risk_manager, '_get_available_margin', return_value=1000.0):
            margin_req = risk_manager.validate_margin_requirement(sample_signal, 10)
            
            assert not margin_req.is_sufficient
            assert margin_req.get_margin_shortage() > 0
    
    def test_emergency_stop_file_detection(self, risk_manager, tmp_path):
        """Test emergency stop file detection"""
        emergency_file = tmp_path / "test_emergency_stop.txt"
        risk_manager.risk_config.emergency_stop_file = str(emergency_file)
        
        # Initially no file
        assert not risk_manager._check_emergency_stop()
        
        # Create file
        emergency_file.write_text("STOP")
        assert risk_manager._check_emergency_stop()
        
        # Remove file
        emergency_file.unlink()
        assert not risk_manager._check_emergency_stop()
    
    def test_position_size_with_low_confidence(self, risk_manager, sample_signal):
        """Test position size calculation with low confidence"""
        sample_signal.confidence = 0.3  # Low confidence
        
        result = risk_manager.calculate_position_size(sample_signal)
        
        assert result.is_valid()
        # With low confidence, size should be reduced
        assert result.confidence_factor == 0.3
    
    def test_position_size_with_high_risk_amount(self, risk_manager, sample_signal):
        """Test position size calculation with high risk amount"""
        # Set high stop loss to increase risk amount
        sample_signal.stop_loss = -5000.0
        
        result = risk_manager.calculate_position_size(sample_signal)
        
        assert result.is_valid()
        assert result.risk_amount > 0
    
    def test_daily_metrics_update(self, risk_manager, sample_trade):
        """Test daily metrics update with trades"""
        # Create multiple trades with different P&L
        trades = []
        for i in range(3):
            trade = Trade(
                trade_id=f"TEST{i:03d}",
                strategy="test_strategy",
                underlying_symbol="BANKNIFTY",
                entry_time=datetime.now(),
                target_pnl=2000.0,
                stop_loss=-1000.0
            )
            
            leg = TradeLeg(
                symbol=f"BANKNIFTY2412550000CE",
                token=f"1234{i}",
                strike=50000.0,
                option_type=OptionType.CE,
                action=OrderAction.SELL,
                quantity=1,
                entry_price=150.0,
                current_price=150.0 - (i * 20)  # Different P&L for each
            )
            trade.add_leg(leg)
            trades.append(trade)
        
        # Monitor positions to update metrics
        risk_manager.monitor_positions(trades)
        
        today_metrics = risk_manager.get_daily_metrics()
        assert today_metrics.trades_count == 3
        assert today_metrics.total_pnl != 0
    
    def test_cleanup(self, risk_manager):
        """Test risk manager cleanup"""
        # Add some data
        risk_manager.active_trades["TEST"] = Mock()
        
        risk_manager.cleanup()
        
        assert not risk_manager.is_initialized()
        assert len(risk_manager.active_trades) == 0
    
    def test_invalid_signal_validation(self, risk_manager):
        """Test validation with invalid signal"""
        invalid_signal = TradingSignal(
            strategy_name="",  # Invalid empty name
            signal_type=SignalType.BUY,
            underlying="BANKNIFTY",
            strikes=[],  # Invalid empty strikes
            option_types=[],
            quantities=[],
            confidence=1.5  # Invalid confidence > 1
        )
        
        result = risk_manager.validate_trade(invalid_signal)
        
        assert not result.is_valid
        assert "invalid" in result.message.lower()


class TestRiskModels:
    """Test cases for risk model classes"""
    
    def test_risk_alert_creation(self):
        """Test RiskAlert creation and string representation"""
        alert = RiskAlert(
            alert_type=RiskAlertType.PROFIT_TARGET_HIT,
            level=RiskLevel.HIGH,
            message="Test alert",
            trade_id="TEST001",
            current_value=2500.0,
            threshold_value=2000.0
        )
        
        assert alert.alert_type == RiskAlertType.PROFIT_TARGET_HIT
        assert alert.level == RiskLevel.HIGH
        assert alert.trade_id == "TEST001"
        assert "PROFIT_TARGET_HIT" in str(alert)
        assert "HIGH" in str(alert)
    
    def test_validation_result_with_alerts(self):
        """Test ValidationResult with alerts"""
        result = ValidationResult(is_valid=True, message="Initial valid")
        
        # Add low-level alert (should not change validity)
        low_alert = RiskAlert(
            alert_type=RiskAlertType.POSITION_SIZE_VIOLATION,
            level=RiskLevel.LOW,
            message="Low level alert"
        )
        result.add_alert(low_alert)
        
        assert result.is_valid  # Should still be valid
        assert len(result.alerts) == 1
        
        # Add high-level alert (should change validity)
        high_alert = RiskAlert(
            alert_type=RiskAlertType.STOP_LOSS_HIT,
            level=RiskLevel.CRITICAL,
            message="Critical alert"
        )
        result.add_alert(high_alert)
        
        assert not result.is_valid  # Should now be invalid
        assert len(result.alerts) == 2
    
    def test_position_size_result_validation(self):
        """Test PositionSizeResult validation"""
        # Valid result
        valid_result = PositionSizeResult(
            recommended_size=2,
            max_allowed_size=5,
            risk_amount=1000.0,
            margin_required=50000.0,
            confidence_factor=0.8,
            calculation_method="fixed"
        )
        
        assert valid_result.is_valid()
        
        # Invalid result (size exceeds max)
        invalid_result = PositionSizeResult(
            recommended_size=10,
            max_allowed_size=5,
            risk_amount=1000.0,
            margin_required=50000.0,
            confidence_factor=0.8,
            calculation_method="fixed"
        )
        
        assert not invalid_result.is_valid()
    
    def test_margin_requirement_shortage(self):
        """Test MarginRequirement margin shortage calculation"""
        # Sufficient margin
        sufficient_margin = MarginRequirement(
            total_margin=100000.0,
            span_margin=70000.0,
            exposure_margin=20000.0,
            premium_margin=10000.0,
            additional_margin=0.0,
            available_margin=150000.0,
            margin_utilization=66.7,
            is_sufficient=True,
            buffer_amount=20000.0
        )
        
        assert sufficient_margin.get_margin_shortage() == 0.0
        
        # Insufficient margin
        insufficient_margin = MarginRequirement(
            total_margin=200000.0,
            span_margin=140000.0,
            exposure_margin=40000.0,
            premium_margin=20000.0,
            additional_margin=0.0,
            available_margin=150000.0,
            margin_utilization=133.3,
            is_sufficient=False,
            buffer_amount=40000.0
        )
        
        assert insufficient_margin.get_margin_shortage() == 50000.0
    
    def test_daily_risk_metrics_calculations(self):
        """Test DailyRiskMetrics property calculations"""
        metrics = DailyRiskMetrics(
            date="2024-01-01",
            total_pnl=-2000.0,
            realized_pnl=-1500.0,
            unrealized_pnl=-500.0,
            max_drawdown=-2500.0,
            trades_count=10,
            winning_trades=6,
            losing_trades=4,
            largest_win=1000.0,
            largest_loss=-800.0,
            daily_loss_limit=5000.0,
            remaining_loss_capacity=3000.0,
            risk_utilization=0.4
        )
        
        assert metrics.win_rate == 0.6  # 6/10
        assert not metrics.is_daily_limit_breached  # 2000 < 5000
        assert metrics.risk_level == RiskLevel.LOW  # 0.4 < 0.5
        
        # Test with high risk utilization
        metrics.risk_utilization = 0.95
        assert metrics.risk_level == RiskLevel.CRITICAL  # >= 0.9


if __name__ == "__main__":
    pytest.main([__file__])