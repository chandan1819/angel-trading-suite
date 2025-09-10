"""
Unit tests for trading strategies in the Bank Nifty Options Trading System.

Tests cover the base strategy framework, strategy manager, and individual
strategy implementations including signal generation and validation.
"""

import unittest
from unittest.mock import Mock, patch, MagicMock
from datetime import datetime, time
import sys
import os

# Add src to path for imports
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'src'))

from strategies.base_strategy import BaseStrategy
from strategies.strategy_manager import StrategyManager
from strategies.straddle_strategy import StraddleStrategy
from strategies.directional_strategy import DirectionalStrategy
from strategies.iron_condor_strategy import IronCondorStrategy
from strategies.greeks_strategy import GreeksStrategy
from strategies.volatility_strategy import VolatilityStrategy
from models.trading_models import TradingSignal, SignalType, OptionType, OptionsChain
from data.data_manager import DataManager


class TestBaseStrategy(unittest.TestCase):
    """Test cases for BaseStrategy abstract class."""
    
    def setUp(self):
        """Set up test fixtures."""
        self.config = {
            'enabled': True,
            'weight': 1.0,
            'min_confidence': 0.6,
            'max_positions': 2,
            'max_loss_per_trade': 1000.0,
            'target_profit_per_trade': 2000.0,
            'min_volume': 100,
            'max_bid_ask_spread_pct': 5.0,
            'min_open_interest': 50
        }
        
        # Create a concrete implementation for testing
        class TestStrategy(BaseStrategy):
            def evaluate(self, market_data):
                return None
        
        self.strategy = TestStrategy("TestStrategy", self.config)
    
    def test_initialization(self):
        """Test strategy initialization."""
        self.assertEqual(self.strategy.name, "TestStrategy")
        self.assertTrue(self.strategy.enabled)
        self.assertEqual(self.strategy.weight, 1.0)
        self.assertEqual(self.strategy.min_confidence, 0.6)
        self.assertEqual(self.strategy.max_positions, 2)
        self.assertEqual(self.strategy.current_positions, 0)
    
    def test_get_parameters(self):
        """Test getting strategy parameters."""
        params = self.strategy.get_parameters()
        self.assertIn('name', params)
        self.assertIn('enabled', params)
        self.assertIn('weight', params)
        self.assertEqual(params['name'], "TestStrategy")
        self.assertTrue(params['enabled'])
    
    def test_update_parameters(self):
        """Test updating strategy parameters."""
        new_params = {
            'enabled': False,
            'weight': 0.5,
            'min_confidence': 0.8
        }
        
        self.strategy.update_parameters(new_params)
        
        self.assertFalse(self.strategy.enabled)
        self.assertEqual(self.strategy.weight, 0.5)
        self.assertEqual(self.strategy.min_confidence, 0.8)
    
    def test_validate_signal_basic(self):
        """Test basic signal validation."""
        # Create a valid signal
        signal = TradingSignal(
            strategy_name="TestStrategy",
            signal_type=SignalType.BUY,
            underlying="BANKNIFTY",
            strikes=[50000],
            option_types=[OptionType.CE],
            quantities=[1],
            confidence=0.8
        )
        
        self.assertTrue(self.strategy.validate_signal(signal))
    
    def test_validate_signal_low_confidence(self):
        """Test signal validation with low confidence."""
        signal = TradingSignal(
            strategy_name="TestStrategy",
            signal_type=SignalType.BUY,
            underlying="BANKNIFTY",
            strikes=[50000],
            option_types=[OptionType.CE],
            quantities=[1],
            confidence=0.4  # Below threshold
        )
        
        self.assertFalse(self.strategy.validate_signal(signal))
    
    def test_validate_signal_disabled_strategy(self):
        """Test signal validation when strategy is disabled."""
        self.strategy.enabled = False
        
        signal = TradingSignal(
            strategy_name="TestStrategy",
            signal_type=SignalType.BUY,
            underlying="BANKNIFTY",
            strikes=[50000],
            option_types=[OptionType.CE],
            quantities=[1],
            confidence=0.8
        )
        
        self.assertFalse(self.strategy.validate_signal(signal))
    
    def test_validate_signal_max_positions(self):
        """Test signal validation when max positions reached."""
        self.strategy.current_positions = 2  # At max
        
        signal = TradingSignal(
            strategy_name="TestStrategy",
            signal_type=SignalType.BUY,
            underlying="BANKNIFTY",
            strikes=[50000],
            option_types=[OptionType.CE],
            quantities=[1],
            confidence=0.8
        )
        
        self.assertFalse(self.strategy.validate_signal(signal))
    
    @patch('strategies.base_strategy.datetime')
    def test_is_market_hours(self, mock_datetime):
        """Test market hours checking."""
        # Test during market hours
        mock_datetime.now.return_value.time.return_value = time(10, 30)
        self.assertTrue(self.strategy.is_market_hours())
        
        # Test outside market hours
        mock_datetime.now.return_value.time.return_value = time(8, 30)
        self.assertFalse(self.strategy.is_market_hours())
    
    def test_validate_option_liquidity(self):
        """Test option liquidity validation."""
        # Good liquidity
        good_option = {
            'volume': 200,
            'oi': 100,
            'bid': 95,
            'ask': 105,
            'ltp': 100
        }
        self.assertTrue(self.strategy.validate_option_liquidity(good_option))
        
        # Poor volume
        poor_volume = {
            'volume': 50,  # Below minimum
            'oi': 100,
            'bid': 95,
            'ask': 105,
            'ltp': 100
        }
        self.assertFalse(self.strategy.validate_option_liquidity(poor_volume))
        
        # Wide spread
        wide_spread = {
            'volume': 200,
            'oi': 100,
            'bid': 90,
            'ask': 110,  # 20% spread
            'ltp': 100
        }
        self.assertFalse(self.strategy.validate_option_liquidity(wide_spread))
    
    def test_position_count_management(self):
        """Test position count management."""
        self.assertEqual(self.strategy.current_positions, 0)
        
        self.strategy.increment_position_count()
        self.assertEqual(self.strategy.current_positions, 1)
        
        self.strategy.increment_position_count()
        self.assertEqual(self.strategy.current_positions, 2)
        
        self.strategy.decrement_position_count()
        self.assertEqual(self.strategy.current_positions, 1)
        
        self.strategy.reset_position_count()
        self.assertEqual(self.strategy.current_positions, 0)


