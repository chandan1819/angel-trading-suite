"""
Integration tests for market data retrieval with mocked API responses.
"""

import pytest
from unittest.mock import Mock, patch, MagicMock
from datetime import datetime, timedelta
import threading
import time

from src.api.market_data import (
    MarketDataManager, DataCache, CacheEntry, OptionsChainData,
    HistoricalDataPoint, RealTimePriceData
)
from src.api.angel_api_client import AngelAPIClient


class TestDataCache:
    """Test cases for DataCache class."""
    
    def setup_method(self):
        """Set up test fixtures."""
        self.cache = DataCache()
    
    def test_cache_set_and_get(self):
        """Test basic cache set and get operations."""
        test_data = {"key": "value"}
        self.cache.set("test_key", test_data, ttl_seconds=60)
        
        retrieved_data = self.cache.get("test_key")
        assert retrieved_data == test_data
    
    def test_cache_expiry(self):
        """Test cache entry expiry."""
        test_data = {"key": "value"}
        self.cache.set("test_key", test_data, ttl_seconds=1)
        
        # Data should be available immediately
        assert self.cache.get("test_key") == test_data
        
        # Wait for expiry
        time.sleep(1.1)
        
        # Data should be expired and return None
        assert self.cache.get("test_key") is None
    
    def test_cache_invalidate(self):
        """Test cache invalidation."""
        test_data = {"key": "value"}
        self.cache.set("test_key", test_data)
        
        assert self.cache.get("test_key") == test_data
        
        self.cache.invalidate("test_key")
        assert self.cache.get("test_key") is None
    
    def test_cache_clear(self):
        """Test clearing all cache entries."""
        self.cache.set("key1", "value1")
        self.cache.set("key2", "value2")
        
        assert self.cache.get("key1") == "value1"
        assert self.cache.get("key2") == "value2"
        
        self.cache.clear()
        
        assert self.cache.get("key1") is None
        assert self.cache.get("key2") is None
    
    def test_cache_cleanup_expired(self):
        """Test cleanup of expired entries."""
        self.cache.set("key1", "value1", ttl_seconds=60)
        self.cache.set("key2", "value2", ttl_seconds=1)
        
        time.sleep(1.1)
        
        # Before cleanup, expired entry still exists in cache dict
        assert len(self.cache.cache) == 2
        
        self.cache.cleanup_expired()
        
        # After cleanup, only non-expired entry remains
        assert len(self.cache.cache) == 1
        assert self.cache.get("key1") == "value1"
        assert self.cache.get("key2") is None


