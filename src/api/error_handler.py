"""
Comprehensive error handling for Angel API operations.
"""

import time
import logging
from typing import Dict, Any, Optional, Callable, Type
from enum import Enum
from dataclasses import dataclass
import SmartApi.smartExceptions as ex

logger = logging.getLogger(__name__)


class ErrorCategory(Enum):
    """Categories of API errors for specific handling strategies."""
    AUTHENTICATION = "authentication"
    RATE_LIMIT = "rate_limit"
    NETWORK = "network"
    ORDER_REJECTION = "order_rejection"
    DATA_ERROR = "data_error"
    SYSTEM_ERROR = "system_error"


class BackoffStrategy(Enum):
    """Backoff strategies for retry logic."""
    EXPONENTIAL = "exponential"
    LINEAR = "linear"
    FIXED = "fixed"


@dataclass
class RetryPolicy:
    """Configuration for retry behavior."""
    max_attempts: int = 3
    backoff_strategy: BackoffStrategy = BackoffStrategy.EXPONENTIAL
    base_delay: float = 1.0
    max_delay: float = 60.0
    backoff_multiplier: float = 2.0
    jitter: bool = True


class APIError(Exception):
    """Enhanced API error with categorization and retry information."""
    
    def __init__(self, message: str, category: ErrorCategory, 
                 original_error: Optional[Exception] = None,
                 retry_after: Optional[float] = None,
                 code: Optional[int] = None):
        super().__init__(message)
        self.category = category
        self.original_error = original_error
        self.retry_after = retry_after
        self.code = code
        self.timestamp = time.time()


class ErrorHandler:
    """Comprehensive error handler for Angel API operations."""
    
    def __init__(self):
        self.retry_policies = {
            ErrorCategory.AUTHENTICATION: RetryPolicy(max_attempts=2, base_delay=1.0),
            ErrorCategory.RATE_LIMIT: RetryPolicy(max_attempts=5, base_delay=2.0, max_delay=30.0),
            ErrorCategory.NETWORK: RetryPolicy(max_attempts=3, base_delay=1.0),
            ErrorCategory.ORDER_REJECTION: RetryPolicy(max_attempts=2, base_delay=0.5),
            ErrorCategory.DATA_ERROR: RetryPolicy(max_attempts=3, base_delay=1.0),
            ErrorCategory.SYSTEM_ERROR: RetryPolicy(max_attempts=1, base_delay=0.0)
        }
        
        # Error mapping from SmartAPI exceptions to our categories
        self.error_mapping = {
            ex.TokenException: ErrorCategory.AUTHENTICATION,
            ex.NetworkException: ErrorCategory.NETWORK,
            ex.OrderException: ErrorCategory.ORDER_REJECTION,
            ex.DataException: ErrorCategory.DATA_ERROR,
            ex.InputException: ErrorCategory.SYSTEM_ERROR,
            ex.PermissionException: ErrorCategory.AUTHENTICATION,
            ex.GeneralException: ErrorCategory.SYSTEM_ERROR
        }
        
        # Rate limit indicators in error messages
        self.rate_limit_indicators = [
            "rate limit",
            "too many requests",
            "throttled",
            "quota exceeded"
        ]
    
    def categorize_error(self, error: Exception) -> ErrorCategory:
        """Categorize an error for appropriate handling."""
        # Direct mapping from SmartAPI exceptions
        error_type = type(error)
        if error_type in self.error_mapping:
            category = self.error_mapping[error_type]
            
            # Special case: check if it's actually a rate limit error
            if category == ErrorCategory.SYSTEM_ERROR:
                error_msg = str(error).lower()
                if any(indicator in error_msg for indicator in self.rate_limit_indicators):
                    return ErrorCategory.RATE_LIMIT
            
            return category
        
        # Check for network-related errors
        if isinstance(error, (ConnectionError, TimeoutError)):
            return ErrorCategory.NETWORK
        
        # Check error message for rate limiting
        error_msg = str(error).lower()
        if any(indicator in error_msg for indicator in self.rate_limit_indicators):
            return ErrorCategory.RATE_LIMIT
        
        # Default to system error
        return ErrorCategory.SYSTEM_ERROR
    
    def should_retry(self, error: APIError, attempt: int) -> bool:
        """Determine if an operation should be retried."""
        policy = self.retry_policies.get(error.category)
        if not policy:
            return False
        
        if attempt >= policy.max_attempts:
            return False
        
        # Don't retry certain system errors
        if error.category == ErrorCategory.SYSTEM_ERROR:
            return False
        
        return True
    
    def calculate_backoff_delay(self, attempt: int, policy: RetryPolicy) -> float:
        """Calculate the delay before next retry attempt."""
        if policy.backoff_strategy == BackoffStrategy.EXPONENTIAL:
            delay = policy.base_delay * (policy.backoff_multiplier ** (attempt - 1))
        elif policy.backoff_strategy == BackoffStrategy.LINEAR:
            delay = policy.base_delay * attempt
        else:  # FIXED
            delay = policy.base_delay
        
        # Apply maximum delay limit
        delay = min(delay, policy.max_delay)
        
        # Add jitter to prevent thundering herd
        if policy.jitter:
            import random
            delay *= (0.5 + random.random() * 0.5)
        
        return delay
    
    def handle_error(self, error: Exception, context: str = "") -> APIError:
        """Convert a raw exception to an APIError with proper categorization."""
        category = self.categorize_error(error)
        
        # Extract retry_after from rate limit errors if available
        retry_after = None
        if category == ErrorCategory.RATE_LIMIT:
            # Try to extract retry-after from error message or headers
            # This would need to be customized based on actual API responses
            retry_after = 60.0  # Default 1 minute for rate limits
        
        # Extract error code if available
        code = getattr(error, 'code', None)
        
        message = f"{context}: {str(error)}" if context else str(error)
        
        api_error = APIError(
            message=message,
            category=category,
            original_error=error,
            retry_after=retry_after,
            code=code
        )
        
        logger.error(f"API Error - Category: {category.value}, Message: {message}, Code: {code}")
        
        return api_error
    
    def execute_with_retry(self, operation: Callable, context: str = "", 
                          custom_policy: Optional[RetryPolicy] = None) -> Any:
        """Execute an operation with retry logic."""
        attempt = 1
        last_error = None
        
        while True:
            try:
                return operation()
            except Exception as e:
                api_error = self.handle_error(e, context)
                last_error = api_error
                
                # Use custom policy if provided, otherwise use default for category
                policy = custom_policy or self.retry_policies.get(api_error.category)
                
                if not self.should_retry(api_error, attempt):
                    logger.error(f"Max retry attempts reached for {context}. Final error: {api_error}")
                    raise api_error
                
                # Calculate delay and wait
                delay = self.calculate_backoff_delay(attempt, policy)
                logger.warning(f"Retry attempt {attempt} for {context} after {delay:.2f}s delay. Error: {api_error}")
                
                time.sleep(delay)
                attempt += 1
        
        # This should never be reached, but just in case
        if last_error:
            raise last_error
        else:
            raise APIError("Unknown error in retry logic", ErrorCategory.SYSTEM_ERROR)


