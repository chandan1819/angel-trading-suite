# Logging and Monitoring Module

This module provides comprehensive logging, trade reporting, analytics, and notification capabilities for the Bank Nifty Options Trading System.

## Components

### LoggingManager
Handles structured logging in JSON and CSV formats with automatic sanitization of sensitive data.

**Features:**
- Structured JSON logging for system events
- Automatic log rotation and cleanup
- Sensitive data sanitization (API keys, credentials)
- Multiple log levels and configurable formats
- Daily log organization

**Usage:**
```python
from src.logging import LoggingManager
from src.models.config_models import LoggingConfig

config = LoggingConfig(log_directory="logs", log_level="INFO")
logger = LoggingManager(config)

# Log system events
logger.log_system_event("STRATEGY_EVALUATION", "Evaluating strategies", {"count": 5})

# Log trade events
logger.log_trade_event(trade, "TRADE_OPENED")

# Log errors
logger.log_error(exception, "order_placement", {"order_id": "12345"})
```

### TradeReporter
Manages trade ledger and generates detailed trading reports.

**Features:**
- Detailed trade ledger with all transaction records
- CSV export functionality for external analysis
- Daily summary report generation
- P&L tracking and performance metrics
- Trade history management

**Usage:**
```python
from src.logging import TradeReporter
from src.models.config_models import LoggingConfig

config = LoggingConfig(log_directory="logs")
reporter = TradeReporter(config)

# Record trade events
reporter.record_trade_entry(trade)
reporter.record_trade_update(trade)
reporter.record_trade_exit(trade)

# Export trades to CSV
export_path = reporter.export_trades_csv(start_date=date(2024, 1, 1))

# Generate daily summary
summary = reporter.generate_daily_summary()
```

### AnalyticsEngine
Calculates comprehensive trading performance metrics and analytics.

**Features:**
- Win rate and profit factor calculations
- Drawdown analysis (maximum drawdown, percentage)
- Risk-adjusted returns (Sharpe ratio, Calmar ratio)
- Strategy-specific performance comparison
- Monthly and yearly performance breakdowns
- Advanced metrics (consecutive streaks, volatility, expectancy)

**Usage:**
```python
from src.logging import AnalyticsEngine
from pathlib import Path

analytics = AnalyticsEngine(Path("logs/reports/trade_ledger.csv"))

# Calculate overall performance
metrics = analytics.calculate_performance_metrics()
print(f"Win Rate: {metrics.win_rate}%")
print(f"Total P&L: ₹{metrics.total_pnl:,.2f}")
print(f"Sharpe Ratio: {metrics.sharpe_ratio}")

# Compare strategies
strategy_comparison = analytics.calculate_strategy_comparison()

# Monthly performance
monthly_data = analytics.calculate_monthly_performance(2024)
```

### NotificationManager
Sends alerts and notifications through multiple channels.

**Features:**
- Multiple notification channels (webhook, email, Slack, Telegram)
- Configurable alert conditions and thresholds
- Rich message formatting with emojis and colors
- Rate limiting to prevent spam
- Error handling and retry logic

**Usage:**
```python
from src.logging import NotificationManager
from src.models.config_models import NotificationConfig, NotificationType

config = NotificationConfig(
    enabled=True,
    types=[NotificationType.SLACK, NotificationType.WEBHOOK],
    slack_webhook_url="https://hooks.slack.com/...",
    webhook_url="https://example.com/webhook"
)

notifier = NotificationManager(config)

# Send trade notifications
notifier.send_trade_entry_notification(trade)
notifier.send_profit_target_notification(trade)
notifier.send_stop_loss_notification(trade)

# Send system alerts
notifier.send_error_notification(exception, "order_placement")
notifier.send_daily_limit_notification("daily_loss", 5500.0, 5000.0)

# Test notifications
results = notifier.test_notifications()
```

## Configuration

All components use the `LoggingConfig` and `NotificationConfig` from the config models:

```python
from src.models.config_models import LoggingConfig, NotificationConfig, NotificationType

# Logging configuration
logging_config = LoggingConfig(
    log_level="INFO",
    log_directory="logs",
    console_logging=True,
    enable_json=True,
    enable_csv=True
)

# Notification configuration
notification_config = NotificationConfig(
    enabled=True,
    types=[NotificationType.SLACK, NotificationType.EMAIL],
    slack_webhook_url="https://hooks.slack.com/...",
    email_smtp_server="smtp.gmail.com",
    email_username="your-email@gmail.com",
    email_to=["alerts@yourcompany.com"],
    notify_on_trade_entry=True,
    notify_on_profit_target=True,
    notify_on_stop_loss=True,
    notify_on_error=True
)
```

## File Structure

The logging system creates the following directory structure:

```
logs/
├── 2024-12-26/           # Daily log directories
│   ├── system.log        # System events (JSON format)
│   ├── errors.log        # Error logs (JSON format)
│   └── ...
├── reports/
│   ├── trade_ledger.csv  # Complete trade ledger
│   ├── daily_summary_20241226.json
│   └── trades_export_*.csv
└── ...
```

## Security Features

- **Data Sanitization**: Automatically removes sensitive information (API keys, passwords) from logs
- **Secure Credentials**: Supports environment variables and encrypted storage for notification credentials
- **Access Control**: File permissions and secure logging practices
- **Rate Limiting**: Prevents notification spam and abuse

## Performance Metrics

The analytics engine calculates the following key metrics:

- **Basic Metrics**: Total trades, win rate, profit factor, total P&L
- **Risk Metrics**: Maximum drawdown, Sharpe ratio, Calmar ratio, volatility
- **Trade Analysis**: Average win/loss, best/worst trades, consecutive streaks
- **Time Analysis**: Average holding period, monthly/yearly performance
- **Strategy Comparison**: Performance breakdown by strategy

## Integration

The logging and monitoring system integrates seamlessly with other trading system components:

- **Strategy Manager**: Logs strategy signals and evaluations
- **Order Manager**: Tracks order placement and execution
- **Risk Manager**: Monitors risk thresholds and violations
- **Trading Manager**: Coordinates all logging activities

## Testing

Comprehensive unit tests are provided for all components:

```bash
# Run all logging tests
python -m pytest tests/test_logging_manager.py
python -m pytest tests/test_trade_reporter.py
python -m pytest tests/test_analytics_engine.py
python -m pytest tests/test_notification_manager.py
```

## Requirements

The logging module requires the following dependencies:

- `requests` - For webhook and API notifications
- `pandas` - For data analysis (optional)
- `numpy` - For mathematical calculations (optional)

For email notifications:
- Standard library `smtplib` and `email` modules

For Slack/Telegram notifications:
- `requests` for webhook calls

All dependencies are included in the main project requirements.