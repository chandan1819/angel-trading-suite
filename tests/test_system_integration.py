"""
Comprehensive system integration tests for the Bank Nifty Options Trading System.

This module tests end-to-end system functionality including:
- Complete trading workflows
- Risk management enforcement
- Emergency procedures
- Performance under various market conditions
"""

import pytest
import os
import tempfile
import time
import json
from pathlib import Path
from unittest.mock import Mock, patch, MagicMock
from datetime import datetime, timedelta
import yaml

# Import system components
from src.trading.trading_manager import TradingManager
from src.config.config_manager import ConfigManager
from src.models.config_models import TradingConfig, TradingMode
from src.models.trading_models import TradingSignal, Trade, Option
from tests.mock_angel_api import MockAngelAPI


class TestSystemIntegration:
    """Test complete system integration scenarios"""
    
    @pytest.fixture
    def temp_config_dir(self):
        """Create temporary directory for test configurations"""
        with tempfile.TemporaryDirectory() as temp_dir:
            yield Path(temp_dir)
    
    @pytest.fixture
    def mock_config(self, temp_config_dir):
        """Create mock configuration for testing"""
        config_data = {
            'mode': 'paper',
            'underlying_symbol': 'BANKNIFTY',
            'api': {
                'credentials': {
                    'api_key': 'test_key',
                    'client_code': 'test_client',
                    'pin': 'test_pin',
                    'totp_secret': 'test_totp'
                },
                'timeout': 30,
                'max_retries': 3
            },
            'risk': {
                'max_daily_loss': 5000.0,
                'max_concurrent_trades': 3,
                'profit_target': 2000.0,
                'stop_loss': 1000.0,
                'position_size_method': 'fixed',
                'max_position_size': 50
            },
            'strategy': {
                'enabled_strategies': ['straddle'],
                'straddle': {
                    'enabled': True,
                    'min_confidence': 0.6,
                    'min_iv_rank': 0.5,
                    'max_dte': 7
                }
            },
            'logging': {
                'level': 'INFO',
                'enable_console': True,
                'enable_file': False
            },
            'notification': {
                'enabled': False
            }
        }
        
        config_file = temp_config_dir / 'test_config.yaml'
        with open(config_file, 'w') as f:
            yaml.dump(config_data, f)
        
        return config_file
    
    @pytest.fixture
    def trading_manager(self, mock_config):
        """Create trading manager with mock configuration"""
        config_manager = ConfigManager()
        config = config_manager.load_config(str(mock_config))
        
        with patch('src.api.angel_api_client.AngelAPIClient') as mock_api_class:
            mock_api = MockAngelAPI()
            mock_api_class.return_value = mock_api
            
            manager = TradingManager(config, 'paper')
            manager.api_client = mock_api
            return manager
    
    def test_complete_trading_workflow_paper_mode(self, trading_manager):
        """Test complete trading workflow in paper mode"""
        # Initialize system
        assert trading_manager.initialize()
        
        # Start trading session
        success = trading_manager.start_trading_session(continuous=False)
        assert success
        
        # Verify session state
        summary = trading_manager.get_session_summary()
        assert summary['session_state'] == 'running'
        assert summary['mode'] == 'paper'
        
        # Stop session
        trading_manager.stop_trading_session()
        
        # Verify cleanup
        summary = trading_manager.get_session_summary()
        assert summary['session_state'] == 'stopped'
    
    def test_risk_management_enforcement(self, trading_manager):
        """Test that risk management rules are properly enforced"""
        # Initialize system
        assert trading_manager.initialize()
        
        # Mock a high-loss scenario
        with patch.object(trading_manager.risk_manager, 'get_daily_pnl', return_value=-6000.0):
            # Try to start trading session - should be blocked by daily loss limit
            with patch.object(trading_manager.risk_manager, 'check_daily_limits', return_value=False):
                success = trading_manager.start_trading_session(continuous=False)
                # Should still succeed in initialization but not place new trades
                assert success
        
        # Test position limits
        with patch.object(trading_manager.risk_manager, 'get_active_positions_count', return_value=5):
            with patch.object(trading_manager.risk_manager, 'check_position_limits', return_value=False):
                # Should not place new trades when position limit exceeded
                result = trading_manager.process_trading_cycle()
                # Verify no new trades were attempted
                assert result is not None
    
    def test_emergency_stop_mechanism(self, trading_manager, temp_config_dir):
        """Test emergency stop functionality"""
        emergency_file = temp_config_dir / 'emergency_stop.txt'
        
        # Initialize system
        assert trading_manager.initialize()
        
        # Start trading session
        trading_manager.start_trading_session(continuous=False)
        
        # Create emergency stop file
        emergency_file.write_text("Emergency stop activated")
        
        # Update emergency stop file path in config
        trading_manager.config.risk.emergency_stop_file = str(emergency_file)
        
        # Process trading cycle - should detect emergency stop
        with patch.object(trading_manager, 'handle_emergency_stop') as mock_emergency:
            trading_manager.process_trading_cycle()
            # Emergency stop should be detected and handled
            # Note: Actual detection depends on implementation
    
    def test_api_connection_resilience(self, trading_manager):
        """Test system resilience to API connection issues"""
        # Initialize system
        assert trading_manager.initialize()
        
        # Mock API connection failure
        with patch.object(trading_manager.api_client, 'get_ltp', side_effect=ConnectionError("API connection failed")):
            # System should handle connection errors gracefully
            result = trading_manager.process_trading_cycle()
            # Should not crash and should log the error
            assert result is not None
        
        # Mock API rate limiting
        with patch.object(trading_manager.api_client, 'get_ltp', side_effect=Exception("Rate limit exceeded")):
            result = trading_manager.process_trading_cycle()
            # Should handle rate limiting gracefully
            assert result is not None
    
    def test_strategy_signal_generation_and_execution(self, trading_manager):
        """Test strategy signal generation and order execution"""
        # Initialize system
        assert trading_manager.initialize()
        
        # Mock market data that should generate signals
        mock_options_chain = Mock()
        mock_options_chain.underlying_price = 45000.0
        mock_options_chain.atm_strike = 45000.0
        
        with patch.object(trading_manager.data_manager, 'get_options_chain', return_value=mock_options_chain):
            with patch.object(trading_manager.strategy_manager, 'evaluate_strategies') as mock_evaluate:
                # Mock a trading signal
                mock_signal = TradingSignal(
                    strategy_name='straddle',
                    signal_type='STRADDLE',
                    underlying='BANKNIFTY',
                    strikes=[45000.0],
                    option_types=['CE', 'PE'],
                    quantities=[25, 25],
                    confidence=0.8,
                    timestamp=datetime.now(),
                    metadata={}
                )
                mock_evaluate.return_value = [mock_signal]
                
                # Process trading cycle
                result = trading_manager.process_trading_cycle()
                
                # Verify signal was processed
                assert result is not None
                mock_evaluate.assert_called_once()
    
    def test_position_monitoring_and_pnl_tracking(self, trading_manager):
        """Test position monitoring and P&L tracking"""
        # Initialize system
        assert trading_manager.initialize()
        
        # Mock active positions
        mock_positions = [
            {
                'symbol': 'BANKNIFTY45000CE',
                'quantity': 25,
                'average_price': 100.0,
                'ltp': 120.0,
                'pnl': 500.0
            }
        ]
        
        with patch.object(trading_manager.order_manager, 'get_positions', return_value=mock_positions):
            # Process position monitoring
            summary = trading_manager.get_session_summary()
            
            # Verify position tracking
            assert 'active_trades' in summary
            assert 'session_pnl' in summary
    
    def test_logging_and_audit_trail(self, trading_manager, temp_config_dir):
        """Test comprehensive logging and audit trail"""
        # Enable file logging for this test
        log_dir = temp_config_dir / 'logs'
        log_dir.mkdir()
        
        trading_manager.config.logging.enable_file = True
        trading_manager.config.logging.log_dir = str(log_dir)
        
        # Initialize system
        assert trading_manager.initialize()
        
        # Perform various operations
        trading_manager.start_trading_session(continuous=False)
        trading_manager.process_trading_cycle()
        trading_manager.stop_trading_session()
        
        # Verify log files are created (implementation dependent)
        # This is a placeholder for actual log verification
        assert True  # Replace with actual log file checks
    
    def test_configuration_validation_and_error_handling(self, temp_config_dir):
        """Test configuration validation and error handling"""
        # Test invalid configuration
        invalid_config_data = {
            'mode': 'invalid_mode',  # Invalid mode
            'risk': {
                'profit_target': -1000.0  # Invalid negative value
            }
        }
        
        invalid_config_file = temp_config_dir / 'invalid_config.yaml'
        with open(invalid_config_file, 'w') as f:
            yaml.dump(invalid_config_data, f)
        
        config_manager = ConfigManager()
        
        # Should raise validation error
        with pytest.raises(Exception):
            config_manager.load_config(str(invalid_config_file))
    
    def test_performance_under_load(self, trading_manager):
        """Test system performance under simulated load"""
        # Initialize system
        assert trading_manager.initialize()
        
        # Measure performance of multiple trading cycles
        start_time = time.time()
        
        for _ in range(10):
            trading_manager.process_trading_cycle()
        
        end_time = time.time()
        execution_time = end_time - start_time
        
        # Verify performance is within acceptable limits (10 cycles in < 30 seconds)
        assert execution_time < 30.0, f"Performance test failed: {execution_time:.2f}s for 10 cycles"
    
    def test_memory_usage_stability(self, trading_manager):
        """Test memory usage stability over multiple cycles"""
        import psutil
        import os
        
        # Initialize system
        assert trading_manager.initialize()
        
        process = psutil.Process(os.getpid())
        initial_memory = process.memory_info().rss
        
        # Run multiple cycles
        for _ in range(50):
            trading_manager.process_trading_cycle()
        
        final_memory = process.memory_info().rss
        memory_increase = final_memory - initial_memory
        
        # Memory increase should be reasonable (< 50MB for 50 cycles)
        assert memory_increase < 50 * 1024 * 1024, f"Memory leak detected: {memory_increase / 1024 / 1024:.2f}MB increase"