# Fallback mechanisms for different error types
class FallbackHandler:
    """Handles fallback strategies when primary operations fail."""
    
    def __init__(self):
        self.fallback_strategies = {
            ErrorCategory.AUTHENTICATION: self._handle_auth_fallback,
            ErrorCategory.RATE_LIMIT: self._handle_rate_limit_fallback,
            ErrorCategory.NETWORK: self._handle_network_fallback,
            ErrorCategory.ORDER_REJECTION: self._handle_order_fallback,
            ErrorCategory.DATA_ERROR: self._handle_data_fallback
        }
    
    def _handle_auth_fallback(self, error: APIError, context: Dict[str, Any]) -> Optional[Any]:
        """Handle authentication failures with re-authentication."""
        logger.info("Attempting re-authentication fallback")
        # This would trigger re-authentication in the main client
        return {"action": "reauthenticate"}
    
    def _handle_rate_limit_fallback(self, error: APIError, context: Dict[str, Any]) -> Optional[Any]:
        """Handle rate limit with extended delay."""
        delay = error.retry_after or 60.0
        logger.info(f"Rate limit fallback: waiting {delay}s")
        return {"action": "wait", "delay": delay}
    
    def _handle_network_fallback(self, error: APIError, context: Dict[str, Any]) -> Optional[Any]:
        """Handle network issues with connection reset."""
        logger.info("Network fallback: resetting connection")
        return {"action": "reset_connection"}
    
    def _handle_order_fallback(self, error: APIError, context: Dict[str, Any]) -> Optional[Any]:
        """Handle order rejection with alternative order types."""
        logger.info("Order fallback: considering alternative order parameters")
        return {"action": "modify_order_params"}
    
    def _handle_data_fallback(self, error: APIError, context: Dict[str, Any]) -> Optional[Any]:
        """Handle data errors with cached data."""
        logger.info("Data fallback: using cached data if available")
        return {"action": "use_cached_data"}
    
    def get_fallback_action(self, error: APIError, context: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        """Get appropriate fallback action for an error."""
        handler = self.fallback_strategies.get(error.category)
        if handler:
            return handler(error, context)
        return None