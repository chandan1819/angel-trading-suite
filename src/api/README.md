# Enhanced Angel API Client

This module provides an enhanced wrapper around the Angel Broking SmartAPI with comprehensive error handling, retry logic, rate limiting, connection pooling, and market data management capabilities.

## Features

### Core Enhancements
- **Comprehensive Error Handling**: Categorized error handling with specific strategies for different error types
- **Retry Logic**: Configurable retry policies with exponential, linear, and fixed backoff strategies
- **Rate Limiting**: Built-in rate limiting to respect API limits and prevent throttling
- **Connection Pooling**: Efficient connection management with configurable pool sizes
- **Automatic Re-authentication**: Seamless token refresh and re-authentication on expiry
- **Fallback Mechanisms**: Multiple fallback strategies for different failure scenarios

### Market Data Management
- **Options Chain Processing**: Automated options chain retrieval and ATM strike identification
- **Historical Data Caching**: Intelligent caching with configurable TTL for different data types
- **Real-time Monitoring**: Multi-threaded real-time price monitoring with callbacks
- **Data Validation**: Comprehensive validation and error handling for market data

## Quick Start

### Basic Usage

```python
from src.api.angel_api_client import AngelAPIClient, APICredentials, ConnectionConfig

# Configure credentials
credentials = APICredentials(
    api_key="your_api_key",
    client_code="your_client_code",
    pin="your_pin",
    totp_secret="your_totp_secret"  # Optional
)

# Configure connection settings
config = ConnectionConfig(
    timeout=10,
    max_retries=3,
    rate_limit_per_second=5.0,
    connection_pool_size=10
)

# Use as context manager (recommended)
with AngelAPIClient(credentials, config) as client:
    # Search for instruments
    instruments = client.search_instruments("NFO", "BANKNIFTY")
    
    # Get LTP
    ltp = client.get_ltp("NSE", "BANKNIFTY", "token")
    
    # Place order
    order_params = {
        'tradingsymbol': 'BANKNIFTY30JAN25CE50000',
        'quantity': '25',
        'transactiontype': 'BUY',
        'ordertype': 'MARKET',
        'product': 'MIS',
        'exchange': 'NFO'
    }
    order_id = client.place_order(order_params)
```

### Market Data Usage

```python
from src.api.market_data import MarketDataManager

# Initialize market data manager
market_data = MarketDataManager(api_client)

# Get options chain
options_chain = market_data.get_options_chain("BANKNIFTY")
print(f"ATM Strike: {options_chain.atm_strike}")
print(f"Underlying Price: {options_chain.underlying_price}")

# Get historical data
historical_data = market_data.get_historical_data(
    symbol="BANKNIFTY",
    token="token",
    exchange="NSE",
    interval="ONE_DAY"
)

# Start real-time monitoring
def price_callback(price_data):
    print(f"Price update: {price_data.symbol} = {price_data.ltp}")

symbols = [{'exchange': 'NSE', 'symbol': 'BANKNIFTY', 'token': 'token'}]
market_data.start_real_time_monitoring(symbols, price_callback)
```

## Error Handling

The enhanced API client provides comprehensive error handling with categorized errors and specific handling strategies:

### Error Categories

- **AUTHENTICATION**: Token expiry, invalid credentials
- **RATE_LIMIT**: API rate limiting, throttling
- **NETWORK**: Connection issues, timeouts
- **ORDER_REJECTION**: Order validation failures
- **DATA_ERROR**: Invalid or missing data
- **SYSTEM_ERROR**: General system errors

### Retry Policies

```python
from src.api.error_handler import RetryPolicy, BackoffStrategy

# Custom retry policy
custom_policy = RetryPolicy(
    max_attempts=5,
    backoff_strategy=BackoffStrategy.EXPONENTIAL,
    base_delay=1.0,
    max_delay=30.0,
    backoff_multiplier=2.0,
    jitter=True
)

# Use with error handler
result = error_handler.execute_with_retry(
    operation=lambda: api_call(),
    context="Custom operation",
    custom_policy=custom_policy
)
```

### Fallback Mechanisms

The client automatically handles various failure scenarios:

- **Authentication failures**: Automatic re-authentication
- **Rate limiting**: Intelligent waiting and retry
- **Network issues**: Connection reset and retry
- **Order rejections**: Alternative order parameters
- **Data errors**: Cached data fallback

