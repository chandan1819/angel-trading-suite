"""
Enhanced Angel API client wrapper with comprehensive error handling,
retry logic, rate limiting, and connection pooling.
"""

import time
import logging
import threading
from typing import Dict, Any, Optional, List, Callable
from datetime import datetime, timedelta
from dataclasses import dataclass
import json
import os

from SmartApi.smartConnect import SmartConnect
import SmartApi.smartExceptions as ex
from .error_handler import ErrorHandler, APIError, ErrorCategory, FallbackHandler
from ..performance.connection_pool import ConnectionPoolManager, ConnectionConfig
from ..performance.performance_monitor import PerformanceMonitor
from ..performance.cache_manager import CacheManager, SmartCache

logger = logging.getLogger(__name__)


@dataclass
class APICredentials:
    """API credentials for Angel Broking."""
    api_key: str
    client_code: str
    pin: str
    totp_secret: Optional[str] = None


@dataclass
class ConnectionConfig:
    """Configuration for API connections."""
    timeout: int = 10
    max_retries: int = 3
    rate_limit_per_second: float = 10.0
    connection_pool_size: int = 10
    enable_ssl: bool = True


class RateLimiter:
    """Rate limiter to respect API limits."""
    
    def __init__(self, max_calls_per_second: float):
        self.max_calls_per_second = max_calls_per_second
        self.min_interval = 1.0 / max_calls_per_second
        self.last_call_time = 0.0
        self.lock = threading.Lock()
    
    def wait_if_needed(self):
        """Wait if necessary to respect rate limits."""
        with self.lock:
            current_time = time.time()
            time_since_last_call = current_time - self.last_call_time
            
            if time_since_last_call < self.min_interval:
                sleep_time = self.min_interval - time_since_last_call
                time.sleep(sleep_time)
            
            self.last_call_time = time.time()


