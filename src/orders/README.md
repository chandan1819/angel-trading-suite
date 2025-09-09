# Order Management System

The Order Management System provides comprehensive order lifecycle management for the Bank Nifty Options Trading System. It includes order placement, validation, tracking, position monitoring, and sophisticated retry mechanisms.

## Components

### 1. OrderManager
The main orchestrator for all order-related operations.

**Features:**
- Order placement with validation
- Support for both paper and live trading modes
- Order tracking and status monitoring
- OCO (One-Cancels-Other) order support
- Integration with retry and fallback mechanisms

**Usage:**
```python
from src.orders import OrderManager, OrderRequest, OrderType, OrderAction

# Initialize
order_manager = OrderManager(api_client, config, mode="paper")

# Create order
order = OrderRequest(
    symbol="BANKNIFTY2412545000CE",
    token="12345",
    exchange="NFO",
    action=OrderAction.BUY,
    order_type=OrderType.LIMIT,
    quantity=25,
    price=100.0
)

# Place order
response = order_manager.place_order(order)
if response.is_success:
    print(f"Order placed: {response.order_id}")
```

### 2. OrderValidator
Comprehensive pre-trade validation system.

**Validation Checks:**
- Basic parameter validation
- Market hours validation
- Symbol and contract validation
- Price reasonableness checks
- Quantity and lot size compliance
- Market condition validation (bid-ask spread, volume, OI)

**Usage:**
```python
from src.orders import OrderValidator

validator = OrderValidator(config)
validation_result = validator.validate_order(order, current_ltp, market_data)

if validation_result.is_valid:
    # Proceed with order placement
    pass
else:
    print(f"Validation failed: {validation_result.message}")
```

### 3. PositionMonitor
Real-time position monitoring and risk management.

**Features:**
- Real-time P&L calculation
- Automatic target and stop-loss monitoring
- Risk limit enforcement
- Trade lifecycle management
- Performance metrics tracking

**Usage:**
```python
from src.orders import PositionMonitor

monitor = PositionMonitor(order_manager, config)
monitor.start_monitoring()

# Add trade for monitoring
monitor.add_trade(trade)

# Get position summary
summary = monitor.get_position_summary()
print(f"Total P&L: ₹{summary['total_unrealized_pnl']:.2f}")
```

### 4. OrderRetryHandler
Advanced retry and fallback mechanisms.

**Features:**
- Multiple retry strategies (exponential, linear, fixed delay)
- Intelligent fallback actions based on error types
- Partial fill handling
- Price adjustment strategies
- Manual intervention triggers

**Retry Strategies:**
- **Exponential Backoff**: Delay increases exponentially
- **Linear Backoff**: Delay increases linearly
- **Fixed Delay**: Constant delay between retries
- **Immediate**: No delay between retries

**Fallback Actions:**
- **Price Adjustment**: Adjust order price to improve execution
- **Convert to Market**: Convert limit orders to market orders
- **Quantity Reduction**: Reduce order quantity
- **Order Splitting**: Split large orders into smaller ones
- **Manual Intervention**: Trigger manual review

**Usage:**
```python
from src.orders import OrderRetryHandler, RetryConfig, FallbackConfig

retry_config = RetryConfig(
    strategy=RetryStrategy.EXPONENTIAL_BACKOFF,
    max_attempts=3,
    base_delay=1.0
)

fallback_config = FallbackConfig(
    enabled=True,
    max_price_adjustment=0.05
)

retry_handler = OrderRetryHandler(retry_config, fallback_config)

# Execute with retry
response = retry_handler.execute_with_retry(order, execute_function)
```

### 5. PartialFillHandler
Specialized handling for partial order fills.

**Completion Strategies:**
- **Immediate**: Try to complete remaining quantity immediately
- **Time-based**: Complete based on elapsed time
- **Price-based**: Complete based on price movement
- **Cancel Remaining**: Cancel remaining quantity

## Data Models

### OrderRequest
Represents an order to be placed.

```python
order = OrderRequest(
    symbol="BANKNIFTY2412545000CE",
    token="12345",
    exchange="NFO",
    action=OrderAction.BUY,
    order_type=OrderType.LIMIT,
    quantity=25,
    price=100.0,
    validity=OrderValidity.DAY,
    product="MIS"
)
```

### OrderResponse
Response from order placement.

```python
response = OrderResponse(
    order_id="ORDER_123",
    status=OrderStatus.COMPLETE,
    message="Order executed successfully"
)
```

### Position
Represents a trading position.

```python
position = Position(
    symbol="BANKNIFTY2412545000CE",
    token="12345",
    exchange="NFO",
    product="MIS",
    quantity=25,
    average_price=100.0,
    ltp=110.0
)
```

## Configuration

