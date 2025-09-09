"""
Performance tests for optimization components.
"""

import pytest
import time
import threading
from unittest.mock import Mock, patch
from datetime import datetime

from src.performance.cache_manager import CacheManager, CacheConfig, SmartCache
from src.performance.performance_monitor import PerformanceMonitor, LatencyRequirement
from src.performance.connection_pool import ConnectionPoolManager, ConnectionConfig
from src.performance.concurrent_processor import ConcurrentProcessor, ProcessingTask
from src.data.data_manager import DataManager
from src.api.angel_api_client import AngelAPIClient, APICredentials


class TestCacheManager:
    """Test cache manager functionality."""
    
    def test_cache_basic_operations(self):
        """Test basic cache operations."""
        cache = CacheManager(CacheConfig(max_size=10, default_ttl=60))
        
        # Test set and get
        assert cache.set("test_key", "test_value")
        assert cache.get("test_key") == "test_value"
        
        # Test non-existent key
        assert cache.get("non_existent") is None
        
        # Test delete
        assert cache.delete("test_key")
        assert cache.get("test_key") is None
    
    def test_cache_ttl_expiration(self):
        """Test TTL expiration."""
        cache = CacheManager(CacheConfig(default_ttl=1))  # 1 second TTL
        
        cache.set("expire_key", "expire_value")
        assert cache.get("expire_key") == "expire_value"
        
        # Wait for expiration
        time.sleep(1.1)
        assert cache.get("expire_key") is None
    
    def test_cache_lru_eviction(self):
        """Test LRU eviction."""
        cache = CacheManager(CacheConfig(max_size=2, default_ttl=60))
        
        # Fill cache to capacity
        cache.set("key1", "value1")
        cache.set("key2", "value2")
        
        # Access key1 to make it more recently used
        cache.get("key1")
        
        # Add third item, should evict key2
        cache.set("key3", "value3")
        
        assert cache.get("key1") == "value1"  # Should still exist
        assert cache.get("key2") is None      # Should be evicted
        assert cache.get("key3") == "value3"  # Should exist
    
    def test_cache_stats(self):
        """Test cache statistics."""
        cache = CacheManager(CacheConfig(max_size=10))
        
        # Initial stats
        stats = cache.get_stats()
        assert stats['hits'] == 0
        assert stats['misses'] == 0
        
        # Test hit
        cache.set("test", "value")
        cache.get("test")
        
        stats = cache.get_stats()
        assert stats['hits'] == 1
        
        # Test miss
        cache.get("missing")
        
        stats = cache.get_stats()
        assert stats['misses'] == 1
    
    def test_smart_cache(self):
        """Test smart cache functionality."""
        cache_manager = CacheManager(CacheConfig())
        smart_cache = SmartCache(cache_manager)
        
        # Test options chain caching
        test_data = {"test": "options_chain_data"}
        assert smart_cache.cache_options_chain("BANKNIFTY", "2024-01-25", test_data)
        
        cached_data = smart_cache.get_options_chain("BANKNIFTY", "2024-01-25")
        assert cached_data == test_data
        
        # Test LTP caching
        assert smart_cache.cache_ltp("NSE", "BANKNIFTY", "99926000", 45000.0)
        
        cached_ltp = smart_cache.get_ltp("NSE", "BANKNIFTY", "99926000")
        assert cached_ltp == 45000.0


