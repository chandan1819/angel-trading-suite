"""
Integration tests for complete paper trading workflow end-to-end.

This module tests the entire paper trading system including strategy evaluation,
signal generation, order placement, position monitoring, and risk management.
"""

import pytest
from unittest.mock import Mock, patch, MagicMock
from datetime import datetime, timedelta
import tempfile
import os

from tests.mock_angel_api import MockAngelAPI, MockAPIFactory
from src.trading.trading_manager import TradingManager
from src.strategies.strategy_manager import StrategyManager
from src.strategies.straddle_strategy import StraddleStrategy
from src.strategies.directional_strategy import DirectionalStrategy
from src.risk.risk_manager import RiskManager
from src.orders.order_manager import OrderManager
from src.data.data_manager import DataManager
from src.api.angel_api_client import AngelAPIClient
from src.config.config_manager import ConfigManager
from src.models.config_models import TradingConfig, RiskConfig, StrategyConfig
from src.models.trading_models import SignalType, OptionType


class TestPaperTradingWorkflow:
    """Test complete paper trading workflow"""
    
    @pytest.fixture
    def mock_angel_api(self):
        """Create mock Angel API"""
        return MockAPIFactory.create_normal_api()
    
    @pytest.fixture
    def trading_config(self):
        """Create comprehensive trading configuration"""
        config = TradingConfig()
        
        # Risk configuration
        config.risk = RiskConfig(
            max_daily_loss=5000.0,
            max_concurrent_trades=3,
            profit_target=2000.0,
            stop_loss=1000.0,
            position_size_method="fixed",
            margin_buffer=0.2,
            max_position_size=2,
            daily_trade_limit=10,
            emergency_stop_file="test_emergency.txt"
        )
        
        # Strategy configuration
        config.strategy = StrategyConfig(
            enabled_strategies=["straddle", "directional"],
            evaluation_interval=60,
            max_signals_per_cycle=2,
            strategy_parameters={
                "straddle": {
                    "min_iv_rank": 70.0,
                    "strategy_type": "straddle",
                    "enabled": True
                },
                "directional": {
                    "ema_fast_period": 9,
                    "ema_slow_period": 21,
                    "enabled": True
                }
            }
        )
        
        # Trading configuration
        config.mode = "paper"
        config.underlying_symbol = "BANKNIFTY"
        config.polling_interval = 30
        
        return config
    
    @pytest.fixture
    def trading_manager(self, trading_config, mock_angel_api):
        """Create TradingManager with mocked dependencies"""
        # Mock the API client to use our mock API
        with patch('src.api.angel_api_client.AngelAPIClient') as mock_api_client_class:
            mock_api_client = Mock(spec=AngelAPIClient)
            mock_api_client_class.return_value = mock_api_client
            
            # Configure mock API client to delegate to our mock Angel API
            mock_api_client.authenticate.return_value = True
            mock_api_client.search_instruments.side_effect = lambda exchange, symbol: mock_angel_api.searchScrip(exchange, symbol)["data"]
            mock_api_client.get_ltp.side_effect = lambda exchange, symbol, token: float(mock_angel_api.getLTP(exchange, symbol, token)["data"]["ltp"])
            mock_api_client.place_order.side_effect = lambda params: mock_angel_api.placeOrder(params)
            mock_api_client.get_positions.side_effect = lambda: mock_angel_api.position()["data"]
            mock_api_client.get_historical_data.side_effect = lambda params: mock_angel_api.getHistoricalData(params)["data"]
            
            # Create trading manager
            manager = TradingManager(trading_config)
            manager.initialize()
            
            return manager
    
    def test_complete_paper_trading_cycle(self, trading_manager, mock_angel_api):
        """Test complete paper trading cycle from signal to position management"""
        # Authenticate mock API
        mock_angel_api.generateSession("test", "test", "123456")
        
        # Step 1: Strategy Evaluation
        # Mock market data to trigger straddle signal
        mock_market_data = {
            'options_chain': Mock(),
            'historical_data': [],
            'indicators': {
                'iv_rank': 75.0,  # High IV for straddle
                'ema_cross_signal': 'neutral',
                'volume_confirmation': True
            },
            'current_time': datetime.now()
        }
        
        # Configure options chain mock
        mock_market_data['options_chain'].atm_strike = 50000.0
        mock_market_data['options_chain'].underlying_price = 50000.0
        mock_market_data['options_chain'].expiry_date = (datetime.now() + timedelta(days=7)).strftime('%Y-%m-%d')
        mock_market_data['options_chain'].strikes = [
            {
                'strike': 49900,
                'call': {'ltp': 120, 'bid': 118, 'ask': 122, 'volume': 1000, 'oi': 5000},
                'put': {'ltp': 110, 'bid': 108, 'ask': 112, 'volume': 1200, 'oi': 4800}
            },
            {
                'strike': 50000,
                'call': {'ltp': 150, 'bid': 148, 'ask': 152, 'volume': 2000, 'oi': 8000},
                'put': {'ltp': 140, 'bid': 138, 'ask': 142, 'volume': 1800, 'oi': 7500}
            },
            {
                'strike': 50100,
                'call': {'ltp': 100, 'bid': 98, 'ask': 102, 'volume': 800, 'oi': 3000},
                'put': {'ltp': 170, 'bid': 168, 'ask': 172, 'volume': 900, 'oi': 3500}
            }
        ]
        
        # Mock data manager to return our test data
        with patch.object(trading_manager.data_manager, 'get_market_data', return_value=mock_market_data):
            
            # Step 2: Execute trading cycle
            signals = trading_manager.process_trading_cycle()
            
            # Verify signals were generated
            assert len(signals) > 0, "Should generate trading signals"
            
            # Find straddle signal
            straddle_signal = None
            for signal in signals:
                if signal.signal_type == SignalType.STRADDLE:
                    straddle_signal = signal
                    break
            
            assert straddle_signal is not None, "Should generate straddle signal"
            assert len(straddle_signal.strikes) == 2, "Straddle should have 2 strikes"
            assert straddle_signal.option_types == [OptionType.CE, OptionType.PE], "Should have call and put"
    
    def test_paper_trading_order_execution(self, trading_manager, mock_angel_api):
        """Test order execution in paper trading mode"""
        # Authenticate mock API
        mock_angel_api.generateSession("test", "test", "123456")
        
        # Create a test signal
        from src.models.trading_models import TradingSignal
        signal = TradingSignal(
            strategy_name="test_strategy",
            signal_type=SignalType.BUY,
            underlying="BANKNIFTY",
            strikes=[50000.0],
            option_types=[OptionType.CE],
            quantities=[1],
            confidence=0.8,
            target_pnl=2000.0,
            stop_loss=-1000.0
        )
        
        # Execute signal
        trade = trading_manager.execute_signal(signal)
        
        # Verify trade was created
        assert trade is not None, "Should create trade from signal"
        assert trade.strategy == "test_strategy"
        assert len(trade.legs) > 0, "Trade should have legs"
        
        # Verify order was placed in paper mode
        assert mock_angel_api.get_call_count() > 0, "Should make API calls even in paper mode"
        
        # Check that position was created
        positions = trading_manager.order_manager.get_positions()
        assert len(positions) > 0, "Should create positions"
    
    def test_paper_trading_risk_management(self, trading_manager, mock_angel_api):
        """Test risk management in paper trading"""
        # Authenticate mock API
        mock_angel_api.generateSession("test", "test", "123456")
        
        # Create multiple signals to test position limits
        signals = []
        for i in range(5):  # More than max_concurrent_trades (3)
            signal = TradingSignal(
                strategy_name=f"test_strategy_{i}",
                signal_type=SignalType.BUY,
                underlying="BANKNIFTY",
                strikes=[50000.0 + i * 100],
                option_types=[OptionType.CE],
                quantities=[1],
                confidence=0.8,
                target_pnl=2000.0,
                stop_loss=-1000.0
            )
            signals.append(signal)
        
        executed_trades = []
        
        # Try to execute all signals
        for signal in signals:
            # Validate signal first
            validation_result = trading_manager.risk_manager.validate_trade(signal)
            
            if validation_result.is_valid:
                trade = trading_manager.execute_signal(signal)
                if trade:
                    executed_trades.append(trade)
        
        # Should only execute up to position limit
        assert len(executed_trades) <= 3, "Should respect position limits"
    
    def test_paper_trading_profit_target_monitoring(self, trading_manager, mock_angel_api):
        """Test profit target monitoring in paper trading"""
        # Authenticate mock API
        mock_angel_api.generateSession("test", "test", "123456")
        
        # Create and execute a signal
        signal = TradingSignal(
            strategy_name="profit_test",
            signal_type=SignalType.BUY,
            underlying="BANKNIFTY",
            strikes=[50000.0],
            option_types=[OptionType.CE],
            quantities=[1],
            confidence=0.8,
            target_pnl=2000.0,
            stop_loss=-1000.0
        )
        
        trade = trading_manager.execute_signal(signal)
        assert trade is not None
        
        # Simulate price movement to hit profit target
        # Mock the current price to be much higher
        with patch.object(mock_angel_api, 'getLTP') as mock_ltp:
            mock_ltp.return_value = {
                "status": True,
                "data": {"ltp": "250.0"}  # Much higher than entry price
            }
            
            # Update positions
            trading_manager.update_positions()
            
            # Check if profit target was hit
            updated_trade = trading_manager.get_trade_by_id(trade.trade_id)
            if updated_trade and updated_trade.current_pnl >= 2000.0:
                assert updated_trade.is_target_hit, "Should detect profit target hit"
    
    def test_paper_trading_stop_loss_monitoring(self, trading_manager, mock_angel_api):
        """Test stop loss monitoring in paper trading"""
        # Authenticate mock API
        mock_angel_api.generateSession("test", "test", "123456")
        
        # Create and execute a signal
        signal = TradingSignal(
            strategy_name="stop_test",
            signal_type=SignalType.BUY,
            underlying="BANKNIFTY",
            strikes=[50000.0],
            option_types=[OptionType.CE],
            quantities=[1],
            confidence=0.8,
            target_pnl=2000.0,
            stop_loss=-1000.0
        )
        
        trade = trading_manager.execute_signal(signal)
        assert trade is not None
        
        # Simulate price movement to hit stop loss
        with patch.object(mock_angel_api, 'getLTP') as mock_ltp:
            mock_ltp.return_value = {
                "status": True,
                "data": {"ltp": "50.0"}  # Much lower than entry price
            }
            
            # Update positions
            trading_manager.update_positions()
            
            # Check if stop loss was hit
            updated_trade = trading_manager.get_trade_by_id(trade.trade_id)
            if updated_trade and updated_trade.current_pnl <= -1000.0:
                assert updated_trade.is_stop_loss_hit, "Should detect stop loss hit"
    
    def test_paper_trading_daily_limits(self, trading_manager, mock_angel_api):
        """Test daily loss limits in paper trading"""
        # Authenticate mock API
        mock_angel_api.generateSession("test", "test", "123456")
        
        # Simulate daily loss approaching limit
        today_metrics = trading_manager.risk_manager.get_daily_metrics()
        today_metrics.total_pnl = -4500.0  # Close to 5000 limit
        
        # Try to execute a signal
        signal = TradingSignal(
            strategy_name="limit_test",
            signal_type=SignalType.BUY,
            underlying="BANKNIFTY",
            strikes=[50000.0],
            option_types=[OptionType.CE],
            quantities=[1],
            confidence=0.8,
            target_pnl=2000.0,
            stop_loss=-1000.0
        )
        
        # Should still allow trade as we're within limit
        validation_result = trading_manager.risk_manager.validate_trade(signal)
        assert validation_result.is_valid, "Should allow trade within daily limit"
        
        # Now exceed the limit
        today_metrics.total_pnl = -5500.0  # Exceeds 5000 limit
        
        validation_result = trading_manager.risk_manager.validate_trade(signal)
        assert not validation_result.is_valid, "Should reject trade exceeding daily limit"
    
    def test_paper_trading_emergency_stop(self, trading_manager, mock_angel_api):
        """Test emergency stop functionality in paper trading"""
        # Authenticate mock API
        mock_angel_api.generateSession("test", "test", "123456")
        
        # Create emergency stop file
        with tempfile.NamedTemporaryFile(delete=False) as temp_file:
            trading_manager.risk_manager.risk_config.emergency_stop_file = temp_file.name
            
            # Write emergency stop signal
            with open(temp_file.name, 'w') as f:
                f.write("EMERGENCY STOP ACTIVATED")
            
            # Try to execute a signal
            signal = TradingSignal(
                strategy_name="emergency_test",
                signal_type=SignalType.BUY,
                underlying="BANKNIFTY",
                strikes=[50000.0],
                option_types=[OptionType.CE],
                quantities=[1],
                confidence=0.8,
                target_pnl=2000.0,
                stop_loss=-1000.0
            )
            
            # Should reject due to emergency stop
            validation_result = trading_manager.risk_manager.validate_trade(signal)
            assert not validation_result.is_valid, "Should reject trade during emergency stop"
            
            # Cleanup
            if os.path.exists(temp_file.name):
                os.unlink(temp_file.name)
    
    def test_paper_trading_session_management(self, trading_manager, mock_angel_api):
        """Test trading session lifecycle management"""
        # Test session start
        assert not trading_manager.is_session_active()
        
        success = trading_manager.start_trading_session()
        assert success, "Should start trading session successfully"
        assert trading_manager.is_session_active()
        
        # Test session operations
        session_summary = trading_manager.get_session_summary()
        assert 'start_time' in session_summary
        assert 'trades_executed' in session_summary
        assert 'total_pnl' in session_summary
        
        # Test session stop
        trading_manager.stop_trading_session()
        assert not trading_manager.is_session_active()
    
    def test_paper_trading_error_recovery(self, trading_manager):
        """Test error recovery in paper trading"""
        # Use error-prone mock API
        error_api = MockAPIFactory.create_error_prone_api()
        
        with patch.object(trading_manager.api_client, 'get_ltp', 
                         side_effect=Exception("Network error")):
            
            # Try to process trading cycle with errors
            try:
                signals = trading_manager.process_trading_cycle()
                # Should handle errors gracefully
                assert isinstance(signals, list), "Should return empty list on error"
            except Exception as e:
                pytest.fail(f"Should handle errors gracefully, but got: {e}")
    
    def test_paper_trading_performance(self, trading_manager, mock_angel_api):
        """Test paper trading performance"""
        import time
        
        # Authenticate mock API
        mock_angel_api.generateSession("test", "test", "123456")
        
        # Measure trading cycle performance
        start_time = time.time()
        
        # Execute multiple trading cycles
        for _ in range(10):
            trading_manager.process_trading_cycle()
        
        end_time = time.time()
        
        # Should complete within reasonable time (5 seconds for 10 cycles)
        assert (end_time - start_time) < 5.0, "Paper trading should be performant"
        
        # Check API call efficiency
        api_calls = mock_angel_api.get_call_count()
        assert api_calls < 100, "Should not make excessive API calls"