class TestStrategyManager(unittest.TestCase):
    """Test cases for StrategyManager."""
    
    def setUp(self):
        """Set up test fixtures."""
        self.mock_data_manager = Mock(spec=DataManager)
        self.config = {
            'max_concurrent_evaluations': 3,
            'evaluation_timeout': 30,
            'enable_concurrent_evaluation': True,
            'max_signals_per_cycle': 2
        }
        self.strategy_manager = StrategyManager(self.mock_data_manager, self.config)
    
    def test_initialization(self):
        """Test strategy manager initialization."""
        self.assertEqual(len(self.strategy_manager.strategies), 0)
        self.assertEqual(self.strategy_manager.max_concurrent_evaluations, 3)
        self.assertTrue(self.strategy_manager.enable_concurrent_evaluation)
    
    def test_register_strategy(self):
        """Test strategy registration."""
        mock_strategy = Mock(spec=BaseStrategy)
        mock_strategy.get_name.return_value = "TestStrategy"
        
        result = self.strategy_manager.register_strategy(mock_strategy)
        
        self.assertTrue(result)
        self.assertIn("TestStrategy", self.strategy_manager.strategies)
        self.assertIn("TestStrategy", self.strategy_manager.strategy_performance)
    
    def test_unregister_strategy(self):
        """Test strategy unregistration."""
        mock_strategy = Mock(spec=BaseStrategy)
        mock_strategy.get_name.return_value = "TestStrategy"
        
        self.strategy_manager.register_strategy(mock_strategy)
        result = self.strategy_manager.unregister_strategy("TestStrategy")
        
        self.assertTrue(result)
        self.assertNotIn("TestStrategy", self.strategy_manager.strategies)
    
    def test_get_enabled_strategies(self):
        """Test getting enabled strategies."""
        # Create mock strategies
        enabled_strategy = Mock(spec=BaseStrategy)
        enabled_strategy.get_name.return_value = "EnabledStrategy"
        enabled_strategy.enabled = True
        
        disabled_strategy = Mock(spec=BaseStrategy)
        disabled_strategy.get_name.return_value = "DisabledStrategy"
        disabled_strategy.enabled = False
        
        self.strategy_manager.register_strategy(enabled_strategy)
        self.strategy_manager.register_strategy(disabled_strategy)
        
        enabled_strategies = self.strategy_manager.get_enabled_strategies()
        
        self.assertEqual(len(enabled_strategies), 1)
        self.assertIn("EnabledStrategy", enabled_strategies)
        self.assertNotIn("DisabledStrategy", enabled_strategies)
    
    def test_evaluate_strategies_sequential(self):
        """Test sequential strategy evaluation."""
        # Disable concurrent evaluation
        self.strategy_manager.enable_concurrent_evaluation = False
        
        # Create mock strategy
        mock_strategy = Mock(spec=BaseStrategy)
        mock_strategy.get_name.return_value = "TestStrategy"
        mock_strategy.enabled = True
        
        # Mock signal
        mock_signal = TradingSignal(
            strategy_name="TestStrategy",
            signal_type=SignalType.BUY,
            underlying="BANKNIFTY",
            strikes=[50000],
            option_types=[OptionType.CE],
            quantities=[1],
            confidence=0.8
        )
        
        mock_strategy.evaluate.return_value = mock_signal
        mock_strategy.validate_signal.return_value = True
        
        self.strategy_manager.register_strategy(mock_strategy)
        
        # Test evaluation
        market_data = {
            'options_chain': Mock(),
            'historical_data': [],
            'indicators': {},
            'current_time': datetime.now()
        }
        
        signals = self.strategy_manager.evaluate_strategies(market_data)
        
        self.assertEqual(len(signals), 1)
        self.assertEqual(signals[0].strategy_name, "TestStrategy")
        mock_strategy.evaluate.assert_called_once_with(market_data)
    
    def test_filter_and_aggregate_signals(self):
        """Test signal filtering and aggregation."""
        # Create multiple signals
        signals = []
        for i in range(5):
            signal = TradingSignal(
                strategy_name=f"Strategy{i}",
                signal_type=SignalType.BUY,
                underlying="BANKNIFTY",
                strikes=[50000],
                option_types=[OptionType.CE],
                quantities=[1],
                confidence=0.5 + i * 0.1  # Increasing confidence
            )
            signals.append(signal)
        
        # Test with limit of 2 signals
        filtered_signals = self.strategy_manager._filter_and_aggregate_signals(signals)
        
        # Should return top 2 by confidence
        self.assertEqual(len(filtered_signals), 2)
        self.assertEqual(filtered_signals[0].strategy_name, "Strategy4")  # Highest confidence
        self.assertEqual(filtered_signals[1].strategy_name, "Strategy3")  # Second highest
    
    def test_get_summary(self):
        """Test getting strategy manager summary."""
        # Register some strategies
        enabled_strategy = Mock(spec=BaseStrategy)
        enabled_strategy.get_name.return_value = "EnabledStrategy"
        enabled_strategy.enabled = True
        
        disabled_strategy = Mock(spec=BaseStrategy)
        disabled_strategy.get_name.return_value = "DisabledStrategy"
        disabled_strategy.enabled = False
        
        self.strategy_manager.register_strategy(enabled_strategy)
        self.strategy_manager.register_strategy(disabled_strategy)
        
        summary = self.strategy_manager.get_summary()
        
        self.assertEqual(summary['total_strategies'], 2)
        self.assertEqual(summary['enabled_strategies'], 1)
        self.assertIn('EnabledStrategy', summary['enabled_strategy_names'])