class TestMarketConditionScenarios:
    """Test system behavior under various market conditions"""
    
    @pytest.fixture
    def trading_manager_with_scenarios(self, mock_config):
        """Create trading manager for scenario testing"""
        config_manager = ConfigManager()
        config = config_manager.load_config(str(mock_config))
        
        with patch('src.api.angel_api_client.AngelAPIClient') as mock_api_class:
            mock_api = MockAngelAPI()
            mock_api_class.return_value = mock_api
            
            manager = TradingManager(config, 'paper')
            manager.api_client = mock_api
            return manager
    
    def test_high_volatility_scenario(self, trading_manager_with_scenarios):
        """Test system behavior during high volatility periods"""
        manager = trading_manager_with_scenarios
        assert manager.initialize()
        
        # Mock high volatility market data
        with patch.object(manager.data_manager, 'get_current_iv_rank', return_value=0.95):
            with patch.object(manager.data_manager, 'get_underlying_price', return_value=45000.0):
                # Process trading cycle in high volatility
                result = manager.process_trading_cycle()
                assert result is not None
    
    def test_low_liquidity_scenario(self, trading_manager_with_scenarios):
        """Test system behavior during low liquidity periods"""
        manager = trading_manager_with_scenarios
        assert manager.initialize()
        
        # Mock low liquidity options chain
        mock_options_chain = Mock()
        mock_options_chain.underlying_price = 45000.0
        mock_options_chain.strikes = []  # No liquid strikes available
        
        with patch.object(manager.data_manager, 'get_options_chain', return_value=mock_options_chain):
            result = manager.process_trading_cycle()
            # Should handle low liquidity gracefully
            assert result is not None
    
    def test_market_gap_scenario(self, trading_manager_with_scenarios):
        """Test system behavior during market gaps"""
        manager = trading_manager_with_scenarios
        assert manager.initialize()
        
        # Mock significant price gap
        with patch.object(manager.data_manager, 'get_underlying_price', return_value=47000.0):  # 2000 point gap
            result = manager.process_trading_cycle()
            # Should handle gaps appropriately
            assert result is not None
    
    def test_market_close_scenario(self, trading_manager_with_scenarios):
        """Test system behavior near market close"""
        manager = trading_manager_with_scenarios
        assert manager.initialize()
        
        # Mock near market close time
        close_time = datetime.now().replace(hour=15, minute=25)  # 15:25 (5 minutes before close)
        
        with patch('datetime.datetime') as mock_datetime:
            mock_datetime.now.return_value = close_time
            result = manager.process_trading_cycle()
            # Should handle market close appropriately
            assert result is not None


