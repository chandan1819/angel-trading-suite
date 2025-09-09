"""
Unit tests for error handling functionality.
"""

import pytest
import time
from unittest.mock import Mock, patch
import SmartApi.smartExceptions as ex

from src.api.error_handler import (
    ErrorHandler, APIError, ErrorCategory, RetryPolicy, 
    BackoffStrategy, FallbackHandler
)


class TestErrorHandler:
    """Test cases for ErrorHandler class."""
    
    def setup_method(self):
        """Set up test fixtures."""
        self.error_handler = ErrorHandler()
    
    def test_categorize_smartapi_exceptions(self):
        """Test categorization of SmartAPI exceptions."""
        test_cases = [
            (ex.TokenException("Token expired"), ErrorCategory.AUTHENTICATION),
            (ex.NetworkException("Network error"), ErrorCategory.NETWORK),
            (ex.OrderException("Order rejected"), ErrorCategory.ORDER_REJECTION),
            (ex.DataException("Invalid data"), ErrorCategory.DATA_ERROR),
            (ex.InputException("Invalid input"), ErrorCategory.SYSTEM_ERROR),
            (ex.PermissionException("No permission"), ErrorCategory.AUTHENTICATION),
            (ex.GeneralException("General error"), ErrorCategory.SYSTEM_ERROR)
        ]
        
        for exception, expected_category in test_cases:
            category = self.error_handler.categorize_error(exception)
            assert category == expected_category
    
    def test_categorize_rate_limit_errors(self):
        """Test categorization of rate limit errors."""
        rate_limit_messages = [
            "Rate limit exceeded",
            "Too many requests",
            "API throttled",
            "Quota exceeded"
        ]
        
        for message in rate_limit_messages:
            error = ex.GeneralException(message)
            category = self.error_handler.categorize_error(error)
            assert category == ErrorCategory.RATE_LIMIT
    
    def test_categorize_network_errors(self):
        """Test categorization of network errors."""
        network_errors = [
            ConnectionError("Connection failed"),
            TimeoutError("Request timeout")
        ]
        
        for error in network_errors:
            category = self.error_handler.categorize_error(error)
            assert category == ErrorCategory.NETWORK
    
    def test_should_retry_logic(self):
        """Test retry decision logic."""
        # Test retry for different categories
        auth_error = APIError("Auth failed", ErrorCategory.AUTHENTICATION)
        assert self.error_handler.should_retry(auth_error, 1) is True
        assert self.error_handler.should_retry(auth_error, 3) is False  # Max attempts reached
        
        # Test no retry for system errors
        system_error = APIError("System error", ErrorCategory.SYSTEM_ERROR)
        assert self.error_handler.should_retry(system_error, 1) is False
    
    def test_calculate_backoff_delay(self):
        """Test backoff delay calculations."""
        # Test exponential backoff
        policy = RetryPolicy(
            backoff_strategy=BackoffStrategy.EXPONENTIAL,
            base_delay=1.0,
            backoff_multiplier=2.0,
            max_delay=10.0,
            jitter=False
        )
        
        assert self.error_handler.calculate_backoff_delay(1, policy) == 1.0
        assert self.error_handler.calculate_backoff_delay(2, policy) == 2.0
        assert self.error_handler.calculate_backoff_delay(3, policy) == 4.0
        assert self.error_handler.calculate_backoff_delay(5, policy) == 10.0  # Max delay
        
        # Test linear backoff
        policy.backoff_strategy = BackoffStrategy.LINEAR
        assert self.error_handler.calculate_backoff_delay(1, policy) == 1.0
        assert self.error_handler.calculate_backoff_delay(2, policy) == 2.0
        assert self.error_handler.calculate_backoff_delay(3, policy) == 3.0
        
        # Test fixed backoff
        policy.backoff_strategy = BackoffStrategy.FIXED
        assert self.error_handler.calculate_backoff_delay(1, policy) == 1.0
        assert self.error_handler.calculate_backoff_delay(5, policy) == 1.0
    
    def test_handle_error_conversion(self):
        """Test conversion of raw exceptions to APIError."""
        original_error = ex.TokenException("Token expired", code=403)
        
        api_error = self.error_handler.handle_error(original_error, "Test context")
        
        assert isinstance(api_error, APIError)
        assert api_error.category == ErrorCategory.AUTHENTICATION
        assert api_error.original_error == original_error
        assert api_error.code == 403
        assert "Test context" in str(api_error)
    
    @patch('time.sleep')
    def test_execute_with_retry_success(self, mock_sleep):
        """Test successful execution with retry."""
        mock_operation = Mock()
        mock_operation.return_value = "success"
        
        result = self.error_handler.execute_with_retry(mock_operation, "Test operation")
        
        assert result == "success"
        mock_operation.assert_called_once()
        mock_sleep.assert_not_called()
    
    @patch('time.sleep')
    def test_execute_with_retry_eventual_success(self, mock_sleep):
        """Test eventual success after retries."""
        mock_operation = Mock()
        mock_operation.side_effect = [
            ex.NetworkException("Network error"),
            ex.NetworkException("Network error"),
            "success"
        ]
        
        result = self.error_handler.execute_with_retry(mock_operation, "Test operation")
        
        assert result == "success"
        assert mock_operation.call_count == 3
        assert mock_sleep.call_count == 2
    
    @patch('time.sleep')
    def test_execute_with_retry_max_attempts(self, mock_sleep):
        """Test failure after max retry attempts."""
        mock_operation = Mock()
        mock_operation.side_effect = ex.NetworkException("Network error")
        
        with pytest.raises(APIError) as exc_info:
            self.error_handler.execute_with_retry(mock_operation, "Test operation")
        
        assert exc_info.value.category == ErrorCategory.NETWORK
        assert mock_operation.call_count == 3  # Default max attempts
        assert mock_sleep.call_count == 2
    
    def test_execute_with_retry_no_retry_category(self):
        """Test no retry for system errors."""
        mock_operation = Mock()
        mock_operation.side_effect = ex.InputException("Invalid input")
        
        with pytest.raises(APIError) as exc_info:
            self.error_handler.execute_with_retry(mock_operation, "Test operation")
        
        assert exc_info.value.category == ErrorCategory.SYSTEM_ERROR
        mock_operation.assert_called_once()  # No retries


