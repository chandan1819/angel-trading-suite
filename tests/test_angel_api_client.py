"""
Integration tests for Angel API client with mocked API responses.
"""

import pytest
from unittest.mock import Mock, patch, MagicMock
from datetime import datetime, timedelta
import threading
import time

from src.api.angel_api_client import AngelAPIClient, APICredentials, ConnectionConfig, RateLimiter
from src.api.error_handler import APIError, ErrorCategory
import SmartApi.smartExceptions as ex


class TestRateLimiter:
    """Test cases for RateLimiter class."""
    
    def test_rate_limiter_basic(self):
        """Test basic rate limiting functionality."""
        rate_limiter = RateLimiter(max_calls_per_second=2.0)  # 2 calls per second
        
        start_time = time.time()
        
        # First call should be immediate
        rate_limiter.wait_if_needed()
        first_call_time = time.time()
        
        # Second call should be delayed
        rate_limiter.wait_if_needed()
        second_call_time = time.time()
        
        # Should have waited at least 0.5 seconds (1/2 calls per second)
        time_diff = second_call_time - first_call_time
        assert time_diff >= 0.4  # Allow some tolerance
    
    def test_rate_limiter_thread_safety(self):
        """Test rate limiter thread safety."""
        rate_limiter = RateLimiter(max_calls_per_second=5.0)
        call_times = []
        
        def make_call():
            rate_limiter.wait_if_needed()
            call_times.append(time.time())
        
        # Create multiple threads
        threads = []
        for _ in range(5):
            thread = threading.Thread(target=make_call)
            threads.append(thread)
        
        # Start all threads
        start_time = time.time()
        for thread in threads:
            thread.start()
        
        # Wait for all threads to complete
        for thread in threads:
            thread.join()
        
        # Verify calls were rate limited
        assert len(call_times) == 5
        call_times.sort()
        
        # Each call should be at least 0.2 seconds apart (1/5 calls per second)
        for i in range(1, len(call_times)):
            time_diff = call_times[i] - call_times[i-1]
            assert time_diff >= 0.15  # Allow some tolerance