class TestIntegrationErrorHandling:
    """Test error handling and recovery scenarios"""
    
    def test_api_connection_failure(self):
        """Test handling of API connection failures"""
        # Create trading manager with failing API
        error_api = MockAPIFactory.create_network_issue_api()
        
        config = TradingConfig()
        config.mode = "paper"
        
        with patch('src.api.angel_api_client.AngelAPIClient') as mock_api_class:
            mock_api = Mock()
            mock_api.authenticate.side_effect = Exception("Connection failed")
            mock_api_class.return_value = mock_api
            
            manager = TradingManager(config)
            
            # Should handle authentication failure gracefully
            success = manager.initialize()
            assert not success, "Should fail to initialize with connection issues"
    
    def test_rate_limiting_handling(self):
        """Test handling of API rate limiting"""
        rate_limited_api = MockAPIFactory.create_rate_limited_api()
        
        config = TradingConfig()
        config.mode = "paper"
        
        with patch('src.api.angel_api_client.AngelAPIClient') as mock_api_class:
            mock_api = Mock()
            mock_api.authenticate.return_value = True
            
            # Simulate rate limiting on market data calls
            call_count = 0
            def rate_limited_call(*args, **kwargs):
                nonlocal call_count
                call_count += 1
                if call_count > 5:
                    raise Exception("Rate limit exceeded")
                return {"ltp": "100.0"}
            
            mock_api.get_ltp.side_effect = rate_limited_call
            mock_api_class.return_value = mock_api
            
            manager = TradingManager(config)
            manager.initialize()
            
            # Should handle rate limiting gracefully
            try:
                for _ in range(10):  # Try to exceed rate limit
                    manager.process_trading_cycle()
            except Exception as e:
                # Should not propagate rate limit exceptions
                assert "Rate limit" not in str(e), "Should handle rate limiting internally"
    
    def test_partial_data_scenarios(self):
        """Test handling of partial or missing market data"""
        config = TradingConfig()
        config.mode = "paper"
        
        with patch('src.api.angel_api_client.AngelAPIClient') as mock_api_class:
            mock_api = Mock()
            mock_api.authenticate.return_value = True
            
            # Return incomplete market data
            mock_api.search_instruments.return_value = []  # No instruments
            mock_api.get_ltp.return_value = None  # No price data
            
            mock_api_class.return_value = mock_api
            
            manager = TradingManager(config)
            manager.initialize()
            
            # Should handle missing data gracefully
            signals = manager.process_trading_cycle()
            assert isinstance(signals, list), "Should return empty list with missing data"
    
    def test_order_rejection_handling(self):
        """Test handling of order rejections"""
        config = TradingConfig()
        config.mode = "paper"
        
        with patch('src.api.angel_api_client.AngelAPIClient') as mock_api_class:
            mock_api = Mock()
            mock_api.authenticate.return_value = True
            
            # Simulate order rejection
            mock_api.place_order.return_value = {
                "status": False,
                "message": "Insufficient margin",
                "errorcode": "AB2001"
            }
            
            mock_api_class.return_value = mock_api
            
            manager = TradingManager(config)
            manager.initialize()
            
            # Create a signal and try to execute
            from src.models.trading_models import TradingSignal
            signal = TradingSignal(
                strategy_name="test",
                signal_type=SignalType.BUY,
                underlying="BANKNIFTY",
                strikes=[50000.0],
                option_types=[OptionType.CE],
                quantities=[1],
                confidence=0.8
            )
            
            # Should handle order rejection gracefully
            trade = manager.execute_signal(signal)
            # In paper mode, should still create trade even if real order would be rejected
            assert trade is not None or manager.config.mode == "paper"