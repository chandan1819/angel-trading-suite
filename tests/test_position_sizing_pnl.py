"""
Comprehensive unit tests for position sizing and P&L calculations.

This module tests position sizing algorithms, P&L calculations for various
option strategies, and risk-based position management.
"""

import pytest
from unittest.mock import Mock, patch
from datetime import datetime, date
from decimal import Decimal

from src.risk.risk_manager import RiskManager
from src.risk.risk_models import PositionSizeResult, DailyRiskMetrics
from src.models.trading_models import (
    TradingSignal, Trade, TradeLeg, SignalType, OptionType, 
    OrderAction, TradeStatus
)
from src.models.config_models import TradingConfig, RiskConfig


class TestPositionSizing:
    """Comprehensive tests for position sizing calculations"""
    
    @pytest.fixture
    def risk_config(self):
        """Create test risk configuration"""
        return RiskConfig(
            max_daily_loss=5000.0,
            max_concurrent_trades=3,
            profit_target=2000.0,
            stop_loss=1000.0,
            position_size_method="percentage",
            margin_buffer=0.2,
            max_position_size=10,
            daily_trade_limit=20,
            emergency_stop_file="test_emergency.txt"
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
    
    def create_signal(self, signal_type: SignalType, confidence: float = 0.8, 
                     stop_loss: float = -1000.0) -> TradingSignal:
        """Helper to create trading signals"""
        return TradingSignal(
            strategy_name="test_strategy",
            signal_type=signal_type,
            underlying="BANKNIFTY",
            strikes=[50000.0],
            option_types=[OptionType.CE],
            quantities=[1],
            confidence=confidence,
            target_pnl=2000.0,
            stop_loss=stop_loss
        )
    
    def test_fixed_position_sizing(self, risk_manager):
        """Test fixed position sizing method"""
        risk_manager.risk_config.position_size_method = "fixed"
        signal = self.create_signal(SignalType.BUY)
        
        result = risk_manager.calculate_position_size(signal)
        
        assert result.is_valid()
        assert result.recommended_size == 1
        assert result.calculation_method == "fixed"
        assert result.confidence_factor == 0.8
        assert result.margin_required > 0
    
    def test_percentage_position_sizing(self, risk_manager):
        """Test percentage-based position sizing"""
        risk_manager.risk_config.position_size_method = "percentage"
        signal = self.create_signal(SignalType.BUY)
        
        # Mock premium estimation
        with patch.object(risk_manager, '_estimate_premium_per_lot', return_value=100.0):
            result = risk_manager.calculate_position_size(signal)
            
            assert result.is_valid()
            assert result.recommended_size >= 1
            assert result.calculation_method == "percentage"
            # With 1000 risk amount and 100 premium, should get 10 lots
            # But adjusted by confidence (0.8) = 8 lots
            assert result.recommended_size == 8
    
    def test_kelly_position_sizing(self, risk_manager):
        """Test Kelly criterion position sizing"""
        risk_manager.risk_config.position_size_method = "kelly"
        signal = self.create_signal(SignalType.BUY)
        
        # Mock historical performance metrics
        with patch.object(risk_manager, '_get_historical_win_rate', return_value=0.6), \
             patch.object(risk_manager, '_get_average_win', return_value=1500.0), \
             patch.object(risk_manager, '_get_average_loss', return_value=800.0), \
             patch.object(risk_manager, '_estimate_premium_per_lot', return_value=100.0):
            
            result = risk_manager.calculate_position_size(signal)
            
            assert result.is_valid()
            assert result.recommended_size >= 1
            assert result.calculation_method == "kelly"
    
    def test_position_sizing_with_confidence_adjustment(self, risk_manager):
        """Test position sizing with different confidence levels"""
        test_cases = [
            (0.3, "low_confidence"),
            (0.6, "medium_confidence"),
            (0.9, "high_confidence"),
            (1.0, "maximum_confidence")
        ]
        
        for confidence, scenario in test_cases:
            signal = self.create_signal(SignalType.BUY, confidence=confidence)
            
            with patch.object(risk_manager, '_estimate_premium_per_lot', return_value=100.0):
                result = risk_manager.calculate_position_size(signal)
                
                assert result.is_valid(), f"Failed for {scenario}"
                assert result.confidence_factor == confidence
                # Higher confidence should lead to larger position size
                if confidence >= 0.6:
                    assert result.recommended_size >= 1
    
    def test_position_sizing_with_risk_amount_variations(self, risk_manager):
        """Test position sizing with different risk amounts"""
        test_cases = [
            (-500.0, "low_risk"),
            (-1000.0, "normal_risk"),
            (-2000.0, "high_risk"),
            (-5000.0, "maximum_risk")
        ]
        
        for stop_loss, scenario in test_cases:
            signal = self.create_signal(SignalType.BUY, stop_loss=stop_loss)
            
            with patch.object(risk_manager, '_estimate_premium_per_lot', return_value=100.0):
                result = risk_manager.calculate_position_size(signal)
                
                assert result.is_valid(), f"Failed for {scenario}"
                assert result.risk_amount == abs(stop_loss)
                # Higher risk amount should allow larger position size
                expected_size = min(10, int(abs(stop_loss) / 100.0 * 0.8))  # Adjusted by confidence
                assert result.recommended_size == max(1, expected_size)
    
    def test_position_sizing_max_limit_enforcement(self, risk_manager):
        """Test position sizing respects maximum limits"""
        risk_manager.risk_config.max_position_size = 3
        signal = self.create_signal(SignalType.BUY, confidence=1.0)
        
        # Use very low premium to trigger large position size
        with patch.object(risk_manager, '_estimate_premium_per_lot', return_value=10.0):
            result = risk_manager.calculate_position_size(signal)
            
            assert result.is_valid()
            assert result.recommended_size <= 3  # Should be capped at max
            assert len(result.warnings) > 0  # Should warn about capping
            assert "capped at maximum" in result.warnings[0]
    
    def test_position_sizing_with_remaining_daily_risk(self, risk_manager):
        """Test position sizing considers remaining daily risk capacity"""
        # Set up daily metrics with some loss already
        today = date.today().isoformat()
        risk_manager.daily_metrics[today].total_pnl = -3000.0  # Already lost 3000
        
        signal = self.create_signal(SignalType.BUY)
        
        with patch.object(risk_manager, '_estimate_premium_per_lot', return_value=100.0):
            result = risk_manager.calculate_position_size(signal)
            
            assert result.is_valid()
            # Risk amount should be limited by remaining daily capacity (2000)
            assert result.risk_amount <= 2000.0
    
    def test_position_sizing_strategy_specific(self, risk_manager):
        """Test position sizing for different strategy types"""
        strategy_tests = [
            (SignalType.STRADDLE, 150.0),  # Higher premium for straddle
            (SignalType.STRANGLE, 120.0),  # Medium premium for strangle
            (SignalType.IRON_CONDOR, 75.0),  # Lower premium for iron condor
            (SignalType.BUY, 100.0),  # Standard premium for single leg
        ]
        
        for signal_type, expected_premium in strategy_tests:
            signal = self.create_signal(signal_type)
            
            # Mock strategy-specific premium estimation
            with patch.object(risk_manager, '_estimate_premium_per_lot', 
                             return_value=expected_premium):
                result = risk_manager.calculate_position_size(signal)
                
                assert result.is_valid()
                # Different strategies should have different position sizes
                expected_size = int(1000.0 / expected_premium * 0.8)  # Confidence adjustment
                assert result.recommended_size == max(1, expected_size)
    
    def test_position_sizing_error_handling(self, risk_manager):
        """Test position sizing error handling"""
        signal = self.create_signal(SignalType.BUY)
        
        # Test with zero premium (should handle gracefully)
        with patch.object(risk_manager, '_estimate_premium_per_lot', return_value=0.0):
            result = risk_manager.calculate_position_size(signal)
            
            assert not result.is_valid()
            assert result.recommended_size == 0
            assert len(result.warnings) > 0
            assert "Could not estimate premium" in result.warnings[0]
        
        # Test with negative premium (should handle gracefully)
        with patch.object(risk_manager, '_estimate_premium_per_lot', return_value=-100.0):
            result = risk_manager.calculate_position_size(signal)
            
            assert not result.is_valid()
            assert result.recommended_size == 0


class TestPnLCalculations:
    """Comprehensive tests for P&L calculations"""
    
    def create_trade_leg(self, action: OrderAction, entry_price: float, 
                        current_price: float, quantity: int = 25) -> TradeLeg:
        """Helper to create trade legs"""
        return TradeLeg(
            symbol="BANKNIFTY2412550000CE",
            token="12345",
            strike=50000.0,
            option_type=OptionType.CE,
            action=action,
            quantity=quantity,
            entry_price=entry_price,
            current_price=current_price
        )
    
    def test_single_leg_buy_pnl(self):
        """Test P&L calculation for single leg buy positions"""
        test_cases = [
            # (entry_price, current_price, quantity, expected_pnl)
            (100.0, 120.0, 25, 500.0),   # Profit: (120-100) * 25 = 500
            (100.0, 80.0, 25, -500.0),   # Loss: (80-100) * 25 = -500
            (150.0, 150.0, 25, 0.0),     # Break-even
            (100.0, 200.0, 50, 5000.0),  # Large profit with 2 lots
        ]
        
        for entry_price, current_price, quantity, expected_pnl in test_cases:
            leg = self.create_trade_leg(OrderAction.BUY, entry_price, current_price, quantity)
            
            pnl = leg.calculate_pnl()
            assert abs(pnl - expected_pnl) < 0.01, f"PnL mismatch: expected {expected_pnl}, got {pnl}"
    
    def test_single_leg_sell_pnl(self):
        """Test P&L calculation for single leg sell positions"""
        test_cases = [
            # (entry_price, current_price, quantity, expected_pnl)
            (100.0, 80.0, 25, 500.0),    # Profit: (100-80) * 25 = 500
            (100.0, 120.0, 25, -500.0),  # Loss: (100-120) * 25 = -500
            (150.0, 150.0, 25, 0.0),     # Break-even
            (200.0, 100.0, 50, 5000.0),  # Large profit with 2 lots
        ]
        
        for entry_price, current_price, quantity, expected_pnl in test_cases:
            leg = self.create_trade_leg(OrderAction.SELL, entry_price, current_price, quantity)
            
            pnl = leg.calculate_pnl()
            assert abs(pnl - expected_pnl) < 0.01, f"PnL mismatch: expected {expected_pnl}, got {pnl}"
    
    def test_straddle_pnl_calculation(self):
        """Test P&L calculation for straddle positions"""
        # Short straddle: Sell ATM call and put
        call_leg = TradeLeg(
            symbol="BANKNIFTY2412550000CE",
            token="12345",
            strike=50000.0,
            option_type=OptionType.CE,
            action=OrderAction.SELL,
            quantity=25,
            entry_price=150.0,
            current_price=100.0  # Call decreased in value
        )
        
        put_leg = TradeLeg(
            symbol="BANKNIFTY2412550000PE",
            token="12346",
            strike=50000.0,
            option_type=OptionType.PE,
            action=OrderAction.SELL,
            quantity=25,
            entry_price=140.0,
            current_price=90.0   # Put decreased in value
        )
        
        trade = Trade(
            trade_id="STRADDLE001",
            strategy="straddle_strategy",
            underlying_symbol="BANKNIFTY",
            entry_time=datetime.now(),
            target_pnl=2000.0,
            stop_loss=-1000.0
        )
        
        trade.add_leg(call_leg)
        trade.add_leg(put_leg)
        
        # Expected P&L: Call profit (150-100)*25 + Put profit (140-90)*25 = 1250 + 1250 = 2500
        expected_pnl = 2500.0
        actual_pnl = trade.calculate_current_pnl()
        
        assert abs(actual_pnl - expected_pnl) < 0.01
        assert trade.is_target_hit  # Should hit 2000 target
    
    def test_iron_condor_pnl_calculation(self):
        """Test P&L calculation for iron condor positions"""
        # Iron condor: Sell OTM call/put, Buy further OTM call/put
        legs = [
            # Short call spread
            TradeLeg("BANKNIFTY2412550300CE", "1", 50300.0, OptionType.CE, 
                    OrderAction.SELL, 25, 80.0, 60.0),   # Profit: 20*25 = 500
            TradeLeg("BANKNIFTY2412550500CE", "2", 50500.0, OptionType.CE, 
                    OrderAction.BUY, 25, 30.0, 20.0),    # Loss: -10*25 = -250
            
            # Short put spread  
            TradeLeg("BANKNIFTY2412549700PE", "3", 49700.0, OptionType.PE, 
                    OrderAction.SELL, 25, 75.0, 55.0),   # Profit: 20*25 = 500
            TradeLeg("BANKNIFTY2412549500PE", "4", 49500.0, OptionType.PE, 
                    OrderAction.BUY, 25, 25.0, 15.0),    # Loss: -10*25 = -250
        ]
        
        trade = Trade(
            trade_id="IC001",
            strategy="iron_condor_strategy", 
            underlying_symbol="BANKNIFTY",
            entry_time=datetime.now(),
            target_pnl=400.0,
            stop_loss=-600.0
        )
        
        for leg in legs:
            trade.add_leg(leg)
        
        # Expected P&L: 500 - 250 + 500 - 250 = 500
        expected_pnl = 500.0
        actual_pnl = trade.calculate_current_pnl()
        
        assert abs(actual_pnl - expected_pnl) < 0.01
        assert trade.is_target_hit  # Should hit 400 target
    
    def test_pnl_with_partial_fills(self):
        """Test P&L calculation with partial fills"""
        # Leg with partial fill (15 out of 25 filled)
        leg = TradeLeg(
            symbol="BANKNIFTY2412550000CE",
            token="12345",
            strike=50000.0,
            option_type=OptionType.CE,
            action=OrderAction.BUY,
            quantity=15,  # Partial fill
            entry_price=100.0,
            current_price=120.0
        )
        
        # Expected P&L: (120-100) * 15 = 300
        expected_pnl = 300.0
        actual_pnl = leg.calculate_pnl()
        
        assert abs(actual_pnl - expected_pnl) < 0.01
    
    def test_pnl_precision_handling(self):
        """Test P&L calculation with high precision requirements"""
        # Use Decimal for high precision
        leg = TradeLeg(
            symbol="BANKNIFTY2412550000CE",
            token="12345",
            strike=50000.0,
            option_type=OptionType.CE,
            action=OrderAction.BUY,
            quantity=25,
            entry_price=100.05,   # Precise entry
            current_price=100.15  # Small move
        )
        
        # Expected P&L: (100.15 - 100.05) * 25 = 0.10 * 25 = 2.50
        expected_pnl = 2.50
        actual_pnl = leg.calculate_pnl()
        
        assert abs(actual_pnl - expected_pnl) < 0.001  # High precision check
    
    def test_target_and_stop_loss_detection(self):
        """Test target and stop-loss hit detection"""
        trade = Trade(
            trade_id="TEST001",
            strategy="test_strategy",
            underlying_symbol="BANKNIFTY", 
            entry_time=datetime.now(),
            target_pnl=2000.0,
            stop_loss=-1000.0
        )
        
        # Test scenarios
        test_cases = [
            (2500.0, True, False, "target_hit"),
            (-1200.0, False, True, "stop_loss_hit"),
            (500.0, False, False, "within_range"),
            (2000.0, True, False, "exact_target"),
            (-1000.0, False, True, "exact_stop_loss"),
        ]
        
        for pnl, expect_target, expect_stop, scenario in test_cases:
            # Create leg with appropriate P&L
            if pnl > 0:
                # Profitable long position
                leg = TradeLeg("TEST", "1", 50000.0, OptionType.CE, OrderAction.BUY, 
                              25, 100.0, 100.0 + pnl/25)
            else:
                # Losing long position  
                leg = TradeLeg("TEST", "1", 50000.0, OptionType.CE, OrderAction.BUY,
                              25, 100.0, 100.0 + pnl/25)
            
            trade.legs = [leg]  # Reset legs
            
            assert trade.is_target_hit == expect_target, f"Target detection failed for {scenario}"
            assert trade.is_stop_loss_hit == expect_stop, f"Stop loss detection failed for {scenario}"
    
    def test_pnl_with_zero_quantity(self):
        """Test P&L calculation with zero quantity (closed position)"""
        leg = TradeLeg(
            symbol="BANKNIFTY2412550000CE",
            token="12345",
            strike=50000.0,
            option_type=OptionType.CE,
            action=OrderAction.BUY,
            quantity=0,  # Closed position
            entry_price=100.0,
            current_price=120.0
        )
        
        pnl = leg.calculate_pnl()
        assert pnl == 0.0  # No P&L for zero quantity
    
    def test_pnl_calculation_performance(self):
        """Test P&L calculation performance with many legs"""
        import time
        
        # Create trade with 100 legs
        trade = Trade(
            trade_id="PERF_TEST",
            strategy="performance_test",
            underlying_symbol="BANKNIFTY",
            entry_time=datetime.now(),
            target_pnl=10000.0,
            stop_loss=-5000.0
        )
        
        for i in range(100):
            leg = TradeLeg(
                symbol=f"BANKNIFTY2412550{i:03d}CE",
                token=str(i),
                strike=50000.0 + i,
                option_type=OptionType.CE,
                action=OrderAction.BUY,
                quantity=25,
                entry_price=100.0,
                current_price=110.0
            )
            trade.add_leg(leg)
        
        # Measure calculation time
        start_time = time.time()
        pnl = trade.calculate_current_pnl()
        end_time = time.time()
        
        # Should complete quickly (under 0.1 seconds)
        assert (end_time - start_time) < 0.1
        assert pnl == 25000.0  # (110-100) * 25 * 100 legs = 25000
    
    def test_complex_multi_leg_strategy_pnl(self):
        """Test P&L for complex multi-leg strategies"""
        # Butterfly spread: Buy 1 ITM, Sell 2 ATM, Buy 1 OTM
        trade = Trade(
            trade_id="BUTTERFLY001",
            strategy="butterfly_strategy",
            underlying_symbol="BANKNIFTY",
            entry_time=datetime.now(),
            target_pnl=1000.0,
            stop_loss=-500.0
        )
        
        legs = [
            # Buy ITM call
            TradeLeg("BANKNIFTY2412549800CE", "1", 49800.0, OptionType.CE,
                    OrderAction.BUY, 25, 250.0, 280.0),   # Profit: 30*25 = 750
            
            # Sell 2 ATM calls  
            TradeLeg("BANKNIFTY2412550000CE", "2", 50000.0, OptionType.CE,
                    OrderAction.SELL, 50, 150.0, 180.0),  # Loss: -30*50 = -1500
            
            # Buy OTM call
            TradeLeg("BANKNIFTY2412550200CE", "3", 50200.0, OptionType.CE,
                    OrderAction.BUY, 25, 80.0, 110.0),    # Profit: 30*25 = 750
        ]
        
        for leg in legs:
            trade.add_leg(leg)
        
        # Expected P&L: 750 - 1500 + 750 = 0
        expected_pnl = 0.0
        actual_pnl = trade.calculate_current_pnl()
        
        assert abs(actual_pnl - expected_pnl) < 0.01