### Order Manager Configuration
```yaml
validation:
  lot_size: 25
  max_order_value: 1000000
  min_price: 0.05
  max_price: 10000
  price_tolerance: 0.20
  min_volume: 100
  min_open_interest: 50

retry:
  strategy: "exponential_backoff"
  max_attempts: 3
  base_delay: 1.0
  max_delay: 30.0
  backoff_multiplier: 2.0

fallback:
  enabled: true
  max_price_adjustment: 0.05
  min_quantity_reduction: 1
  split_threshold: 100
  manual_intervention_threshold: 5

monitoring_interval: 30
```

### Position Monitor Configuration
```yaml
default_target_pnl: 2000.0
default_stop_loss: -1000.0
max_daily_loss: -5000.0
position_timeout_hours: 6
monitoring_interval: 30
price_update_interval: 10
auto_close_on_target: true
auto_close_on_stop: true
auto_place_oco_orders: true
```

## Error Handling

The system provides comprehensive error handling with categorized errors:

### Order Validation Errors
- `VALIDATION_ERROR`: Basic parameter validation failed
- `MARKET_HOURS_ERROR`: Trading outside market hours
- `SYMBOL_ERROR`: Invalid symbol or contract
- `PRICE_ERROR`: Price outside acceptable range
- `QUANTITY_ERROR`: Invalid quantity or lot size

### Order Placement Errors
- `API_PLACEMENT_ERROR`: API call failed
- `NETWORK_ERROR`: Network connectivity issues
- `RATE_LIMIT_ERROR`: API rate limits exceeded
- `AUTHENTICATION_ERROR`: API authentication failed

### Position Monitoring Errors
- `POSITION_NOT_FOUND`: Position not found for monitoring
- `PRICE_UPDATE_ERROR`: Failed to update position prices
- `RISK_LIMIT_BREACH`: Risk limits exceeded

## Testing

The system includes comprehensive test coverage:

### Unit Tests
- `test_order_manager.py`: OrderManager functionality
- `test_order_retry.py`: Retry and fallback mechanisms

### Integration Tests
- `test_order_integration.py`: Complete workflow testing

**Run Tests:**
```bash
python -m pytest tests/test_order_manager.py -v
python -m pytest tests/test_order_retry.py -v
python -m pytest tests/test_order_integration.py -v
```

## Performance Considerations

### Latency Requirements
- Order validation: < 1 second
- Order placement: < 3 seconds
- Position monitoring: < 30 seconds
- Price updates: < 10 seconds

### Scalability
- Supports concurrent order processing
- Efficient position monitoring for multiple trades
- Optimized retry mechanisms to minimize API calls

### Memory Usage
- Efficient data structures for order tracking
- Configurable history retention
- Automatic cleanup of completed orders

## Security

### Credential Protection
- No hardcoded API credentials
- Secure logging (sanitized sensitive data)
- Environment variable configuration

### Data Validation
- Input sanitization for all order parameters
- SQL injection prevention (if using database)
- Rate limiting compliance

## Monitoring and Alerting

### Metrics Tracked
- Order success/failure rates
- Retry statistics
- Position P&L metrics
- Risk limit breaches
- System performance metrics

### Alerts
- Risk limit breaches
- Order execution failures
- System errors
- Performance degradation

## Best Practices

### Order Placement
1. Always validate orders before placement
2. Use appropriate order types for market conditions
3. Implement proper error handling
4. Monitor order status until completion

### Position Management
1. Set appropriate target and stop-loss levels
2. Monitor positions in real-time
3. Implement emergency stop mechanisms
4. Track performance metrics

### Risk Management
1. Enforce daily loss limits
2. Limit position sizes
3. Monitor margin requirements
4. Implement circuit breakers

### Error Recovery
1. Use retry mechanisms for transient errors
2. Implement fallback strategies
3. Log all errors for analysis
4. Have manual intervention procedures

## Troubleshooting

### Common Issues

**Order Validation Failures**
- Check lot size compliance
- Verify price within acceptable range
- Ensure market is open
- Validate symbol format

**Order Placement Failures**
- Check API connectivity
- Verify authentication
- Check rate limits
- Review error messages

**Position Monitoring Issues**
- Verify position data accuracy
- Check price update frequency
- Review risk calculations
- Monitor system resources

### Debug Mode
Enable debug logging for detailed troubleshooting:

```python
import logging
logging.getLogger('src.orders').setLevel(logging.DEBUG)
```

## Future Enhancements

### Planned Features
1. Advanced order types (iceberg, hidden, etc.)
2. Multi-exchange support
3. Portfolio-level risk management
4. Machine learning-based retry optimization
5. Real-time performance analytics
6. Advanced position sizing algorithms

### Performance Optimizations
1. Async order processing
2. Batch order operations
3. Caching mechanisms
4. Database integration for persistence
5. Distributed processing support