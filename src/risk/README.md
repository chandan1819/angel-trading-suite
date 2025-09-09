# Risk Management Module

The risk management module provides comprehensive risk control capabilities for the Bank Nifty Options Trading System. It includes position sizing, margin validation, daily limits enforcement, and real-time position monitoring.

## Components

### RiskManager

The main risk management class that handles:

- **Trade Validation**: Validates trades against all risk rules before execution
- **Position Sizing**: Calculates appropriate position sizes based on risk parameters
- **Daily Limits**: Enforces daily loss limits and trade count limits
- **Margin Validation**: Validates margin requirements before trade placement
- **Emergency Controls**: Handles emergency stop conditions

#### Key Methods

```python
# Validate a trading signal
result = risk_manager.validate_trade(signal)
if result.is_valid:
    position_size = result.metadata['position_size']
    # Proceed with trade
else:
    # Handle validation failure
    print(f"Trade rejected: {result.message}")

# Calculate position size
size_result = risk_manager.calculate_position_size(signal)
if size_result.is_valid():
    recommended_size = size_result.recommended_size
    margin_required = size_result.margin_required

# Monitor positions for risk alerts
alerts = risk_manager.monitor_positions(active_trades)
for alert in alerts:
    if alert.level == RiskLevel.CRITICAL:
        # Handle critical alert
        handle_critical_alert(alert)

# Check if position should be closed
if risk_manager.should_close_position(trade):
    # Close the position
    close_position(trade)
```

### PositionMonitor

Real-time position monitoring with automatic risk management:

- **Continuous Monitoring**: Monitors positions in real-time
- **Alert Generation**: Generates alerts when risk thresholds are breached
- **Automatic Closure**: Triggers position closure on target/stop-loss hits
- **Position Risk Metrics**: Calculates detailed risk metrics for each position

#### Key Methods

```python
# Start monitoring
position_monitor.start_monitoring()

# Add position to monitoring
position_monitor.add_position(trade)

# Register alert callback
def handle_alert(alert):
    print(f"Risk Alert: {alert.message}")
    
position_monitor.add_alert_callback(handle_alert)

# Register position close callback
def handle_close(trade, reason):
    print(f"Closing position {trade.trade_id}: {reason}")
    order_manager.close_position(trade)
    
position_monitor.add_position_close_callback(handle_close)

# Force close all positions (emergency)
closed_positions = position_monitor.force_close_all_positions("Emergency stop")
```

## Risk Models

### RiskAlert

Represents risk management alerts with different severity levels:

```python
alert = RiskAlert(
    alert_type=RiskAlertType.PROFIT_TARGET_HIT,
    level=RiskLevel.HIGH,
    message="Profit target reached",
    trade_id="TRADE001",
    current_value=2500.0,
    threshold_value=2000.0
)
```

### ValidationResult

Result of trade validation operations:

```python
result = ValidationResult(
    is_valid=True,
    message="Trade validation passed",
    alerts=[],
    metadata={'position_size': 2, 'margin_required': 100000.0}
)
```

### PositionSizeResult

Result of position sizing calculations:

```python
size_result = PositionSizeResult(
    recommended_size=2,
    max_allowed_size=5,
    risk_amount=1000.0,
    margin_required=100000.0,
    confidence_factor=0.8,
    calculation_method="kelly"
)
```

### MarginRequirement

Detailed margin requirement analysis:

```python
margin_req = MarginRequirement(
    total_margin=120000.0,
    span_margin=84000.0,
    exposure_margin=24000.0,
    premium_margin=12000.0,
    available_margin=200000.0,
    margin_utilization=60.0,
    is_sufficient=True,
    buffer_amount=24000.0
)
```

## Configuration

Risk management is configured through the `RiskConfig` class:

```python
risk_config = RiskConfig(
    max_daily_loss=5000.0,          # Maximum daily loss limit
    max_concurrent_trades=3,         # Maximum concurrent positions
    profit_target=2000.0,           # Default profit target per trade
    stop_loss=1000.0,               # Default stop loss per trade
    position_size_method="kelly",    # Position sizing method
    margin_buffer=0.2,              # 20% margin buffer
    max_position_size=5,            # Maximum lots per position
    daily_trade_limit=10,           # Maximum trades per day
    emergency_stop_file="emergency_stop.txt"  # Emergency stop file
)
```

### Position Sizing Methods

1. **Fixed**: Always use 1 lot per trade
2. **Percentage**: Size based on percentage of risk capital
3. **Kelly**: Kelly criterion-based sizing using historical win/loss data

## Emergency Controls

### Emergency Stop File

Create a file named `emergency_stop.txt` (or as configured) to immediately halt all trading:

```bash
touch emergency_stop.txt  # Activate emergency stop
rm emergency_stop.txt     # Deactivate emergency stop
```

When emergency stop is active:
- No new trades are allowed
- All open positions are flagged for closure
- System continues monitoring but blocks new entries

