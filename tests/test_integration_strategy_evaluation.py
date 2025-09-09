"""
Integration tests for strategy evaluation workflows.

This module tests the complete strategy evaluation process including
data retrieval, signal generation, validation, and strategy coordination.
"""

import pytest
from unittest.mock import Mock, patch, MagicMock
from datetime import datetime, timedelta
from typing import Dict, Any, List

from tests.mock_angel_api import MockAngelAPI, MockAPIFactory
from src.strategies.strategy_manager import StrategyManager
from src.strategies.straddle_strategy import StraddleStrategy
from src.strategies.directional_strategy import DirectionalStrategy
from src.strategies.iron_condor_strategy import IronCondorStrategy
from src.strategies.greeks_strategy import GreeksStrategy
from src.strategies.volatility_strategy import VolatilityStrategy
from src.data.data_manager import DataManager
from src.api.angel_api_client import AngelAPIClient
from src.models.trading_models import TradingSignal, SignalType, OptionType, OptionsChain
from src.models.config_models import StrategyConfig


class TestStrategyEvaluationWorkflow:
    """Test complete strategy evaluation workflow"""
    
    @pytest.fixture
    def mock_angel_api(self):
        """Create mock Angel API"""
        return MockAPIFactory.create_normal_api()
    
    @pytest.fixture
    def data_manager(self, mock_angel_api):
        """Create DataManager with mocked API"""
        with patch('src.api.angel_api_client.AngelAPIClient') as mock_api_class:
            mock_api_client = Mock(spec=AngelAPIClient)
            mock_api_client.search_instruments.side_effect = lambda exchange, symbol: mock_angel_api.searchScrip(exchange, symbol)["data"]
            mock_api_client.get_ltp.side_effect = lambda exchange, symbol, token: float(mock_angel_api.getLTP(exchange, symbol, token)["data"]["ltp"])
            mock_api_client.get_historical_data.side_effect = lambda params: mock_angel_api.getHistoricalData(params)["data"]
            mock_api_class.return_value = mock_api_client
            
            return DataManager(mock_api_client)
    
    @pytest.fixture
    def strategy_manager(self, data_manager):
        """Create StrategyManager with test configuration"""
        config = {
            'max_concurrent_evaluations': 5,
            'evaluation_timeout': 30,
            'enable_concurrent_evaluation': False,  # Sequential for testing
            'max_signals_per_cycle': 3
        }
        return StrategyManager(data_manager, config)
    
    @pytest.fixture
    def sample_market_data(self):
        """Create comprehensive sample market data"""
        return {
            'options_chain': self.create_mock_options_chain(),
            'historical_data': self.create_mock_historical_data(),
            'indicators': {
                'iv_rank': 75.0,
                'iv_percentile': 80.0,
                'ema_9': 49950.0,
                'ema_21': 49900.0,
                'ema_cross_signal': 'bullish',
                'atr': 250.0,
                'atr_breakout_signal': 'neutral',
                'rsi': 65.0,
                'momentum': 1.5,
                'volume_confirmation': True,
                'bid_ask_spread_avg': 2.5,
                'option_volume_ratio': 1.2
            },
            'current_time': datetime.now(),
            'market_hours': True,
            'volatility_regime': 'high'
        }
    
    def create_mock_options_chain(self) -> Mock:
        """Create mock options chain with realistic data"""
        options_chain = Mock()
        options_chain.underlying_symbol = "BANKNIFTY"
        options_chain.underlying_price = 50000.0
        options_chain.atm_strike = 50000.0
        options_chain.expiry_date = (datetime.now() + timedelta(days=7)).strftime('%Y-%m-%d')
        
        # Create strikes with realistic option data
        strikes = []
        for strike_price in range(49000, 51100, 100):
            distance_from_atm = abs(strike_price - 50000)
            
            # Calculate realistic premiums based on distance from ATM
            call_premium = max(5.0, 150 - distance_from_atm * 0.1)
            put_premium = max(5.0, 140 - distance_from_atm * 0.1)
            
            # Add some randomness
            call_premium *= (0.9 + 0.2 * (strike_price % 3) / 3)
            put_premium *= (0.9 + 0.2 * (strike_price % 5) / 5)
            
            strike_data = {
                'strike': strike_price,
                'call': {
                    'symbol': f'BANKNIFTY{options_chain.expiry_date.replace("-", "")}CE{strike_price}',
                    'token': f'{strike_price}1',
                    'ltp': round(call_premium, 2),
                    'bid': round(call_premium * 0.98, 2),
                    'ask': round(call_premium * 1.02, 2),
                    'volume': max(100, 2000 - distance_from_atm * 2),
                    'oi': max(500, 10000 - distance_from_atm * 5),
                    'delta': max(0.01, 0.5 - distance_from_atm * 0.001),
                    'theta': -0.5,
                    'vega': 0.3,
                    'gamma': 0.001,
                    'iv': 0.25 + distance_from_atm * 0.0001
                },
                'put': {
                    'symbol': f'BANKNIFTY{options_chain.expiry_date.replace("-", "")}PE{strike_price}',
                    'token': f'{strike_price}2',
                    'ltp': round(put_premium, 2),
                    'bid': round(put_premium * 0.98, 2),
                    'ask': round(put_premium * 1.02, 2),
                    'volume': max(100, 1800 - distance_from_atm * 2),
                    'oi': max(500, 9500 - distance_from_atm * 5),
                    'delta': min(-0.01, -0.5 + distance_from_atm * 0.001),
                    'theta': -0.5,
                    'vega': 0.3,
                    'gamma': 0.001,
                    'iv': 0.24 + distance_from_atm * 0.0001
                }
            }
            strikes.append(strike_data)
        
        options_chain.strikes = strikes
        return options_chain
    
    def create_mock_historical_data(self) -> List[Dict[str, Any]]:
        """Create mock historical price data"""
        historical_data = []
        base_price = 50000.0
        current_time = datetime.now()
        
        # Generate 100 data points (last 100 minutes)
        for i in range(100):
            timestamp = current_time - timedelta(minutes=100-i)
            
            # Simulate price movement
            price_change = (i % 10 - 5) * 10  # Oscillating movement
            price = base_price + price_change + (i * 2)  # Slight uptrend
            
            historical_data.append({
                'timestamp': timestamp.isoformat(),
                'open': round(price - 5, 2),
                'high': round(price + 15, 2),
                'low': round(price - 10, 2),
                'close': round(price, 2),
                'volume': 10000 + (i % 5) * 2000
            })
        
        return historical_data
    
    def test_straddle_strategy_evaluation(self, strategy_manager, sample_market_data):
        """Test straddle strategy evaluation with high IV"""
        # Configure straddle strategy
        straddle_config = {
            'min_iv_rank': 70.0,
            'max_iv_rank': 95.0,
            'strategy_type': 'straddle',
            'min_dte': 0,
            'max_dte': 30,
            'enabled': True
        }
        
        straddle_strategy = StraddleStrategy(straddle_config)
        strategy_manager.register_strategy(straddle_strategy)
        
        # Evaluate strategies
        signals = strategy_manager.evaluate_strategies(sample_market_data)
        
        # Should generate straddle signal due to high IV
        straddle_signals = [s for s in signals if s.signal_type == SignalType.STRADDLE]
        assert len(straddle_signals) > 0, "Should generate straddle signal with high IV"
        
        signal = straddle_signals[0]
        assert signal.strategy_name == "StraddleStrategy"
        assert len(signal.strikes) == 2, "Straddle should have 2 strikes"
        assert signal.option_types == [OptionType.CE, OptionType.PE], "Should have call and put"
        assert signal.confidence > 0.5, "Should have reasonable confidence"
    
    def test_directional_strategy_evaluation(self, strategy_manager, sample_market_data):
        """Test directional strategy evaluation with bullish signals"""
        # Configure directional strategy
        directional_config = {
            'ema_fast_period': 9,
            'ema_slow_period': 21,
            'atr_period': 14,
            'atr_multiplier': 2.0,
            'strike_selection_method': 'atm',
            'enabled': True
        }
        
        directional_strategy = DirectionalStrategy(directional_config)
        strategy_manager.register_strategy(directional_strategy)
        
        # Evaluate strategies
        signals = strategy_manager.evaluate_strategies(sample_market_data)
        
        # Should generate directional signal due to bullish EMA cross
        directional_signals = [s for s in signals if s.signal_type == SignalType.BUY]
        assert len(directional_signals) > 0, "Should generate directional signal with bullish indicators"
        
        signal = directional_signals[0]
        assert signal.strategy_name == "DirectionalStrategy"
        assert len(signal.strikes) == 1, "Directional should have 1 strike"
        assert signal.option_types == [OptionType.CE], "Should be call option for bullish signal"
    
    def test_iron_condor_strategy_evaluation(self, strategy_manager, sample_market_data):
        """Test iron condor strategy evaluation"""
        # Modify market data for iron condor conditions (medium IV)
        sample_market_data['indicators']['iv_rank'] = 55.0  # Medium IV
        
        # Configure iron condor strategy
        iron_condor_config = {
            'wing_distance_points': 200.0,
            'short_strike_distance_points': 300.0,
            'min_iv_rank': 40.0,
            'max_iv_rank': 80.0,
            'min_credit_received': 50.0,
            'enabled': True
        }
        
        iron_condor_strategy = IronCondorStrategy(iron_condor_config)
        strategy_manager.register_strategy(iron_condor_strategy)
        
        # Evaluate strategies
        signals = strategy_manager.evaluate_strategies(sample_market_data)
        
        # Should generate iron condor signal
        iron_condor_signals = [s for s in signals if s.signal_type == SignalType.IRON_CONDOR]
        assert len(iron_condor_signals) > 0, "Should generate iron condor signal with medium IV"
        
        signal = iron_condor_signals[0]
        assert signal.strategy_name == "IronCondorStrategy"
        assert len(signal.strikes) == 4, "Iron condor should have 4 strikes"
        assert len(set(signal.option_types)) == 2, "Should have both calls and puts"
    
    def test_greeks_strategy_evaluation(self, strategy_manager, sample_market_data):
        """Test Greeks-based strategy evaluation"""
        # Configure Greeks strategy
        greeks_config = {
            'target_delta_range': [0.3, 0.7],
            'max_theta_decay': -1.0,
            'min_vega_exposure': 0.2,
            'momentum_threshold': 1.0,
            'enabled': True
        }
        
        greeks_strategy = GreeksStrategy(greeks_config)
        strategy_manager.register_strategy(greeks_strategy)
        
        # Evaluate strategies
        signals = strategy_manager.evaluate_strategies(sample_market_data)
        
        # Should generate Greeks-based signal
        greeks_signals = [s for s in signals if s.strategy_name == "GreeksStrategy"]
        assert len(greeks_signals) > 0, "Should generate Greeks-based signal"
        
        signal = greeks_signals[0]
        assert signal.confidence > 0.0, "Should have valid confidence"
    
    def test_volatility_strategy_evaluation(self, strategy_manager, sample_market_data):
        """Test volatility-based strategy evaluation"""
        # Configure volatility strategy
        volatility_config = {
            'iv_rank_buy_threshold': 30.0,
            'iv_rank_sell_threshold': 70.0,
            'iv_percentile_threshold': 75.0,
            'volatility_regime_filter': True,
            'enabled': True
        }
        
        volatility_strategy = VolatilityStrategy(volatility_config)
        strategy_manager.register_strategy(volatility_strategy)
        
        # Evaluate strategies
        signals = strategy_manager.evaluate_strategies(sample_market_data)
        
        # Should generate volatility-based signal
        volatility_signals = [s for s in signals if s.strategy_name == "VolatilityStrategy"]
        assert len(volatility_signals) > 0, "Should generate volatility-based signal"
    
    def test_multiple_strategy_coordination(self, strategy_manager, sample_market_data):
        """Test coordination of multiple strategies"""
        # Register multiple strategies
        strategies = [
            StraddleStrategy({'min_iv_rank': 70.0, 'enabled': True}),
            DirectionalStrategy({'ema_fast_period': 9, 'ema_slow_period': 21, 'enabled': True}),
            IronCondorStrategy({'min_iv_rank': 40.0, 'max_iv_rank': 80.0, 'enabled': True})
        ]
        
        for strategy in strategies:
            strategy_manager.register_strategy(strategy)
        
        # Evaluate all strategies
        signals = strategy_manager.evaluate_strategies(sample_market_data)
        
        # Should generate signals from multiple strategies
        assert len(signals) > 0, "Should generate signals from multiple strategies"
        
        # Check signal diversity
        strategy_names = [s.strategy_name for s in signals]
        unique_strategies = set(strategy_names)
        assert len(unique_strategies) > 1, "Should have signals from multiple strategies"
        
        # Verify signal filtering and prioritization
        assert len(signals) <= 3, "Should respect max_signals_per_cycle limit"
        
        # Signals should be sorted by confidence (highest first)
        confidences = [s.confidence for s in signals]
        assert confidences == sorted(confidences, reverse=True), "Signals should be sorted by confidence"
    
    def test_strategy_evaluation_with_market_conditions(self, strategy_manager):
        """Test strategy evaluation under different market conditions"""
        # Test different market scenarios
        market_scenarios = [
            {
                'name': 'high_volatility',
                'indicators': {'iv_rank': 85.0, 'ema_cross_signal': 'neutral', 'momentum': 0.5},
                'expected_strategies': ['StraddleStrategy']
            },
            {
                'name': 'low_volatility',
                'indicators': {'iv_rank': 25.0, 'ema_cross_signal': 'bullish', 'momentum': 2.0},
                'expected_strategies': ['DirectionalStrategy']
            },
            {
                'name': 'medium_volatility',
                'indicators': {'iv_rank': 55.0, 'ema_cross_signal': 'neutral', 'momentum': 0.8},
                'expected_strategies': ['IronCondorStrategy']
            }
        ]
        
        # Register all strategies
        strategies = [
            StraddleStrategy({'min_iv_rank': 70.0, 'enabled': True}),
            DirectionalStrategy({'ema_fast_period': 9, 'ema_slow_period': 21, 'enabled': True}),
            IronCondorStrategy({'min_iv_rank': 40.0, 'max_iv_rank': 80.0, 'enabled': True})
        ]
        
        for strategy in strategies:
            strategy_manager.register_strategy(strategy)
        
        for scenario in market_scenarios:
            # Create market data for scenario
            market_data = {
                'options_chain': self.create_mock_options_chain(),
                'historical_data': self.create_mock_historical_data(),
                'indicators': {
                    **scenario['indicators'],
                    'volume_confirmation': True,
                    'bid_ask_spread_avg': 2.0
                },
                'current_time': datetime.now(),
                'market_hours': True
            }
            
            # Evaluate strategies
            signals = strategy_manager.evaluate_strategies(market_data)
            
            if signals:
                # Check if expected strategies generated signals
                generated_strategies = [s.strategy_name for s in signals]
                
                # At least one expected strategy should generate a signal
                expected_found = any(expected in generated_strategies 
                                   for expected in scenario['expected_strategies'])
                
                assert expected_found, f"Expected strategies {scenario['expected_strategies']} not found in {generated_strategies} for scenario {scenario['name']}"
    
    def test_strategy_evaluation_performance(self, strategy_manager, sample_market_data):
        """Test strategy evaluation performance"""
        import time
        
        # Register multiple strategies
        strategies = [
            StraddleStrategy({'enabled': True}),
            DirectionalStrategy({'enabled': True}),
            IronCondorStrategy({'enabled': True}),
            GreeksStrategy({'enabled': True}),
            VolatilityStrategy({'enabled': True})
        ]
        
        for strategy in strategies:
            strategy_manager.register_strategy(strategy)
        
        # Measure evaluation time
        start_time = time.time()
        
        # Run multiple evaluation cycles
        for _ in range(10):
            signals = strategy_manager.evaluate_strategies(sample_market_data)
        
        end_time = time.time()
        
        # Should complete within 5 seconds (requirement)
        total_time = end_time - start_time
        assert total_time < 5.0, f"Strategy evaluation too slow: {total_time:.2f}s for 10 cycles"
        
        # Average time per cycle should be reasonable
        avg_time_per_cycle = total_time / 10
        assert avg_time_per_cycle < 0.5, f"Average evaluation time too slow: {avg_time_per_cycle:.2f}s"
    
    def test_strategy_evaluation_error_handling(self, strategy_manager, sample_market_data):
        """Test error handling during strategy evaluation"""
        # Create a strategy that throws errors
        class ErrorStrategy(StraddleStrategy):
            def evaluate(self, market_data):
                raise Exception("Strategy evaluation error")
        
        error_strategy = ErrorStrategy({'enabled': True})
        strategy_manager.register_strategy(error_strategy)
        
        # Also register a working strategy
        working_strategy = DirectionalStrategy({'enabled': True})
        strategy_manager.register_strategy(working_strategy)
        
        # Evaluate strategies - should handle errors gracefully
        signals = strategy_manager.evaluate_strategies(sample_market_data)
        
        # Should still get signals from working strategy
        assert isinstance(signals, list), "Should return list even with strategy errors"
        
        # Working strategy should still produce signals
        working_signals = [s for s in signals if s.strategy_name == "DirectionalStrategy"]
        # Note: May or may not have signals depending on market conditions, but should not crash
    
    def test_strategy_evaluation_with_missing_data(self, strategy_manager):
        """Test strategy evaluation with incomplete market data"""
        # Create incomplete market data
        incomplete_data_scenarios = [
            {
                'name': 'missing_options_chain',
                'data': {
                    'options_chain': None,
                    'indicators': {'iv_rank': 75.0},
                    'current_time': datetime.now()
                }
            },
            {
                'name': 'missing_indicators',
                'data': {
                    'options_chain': self.create_mock_options_chain(),
                    'indicators': {},
                    'current_time': datetime.now()
                }
            },
            {
                'name': 'empty_options_chain',
                'data': {
                    'options_chain': Mock(strikes=[]),
                    'indicators': {'iv_rank': 75.0},
                    'current_time': datetime.now()
                }
            }
        ]
        
        # Register strategy
        strategy = StraddleStrategy({'enabled': True})
        strategy_manager.register_strategy(strategy)
        
        for scenario in incomplete_data_scenarios:
            # Should handle incomplete data gracefully
            signals = strategy_manager.evaluate_strategies(scenario['data'])
            
            assert isinstance(signals, list), f"Should return list for scenario: {scenario['name']}"
            # May be empty due to missing data, but should not crash
    
    def test_strategy_signal_validation(self, strategy_manager, sample_market_data):
        """Test signal validation during strategy evaluation"""
        # Create strategy that generates invalid signals
        class InvalidSignalStrategy(StraddleStrategy):
            def evaluate(self, market_data):
                # Return invalid signal
                return TradingSignal(
                    strategy_name="",  # Invalid empty name
                    signal_type=SignalType.BUY,
                    underlying="BANKNIFTY",
                    strikes=[],  # Invalid empty strikes
                    option_types=[],
                    quantities=[],
                    confidence=1.5  # Invalid confidence > 1.0
                )
        
        invalid_strategy = InvalidSignalStrategy({'enabled': True})
        strategy_manager.register_strategy(invalid_strategy)
        
        # Evaluate strategies
        signals = strategy_manager.evaluate_strategies(sample_market_data)
        
        # Invalid signals should be filtered out
        assert all(signal.validate() for signal in signals), "All returned signals should be valid"
    
    def test_concurrent_strategy_evaluation(self, data_manager):
        """Test concurrent strategy evaluation"""
        # Create strategy manager with concurrent evaluation enabled
        config = {
            'max_concurrent_evaluations': 3,
            'evaluation_timeout': 10,
            'enable_concurrent_evaluation': True,
            'max_signals_per_cycle': 5
        }
        
        concurrent_manager = StrategyManager(data_manager, config)
        
        # Register multiple strategies
        strategies = [
            StraddleStrategy({'enabled': True}),
            DirectionalStrategy({'enabled': True}),
            IronCondorStrategy({'enabled': True})
        ]
        
        for strategy in strategies:
            concurrent_manager.register_strategy(strategy)
        
        # Create market data
        market_data = {
            'options_chain': self.create_mock_options_chain(),
            'indicators': {'iv_rank': 75.0, 'ema_cross_signal': 'bullish'},
            'current_time': datetime.now()
        }
        
        # Evaluate strategies concurrently
        import time
        start_time = time.time()
        signals = concurrent_manager.evaluate_strategies(market_data)
        end_time = time.time()
        
        # Should complete and return valid signals
        assert isinstance(signals, list), "Should return list of signals"
        
        # Concurrent evaluation should not take significantly longer than sequential
        # (This is a basic test - real performance gains depend on strategy complexity)
        evaluation_time = end_time - start_time
        assert evaluation_time < 5.0, "Concurrent evaluation should complete in reasonable time"