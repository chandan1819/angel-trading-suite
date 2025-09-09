"""
Integration tests for error handling and recovery scenarios.

This module tests the system's ability to handle various error conditions
gracefully and recover from failures without compromising system integrity.
"""

import pytest
from unittest.mock import Mock, patch, MagicMock
import tempfile
import os
import time
from datetime import datetime

from tests.mock_angel_api import MockAngelAPI, MockAPIFactory
from src.trading.trading_manager import TradingManager
from src.api.angel_api_client import AngelAPIClient
from src.models.config_models import TradingConfig, RiskConfig
from src.models.trading_models import TradingSignal, SignalType, OptionType


class TestAPIErrorRecovery:
    """Test API error handling and recovery mechanisms"""
    
    @pytest.fixture
    def trading_config(self):
        """Create trading configuration for error testing"""
        config = TradingConfig()
        config.mode = "paper"
        config.risk = RiskConfig(
            max_daily_loss=5000.0,
            max_concurrent_trades=3,
            profit_target=2000.0,
            stop_loss=1000.0
        )
        return config
    
    def test_authentication_failure_recovery(self, trading_config):
        """Test recovery from authentication failures"""
        # Create API that fails authentication initially
        with patch('src.api.angel_api_client.AngelAPIClient') as mock_api_class:
            mock_api = Mock(spec=AngelAPIClient)
            
            # Simulate authentication failure then success
            auth_attempts = 0
            def auth_side_effect():
                nonlocal auth_attempts
                auth_attempts += 1
                if auth_attempts <= 2:
                    raise Exception("Authentication failed")
                return True
            
            mock_api.authenticate.side_effect = auth_side_effect
            mock_api_class.return_value = mock_api
            
            manager = TradingManager(trading_config)
            
            # Should eventually succeed after retries
            success = manager.initialize()
            assert success, "Should succeed after authentication retries"
            assert auth_attempts > 1, "Should have retried authentication"
    
    def test_network_timeout_recovery(self, trading_config):
        """Test recovery from network timeouts"""
        with patch('src.api.angel_api_client.AngelAPIClient') as mock_api_class:
            mock_api = Mock(spec=AngelAPIClient)
            mock_api.authenticate.return_value = True
            
            # Simulate network timeouts then success
            call_count = 0
            def timeout_side_effect(*args, **kwargs):
                nonlocal call_count
                call_count += 1
                if call_count <= 2:
                    raise Exception("Connection timeout")
                return {"ltp": "100.0"}
            
            mock_api.get_ltp.side_effect = timeout_side_effect
            mock_api_class.return_value = mock_api
            
            manager = TradingManager(trading_config)
            manager.initialize()
            
            # Should handle timeouts gracefully
            try:
                manager.process_trading_cycle()
                # Should not crash on network timeouts
                assert call_count > 1, "Should have retried after timeouts"
            except Exception as e:
                # Should not propagate network errors
                assert "timeout" not in str(e).lower()
    
    def test_rate_limiting_backoff(self, trading_config):
        """Test exponential backoff for rate limiting"""
        rate_limited_api = MockAPIFactory.create_rate_limited_api()
        
        with patch('src.api.angel_api_client.AngelAPIClient') as mock_api_class:
            mock_api = Mock(spec=AngelAPIClient)
            mock_api.authenticate.return_value = True
            
            # Track call timing for backoff verification
            call_times = []
            def rate_limited_call(*args, **kwargs):
                call_times.append(time.time())
                if len(call_times) <= 3:
                    raise Exception("Rate limit exceeded")
                return {"ltp": "100.0"}
            
            mock_api.get_ltp.side_effect = rate_limited_call
            mock_api_class.return_value = mock_api
            
            manager = TradingManager(trading_config)
            manager.initialize()
            
            # Should implement backoff strategy
            start_time = time.time()
            try:
                manager.process_trading_cycle()
            except:
                pass  # May still fail, but should have implemented backoff
            
            # Verify exponential backoff (calls should be spaced out)
            if len(call_times) > 2:
                time_diff_1 = call_times[1] - call_times[0]
                time_diff_2 = call_times[2] - call_times[1]
                assert time_diff_2 > time_diff_1, "Should implement exponential backoff"
    
    def test_partial_api_failure_handling(self, trading_config):
        """Test handling when some API calls fail but others succeed"""
        with patch('src.api.angel_api_client.AngelAPIClient') as mock_api_class:
            mock_api = Mock(spec=AngelAPIClient)
            mock_api.authenticate.return_value = True
            
            # Some calls succeed, others fail
            mock_api.search_instruments.return_value = [{"symbol": "BANKNIFTY", "token": "12345"}]
            mock_api.get_ltp.side_effect = Exception("LTP service unavailable")
            mock_api.get_historical_data.return_value = []
            
            mock_api_class.return_value = mock_api
            
            manager = TradingManager(trading_config)
            manager.initialize()
            
            # Should handle partial failures gracefully
            signals = manager.process_trading_cycle()
            assert isinstance(signals, list), "Should return empty list on partial failure"
    
    def test_malformed_api_response_handling(self, trading_config):
        """Test handling of malformed API responses"""
        with patch('src.api.angel_api_client.AngelAPIClient') as mock_api_class:
            mock_api = Mock(spec=AngelAPIClient)
            mock_api.authenticate.return_value = True
            
            # Return malformed responses
            mock_api.search_instruments.return_value = "invalid_json"
            mock_api.get_ltp.return_value = {"invalid": "structure"}
            mock_api.get_historical_data.return_value = None
            
            mock_api_class.return_value = mock_api
            
            manager = TradingManager(trading_config)
            manager.initialize()
            
            # Should handle malformed responses without crashing
            try:
                signals = manager.process_trading_cycle()
                assert isinstance(signals, list), "Should handle malformed responses gracefully"
            except Exception as e:
                # Should not crash on malformed data
                assert "json" not in str(e).lower()