class TestRetryPolicy:
    """Test cases for RetryPolicy configuration."""
    
    def test_default_retry_policy(self):
        """Test default retry policy values."""
        policy = RetryPolicy()
        
        assert policy.max_attempts == 3
        assert policy.backoff_strategy == BackoffStrategy.EXPONENTIAL
        assert policy.base_delay == 1.0
        assert policy.max_delay == 60.0
        assert policy.backoff_multiplier == 2.0
        assert policy.jitter is True
    
    def test_custom_retry_policy(self):
        """Test custom retry policy configuration."""
        policy = RetryPolicy(
            max_attempts=5,
            backoff_strategy=BackoffStrategy.LINEAR,
            base_delay=2.0,
            max_delay=30.0,
            jitter=False
        )
        
        assert policy.max_attempts == 5
        assert policy.backoff_strategy == BackoffStrategy.LINEAR
        assert policy.base_delay == 2.0
        assert policy.max_delay == 30.0
        assert policy.jitter is False


class TestAPIError:
    """Test cases for APIError class."""
    
    def test_api_error_creation(self):
        """Test APIError creation with all parameters."""
        original_error = Exception("Original error")
        
        api_error = APIError(
            message="Test error",
            category=ErrorCategory.AUTHENTICATION,
            original_error=original_error,
            retry_after=30.0,
            code=403
        )
        
        assert str(api_error) == "Test error"
        assert api_error.category == ErrorCategory.AUTHENTICATION
        assert api_error.original_error == original_error
        assert api_error.retry_after == 30.0
        assert api_error.code == 403
        assert isinstance(api_error.timestamp, float)
    
    def test_api_error_minimal(self):
        """Test APIError creation with minimal parameters."""
        api_error = APIError("Simple error", ErrorCategory.NETWORK)
        
        assert str(api_error) == "Simple error"
        assert api_error.category == ErrorCategory.NETWORK
        assert api_error.original_error is None
        assert api_error.retry_after is None
        assert api_error.code is None


class TestFallbackHandler:
    """Test cases for FallbackHandler class."""
    
    def setup_method(self):
        """Set up test fixtures."""
        self.fallback_handler = FallbackHandler()
    
    def test_auth_fallback(self):
        """Test authentication fallback strategy."""
        error = APIError("Auth failed", ErrorCategory.AUTHENTICATION)
        context = {"context": "test"}
        
        action = self.fallback_handler.get_fallback_action(error, context)
        
        assert action is not None
        assert action["action"] == "reauthenticate"
    
    def test_rate_limit_fallback(self):
        """Test rate limit fallback strategy."""
        error = APIError("Rate limited", ErrorCategory.RATE_LIMIT, retry_after=120.0)
        context = {"context": "test"}
        
        action = self.fallback_handler.get_fallback_action(error, context)
        
        assert action is not None
        assert action["action"] == "wait"
        assert action["delay"] == 120.0
    
    def test_network_fallback(self):
        """Test network fallback strategy."""
        error = APIError("Network error", ErrorCategory.NETWORK)
        context = {"context": "test"}
        
        action = self.fallback_handler.get_fallback_action(error, context)
        
        assert action is not None
        assert action["action"] == "reset_connection"
    
    def test_order_fallback(self):
        """Test order rejection fallback strategy."""
        error = APIError("Order rejected", ErrorCategory.ORDER_REJECTION)
        context = {"context": "test"}
        
        action = self.fallback_handler.get_fallback_action(error, context)
        
        assert action is not None
        assert action["action"] == "modify_order_params"
    
    def test_data_fallback(self):
        """Test data error fallback strategy."""
        error = APIError("Data error", ErrorCategory.DATA_ERROR)
        context = {"context": "test"}
        
        action = self.fallback_handler.get_fallback_action(error, context)
        
        assert action is not None
        assert action["action"] == "use_cached_data"
    
    def test_no_fallback_for_unknown_category(self):
        """Test no fallback for unknown error categories."""
        error = APIError("Unknown error", ErrorCategory.SYSTEM_ERROR)
        context = {"context": "test"}
        
        action = self.fallback_handler.get_fallback_action(error, context)
        
        assert action is None


if __name__ == "__main__":
    pytest.main([__file__])