### Daily Limits

The system enforces several daily limits:

- **Daily Loss Limit**: Maximum loss allowed per day
- **Trade Count Limit**: Maximum number of trades per day
- **Position Count Limit**: Maximum concurrent open positions

## Risk Monitoring

### Real-time Monitoring

The position monitor continuously checks:

- Profit target achievement
- Stop loss breaches
- Position timeouts
- Emergency stop conditions
- Daily limit violations

### Risk Metrics

For each position, the system calculates:

- Current P&L and distance to targets
- Greeks exposure (delta, theta, vega, gamma)
- Risk-reward ratios
- Time decay risk
- Volatility risk

### Alert Levels

- **LOW**: Informational alerts
- **MEDIUM**: Warning conditions
- **HIGH**: Immediate attention required
- **CRITICAL**: Emergency action required

## Usage Examples

### Basic Risk Management Setup

```python
from src.risk import RiskManager, PositionMonitor
from src.models.config_models import TradingConfig

# Initialize risk manager
config = TradingConfig()
risk_manager = RiskManager(config)
risk_manager.initialize()

# Initialize position monitor
position_monitor = PositionMonitor(config)
position_monitor.initialize()
position_monitor.start_monitoring()

# Set up callbacks
def handle_risk_alert(alert):
    if alert.level == RiskLevel.CRITICAL:
        # Handle critical situations
        if alert.alert_type == RiskAlertType.STOP_LOSS_HIT:
            print(f"CRITICAL: Stop loss hit for {alert.trade_id}")
        elif alert.alert_type == RiskAlertType.EMERGENCY_STOP:
            print("EMERGENCY STOP ACTIVATED")

def handle_position_close(trade, reason):
    print(f"Closing position {trade.trade_id}: {reason}")
    # Implement actual position closure logic here

position_monitor.add_alert_callback(handle_risk_alert)
position_monitor.add_position_close_callback(handle_position_close)
```

### Trade Validation Workflow

```python
# Validate trade before execution
signal = TradingSignal(...)  # Your trading signal
validation_result = risk_manager.validate_trade(signal)

if validation_result.is_valid:
    # Get recommended position size
    position_size = validation_result.metadata['position_size']
    margin_required = validation_result.metadata['margin_required']
    
    print(f"Trade approved: Size={position_size}, Margin={margin_required}")
    
    # Execute trade
    trade = execute_trade(signal, position_size)
    
    # Add to monitoring
    position_monitor.add_position(trade)
    
else:
    print(f"Trade rejected: {validation_result.message}")
    for alert in validation_result.alerts:
        print(f"  - {alert.alert_type.value}: {alert.message}")
```

### Daily Risk Monitoring

```python
# Get daily risk metrics
daily_metrics = risk_manager.get_daily_metrics()

print(f"Daily P&L: {daily_metrics.total_pnl}")
print(f"Trades: {daily_metrics.trades_count}")
print(f"Win Rate: {daily_metrics.win_rate:.2%}")
print(f"Risk Utilization: {daily_metrics.risk_utilization:.2%}")

if daily_metrics.is_daily_limit_breached:
    print("WARNING: Daily loss limit breached!")

# Check remaining capacity
remaining = daily_metrics.remaining_loss_capacity
print(f"Remaining loss capacity: ₹{remaining}")
```

## Testing

The module includes comprehensive unit tests:

```bash
# Run all risk management tests
python -m pytest tests/test_risk_manager.py -v

# Run position monitor tests
python -m pytest tests/test_position_monitor.py -v

# Run with coverage
python -m pytest tests/test_risk_manager.py tests/test_position_monitor.py --cov=src.risk
```

## Integration

The risk management module integrates with other system components:

- **Trading Manager**: Uses risk manager for trade validation
- **Order Manager**: Receives position close signals from monitor
- **Strategy Manager**: Position sizing affects strategy execution
- **Logging Manager**: Receives risk events for logging
- **Notification Manager**: Receives alerts for notifications

## Best Practices

1. **Always validate trades** before execution
2. **Monitor positions continuously** during market hours
3. **Set appropriate daily limits** based on capital
4. **Use emergency stop file** for immediate halt capability
5. **Review daily metrics** regularly
6. **Test risk controls** in paper mode first
7. **Keep margin buffers** for unexpected volatility
8. **Monitor system alerts** and respond promptly

## Troubleshooting

### Common Issues

1. **Trade validation fails**: Check daily limits, position limits, and emergency stop status
2. **Position monitor not working**: Ensure monitoring is started and callbacks are registered
3. **Margin validation errors**: Check available margin and buffer settings
4. **Emergency stop not working**: Verify file path and permissions

### Debug Information

Enable debug logging to see detailed risk management operations:

```python
import logging
logging.getLogger('src.risk').setLevel(logging.DEBUG)
```

This will show detailed information about:
- Trade validation steps
- Position sizing calculations
- Risk threshold checks
- Alert generation
- Position monitoring activities