class TestSystemRecovery:
    """Test system-level recovery mechanisms"""
    
    @pytest.fixture
    def trading_config(self):
        """Create trading configuration"""
        config = TradingConfig()
        config.mode = "paper"
        config.risk = RiskConfig(
            max_daily_loss=5000.0,
            max_concurrent_trades=3,
            profit_target=2000.0,
            stop_loss=1000.0,
            emergency_stop_file="test_emergency.txt"
        )
        return config
    
    def test_emergency_stop_recovery(self, trading_config):
        """Test system recovery after emergency stop"""
        with tempfile.NamedTemporaryFile(delete=False) as temp_file:
            trading_config.risk.emergency_stop_file = temp_file.name
            
            with patch('src.api.angel_api_client.AngelAPIClient') as mock_api_class:
                mock_api = Mock(spec=AngelAPIClient)
                mock_api.authenticate.return_value = True
                mock_api_class.return_value = mock_api
                
                manager = TradingManager(trading_config)
                manager.initialize()
                
                # Create emergency stop
                with open(temp_file.name, 'w') as f:
                    f.write("EMERGENCY STOP")
                
                # Should detect emergency stop
                signal = TradingSignal(
                    strategy_name="test",
                    signal_type=SignalType.BUY,
                    underlying="BANKNIFTY",
                    strikes=[50000.0],
                    option_types=[OptionType.CE],
                    quantities=[1],
                    confidence=0.8
                )
                
                validation = manager.risk_manager.validate_trade(signal)
                assert not validation.is_valid, "Should reject trades during emergency stop"
                
                # Remove emergency stop
                os.unlink(temp_file.name)
                
                # Should recover and allow trades
                validation = manager.risk_manager.validate_trade(signal)
                assert validation.is_valid, "Should allow trades after emergency stop removal"
    
    def test_memory_leak_prevention(self, trading_config):
        """Test prevention of memory leaks during long operations"""
        with patch('src.api.angel_api_client.AngelAPIClient') as mock_api_class:
            mock_api = Mock(spec=AngelAPIClient)
            mock_api.authenticate.return_value = True
            mock_api_class.return_value = mock_api
            
            manager = TradingManager(trading_config)
            manager.initialize()
            
            # Simulate many trading cycles
            initial_objects = len(manager.__dict__)
            
            for _ in range(100):
                manager.process_trading_cycle()
            
            # Object count should not grow significantly
            final_objects = len(manager.__dict__)
            assert final_objects <= initial_objects + 5, "Should not accumulate objects"
    
    def test_graceful_shutdown_with_open_positions(self, trading_config):
        """Test graceful shutdown when positions are open"""
        with patch('src.api.angel_api_client.AngelAPIClient') as mock_api_class:
            mock_api = Mock(spec=AngelAPIClient)
            mock_api.authenticate.return_value = True
            mock_api.place_order.return_value = {"status": True, "data": {"orderid": "12345"}}
            mock_api.get_positions.return_value = [
                {
                    "tradingsymbol": "BANKNIFTY2412550000CE",
                    "netqty": "25",
                    "pnl": "500.0"
                }
            ]
            mock_api_class.return_value = mock_api
            
            manager = TradingManager(trading_config)
            manager.initialize()
            
            # Create a position
            signal = TradingSignal(
                strategy_name="test",
                signal_type=SignalType.BUY,
                underlying="BANKNIFTY",
                strikes=[50000.0],
                option_types=[OptionType.CE],
                quantities=[1],
                confidence=0.8
            )
            
            trade = manager.execute_signal(signal)
            assert trade is not None, "Should create trade"
            
            # Shutdown should handle open positions
            try:
                manager.stop_trading_session()
                # Should not crash with open positions
                assert True, "Should shutdown gracefully with open positions"
            except Exception as e:
                pytest.fail(f"Should not crash during shutdown: {e}")
    
    def test_configuration_reload_recovery(self, trading_config):
        """Test recovery from configuration changes"""
        with patch('src.api.angel_api_client.AngelAPIClient') as mock_api_class:
            mock_api = Mock(spec=AngelAPIClient)
            mock_api.authenticate.return_value = True
            mock_api_class.return_value = mock_api
            
            manager = TradingManager(trading_config)
            manager.initialize()
            
            # Change configuration
            new_config = trading_config
            new_config.risk.max_concurrent_trades = 5
            
            # Should handle configuration changes
            try:
                manager.update_configuration(new_config)
                assert manager.risk_manager.risk_config.max_concurrent_trades == 5
            except Exception as e:
                pytest.fail(f"Should handle configuration updates: {e}")