class TestStraddleStrategy(unittest.TestCase):
    """Test cases for StraddleStrategy."""
    
    def setUp(self):
        """Set up test fixtures."""
        self.config = {
            'min_iv_rank': 70.0,
            'max_iv_rank': 95.0,
            'strategy_type': 'straddle',
            'min_dte': 0,
            'max_dte': 7
        }
        self.strategy = StraddleStrategy(self.config)
    
    def test_initialization(self):
        """Test straddle strategy initialization."""
        self.assertEqual(self.strategy.name, "StraddleStrategy")
        self.assertEqual(self.strategy.strategy_type, 'straddle')
        self.assertEqual(self.strategy.min_iv_rank, 70.0)
    
    def test_select_straddle_strikes(self):
        """Test straddle strike selection."""
        mock_options_chain = Mock()
        mock_options_chain.atm_strike = 50000
        
        strikes, option_types = self.strategy._select_straddle_strikes(mock_options_chain)
        
        self.assertEqual(len(strikes), 2)
        self.assertEqual(strikes[0], 50000)  # ATM call
        self.assertEqual(strikes[1], 50000)  # ATM put
        self.assertEqual(option_types[0], OptionType.CE)
        self.assertEqual(option_types[1], OptionType.PE)
    
    def test_select_strangle_strikes(self):
        """Test strangle strike selection."""
        self.strategy.strategy_type = 'strangle'
        self.strategy.strangle_otm_distance = 200.0
        
        mock_options_chain = Mock()
        mock_options_chain.atm_strike = 50000
        mock_options_chain.underlying_price = 50000
        mock_options_chain.strikes = [
            {'strike': 49800}, {'strike': 50000}, {'strike': 50200}
        ]
        
        strikes, option_types = self.strategy._select_strangle_strikes(mock_options_chain)
        
        self.assertEqual(len(strikes), 2)
        self.assertGreater(strikes[0], 50000)  # OTM call
        self.assertLess(strikes[1], 50000)     # OTM put
        self.assertEqual(option_types[0], OptionType.CE)
        self.assertEqual(option_types[1], OptionType.PE)
    
    @patch('strategies.straddle_strategy.datetime')
    def test_check_market_conditions(self, mock_datetime):
        """Test market conditions checking."""
        mock_datetime.now.return_value.time.return_value = time(10, 30)
        
        mock_options_chain = Mock()
        mock_options_chain.underlying_price = 50000
        mock_options_chain.expiry_date = "2024-12-26"  # Future date
        
        # Mock the days to expiry calculation
        with patch.object(self.strategy, '_calculate_days_to_expiry', return_value=3):
            result = self.strategy._check_market_conditions(mock_options_chain, datetime.now())
            self.assertTrue(result)