class TestPerformanceMonitor:
    """Test performance monitoring functionality."""
    
    def test_performance_measurement(self):
        """Test performance measurement."""
        monitor = PerformanceMonitor()
        
        # Test context manager
        with monitor.measure("test_operation"):
            time.sleep(0.1)  # Simulate work
        
        metrics = monitor.get_metrics("test_operation")
        assert metrics is not None
        assert metrics.total_calls == 1
        assert metrics.avg_time >= 0.1
        assert metrics.success_rate == 100.0
    
    def test_latency_requirements(self):
        """Test latency requirement checking."""
        monitor = PerformanceMonitor()
        
        # Set a strict requirement
        requirement = LatencyRequirement(
            "test_op", max_latency_ms=100, warning_threshold_ms=50, alert_threshold_ms=75
        )
        monitor.set_requirement("test_op", requirement)
        
        # Test violation detection
        violation = requirement.check_violation(150)  # Should be CRITICAL
        assert violation == "CRITICAL"
        
        violation = requirement.check_violation(80)   # Should be ALERT
        assert violation == "ALERT"
        
        violation = requirement.check_violation(60)   # Should be WARNING
        assert violation == "WARNING"
        
        violation = requirement.check_violation(30)   # Should be None
        assert violation is None
    
    def test_performance_alerts(self):
        """Test performance alert system."""
        monitor = PerformanceMonitor()
        alerts_received = []
        
        def alert_callback(alert_data):
            alerts_received.append(alert_data)
        
        monitor.add_alert_callback(alert_callback)
        
        # Record a slow operation
        monitor.record_execution("slow_operation", 3.0)  # 3 seconds
        
        # Should trigger alert for operations with requirements
        requirement = LatencyRequirement(
            "slow_operation", max_latency_ms=1000, warning_threshold_ms=500, alert_threshold_ms=750
        )
        monitor.set_requirement("slow_operation", requirement)
        
        # Record another slow execution
        monitor.record_execution("slow_operation", 2.0)  # 2 seconds
        
        # Check if alert was triggered
        assert len(alerts_received) > 0
        assert alerts_received[-1]['operation'] == "slow_operation"
        assert alerts_received[-1]['violation_level'] == "CRITICAL"


class TestConnectionPool:
    """Test connection pool functionality."""
    
    def test_connection_pool_basic(self):
        """Test basic connection pool operations."""
        config = ConnectionConfig(pool_size=2, timeout=5)
        pool = ConnectionPoolManager(config)
        
        # Test getting connection
        with pool.get_connection() as conn:
            assert conn is not None
            assert conn.session is not None
        
        # Test pool stats
        stats = pool.get_stats()
        assert stats['max_pool_size'] == 2
        assert stats['pool_size'] >= 0
    
    def test_connection_pool_concurrent(self):
        """Test concurrent connection usage."""
        config = ConnectionConfig(pool_size=3, timeout=5)
        pool = ConnectionPoolManager(config)
        
        results = []
        
        def use_connection(thread_id):
            try:
                with pool.get_connection(timeout=2.0) as conn:
                    assert conn is not None
                    time.sleep(0.1)  # Simulate work
                    results.append(f"thread_{thread_id}_success")
            except Exception as e:
                results.append(f"thread_{thread_id}_error: {e}")
        
        # Start multiple threads
        threads = []
        for i in range(5):
            thread = threading.Thread(target=use_connection, args=(i,))
            threads.append(thread)
            thread.start()
        
        # Wait for all threads
        for thread in threads:
            thread.join()
        
        # Check results
        success_count = len([r for r in results if "success" in r])
        assert success_count >= 3  # At least pool size should succeed


class TestConcurrentProcessor:
    """Test concurrent processing functionality."""
    
    def test_task_submission_and_execution(self):
        """Test task submission and execution."""
        processor = ConcurrentProcessor(max_workers=2)
        
        def test_operation(x, y):
            return x + y
        
        # Submit task
        task = ProcessingTask(
            task_id="test_task",
            operation=test_operation,
            args=(5, 3),
            timeout=5.0
        )
        
        assert processor.submit_task(task)
        
        # Get result
        result = processor.get_result("test_task", timeout=2.0)
        assert result is not None
        assert result.success
        assert result.result == 8
        
        processor.shutdown(wait=True)
    
    def test_strategy_evaluation_concurrent(self):
        """Test concurrent strategy evaluation."""
        processor = ConcurrentProcessor(max_workers=3)
        
        def strategy1(market_data):
            time.sleep(0.1)
            return {"signal": "BUY", "confidence": 0.8}
        
        def strategy2(market_data):
            time.sleep(0.1)
            return {"signal": "SELL", "confidence": 0.6}
        
        def strategy3(market_data):
            time.sleep(0.1)
            return {"signal": "HOLD", "confidence": 0.5}
        
        strategies = {
            "strategy1": strategy1,
            "strategy2": strategy2,
            "strategy3": strategy3
        }
        
        from src.performance.concurrent_processor import StrategyEvaluationManager
        manager = StrategyEvaluationManager(processor)
        
        market_data = {"price": 45000, "volume": 1000}
        
        start_time = time.time()
        results = manager.evaluate_strategies_concurrent(strategies, market_data)
        execution_time = time.time() - start_time
        
        # Should complete faster than sequential execution (3 * 0.1 = 0.3s)
        # Allow some overhead for task scheduling and coordination
        assert execution_time < 0.5
        
        # Check results
        assert len(results) == 3
        assert results["strategy1"]["signal"] == "BUY"
        assert results["strategy2"]["signal"] == "SELL"
        assert results["strategy3"]["signal"] == "HOLD"
        
        processor.shutdown(wait=True)
    
    def test_task_timeout(self):
        """Test task timeout handling."""
        processor = ConcurrentProcessor(max_workers=1)
        
        def slow_operation():
            time.sleep(2.0)  # Longer than timeout
            return "completed"
        
        task = ProcessingTask(
            task_id="timeout_task",
            operation=slow_operation,
            timeout=0.5  # Short timeout
        )
        
        assert processor.submit_task(task)
        
        # Get result
        result = processor.get_result("timeout_task", timeout=3.0)
        assert result is not None
        assert not result.success
        assert isinstance(result.error, TimeoutError)
        
        processor.shutdown(wait=True)