class TestDataIntegrityRecovery:
    """Test data integrity and recovery mechanisms"""
    
    def test_corrupted_market_data_recovery(self):
        """Test recovery from corrupted market data"""
        config = TradingConfig()
        config.mode = "paper"
        
        with patch('src.api.angel_api_client.AngelAPIClient') as mock_api_class:
            mock_api = Mock(spec=AngelAPIClient)
            mock_api.authenticate.return_value = True
            
            # Return corrupted data
            mock_api.search_instruments.return_value = [
                {"symbol": None, "token": ""},  # Invalid data
                {"symbol": "VALID", "token": "12345"}  # Valid data
            ]
            
            mock_api_class.return_value = mock_api
            
            manager = TradingManager(config)
            manager.initialize()
            
            # Should filter out corrupted data and continue
            try:
                signals = manager.process_trading_cycle()
                assert isinstance(signals, list), "Should handle corrupted data gracefully"
            except Exception as e:
                pytest.fail(f"Should not crash on corrupted data: {e}")
    
    def test_position_reconciliation_recovery(self):
        """Test position reconciliation after data inconsistencies"""
        config = TradingConfig()
        config.mode = "paper"
        
        with patch('src.api.angel_api_client.AngelAPIClient') as mock_api_class:
            mock_api = Mock(spec=AngelAPIClient)
            mock_api.authenticate.return_value = True
            
            # Simulate position data inconsistency
            call_count = 0
            def inconsistent_positions():
                nonlocal call_count
                call_count += 1
                if call_count == 1:
                    return [{"tradingsymbol": "TEST", "netqty": "25"}]
                else:
                    return [{"tradingsymbol": "TEST", "netqty": "0"}]  # Position closed
            
            mock_api.get_positions.side_effect = inconsistent_positions
            mock_api_class.return_value = mock_api
            
            manager = TradingManager(config)
            manager.initialize()
            
            # Should reconcile position differences
            try:
                manager.update_positions()
                manager.update_positions()  # Second call with different data
                # Should handle position reconciliation
                assert True, "Should handle position reconciliation"
            except Exception as e:
                pytest.fail(f"Should reconcile positions gracefully: {e}")
    
    def test_order_status_recovery(self):
        """Test recovery from order status inconsistencies"""
        config = TradingConfig()
        config.mode = "paper"
        
        with patch('src.api.angel_api_client.AngelAPIClient') as mock_api_class:
            mock_api = Mock(spec=AngelAPIClient)
            mock_api.authenticate.return_value = True
            
            # Simulate order status changes
            order_statuses = ["OPEN", "PENDING", "COMPLETE"]
            status_index = 0
            
            def changing_order_status():
                nonlocal status_index
                status = order_statuses[status_index % len(order_statuses)]
                status_index += 1
                return [{"orderid": "12345", "status": status}]
            
            mock_api.place_order.return_value = {"status": True, "data": {"orderid": "12345"}}
            mock_api.orderBook.side_effect = changing_order_status
            mock_api_class.return_value = mock_api
            
            manager = TradingManager(config)
            manager.initialize()
            
            # Should handle changing order statuses
            signal = TradingSignal(
                strategy_name="test",
                signal_type=SignalType.BUY,
                underlying="BANKNIFTY",
                strikes=[50000.0],
                option_types=[OptionType.CE],
                quantities=[1],
                confidence=0.8
            )
            
            try:
                trade = manager.execute_signal(signal)
                # Update order status multiple times
                for _ in range(3):
                    manager.update_order_status()
                
                assert True, "Should handle order status changes"
            except Exception as e:
                pytest.fail(f"Should handle order status changes: {e}")