class TestMarketDataManager:
    """Test cases for MarketDataManager class."""
    
    def setup_method(self):
        """Set up test fixtures."""
        self.mock_api_client = Mock(spec=AngelAPIClient)
        self.market_data_manager = MarketDataManager(self.mock_api_client)
    
    def test_extract_expiry_from_symbol(self):
        """Test expiry extraction from trading symbols."""
        test_cases = [
            ("BANKNIFTY01JAN25CE50000", "2025-01-01"),
            ("BANKNIFTY15FEB24PE45000", "2024-02-15"),
            ("BANKNIFTY30DEC23CE55000", "2023-12-30"),
            ("INVALID_SYMBOL", None)
        ]
        
        for symbol, expected_expiry in test_cases:
            result = self.market_data_manager._extract_expiry_from_symbol(symbol)
            assert result == expected_expiry
    
    def test_extract_strike_from_symbol(self):
        """Test strike extraction from trading symbols."""
        test_cases = [
            ("BANKNIFTY01JAN25CE50000", 50000.0),
            ("BANKNIFTY15FEB24PE45000", 45000.0),
            ("BANKNIFTY30DEC23CE55500", 55500.0),
            ("INVALID_SYMBOL", None)
        ]
        
        for symbol, expected_strike in test_cases:
            result = self.market_data_manager._extract_strike_from_symbol(symbol)
            assert result == expected_strike
    
    def test_find_atm_strike(self):
        """Test ATM strike identification."""
        strikes_data = [
            {'strike': 49000.0, 'call': {}, 'put': {}},
            {'strike': 49500.0, 'call': {}, 'put': {}},
            {'strike': 50000.0, 'call': {}, 'put': {}},
            {'strike': 50500.0, 'call': {}, 'put': {}},
            {'strike': 51000.0, 'call': {}, 'put': {}}
        ]
        
        # Test exact match
        atm_strike = self.market_data_manager._find_atm_strike(strikes_data, 50000.0)
        assert atm_strike == 50000.0
        
        # Test closest match (higher)
        atm_strike = self.market_data_manager._find_atm_strike(strikes_data, 50200.0)
        assert atm_strike == 50000.0  # Closer to 50000 than 50500
        
        # Test tie-breaker (choose lower strike)
        atm_strike = self.market_data_manager._find_atm_strike(strikes_data, 50250.0)
        assert atm_strike == 50000.0  # Exactly between 50000 and 50500, choose lower
    
    @patch('src.api.market_data.MarketDataManager._get_current_month_expiry')
    @patch('src.api.market_data.MarketDataManager._search_options_instruments')
    @patch('src.api.market_data.MarketDataManager._get_underlying_price')
    @patch('src.api.market_data.MarketDataManager._process_options_chain')
    def test_get_options_chain_success(self, mock_process_chain, mock_get_price,
                                     mock_search_instruments, mock_get_expiry):
        """Test successful options chain retrieval."""
        # Setup mocks
        mock_get_expiry.return_value = "2025-01-30"
        mock_search_instruments.return_value = [
            {'tradingsymbol': 'BANKNIFTY30JAN25CE50000', 'symboltoken': '12345', 'exchange': 'NFO'},
            {'tradingsymbol': 'BANKNIFTY30JAN25PE50000', 'symboltoken': '12346', 'exchange': 'NFO'}
        ]
        mock_get_price.return_value = 50000.0
        mock_process_chain.return_value = [
            {'strike': 50000.0, 'call': {'symbol': 'BANKNIFTY30JAN25CE50000'}, 'put': {'symbol': 'BANKNIFTY30JAN25PE50000'}}
        ]
        
        # Test
        result = self.market_data_manager.get_options_chain("BANKNIFTY", use_cache=False)
        
        # Assertions
        assert result is not None
        assert isinstance(result, OptionsChainData)
        assert result.underlying_symbol == "BANKNIFTY"
        assert result.underlying_price == 50000.0
        assert result.expiry_date == "2025-01-30"
        assert len(result.strikes) == 1
        assert result.atm_strike == 50000.0
    
    @patch('src.api.market_data.MarketDataManager._get_current_month_expiry')
    def test_get_options_chain_no_expiry(self, mock_get_expiry):
        """Test options chain retrieval when expiry cannot be determined."""
        mock_get_expiry.return_value = None
        
        result = self.market_data_manager.get_options_chain("BANKNIFTY", use_cache=False)
        
        assert result is None
    
    def test_get_options_chain_with_cache(self):
        """Test options chain retrieval with caching."""
        # Create mock cached data
        cached_data = OptionsChainData(
            underlying_symbol="BANKNIFTY",
            underlying_price=50000.0,
            expiry_date="2025-01-30",
            strikes=[],
            timestamp=datetime.now()
        )
        
        # Set cache
        self.market_data_manager.cache.set("options_chain_BANKNIFTY_current", cached_data)
        
        # Test
        result = self.market_data_manager.get_options_chain("BANKNIFTY", use_cache=True)
        
        # Should return cached data without calling API
        assert result == cached_data
        self.mock_api_client.search_instruments.assert_not_called()
    
    def test_get_historical_data_success(self):
        """Test successful historical data retrieval."""
        # Setup mock API response
        mock_raw_data = [
            ['2025-01-01T09:15:00', '50000', '50100', '49900', '50050', '1000'],
            ['2025-01-01T09:16:00', '50050', '50150', '49950', '50100', '1100']
        ]
        self.mock_api_client.get_historical_data.return_value = mock_raw_data
        
        # Test
        result = self.market_data_manager.get_historical_data(
            symbol="BANKNIFTY",
            token="12345",
            exchange="NSE",
            use_cache=False
        )
        
        # Assertions
        assert len(result) == 2
        assert all(isinstance(point, HistoricalDataPoint) for point in result)
        assert result[0].open == 50000.0
        assert result[0].high == 50100.0
        assert result[0].low == 49900.0
        assert result[0].close == 50050.0
        assert result[0].volume == 1000
    
    def test_get_historical_data_with_cache(self):
        """Test historical data retrieval with caching."""
        # Create mock cached data
        cached_data = [
            HistoricalDataPoint(
                timestamp=datetime.now(),
                open=50000.0,
                high=50100.0,
                low=49900.0,
                close=50050.0,
                volume=1000
            )
        ]
        
        # Set cache
        cache_key = "historical_BANKNIFTY_ONE_DAY_2024-12-01_2025-01-01"
        self.market_data_manager.cache.set(cache_key, cached_data)
        
        # Test
        result = self.market_data_manager.get_historical_data(
            symbol="BANKNIFTY",
            token="12345",
            exchange="NSE",
            from_date="2024-12-01",
            to_date="2025-01-01",
            use_cache=True
        )
        
        # Should return cached data without calling API
        assert result == cached_data
        self.mock_api_client.get_historical_data.assert_not_called()
    
    def test_real_time_monitoring_start_stop(self):
        """Test starting and stopping real-time monitoring."""
        symbols = [
            {'exchange': 'NSE', 'symbol': 'BANKNIFTY', 'token': '12345'}
        ]
        
        callback = Mock()
        
        # Start monitoring
        self.market_data_manager.start_real_time_monitoring(symbols, callback, interval_seconds=1)
        
        assert self.market_data_manager.monitoring_active is True
        assert len(self.market_data_manager.price_monitors) == 1
        assert self.market_data_manager.monitor_thread is not None
        
        # Let it run briefly
        time.sleep(0.1)
        
        # Stop monitoring
        self.market_data_manager.stop_real_time_monitoring()
        
        assert self.market_data_manager.monitoring_active is False
        assert len(self.market_data_manager.price_monitors) == 0
    
    def test_real_time_monitoring_callback(self):
        """Test real-time monitoring callback execution."""
        symbols = [
            {'exchange': 'NSE', 'symbol': 'BANKNIFTY', 'token': '12345'}
        ]
        
        # Setup mock API to return price
        self.mock_api_client.get_ltp.return_value = 50000.0
        
        callback = Mock()
        
        # Start monitoring with short interval
        self.market_data_manager.start_real_time_monitoring(symbols, callback, interval_seconds=0.1)
        
        # Wait for at least one callback
        time.sleep(0.2)
        
        # Stop monitoring
        self.market_data_manager.stop_real_time_monitoring()
        
        # Verify callback was called
        assert callback.call_count >= 1
        
        # Verify callback received RealTimePriceData
        call_args = callback.call_args[0][0]
        assert isinstance(call_args, RealTimePriceData)
        assert call_args.symbol == 'BANKNIFTY'
        assert call_args.ltp == 50000.0
    
    def test_cache_info_and_cleanup(self):
        """Test cache information and cleanup functionality."""
        # Add some test data to cache
        self.market_data_manager.cache.set("test_key1", "data1", ttl_seconds=60)
        self.market_data_manager.cache.set("test_key2", "data2", ttl_seconds=1)
        
        # Get cache info
        cache_info = self.market_data_manager.get_cached_data_info()
        
        assert cache_info['total_entries'] == 2
        assert 'test_key1' in cache_info['entries']
        assert 'test_key2' in cache_info['entries']
        
        # Wait for one entry to expire
        time.sleep(1.1)
        
        # Cleanup cache
        self.market_data_manager.cleanup_cache()
        
        # Verify expired entry was removed
        cache_info_after = self.market_data_manager.get_cached_data_info()
        assert cache_info_after['total_entries'] == 1
        assert 'test_key1' in cache_info_after['entries']
        assert 'test_key2' not in cache_info_after['entries']
    
    def test_invalidate_cache_pattern(self):
        """Test cache invalidation with pattern matching."""
        # Add test data
        self.market_data_manager.cache.set("options_chain_BANKNIFTY_current", "data1")
        self.market_data_manager.cache.set("options_chain_NIFTY_current", "data2")
        self.market_data_manager.cache.set("historical_BANKNIFTY_data", "data3")
        
        # Invalidate options chain entries
        self.market_data_manager.invalidate_cache("options_chain")
        
        # Verify only matching entries were removed
        cache_info = self.market_data_manager.get_cached_data_info()
        assert cache_info['total_entries'] == 1
        assert 'historical_BANKNIFTY_data' in cache_info['entries']
    
    def test_process_options_chain(self):
        """Test options chain processing."""
        # Mock instruments data
        mock_instruments = [
            {
                'tradingsymbol': 'BANKNIFTY30JAN25CE50000',
                'symboltoken': '12345',
                'exchange': 'NFO'
            },
            {
                'tradingsymbol': 'BANKNIFTY30JAN25PE50000',
                'symboltoken': '12346',
                'exchange': 'NFO'
            },
            {
                'tradingsymbol': 'BANKNIFTY30JAN25CE50500',
                'symboltoken': '12347',
                'exchange': 'NFO'
            }
        ]
        
        # Mock LTP responses
        self.mock_api_client.get_ltp.side_effect = [100.0, 95.0, 80.0]
        
        # Test
        result = self.market_data_manager._process_options_chain(mock_instruments, 50000.0)
        
        # Assertions
        assert len(result) == 2  # Two different strikes
        
        # Find 50000 strike
        strike_50000 = next((s for s in result if s['strike'] == 50000.0), None)
        assert strike_50000 is not None
        assert strike_50000['call'] is not None
        assert strike_50000['put'] is not None
        assert strike_50000['call']['ltp'] == 100.0
        assert strike_50000['put']['ltp'] == 95.0
        
        # Find 50500 strike
        strike_50500 = next((s for s in result if s['strike'] == 50500.0), None)
        assert strike_50500 is not None
        assert strike_50500['call'] is not None
        assert strike_50500['put'] is None  # No put option for this strike in test data


if __name__ == "__main__":
    pytest.main([__file__])