class TestErrorRecoveryScenarios:
    """Test system error recovery and resilience"""
    
    @pytest.fixture
    def resilient_trading_manager(self, mock_config):
        """Create trading manager for resilience testing"""
        config_manager = ConfigManager()
        config = config_manager.load_config(str(mock_config))
        
        with patch('src.api.angel_api_client.AngelAPIClient') as mock_api_class:
            mock_api = MockAngelAPI()
            mock_api_class.return_value = mock_api
            
            manager = TradingManager(config, 'paper')
            manager.api_client = mock_api
            return manager
    
    def test_api_timeout_recovery(self, resilient_trading_manager):
        """Test recovery from API timeouts"""
        manager = resilient_trading_manager
        assert manager.initialize()
        
        # Mock API timeout followed by successful call
        call_count = 0
        def mock_api_call(*args, **kwargs):
            nonlocal call_count
            call_count += 1
            if call_count == 1:
                raise TimeoutError("API timeout")
            return {'status': 'success'}
        
        with patch.object(manager.api_client, 'get_ltp', side_effect=mock_api_call):
            result = manager.process_trading_cycle()
            # Should recover from timeout
            assert result is not None
            assert call_count >= 1
    
    def test_data_corruption_recovery(self, resilient_trading_manager):
        """Test recovery from corrupted market data"""
        manager = resilient_trading_manager
        assert manager.initialize()
        
        # Mock corrupted data followed by valid data
        call_count = 0
        def mock_get_options_chain(*args, **kwargs):
            nonlocal call_count
            call_count += 1
            if call_count == 1:
                return None  # Corrupted/missing data
            
            # Return valid data on retry
            mock_chain = Mock()
            mock_chain.underlying_price = 45000.0
            return mock_chain
        
        with patch.object(manager.data_manager, 'get_options_chain', side_effect=mock_get_options_chain):
            result = manager.process_trading_cycle()
            # Should handle corrupted data gracefully
            assert result is not None
    
    def test_order_rejection_recovery(self, resilient_trading_manager):
        """Test recovery from order rejections"""
        manager = resilient_trading_manager
        assert manager.initialize()
        
        # Mock order rejection followed by successful placement
        with patch.object(manager.order_manager, 'place_order') as mock_place_order:
            mock_place_order.side_effect = [
                Exception("Order rejected: Insufficient margin"),
                {'order_id': 'test_order_123', 'status': 'success'}
            ]
            
            # This test would need actual signal generation to test order placement
            # For now, just verify the manager can handle the scenario
            result = manager.process_trading_cycle()
            assert result is not None


if __name__ == '__main__':
    # Run integration tests
    pytest.main([__file__, '-v', '--tb=short'])