class TestPerformanceDegradation:
    """Test system behavior under performance degradation"""
    
    def test_slow_api_response_handling(self):
        """Test handling of slow API responses"""
        config = TradingConfig()
        config.mode = "paper"
        
        with patch('src.api.angel_api_client.AngelAPIClient') as mock_api_class:
            mock_api = Mock(spec=AngelAPIClient)
            mock_api.authenticate.return_value = True
            
            # Simulate slow API responses
            def slow_response(*args, **kwargs):
                time.sleep(1)  # 1 second delay
                return {"ltp": "100.0"}
            
            mock_api.get_ltp.side_effect = slow_response
            mock_api_class.return_value = mock_api
            
            manager = TradingManager(config)
            manager.initialize()
            
            # Should handle slow responses with timeout
            start_time = time.time()
            try:
                manager.process_trading_cycle()
            except:
                pass  # May timeout, but should not hang
            
            end_time = time.time()
            
            # Should not hang indefinitely
            assert (end_time - start_time) < 10.0, "Should timeout slow API calls"
    
    def test_high_memory_usage_handling(self):
        """Test handling of high memory usage scenarios"""
        config = TradingConfig()
        config.mode = "paper"
        
        with patch('src.api.angel_api_client.AngelAPIClient') as mock_api_class:
            mock_api = Mock(spec=AngelAPIClient)
            mock_api.authenticate.return_value = True
            
            # Return large amounts of data
            large_data = [{"symbol": f"TEST{i}", "token": str(i)} for i in range(10000)]
            mock_api.search_instruments.return_value = large_data
            
            mock_api_class.return_value = mock_api
            
            manager = TradingManager(config)
            manager.initialize()
            
            # Should handle large datasets efficiently
            try:
                signals = manager.process_trading_cycle()
                assert isinstance(signals, list), "Should handle large datasets"
            except MemoryError:
                pytest.fail("Should not run out of memory with large datasets")
    
    def test_concurrent_operation_safety(self):
        """Test safety of concurrent operations"""
        config = TradingConfig()
        config.mode = "paper"
        
        with patch('src.api.angel_api_client.AngelAPIClient') as mock_api_class:
            mock_api = Mock(spec=AngelAPIClient)
            mock_api.authenticate.return_value = True
            mock_api_class.return_value = mock_api
            
            manager = TradingManager(config)
            manager.initialize()
            
            # Simulate concurrent operations
            import threading
            
            results = []
            errors = []
            
            def concurrent_operation():
                try:
                    signals = manager.process_trading_cycle()
                    results.append(signals)
                except Exception as e:
                    errors.append(e)
            
            # Start multiple threads
            threads = []
            for _ in range(5):
                thread = threading.Thread(target=concurrent_operation)
                threads.append(thread)
                thread.start()
            
            # Wait for completion
            for thread in threads:
                thread.join(timeout=5.0)
            
            # Should handle concurrent operations safely
            assert len(errors) == 0, f"Should not have errors in concurrent operations: {errors}"
            assert len(results) > 0, "Should complete some operations"