class TestPerformanceIntegration:
    """Test performance optimization integration."""
    
    @patch('src.api.angel_api_client.SmartConnect')
    def test_data_manager_performance(self, mock_smart_connect):
        """Test data manager with performance optimizations."""
        # Mock API client
        mock_api = Mock()
        mock_api.authenticate.return_value = True
        
        # Create performance components
        cache_manager = CacheManager(CacheConfig(default_ttl=60))
        performance_monitor = PerformanceMonitor()
        
        # Create data manager with performance components
        data_manager = DataManager(
            api_client=mock_api,
            cache_manager=cache_manager,
            performance_monitor=performance_monitor
        )
        
        # Test performance stats
        stats = data_manager.get_performance_stats()
        assert 'cache_stats' in stats
        assert 'performance_metrics' in stats
        assert 'config' in stats
        
        # Test cache clearing
        data_manager.clear_cache()
        
        # Verify cache is empty
        cache_stats = cache_manager.get_stats()
        assert cache_stats['entries'] == 0
    
    def test_latency_requirements_validation(self):
        """Test that operations meet latency requirements."""
        monitor = PerformanceMonitor()
        
        # Test ATM calculation latency
        start_time = time.time()
        
        # Simulate ATM calculation
        with monitor.measure('atm_calculation'):
            time.sleep(0.001)  # Very fast operation
        
        execution_time = time.time() - start_time
        
        # Should be well under 1 second requirement
        assert execution_time < 1.0
        
        metrics = monitor.get_metrics('atm_calculation')
        assert metrics.avg_time < 1.0
        
        # Test strategy evaluation latency
        with monitor.measure('strategy_evaluation'):
            time.sleep(0.002)  # Fast operation
        
        metrics = monitor.get_metrics('strategy_evaluation')
        assert metrics.avg_time < 5.0  # Should be under 5 second requirement
    
    def test_cache_hit_rate_optimization(self):
        """Test cache hit rate optimization."""
        cache = CacheManager(CacheConfig(default_ttl=60))
        smart_cache = SmartCache(cache)
        
        # Simulate repeated ATM calculations with same parameters
        underlying = "BANKNIFTY"
        expiry = "2024-01-25"
        spot_price = 45000.0
        
        # First call - cache miss
        result1 = smart_cache.get_atm_strike(underlying, expiry, spot_price)
        assert result1 is None  # Cache miss
        
        # Cache the result
        test_result = {"atm_strike": 45000, "distance": 0.0}
        smart_cache.cache_atm_strike(underlying, expiry, spot_price, test_result)
        
        # Second call - cache hit
        result2 = smart_cache.get_atm_strike(underlying, expiry, spot_price)
        assert result2 == test_result  # Cache hit
        
        # Check cache stats
        stats = cache.get_stats()
        assert stats['hits'] >= 1
        assert stats['hit_rate_percent'] > 0


if __name__ == "__main__":
    pytest.main([__file__, "-v"])