class TestDirectionalStrategy(unittest.TestCase):
    """Test cases for DirectionalStrategy."""
    
    def setUp(self):
        """Set up test fixtures."""
        self.config = {
            'ema_fast_period': 9,
            'ema_slow_period': 21,
            'atr_period': 14,
            'atr_multiplier': 2.0,
            'strike_selection_method': 'atm'
        }
        self.strategy = DirectionalStrategy(self.config)
    
    def test_initialization(self):
        """Test directional strategy initialization."""
        self.assertEqual(self.strategy.name, "DirectionalStrategy")
        self.assertEqual(self.strategy.ema_fast_period, 9)
        self.assertEqual(self.strategy.ema_slow_period, 21)
        self.assertEqual(self.strategy.strike_selection_method, 'atm')
    
    def test_determine_direction_bullish(self):
        """Test bullish direction determination."""
        indicators = {
            'ema_cross_signal': 'bullish',
            'atr_breakout_signal': 'bullish',
            'rsi': 60,
            'momentum': 2.0,
            'volume_confirmation': True
        }
        
        direction, strength = self.strategy._determine_direction(indicators, [])
        
        self.assertEqual(direction, 'bullish')
        self.assertGreater(strength, 0.5)
    
    def test_determine_direction_bearish(self):
        """Test bearish direction determination."""
        indicators = {
            'ema_cross_signal': 'bearish',
            'atr_breakout_signal': 'bearish',
            'rsi': 40,
            'momentum': -2.0,
            'volume_confirmation': True
        }
        
        direction, strength = self.strategy._determine_direction(indicators, [])
        
        self.assertEqual(direction, 'bearish')
        self.assertGreater(strength, 0.5)
    
    def test_select_option_bullish(self):
        """Test option selection for bullish direction."""
        mock_options_chain = Mock()
        mock_options_chain.atm_strike = 50000
        mock_options_chain.underlying_price = 50000
        mock_options_chain.strikes = [
            {'strike': 49800}, {'strike': 50000}, {'strike': 50200}
        ]
        
        strike, option_type = self.strategy._select_option(mock_options_chain, 'bullish')
        
        self.assertEqual(strike, 50000)  # ATM for 'atm' method
        self.assertEqual(option_type, OptionType.CE)
    
    def test_select_option_bearish(self):
        """Test option selection for bearish direction."""
        mock_options_chain = Mock()
        mock_options_chain.atm_strike = 50000
        mock_options_chain.underlying_price = 50000
        mock_options_chain.strikes = [
            {'strike': 49800}, {'strike': 50000}, {'strike': 50200}
        ]
        
        strike, option_type = self.strategy._select_option(mock_options_chain, 'bearish')
        
        self.assertEqual(strike, 50000)  # ATM for 'atm' method
        self.assertEqual(option_type, OptionType.PE)


class TestIronCondorStrategy(unittest.TestCase):
    """Test cases for IronCondorStrategy."""
    
    def setUp(self):
        """Set up test fixtures."""
        self.config = {
            'wing_distance_points': 200.0,
            'short_strike_distance_points': 300.0,
            'min_iv_rank': 40.0,
            'max_iv_rank': 80.0,
            'min_credit_received': 50.0
        }
        self.strategy = IronCondorStrategy(self.config)
    
    def test_initialization(self):
        """Test iron condor strategy initialization."""
        self.assertEqual(self.strategy.name, "IronCondorStrategy")
        self.assertEqual(self.strategy.wing_distance_points, 200.0)
        self.assertEqual(self.strategy.short_strike_distance_points, 300.0)
    
    def test_select_iron_condor_strikes(self):
        """Test iron condor strike selection."""
        mock_options_chain = Mock()
        mock_options_chain.atm_strike = 50000
        mock_options_chain.underlying_price = 50000
        mock_options_chain.strikes = [
            {'strike': 49400}, {'strike': 49700}, {'strike': 50000}, 
            {'strike': 50300}, {'strike': 50600}
        ]
        
        strikes_config = self.strategy._select_iron_condor_strikes(mock_options_chain)
        
        self.assertIsNotNone(strikes_config)
        self.assertIn('short_call', strikes_config)
        self.assertIn('long_call', strikes_config)
        self.assertIn('short_put', strikes_config)
        self.assertIn('long_put', strikes_config)
        
        # Validate strike relationships
        self.assertGreater(strikes_config['short_call'], 50000)  # OTM call
        self.assertLess(strikes_config['short_put'], 50000)      # OTM put
        s