class TestAngelAPIClient:
    """Test cases for AngelAPIClient class."""
    
    def setup_method(self):
        """Set up test fixtures."""
        self.credentials = APICredentials(
            api_key="test_api_key",
            client_code="test_client",
            pin="1234",
            totp_secret="test_totp_secret"
        )
        self.config = ConnectionConfig(
            timeout=5,
            max_retries=2,
            rate_limit_per_second=10.0
        )
    
    @patch('src.api.angel_api_client.SmartConnect')
    def test_initialization_success(self, mock_smart_connect):
        """Test successful API client initialization."""
        mock_smart_api = Mock()
        mock_smart_connect.return_value = mock_smart_api
        
        client = AngelAPIClient(self.credentials, self.config)
        
        assert client.credentials == self.credentials
        assert client.config == self.config
        assert client.smart_api == mock_smart_api
        assert client.access_token is None
        assert client.refresh_token is None
    
    @patch('src.api.angel_api_client.SmartConnect')
    def test_initialization_failure(self, mock_smart_connect):
        """Test API client initialization failure."""
        mock_smart_connect.side_effect = Exception("Connection failed")
        
        with pytest.raises(APIError) as exc_info:
            AngelAPIClient(self.credentials, self.config)
        
        assert exc_info.value.category == ErrorCategory.SYSTEM_ERROR
    
    @patch('src.api.angel_api_client.SmartConnect')
    @patch('src.api.angel_api_client.AngelAPIClient._generate_totp')
    def test_authentication_success(self, mock_generate_totp, mock_smart_connect):
        """Test successful authentication."""
        # Setup mocks
        mock_smart_api = Mock()
        mock_smart_connect.return_value = mock_smart_api
        mock_generate_totp.return_value = "123456"
        
        mock_auth_response = {
            'status': True,
            'data': {
                'jwtToken': 'test_jwt_token',
                'refreshToken': 'test_refresh_token',
                'feedToken': 'test_feed_token',
                'clientcode': 'test_client'
            }
        }
        mock_smart_api.generateSession.return_value = mock_auth_response
        
        # Test
        client = AngelAPIClient(self.credentials, self.config)
        result = client.authenticate()
        
        # Assertions
        assert result is True
        assert client.access_token == 'test_jwt_token'
        assert client.refresh_token == 'test_refresh_token'
        assert client.feed_token == 'test_feed_token'
        assert client.user_id == 'test_client'
        assert client.last_auth_time is not None
        
        mock_smart_api.generateSession.assert_called_once_with(
            self.credentials.client_code,
            self.credentials.pin,
            "123456"
        )
    
    @patch('src.api.angel_api_client.SmartConnect')
    def test_authentication_failure(self, mock_smart_connect):
        """Test authentication failure."""
        mock_smart_api = Mock()
        mock_smart_connect.return_value = mock_smart_api
        
        mock_auth_response = {
            'status': False,
            'message': 'Invalid credentials'
        }
        mock_smart_api.generateSession.return_value = mock_auth_response
        
        client = AngelAPIClient(self.credentials, self.config)
        result = client.authenticate()
        
        assert result is False
        assert client.access_token is None
    
    @patch('src.api.angel_api_client.SmartConnect')
    def test_authentication_exception(self, mock_smart_connect):
        """Test authentication with exception."""
        mock_smart_api = Mock()
        mock_smart_connect.return_value = mock_smart_api
        mock_smart_api.generateSession.side_effect = ex.TokenException("Invalid token")
        
        client = AngelAPIClient(self.credentials, self.config)
        result = client.authenticate()
        
        assert result is False
    
    @patch('src.api.angel_api_client.SmartConnect')
    def test_reauthentication_success(self, mock_smart_connect):
        """Test successful re-authentication using refresh token."""
        mock_smart_api = Mock()
        mock_smart_connect.return_value = mock_smart_api
        
        # Setup initial state
        client = AngelAPIClient(self.credentials, self.config)
        client.refresh_token = 'test_refresh_token'
        
        mock_refresh_response = {
            'status': True,
            'data': {
                'jwtToken': 'new_jwt_token',
                'feedToken': 'new_feed_token'
            }
        }
        mock_smart_api.generateToken.return_value = mock_refresh_response
        
        # Test
        result = client._reauthenticate()
        
        # Assertions
        assert result is True
        assert client.access_token == 'new_jwt_token'
        assert client.feed_token == 'new_feed_token'
        
        mock_smart_api.generateToken.assert_called_once_with('test_refresh_token')
    
    @patch('src.api.angel_api_client.SmartConnect')
    def test_reauthentication_fallback_to_full_auth(self, mock_smart_connect):
        """Test re-authentication fallback to full authentication."""
        mock_smart_api = Mock()
        mock_smart_connect.return_value = mock_smart_api
        
        client = AngelAPIClient(self.credentials, self.config)
        client.refresh_token = None  # No refresh token
        
        # Mock full authentication
        mock_auth_response = {
            'status': True,
            'data': {
                'jwtToken': 'test_jwt_token',
                'refreshToken': 'test_refresh_token',
                'feedToken': 'test_feed_token',
                'clientcode': 'test_client'
            }
        }
        mock_smart_api.generateSession.return_value = mock_auth_response
        
        with patch.object(client, '_generate_totp', return_value='123456'):
            result = client._reauthenticate()
        
        assert result is True
        mock_smart_api.generateSession.assert_called_once()
    
    @patch('src.api.angel_api_client.SmartConnect')
    def test_ensure_authenticated_token_refresh(self, mock_smart_connect):
        """Test automatic token refresh when token is expired."""
        mock_smart_api = Mock()
        mock_smart_connect.return_value = mock_smart_api
        
        client = AngelAPIClient(self.credentials, self.config)
        client.access_token = 'old_token'
        client.refresh_token = 'refresh_token'
        client.last_auth_time = datetime.now() - timedelta(hours=6)  # Expired
        
        # Mock token refresh
        mock_refresh_response = {
            'status': True,
            'data': {
                'jwtToken': 'new_jwt_token',
                'feedToken': 'new_feed_token'
            }
        }
        mock_smart_api.generateToken.return_value = mock_refresh_response
        
        # Test
        result = client._ensure_authenticated()
        
        # Assertions
        assert result is True
        assert client.access_token == 'new_jwt_token'
        mock_smart_api.generateToken.assert_called_once()
    
    @patch('src.api.angel_api_client.SmartConnect')
    def test_execute_api_call_success(self, mock_smart_connect):
        """Test successful API call execution."""
        mock_smart_api = Mock()
        mock_smart_connect.return_value = mock_smart_api
        
        client = AngelAPIClient(self.credentials, self.config)
        client.access_token = 'test_token'
        client.last_auth_time = datetime.now()
        
        # Mock operation
        mock_operation = Mock(return_value={'status': True, 'data': 'test_data'})
        
        # Test
        result = client._execute_api_call(mock_operation, "Test operation")
        
        # Assertions
        assert result == {'status': True, 'data': 'test_data'}
        mock_operation.assert_called_once()
    
    @patch('src.api.angel_api_client.SmartConnect')
    def test_execute_api_call_with_token_error_and_retry(self, mock_smart_connect):
        """Test API call with token error and automatic retry after re-auth."""
        mock_smart_api = Mock()
        mock_smart_connect.return_value = mock_smart_api
        
        client = AngelAPIClient(self.credentials, self.config)
        client.access_token = 'test_token'
        client.refresh_token = 'refresh_token'
        client.last_auth_time = datetime.now()
        
        # Mock operation that fails first time with token error, then succeeds
        mock_operation = Mock()
        mock_operation.side_effect = [
            ex.TokenException("Token expired"),
            {'status': True, 'data': 'success_after_reauth'}
        ]
        
        # Mock token refresh
        mock_refresh_response = {
            'status': True,
            'data': {
                'jwtToken': 'new_jwt_token',
                'feedToken': 'new_feed_token'
            }
        }
        mock_smart_api.generateToken.return_value = mock_refresh_response
        
        # Test
        result = client._execute_api_call(mock_operation, "Test operation")
        
        # Assertions
        assert result == {'status': True, 'data': 'success_after_reauth'}
        assert mock_operation.call_count == 2  # Called twice (fail, then success)
        assert client.access_token == 'new_jwt_token'
    
    @patch('src.api.angel_api_client.SmartConnect')
    def test_get_ltp_success(self, mock_smart_connect):
        """Test successful LTP retrieval."""
        mock_smart_api = Mock()
        mock_smart_connect.return_value = mock_smart_api
        
        client = AngelAPIClient(self.credentials, self.config)
        client.access_token = 'test_token'
        client.last_auth_time = datetime.now()
        
        mock_ltp_response = {
            'status': True,
            'data': {'ltp': '50000.50'}
        }
        mock_smart_api.ltpData.return_value = mock_ltp_response
        
        # Test
        result = client.get_ltp("NSE", "BANKNIFTY", "12345")
        
        # Assertions
        assert result == 50000.50
        mock_smart_api.ltpData.assert_called_once_with("NSE", "BANKNIFTY", "12345")
    
    @patch('src.api.angel_api_client.SmartConnect')
    def test_get_ltp_no_data(self, mock_smart_connect):
        """Test LTP retrieval with no data."""
        mock_smart_api = Mock()
        mock_smart_connect.return_value = mock_smart_api
        
        client = AngelAPIClient(self.credentials, self.config)
        client.access_token = 'test_token'
        client.last_auth_time = datetime.now()
        
        mock_ltp_response = {
            'status': False,
            'message': 'No data available'
        }
        mock_smart_api.ltpData.return_value = mock_ltp_response
        
        # Test
        result = client.get_ltp("NSE", "BANKNIFTY", "12345")
        
        # Assertions
        assert result is None
    
    @patch('src.api.angel_api_client.SmartConnect')
    def test_place_order_success(self, mock_smart_connect):
        """Test successful order placement."""
        mock_smart_api = Mock()
        mock_smart_connect.return_value = mock_smart_api
        
        client = AngelAPIClient(self.credentials, self.config)
        client.access_token = 'test_token'
        client.last_auth_time = datetime.now()
        
        mock_smart_api.placeOrder.return_value = "ORDER123"
        
        order_params = {
            'tradingsymbol': 'BANKNIFTY30JAN25CE50000',
            'quantity': '25',
            'transactiontype': 'BUY'
        }
        
        # Test
        result = client.place_order(order_params)
        
        # Assertions
        assert result == "ORDER123"
        mock_smart_api.placeOrder.assert_called_once_with(order_params)
    
    @patch('src.api.angel_api_client.SmartConnect')
    def test_search_instruments_success(self, mock_smart_connect):
        """Test successful instrument search."""
        mock_smart_api = Mock()
        mock_smart_connect.return_value = mock_smart_api
        
        client = AngelAPIClient(self.credentials, self.config)
        client.access_token = 'test_token'
        client.last_auth_time = datetime.now()
        
        mock_search_response = {
            'status': True,
            'data': [
                {
                    'exchange': 'NFO',
                    'tradingsymbol': 'BANKNIFTY30JAN25CE50000',
                    'symboltoken': '12345'
                }
            ]
        }
        mock_smart_api.searchScrip.return_value = mock_search_response
        
        # Test
        result = client.search_instruments("NFO", "BANKNIFTY")
        
        # Assertions
        assert len(result) == 1
        assert result[0]['tradingsymbol'] == 'BANKNIFTY30JAN25CE50000'
        mock_smart_api.searchScrip.assert_called_once_with("NFO", "BANKNIFTY")
    
    @patch('src.api.angel_api_client.SmartConnect')
    def test_get_positions_success(self, mock_smart_connect):
        """Test successful positions retrieval."""
        mock_smart_api = Mock()
        mock_smart_connect.return_value = mock_smart_api
        
        client = AngelAPIClient(self.credentials, self.config)
        client.access_token = 'test_token'
        client.last_auth_time = datetime.now()
        
        mock_positions_response = {
            'status': True,
            'data': [
                {
                    'tradingsymbol': 'BANKNIFTY30JAN25CE50000',
                    'netqty': '25',
                    'pnl': '1000.00'
                }
            ]
        }
        mock_smart_api.position.return_value = mock_positions_response
        
        # Test
        result = client.get_positions()
        
        # Assertions
        assert len(result) == 1
        assert result[0]['tradingsymbol'] == 'BANKNIFTY30JAN25CE50000'
        mock_smart_api.position.assert_called_once()
    
    @patch('src.api.angel_api_client.SmartConnect')
    def test_get_historical_data_success(self, mock_smart_connect):
        """Test successful historical data retrieval."""
        mock_smart_api = Mock()
        mock_smart_connect.return_value = mock_smart_api
        
        client = AngelAPIClient(self.credentials, self.config)
        client.access_token = 'test_token'
        client.last_auth_time = datetime.now()
        
        mock_historical_response = {
            'status': True,
            'data': [
                ['2025-01-01T09:15:00', '50000', '50100', '49900', '50050', '1000']
            ]
        }
        mock_smart_api.getCandleData.return_value = mock_historical_response
        
        params = {
            'exchange': 'NSE',
            'symboltoken': '12345',
            'interval': 'ONE_DAY'
        }
        
        # Test
        result = client.get_historical_data(params)
        
        # Assertions
        assert len(result) == 1
        assert result[0] == ['2025-01-01T09:15:00', '50000', '50100', '49900', '50050', '1000']
        mock_smart_api.getCandleData.assert_called_once_with(params)
    
    @patch('src.api.angel_api_client.SmartConnect')
    def test_connection_status(self, mock_smart_connect):
        """Test connection status reporting."""
        mock_smart_api = Mock()
        mock_smart_connect.return_value = mock_smart_api
        
        client = AngelAPIClient(self.credentials, self.config)
        
        # Test disconnected state
        status = client.get_connection_status()
        assert status['connected'] is False
        assert status['user_id'] is None
        assert status['has_access_token'] is False
        
        # Set connected state
        client.access_token = 'test_token'
        client.refresh_token = 'refresh_token'
        client.feed_token = 'feed_token'
        client.user_id = 'test_user'
        client.last_auth_time = datetime.now()
        
        # Test connected state
        status = client.get_connection_status()
        assert status['connected'] is True
        assert status['user_id'] == 'test_user'
        assert status['has_access_token'] is True
        assert status['has_refresh_token'] is True
        assert status['has_feed_token'] is True
        assert status['last_auth_time'] is not None
    
    @patch('src.api.angel_api_client.SmartConnect')
    def test_context_manager(self, mock_smart_connect):
        """Test context manager functionality."""
        mock_smart_api = Mock()
        mock_smart_connect.return_value = mock_smart_api
        
        # Mock successful authentication
        mock_auth_response = {
            'status': True,
            'data': {
                'jwtToken': 'test_jwt_token',
                'refreshToken': 'test_refresh_token',
                'feedToken': 'test_feed_token',
                'clientcode': 'test_client'
            }
        }
        mock_smart_api.generateSession.return_value = mock_auth_response
        
        with patch.object(AngelAPIClient, '_generate_totp', return_value='123456'):
            with AngelAPIClient(self.credentials, self.config) as client:
                assert client.is_connected() is True
                assert client.access_token == 'test_jwt_token'
        
        # After context exit, should be disconnected
        assert client.access_token is None
        assert client.user_id is None
    
    @patch('src.api.angel_api_client.SmartConnect')
    def test_disconnect(self, mock_smart_connect):
        """Test disconnect functionality."""
        mock_smart_api = Mock()
        mock_smart_connect.return_value = mock_smart_api
        
        client = AngelAPIClient(self.credentials, self.config)
        client.access_token = 'test_token'
        client.refresh_token = 'refresh_token'
        client.feed_token = 'feed_token'
        client.user_id = 'test_user'
        client.last_auth_time = datetime.now()
        
        # Test disconnect
        client.disconnect()
        
        # Verify cleanup
        assert client.access_token is None
        assert client.refresh_token is None
        assert client.feed_token is None
        assert client.user_id is None
        assert client.last_auth_time is None
        
        mock_smart_api.terminateSession.assert_called_once_with('test_user')


if __name__ == "__main__":
    pytest.main([__file__])