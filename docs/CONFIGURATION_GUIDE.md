# Configuration Guide

This guide provides detailed explanations and examples for configuring the Bank Nifty Options Trading System.

## Table of Contents

1. [Configuration File Structure](#configuration-file-structure)
2. [Trading Mode Configuration](#trading-mode-configuration)
3. [API Configuration](#api-configuration)
4. [Risk Management Configuration](#risk-management-configuration)
5. [Strategy Configuration](#strategy-configuration)
6. [Logging Configuration](#logging-configuration)
7. [Notification Configuration](#notification-configuration)
8. [Backtesting Configuration](#backtesting-configuration)
9. [Environment Variables](#environment-variables)
10. [Configuration Examples](#configuration-examples)

## Configuration File Structure

The system uses YAML configuration files with the following main sections:

```yaml
mode: paper                    # Trading mode
underlying_symbol: BANKNIFTY   # Symbol to trade
api: {}                       # API settings
risk: {}                      # Risk management
strategy: {}                  # Strategy settings
logging: {}                   # Logging configuration
notification: {}              # Alert settings
backtest: {}                  # Backtesting parameters
```

## Trading Mode Configuration

### Basic Settings

```yaml
# Trading mode: 'paper' for simulation, 'live' for actual trading
mode: paper

# Underlying symbol to trade (currently supports BANKNIFTY)
underlying_symbol: BANKNIFTY
```

**Options:**
- `paper`: Simulates all trades without placing real orders
- `live`: Places actual orders via Angel Broking API

**Best Practices:**
- Always start with `paper` mode for testing
- Validate all configurations in paper mode before switching to live
- Use paper mode for strategy development and backtesting

## API Configuration

### Basic API Settings

```yaml
api:
  credentials:
    api_key: ${ANGEL_API_KEY}
    client_code: ${ANGEL_CLIENT_CODE}
    pin: ${ANGEL_PIN}
    totp_secret: ${ANGEL_TOTP_SECRET}
  
  base_url: https://apiconnect.angelbroking.com
  timeout: 30
  max_retries: 3
  retry_delay: 1.0
  rate_limit_calls: 100
  rate_limit_period: 60
  connection_pool_size: 10
```

**Parameters Explained:**

- `credentials`: API authentication details (use environment variables)
- `base_url`: Angel Broking API endpoint
- `timeout`: Request timeout in seconds (recommended: 30)
- `max_retries`: Maximum retry attempts for failed requests (recommended: 3)
- `retry_delay`: Initial delay between retries in seconds
- `rate_limit_calls`: Maximum API calls per period (Angel limit: 100)
- `rate_limit_period`: Rate limit period in seconds (60 = 1 minute)
- `connection_pool_size`: HTTP connection pool size for performance

### Advanced API Settings

```yaml
api:
  # Connection settings
  keep_alive: true
  verify_ssl: true
  
  # Retry configuration
  retry_backoff_factor: 2.0
  retry_status_codes: [429, 500, 502, 503, 504]
  
  # Request settings
  user_agent: "BankNiftyTrader/1.0"
  compression: true
```

## Risk Management Configuration

### Basic Risk Settings

```yaml
risk:
  max_daily_loss: 5000.0
  max_concurrent_trades: 3
  profit_target: 2000.0
  stop_loss: 1000.0
  position_size_method: fixed
  margin_buffer: 0.2
  max_position_size: 100
  daily_trade_limit: 10
  emergency_stop_file: emergency_stop.txt
```

**Parameters Explained:**

- `max_daily_loss`: Maximum loss per day in rupees (system stops trading)
- `max_concurrent_trades`: Maximum number of simultaneous open positions
- `profit_target`: Profit target per trade in rupees (₹2,000 recommended)
- `stop_loss`: Stop loss per trade in rupees (₹1,000 recommended)
- `position_size_method`: How to calculate position size (`fixed`, `percentage`, `kelly`)
- `margin_buffer`: Additional margin buffer as percentage (0.2 = 20%)
- `max_position_size`: Maximum quantity per position
- `daily_trade_limit`: Maximum trades per day
- `emergency_stop_file`: File to monitor for emergency stop

### Advanced Risk Settings

```yaml
risk:
  # Position sizing
  position_size_method: percentage
  risk_per_trade: 0.02  # 2% of capital per trade
  kelly_fraction: 0.25  # Kelly criterion fraction
  
  # Advanced limits
  max_sector_exposure: 0.5  # 50% max exposure to single sector
  correlation_limit: 0.7    # Maximum correlation between positions
  
  # Time-based limits
  max_trades_per_hour: 2
  cooldown_period: 300  # 5 minutes between trades
  
  # Volatility-based adjustments
  volatility_adjustment: true
  high_vol_threshold: 0.3
  low_vol_threshold: 0.1
```

## Strategy Configuration

### Global Strategy Settings

```yaml
strategy:
  enabled_strategies:
    - straddle
    - directional
  
  evaluation_interval: 60
  market_start_time: "09:15"
  market_end_time: "15:30"
  timezone: Asia/Kolkata
```

### Straddle Strategy Configuration

```yaml
strategy:
  straddle:
    enabled: true
    weight: 1.0
    min_confidence: 0.6
    
    # IV and volatility filters
    min_iv_rank: 0.5
    max_iv_rank: 0.9
    iv_percentile_threshold: 0.7
    
    # Time and expiry filters
    max_dte: 7
    min_dte: 0
    exit_time_minutes: 30
    
    # Liquidity filters
    min_volume: 100
    min_open_interest: 1000
    max_bid_ask_spread: 5.0
    
    # Entry conditions
    min_underlying_move: 0.01  # 1% minimum move
    volatility_expansion: true
    
    # Exit conditions
    profit_target_multiplier: 1.0  # Use global profit target
    stop_loss_multiplier: 1.0      # Use global stop loss
    time_decay_exit: true
    delta_neutral_exit: false
```

### Directional Strategy Configuration

```yaml
strategy:
  directional:
    enabled: true
    weight: 0.8
    min_confidence: 0.7
    
    # Technical indicators
    ema_period: 20
    atr_period: 14
    atr_multiplier: 2.0
    rsi_period: 14
    
    # Momentum filters
    min_momentum: 0.02
    momentum_lookback: 5
    trend_strength_threshold: 0.6
    
    # Option selection
    target_delta: 0.3
    max_delta: 0.5
    min_theta: -5.0
    
    # Entry conditions
    breakout_confirmation: true
    volume_confirmation: true
    multiple_timeframe: false
```

### Iron Condor Strategy Configuration

```yaml
strategy:
  iron_condor:
    enabled: false
    weight: 0.6
    min_confidence: 0.5
    
    # Spread configuration
    wing_distance: 200
    call_strike_distance: 100
    put_strike_distance: 100
    
    # Market conditions
    max_dte: 30
    min_dte: 7
    low_volatility_threshold: 0.2
    
    # Greeks targets
    target_delta: 0.15
    max_gamma: 0.01
    min_theta: -20.0
    
    # Profit/Loss management
    profit_target_percentage: 0.5  # 50% of max profit
    loss_limit_percentage: 2.0     # 200% of credit received
    
    # Adjustment rules
    delta_adjustment_threshold: 0.3
    gamma_adjustment_threshold: 0.02
    adjustment_frequency: daily
```

### Greeks Strategy Configuration

```yaml
strategy:
  greeks:
    enabled: false
    weight: 0.7
    min_confidence: 0.6
    
    # Target Greeks
    target_delta: 0.3
    max_delta: 0.5
    min_delta: 0.1
    
    max_theta: -10.0
    min_theta: -50.0
    
    min_vega: 5.0
    max_vega: 30.0
    
    max_gamma: 0.01
    
    # Greeks-based signals
    delta_momentum: true
    theta_decay_acceleration: true
    vega_volatility_mismatch: true
    gamma_scalping: false
    
    # Risk management
    delta_hedge_threshold: 0.1
    gamma_hedge_threshold: 0.005
    vega_hedge_threshold: 10.0
```

### Volatility Strategy Configuration

```yaml
strategy:
  volatility:
    enabled: false
    weight: 0.5
    min_confidence: 0.6
    
    # Volatility metrics
    iv_percentile_threshold: 0.8
    iv_rank_threshold: 0.7
    min_iv_rank: 0.2
    volatility_lookback: 30
    
    # Volatility regime detection
    regime_detection: true
    high_vol_threshold: 0.4
    low_vol_threshold: 0.15
    
    # Mean reversion
    mean_reversion_period: 20
    reversion_threshold: 2.0  # Standard deviations
    
    # Volatility trading
    buy_low_iv: true
    sell_high_iv: true
    volatility_spread_trading: false
    
    # Calendar spreads
    calendar_spread_enabled: false
    front_month_dte: 7
    back_month_dte: 35
```

## Logging Configuration

### Basic Logging Settings

```yaml
logging:
  level: INFO
  log_dir: logs
  log_file: trading.log
  max_file_size: 10485760  # 10MB
  backup_count: 5
  format: "%(asctime)s - %(name)s - %(levelname)s - %(message)s"
  date_format: "%Y-%m-%d %H:%M:%S"
  enable_console: true
  enable_file: true
  enable_json: true
  json_file: trading.json
```

### Advanced Logging Settings

```yaml
logging:
  # Structured logging
  structured_logging: true
  log_format: json
  
  # Component-specific levels
  component_levels:
    api: DEBUG
    strategy: INFO
    risk: WARNING
    orders: INFO
    data: ERROR
  
  # Log rotation
  rotation_when: midnight
  rotation_interval: 1
  rotation_backup_count: 30
  
  # Performance logging
  performance_logging: true
  slow_query_threshold: 1.0  # Log queries > 1 second
  
  # Security logging
  sanitize_logs: true
  log_api_requests: false  # Never log API keys
  audit_logging: true
```

## Notification Configuration

### Basic Notification Settings

```yaml
notification:
  enabled: false
  types: []  # webhook, email, slack, telegram
  
  # Notification conditions
  notify_on_trade_entry: true
  notify_on_trade_exit: true
  notify_on_profit_target: true
  notify_on_stop_loss: true
  notify_on_daily_limit: true
  notify_on_error: true
```

### Webhook Configuration

```yaml
notification:
  enabled: true
  types: [webhook]
  
  webhook_url: "https://your-webhook-url.com/trading-alerts"
  webhook_timeout: 10
  webhook_retries: 3
  webhook_headers:
    Authorization: "Bearer ${WEBHOOK_TOKEN}"
    Content-Type: "application/json"
```

### Email Configuration

```yaml
notification:
  enabled: true
  types: [email]
  
  email_smtp_server: "smtp.gmail.com"
  email_smtp_port: 587
  email_username: "your-email@gmail.com"
  email_password: "${EMAIL_PASSWORD}"
  email_to: ["trader@example.com", "risk@example.com"]
  email_from: "trading-system@example.com"
  email_subject_prefix: "[Trading Alert]"
```

### Slack Configuration

```yaml
notification:
  enabled: true
  types: [slack]
  
  slack_webhook_url: "${SLACK_WEBHOOK_URL}"
  slack_channel: "#trading-alerts"
  slack_username: "Trading Bot"
  slack_icon_emoji: ":chart_with_upwards_trend:"
```

### Telegram Configuration

```yaml
notification:
  enabled: true
  types: [telegram]
  
  telegram_bot_token: "${TELEGRAM_BOT_TOKEN}"
  telegram_chat_id: "${TELEGRAM_CHAT_ID}"
  telegram_parse_mode: "Markdown"
```

## Backtesting Configuration

### Basic Backtesting Settings

```yaml
backtest:
  start_date: ""
  end_date: ""
  initial_capital: 100000.0
  commission_per_trade: 20.0
  slippage: 0.5
  data_source: angel_api
  output_dir: backtest_results
  generate_csv: true
  generate_json: true
```

### Advanced Backtesting Settings

```yaml
backtest:
  # Market simulation
  realistic_fills: true
  market_impact: 0.001  # 0.1% market impact
  bid_ask_spread_simulation: true
  
  # Performance metrics
  benchmark_symbol: "NIFTY"
  risk_free_rate: 0.06  # 6% annual
  calculate_sharpe: true
  calculate_sortino: true
  calculate_calmar: true
  
  # Reporting
  generate_equity_curve: true
  generate_drawdown_chart: true
  generate_trade_analysis: true
  detailed_logs: true
  
  # Optimization
  parameter_optimization: false
  optimization_metric: "sharpe_ratio"
  walk_forward_analysis: false
```

## Environment Variables

Set these environment variables for secure credential management:

```bash
# Angel Broking API credentials
export ANGEL_API_KEY="your_api_key_here"
export ANGEL_CLIENT_CODE="your_client_code_here"
export ANGEL_PIN="your_pin_here"
export ANGEL_TOTP_SECRET="your_totp_secret_here"

# Notification credentials
export EMAIL_PASSWORD="your_email_password"
export SLACK_WEBHOOK_URL="https://hooks.slack.com/services/..."
export TELEGRAM_BOT_TOKEN="your_telegram_bot_token"
export TELEGRAM_CHAT_ID="your_telegram_chat_id"
export WEBHOOK_TOKEN="your_webhook_auth_token"

# Database credentials (if using external database)
export DB_HOST="localhost"
export DB_PORT="5432"
export DB_NAME="trading_db"
export DB_USER="trading_user"
export DB_PASSWORD="your_db_password"
```

## Configuration Examples

### Conservative Trading Configuration

```yaml
mode: paper
underlying_symbol: BANKNIFTY

risk:
  max_daily_loss: 2000.0
  max_concurrent_trades: 1
  profit_target: 1000.0
  stop_loss: 500.0
  position_size_method: fixed
  max_position_size: 25

strategy:
  enabled_strategies: [straddle]
  
  straddle:
    enabled: true
    min_confidence: 0.8
    min_iv_rank: 0.7
    max_dte: 3
    exit_time_minutes: 60
    min_volume: 500
```

### Aggressive Trading Configuration

```yaml
mode: live
underlying_symbol: BANKNIFTY

risk:
  max_daily_loss: 10000.0
  max_concurrent_trades: 5
  profit_target: 3000.0
  stop_loss: 1500.0
  position_size_method: percentage
  risk_per_trade: 0.03

strategy:
  enabled_strategies: [straddle, directional, volatility]
  
  straddle:
    enabled: true
    min_confidence: 0.6
    min_iv_rank: 0.4
    max_dte: 7
  
  directional:
    enabled: true
    min_confidence: 0.7
    min_momentum: 0.015
  
  volatility:
    enabled: true
    iv_percentile_threshold: 0.6
```

### Backtesting Configuration

```yaml
mode: paper
underlying_symbol: BANKNIFTY

backtest:
  initial_capital: 500000.0
  commission_per_trade: 40.0
  slippage: 1.0
  realistic_fills: true
  generate_csv: true
  generate_json: true
  detailed_logs: true

strategy:
  enabled_strategies: [straddle]
  
  straddle:
    enabled: true
    min_confidence: 0.5
    min_iv_rank: 0.3
    max_dte: 14
```

### Paper Trading Configuration

```yaml
mode: paper
underlying_symbol: BANKNIFTY

api:
  timeout: 60
  max_retries: 5

risk:
  max_daily_loss: 50000.0
  max_concurrent_trades: 10
  profit_target: 2000.0
  stop_loss: 1000.0

logging:
  level: DEBUG
  enable_console: true
  enable_file: true

notification:
  enabled: true
  types: [webhook]
  webhook_url: "https://your-test-webhook.com"
```

## Configuration Validation

The system automatically validates configuration files. Common validation errors:

### Missing Required Fields
```
Error: Missing required field 'api.credentials.api_key'
Solution: Add the missing field or set environment variable
```

### Invalid Values
```
Error: risk.profit_target must be positive
Solution: Set profit_target to a positive value (e.g., 2000.0)
```

### Conflicting Settings
```
Error: Cannot enable live mode without valid API credentials
Solution: Set all required environment variables or use paper mode
```

## Best Practices

1. **Start with Paper Mode**: Always test configurations in paper mode first
2. **Use Environment Variables**: Never hardcode credentials in configuration files
3. **Validate Regularly**: Use `python main.py config --validate` to check configurations
4. **Backup Configurations**: Keep versioned backups of working configurations
5. **Monitor Logs**: Regularly check logs for warnings and errors
6. **Test Emergency Procedures**: Verify emergency stop mechanisms work correctly
7. **Gradual Scaling**: Start with small position sizes and gradually increase
8. **Regular Reviews**: Periodically review and update risk parameters

## Troubleshooting

### Configuration Not Loading
- Check file path and permissions
- Validate YAML syntax
- Ensure environment variables are set

### API Connection Issues
- Verify credentials are correct
- Check network connectivity
- Ensure API limits are not exceeded

### Strategy Not Executing
- Check if strategy is enabled
- Verify market hours configuration
- Check minimum confidence thresholds

### Risk Limits Triggered
- Review daily loss limits
- Check position size calculations
- Verify margin requirements