## Configuration

### API Credentials

```python
credentials = APICredentials(
    api_key="your_api_key",
    client_code="your_client_code", 
    pin="your_pin",
    totp_secret="your_totp_secret"  # Optional for TOTP
)
```

### Connection Configuration

```python
config = ConnectionConfig(
    timeout=10,                    # Request timeout in seconds
    max_retries=3,                # Maximum retry attempts
    rate_limit_per_second=5.0,    # API calls per second limit
    connection_pool_size=10,      # Connection pool size
    enable_ssl=True               # Enable SSL verification
)
```

### Cache Configuration

```python
# Cache TTL settings (in seconds)
cache_ttl = {
    'options_chain': 60,      # 1 minute
    'historical_data': 3600,  # 1 hour  
    'ltp': 5,                 # 5 seconds
    'instruments': 86400      # 24 hours
}
```

## Advanced Features

### Custom Error Handling

```python
from src.api.error_handler import ErrorHandler, APIError, ErrorCategory

error_handler = ErrorHandler()

try:
    result = api_operation()
except Exception as e:
    api_error = error_handler.handle_error(e, "Operation context")
    
    if api_error.category == ErrorCategory.RATE_LIMIT:
        # Handle rate limiting
        time.sleep(api_error.retry_after or 60)
    elif api_error.category == ErrorCategory.AUTHENTICATION:
        # Handle authentication error
        client.authenticate()
```

### Real-time Monitoring with Custom Callbacks

```python
def advanced_price_callback(price_data):
    # Custom processing
    if price_data.ltp > threshold:
        trigger_alert(price_data)
    
    # Store in database
    store_price_data(price_data)

# Start monitoring with custom interval
market_data.start_real_time_monitoring(
    symbols=monitor_symbols,
    callback=advanced_price_callback,
    interval_seconds=1  # 1 second updates
)
```

### Cache Management

```python
# Get cache information
cache_info = market_data.get_cached_data_info()
print(f"Total cached entries: {cache_info['total_entries']}")

# Cleanup expired entries
market_data.cleanup_cache()

# Invalidate specific cache entries
market_data.invalidate_cache("options_chain")

# Clear all cache
market_data.invalidate_cache()
```

## Testing

The module includes comprehensive test suites:

```bash
# Run all tests
python -m pytest tests/test_error_handler.py -v
python -m pytest tests/test_angel_api_client.py -v
python -m pytest tests/test_market_data.py -v

# Run with coverage
python -m pytest tests/ --cov=src/api --cov-report=html
```

## Examples

See the `examples/` directory for complete usage examples:

- `api_client_demo.py`: Comprehensive demo of all features
- `error_handling_demo.py`: Error handling examples
- `market_data_demo.py`: Market data processing examples

## Dependencies

- `requests`: HTTP client library
- `SmartApi`: Angel Broking SmartAPI SDK
- `pyotp`: TOTP generation (optional)
- `pytest`: Testing framework
- `threading`: Multi-threading support

## Security Considerations

- Never hardcode API credentials in source code
- Use environment variables or secure credential storage
- Enable SSL verification in production
- Implement proper logging sanitization
- Follow rate limiting guidelines

## Performance Optimization

- Use connection pooling for high-frequency operations
- Implement intelligent caching strategies
- Monitor and adjust rate limiting based on usage
- Use concurrent processing for multiple operations
- Optimize cache TTL based on data volatility

## Troubleshooting

### Common Issues

1. **Authentication Failures**
   - Verify API credentials
   - Check TOTP secret if using 2FA
   - Ensure proper network connectivity

2. **Rate Limiting**
   - Reduce API call frequency
   - Implement proper retry logic
   - Use caching to minimize API calls

3. **Network Issues**
   - Check internet connectivity
   - Verify firewall settings
   - Increase timeout values if needed

4. **Data Issues**
   - Validate input parameters
   - Check market hours and holidays
   - Verify instrument tokens and symbols

### Debug Mode

Enable debug logging for detailed troubleshooting:

```python
import logging
logging.basicConfig(level=logging.DEBUG)

# API client will log detailed request/response information
```

## Contributing

1. Follow PEP 8 style guidelines
2. Add comprehensive tests for new features
3. Update documentation for API changes
4. Ensure backward compatibility
5. Add proper error handling and logging

## License

This module is part of the Bank Nifty Options Trading System and follows the same licensing terms.