class AngelAPIClient:
    """
    Enhanced Angel API client with comprehensive error handling,
    retry logic, rate limiting, and connection pooling.
    """
    
    def __init__(self, credentials: APICredentials, config: ConnectionConfig = None,
                 performance_monitor: Optional[PerformanceMonitor] = None,
                 cache_manager: Optional[CacheManager] = None):
        self.credentials = credentials
        self.config = config or ConnectionConfig()
        
        # Performance components
        self.performance_monitor = performance_monitor or PerformanceMonitor()
        self.cache_manager = cache_manager
        self.smart_cache = SmartCache(cache_manager) if cache_manager else None
        
        # Initialize components
        self.error_handler = ErrorHandler()
        self.fallback_handler = FallbackHandler()
        self.rate_limiter = RateLimiter(self.config.rate_limit_per_second)
        
        # Connection pooling
        self.connection_pool = ConnectionPoolManager(self.config)
        
        # Connection management
        self.smart_api = None
        self.last_auth_time = None
        self.auth_lock = threading.Lock()
        self.connection_lock = threading.Lock()
        
        # Session management
        self.access_token = None
        self.refresh_token = None
        self.feed_token = None
        self.user_id = None
        
        # Initialize connection
        self._initialize_connection()
    
    def _initialize_connection(self):
        """Initialize the SmartConnect client with connection pooling."""
        try:
            pool_config = {
                'pool_connections': self.config.connection_pool_size,
                'pool_maxsize': self.config.connection_pool_size,
                'max_retries': 0  # We handle retries ourselves
            }
            
            self.smart_api = SmartConnect(
                api_key=self.credentials.api_key,
                timeout=self.config.timeout,
                pool=pool_config,
                disable_ssl=not self.config.enable_ssl
            )
            
            logger.info("Angel API client initialized successfully")
            
        except Exception as e:
            error = self.error_handler.handle_error(e, "API client initialization")
            logger.error(f"Failed to initialize API client: {error}")
            raise error
    
    def _reset_connection(self):
        """Reset the API connection."""
        with self.connection_lock:
            try:
                logger.info("Resetting API connection")
                self._initialize_connection()
                
                # Re-authenticate if we had valid tokens
                if self.access_token and self.refresh_token:
                    self._reauthenticate()
                    
            except Exception as e:
                error = self.error_handler.handle_error(e, "Connection reset")
                logger.error(f"Failed to reset connection: {error}")
                raise error
    
    def authenticate(self) -> bool:
        """
        Authenticate with Angel API and obtain tokens.
        
        Returns:
            bool: True if authentication successful, False otherwise
        """
        with self.auth_lock:
            try:
                # Generate TOTP if secret is provided
                totp = None
                if self.credentials.totp_secret:
                    totp = self._generate_totp()
                
                def auth_operation():
                    return self.smart_api.generateSession(
                        self.credentials.client_code,
                        self.credentials.pin,
                        totp
                    )
                
                response = self.error_handler.execute_with_retry(
                    auth_operation,
                    "Authentication"
                )
                
                if response and response.get('status'):
                    # Extract tokens from response
                    data = response.get('data', {})
                    self.access_token = data.get('jwtToken')
                    self.refresh_token = data.get('refreshToken')
                    self.feed_token = data.get('feedToken')
                    self.user_id = data.get('clientcode')
                    self.last_auth_time = datetime.now()
                    
                    logger.info(f"Authentication successful for user: {self.user_id}")
                    return True
                else:
                    logger.error(f"Authentication failed: {response}")
                    return False
                    
            except APIError as e:
                if e.category == ErrorCategory.AUTHENTICATION:
                    logger.error(f"Authentication failed: {e}")
                    return False
                raise e
            except Exception as e:
                error = self.error_handler.handle_error(e, "Authentication")
                logger.error(f"Authentication error: {error}")
                return False
    
    def _reauthenticate(self) -> bool:
        """Re-authenticate using refresh token."""
        try:
            if not self.refresh_token:
                logger.warning("No refresh token available for re-authentication")
                return self.authenticate()
            
            def refresh_operation():
                return self.smart_api.generateToken(self.refresh_token)
            
            response = self.error_handler.execute_with_retry(
                refresh_operation,
                "Token refresh"
            )
            
            if response and response.get('status'):
                data = response.get('data', {})
                self.access_token = data.get('jwtToken')
                self.feed_token = data.get('feedToken')
                self.last_auth_time = datetime.now()
                
                logger.info("Re-authentication successful")
                return True
            else:
                logger.warning("Token refresh failed, attempting full authentication")
                return self.authenticate()
                
        except Exception as e:
            logger.warning(f"Re-authentication failed: {e}, attempting full authentication")
            return self.authenticate()
    
    def _generate_totp(self) -> Optional[str]:
        """Generate TOTP token if secret is available."""
        if not self.credentials.totp_secret:
            return None
        
        try:
            import pyotp
            totp = pyotp.TOTP(self.credentials.totp_secret)
            return totp.now()
        except ImportError:
            logger.warning("pyotp not available, TOTP generation skipped")
            return None
        except Exception as e:
            logger.error(f"TOTP generation failed: {e}")
            return None
    
    def _ensure_authenticated(self) -> bool:
        """Ensure we have valid authentication."""
        # Check if we need to authenticate
        if not self.access_token:
            return self.authenticate()
        
        # Check if token is expired (assume 6 hours validity)
        if self.last_auth_time:
            token_age = datetime.now() - self.last_auth_time
            if token_age > timedelta(hours=5):  # Refresh before expiry
                return self._reauthenticate()
        
        return True
    
    def _execute_api_call(self, operation: Callable, context: str, 
                         handle_auth_error: bool = True) -> Any:
        """
        Execute an API call with comprehensive error handling.
        
        Args:
            operation: The API operation to execute
            context: Description of the operation for logging
            handle_auth_error: Whether to handle authentication errors automatically
            
        Returns:
            API response data
        """
        # Ensure we're authenticated
        if not self._ensure_authenticated():
            raise APIError("Authentication failed", ErrorCategory.AUTHENTICATION)
        
        # Apply rate limiting
        self.rate_limiter.wait_if_needed()
        
        def wrapped_operation():
            try:
                return operation()
            except ex.TokenException as e:
                if handle_auth_error:
                    logger.info("Token expired, attempting re-authentication")
                    if self._reauthenticate():
                        # Retry the operation once after re-authentication
                        return operation()
                raise e
        
        try:
            return self.error_handler.execute_with_retry(wrapped_operation, context)
        except APIError as e:
            # Try fallback strategies
            fallback_action = self.fallback_handler.get_fallback_action(e, {"context": context})
            
            if fallback_action:
                action = fallback_action.get("action")
                
                if action == "reauthenticate":
                    if self._reauthenticate():
                        return self.error_handler.execute_with_retry(operation, context)
                
                elif action == "reset_connection":
                    self._reset_connection()
                    return self.error_handler.execute_with_retry(operation, context)
                
                elif action == "wait":
                    delay = fallback_action.get("delay", 60)
                    logger.info(f"Fallback wait: {delay}s")
                    time.sleep(delay)
                    return self.error_handler.execute_with_retry(operation, context)
            
            # If no fallback worked, re-raise the error
            raise e
    
    # Core API methods with enhanced error handling
    
    def get_profile(self) -> Dict[str, Any]:
        """Get user profile information."""
        def operation():
            return self.smart_api.getProfile(self.refresh_token)
        
        return self._execute_api_call(operation, "Get profile")
    
    def search_instruments(self, exchange: str, search_term: str) -> List[Dict[str, Any]]:
        """
        Search for trading instruments with caching.
        
        Args:
            exchange: Exchange name (NSE, BSE, etc.)
            search_term: Search term for instruments
            
        Returns:
            List of matching instruments
        """
        with self.performance_monitor.measure('api_call'):
            # Check cache first
            if self.smart_cache:
                cached_results = self.smart_cache.get_instrument_search(exchange, search_term)
                if cached_results is not None:
                    return cached_results
            
            def operation():
                response = self.smart_api.searchScrip(exchange, search_term)
                if response and response.get('status') and response.get('data'):
                    results = response['data']
                    
                    # Cache the results
                    if self.smart_cache and results:
                        self.smart_cache.cache_instrument_search(exchange, search_term, results)
                    
                    return results
                return []
            
            return self._execute_api_call(operation, f"Search instruments: {exchange}:{search_term}")
    
    def get_ltp(self, exchange: str, trading_symbol: str, token: str) -> Optional[float]:
        """
        Get Last Traded Price for an instrument with caching.
        
        Args:
            exchange: Exchange name
            trading_symbol: Trading symbol
            token: Instrument token
            
        Returns:
            Last traded price or None if not available
        """
        with self.performance_monitor.measure('api_call'):
            # Check cache first
            if self.smart_cache:
                cached_ltp = self.smart_cache.get_ltp(exchange, trading_symbol, token)
                if cached_ltp is not None:
                    return cached_ltp
            
            def operation():
                response = self.smart_api.ltpData(exchange, trading_symbol, token)
                if response and response.get('status') and response.get('data'):
                    ltp = float(response['data'].get('ltp', 0))
                    
                    # Cache the result
                    if self.smart_cache and ltp > 0:
                        self.smart_cache.cache_ltp(exchange, trading_symbol, token, ltp)
                    
                    return ltp
                return None
            
            return self._execute_api_call(operation, f"Get LTP: {exchange}:{trading_symbol}")
    
    def place_order(self, order_params: Dict[str, Any]) -> Optional[str]:
        """
        Place a trading order.
        
        Args:
            order_params: Order parameters dictionary
            
        Returns:
            Order ID if successful, None otherwise
        """
        def operation():
            return self.smart_api.placeOrder(order_params)
        
        return self._execute_api_call(operation, f"Place order: {order_params.get('tradingsymbol', 'Unknown')}")
    
    def modify_order(self, order_params: Dict[str, Any]) -> Dict[str, Any]:
        """
        Modify an existing order.
        
        Args:
            order_params: Modified order parameters
            
        Returns:
            API response
        """
        def operation():
            return self.smart_api.modifyOrder(order_params)
        
        return self._execute_api_call(operation, f"Modify order: {order_params.get('orderid', 'Unknown')}")
    
    def cancel_order(self, order_id: str, variety: str) -> Dict[str, Any]:
        """
        Cancel an order.
        
        Args:
            order_id: Order ID to cancel
            variety: Order variety
            
        Returns:
            API response
        """
        def operation():
            return self.smart_api.cancelOrder(order_id, variety)
        
        return self._execute_api_call(operation, f"Cancel order: {order_id}")
    
    def get_order_book(self) -> List[Dict[str, Any]]:
        """Get order book."""
        def operation():
            response = self.smart_api.orderBook()
            if response and response.get('status') and response.get('data'):
                return response['data']
            return []
        
        return self._execute_api_call(operation, "Get order book")
    
    def get_positions(self) -> List[Dict[str, Any]]:
        """Get current positions."""
        def operation():
            response = self.smart_api.position()
            if response and response.get('status') and response.get('data'):
                return response['data']
            return []
        
        return self._execute_api_call(operation, "Get positions")
    
    def get_trade_book(self) -> List[Dict[str, Any]]:
        """Get trade book."""
        def operation():
            response = self.smart_api.tradeBook()
            if response and response.get('status') and response.get('data'):
                return response['data']
            return []
        
        return self._execute_api_call(operation, "Get trade book")
    
    def get_historical_data(self, params: Dict[str, Any]) -> List[Dict[str, Any]]:
        """
        Get historical candle data with caching.
        
        Args:
            params: Historical data parameters
            
        Returns:
            List of historical data points
        """
        with self.performance_monitor.measure('api_call'):
            # Check cache first
            if self.smart_cache:
                symbol = params.get('symboltoken', 'unknown')
                interval = params.get('interval', 'unknown')
                from_date = params.get('fromdate', 'unknown')
                to_date = params.get('todate', 'unknown')
                
                cached_data = self.smart_cache.get_historical_data(
                    symbol, interval, from_date, to_date
                )
                if cached_data is not None:
                    return cached_data
            
            def operation():
                response = self.smart_api.getCandleData(params)
                if response and response.get('status') and response.get('data'):
                    data = response['data']
                    
                    # Cache the results
                    if self.smart_cache and data:
                        symbol = params.get('symboltoken', 'unknown')
                        interval = params.get('interval', 'unknown')
                        from_date = params.get('fromdate', 'unknown')
                        to_date = params.get('todate', 'unknown')
                        
                        self.smart_cache.cache_historical_data(
                            symbol, interval, from_date, to_date, data
                        )
                    
                    return data
                return []
            
            return self._execute_api_call(operation, f"Get historical data: {params.get('symboltoken', 'Unknown')}")
    
    def get_market_data(self, mode: str, exchange_tokens: List[Dict[str, str]]) -> Dict[str, Any]:
        """
        Get market data for multiple instruments.
        
        Args:
            mode: Data mode (LTP, FULL, etc.)
            exchange_tokens: List of exchange:token pairs
            
        Returns:
            Market data response
        """
        def operation():
            return self.smart_api.getMarketData(mode, exchange_tokens)
        
        return self._execute_api_call(operation, f"Get market data: {len(exchange_tokens)} instruments")
    
    # Connection and session management
    
    def is_connected(self) -> bool:
        """Check if the client is connected and authenticated."""
        return (self.smart_api is not None and 
                self.access_token is not None and 
                self.user_id is not None)
    
    def disconnect(self):
        """Disconnect and cleanup resources."""
        try:
            if self.smart_api and self.user_id:
                self.smart_api.terminateSession(self.user_id)
            
            self.access_token = None
            self.refresh_token = None
            self.feed_token = None
            self.user_id = None
            self.last_auth_time = None
            
            logger.info("API client disconnected successfully")
            
        except Exception as e:
            logger.warning(f"Error during disconnect: {e}")
    
    def get_connection_status(self) -> Dict[str, Any]:
        """Get detailed connection status information."""
        return {
            "connected": self.is_connected(),
            "user_id": self.user_id,
            "last_auth_time": self.last_auth_time.isoformat() if self.last_auth_time else None,
            "has_access_token": bool(self.access_token),
            "has_refresh_token": bool(self.refresh_token),
            "has_feed_token": bool(self.feed_token)
        }
    
    def __enter__(self):
        """Context manager entry."""
        if not self.is_connected():
            self.authenticate()
        return self
    
    def __exit__(self, exc_type, exc_val, exc_tb):
        """Context manager exit."""
        self.disconnect()
    
    def get_performance_stats(self) -> Dict[str, Any]:
        """Get performance statistics for API operations."""
        stats = {
            'performance_metrics': self.performance_monitor.get_summary(),
            'connection_pool': self.connection_pool.get_stats(),
            'rate_limiter': {
                'max_calls_per_second': self.rate_limiter.max_calls_per_second,
                'last_call_time': self.rate_limiter.last_call_time
            }
        }
        
        if self.cache_manager:
            stats['cache_stats'] = self.cache_manager.get_stats()
        
        return stats
    
    def clear_cache(self):
        """Clear API response cache."""
        if self.cache_manager:
            self.cache_manager.clear()
            logger.info("API cache cleared")
    
    def optimize_connection_pool(self):
        """Trigger connection pool optimization."""
        self.connection_pool._perform_maintenance()
        logger.info("Connection pool optimization completed")