# Bank Nifty Options Trading System - CLI Usage Guide

This document provides comprehensive usage instructions for the Bank Nifty Options Trading System command-line interface.

## Quick Start

### Basic Trading Session

```bash
# Run paper trading session (safe mode)
python3 main.py trade --mode paper --continuous --interval 30

# Run single evaluation in live mode
python3 main.py trade --mode live --once

# Run with specific strategies only
python3 main.py trade --mode paper --strategies straddle directional --continuous
```

### Configuration Management

```bash
# Create default configuration
python3 main.py config --create-default

# Validate existing configuration
python3 main.py config --validate

# Show current configuration
python3 main.py config --show
```

### Backtesting

```bash
# Backtest all strategies for 2024
python3 main.py backtest --strategy all --start 2024-01-01 --end 2024-12-31

# Backtest specific strategy
python3 main.py backtest --strategy straddle --start 2024-06-01 --end 2024-12-31 --output-dir results/
```

## Command Reference

### Global Options

| Option | Description | Default |
|--------|-------------|---------|
| `--config`, `-c` | Configuration file path | `trading_config.yaml` |
| `--log-level` | Logging level (DEBUG, INFO, WARNING, ERROR, CRITICAL) | `INFO` |
| `--log-file` | Log file path (optional) | Console only |

### Trade Command

Start a trading session with various modes and options.

```bash
python3 main.py trade [OPTIONS]
```

#### Trading Mode Options

| Option | Description |
|--------|-------------|
| `--mode`, `-m` | Trading mode: `paper` (simulation) or `live` (real trading) |

#### Execution Mode Options (Mutually Exclusive)

| Option | Description |
|--------|-------------|
| `--continuous` | Run continuously with polling intervals |
| `--once` | Execute single evaluation and exit |

#### Trading Parameters

| Option | Description | Default |
|--------|-------------|---------|
| `--interval`, `-i` | Polling interval in seconds (continuous mode) | `30` |
| `--strategies` | Specific strategies to enable | All enabled in config |
| `--max-trades` | Maximum concurrent trades | From config |
| `--daily-loss-limit` | Daily loss limit in rupees | From config |
| `--emergency-stop-file` | Emergency stop file path | `emergency_stop.txt` |

#### Available Strategies

- `straddle` - Short intraday straddle/strangle
- `directional` - Single-leg directional trades
- `iron_condor` - Defined-risk spreads
- `greeks` - Greeks-based momentum entry
- `volatility` - IV rank-based trades

#### Examples

```bash
# Paper trading with 60-second intervals
python3 main.py trade --mode paper --continuous --interval 60

# Live trading with only straddle strategy
python3 main.py trade --mode live --strategies straddle --continuous

# Single evaluation with custom loss limit
python3 main.py trade --mode paper --once --daily-loss-limit 5000

# Override maximum concurrent trades
python3 main.py trade --mode paper --continuous --max-trades 2
```

### Backtest Command

Run historical backtesting on strategies.

```bash
python3 main.py backtest [OPTIONS]
```

#### Required Options

| Option | Description |
|--------|-------------|
| `--start`, `-s` | Start date (YYYY-MM-DD) |
| `--end`, `-e` | End date (YYYY-MM-DD) |

#### Optional Parameters

| Option | Description | Default |
|--------|-------------|---------|
| `--strategy` | Strategy to test (`all`, `straddle`, `directional`, etc.) | `all` |
| `--output-dir` | Output directory for results | `backtest_results` |
| `--initial-capital` | Initial capital for backtesting | `100000` |
| `--format` | Output format (`csv`, `json`, `both`) | `both` |

#### Examples

```bash
# Backtest all strategies for 6 months
python3 main.py backtest --start 2024-06-01 --end 2024-12-31

# Backtest straddle strategy with custom capital
python3 main.py backtest --strategy straddle --start 2024-01-01 --end 2024-06-30 --initial-capital 200000

# Generate only CSV output
python3 main.py backtest --strategy directional --start 2024-09-01 --end 2024-12-31 --format csv
```

### Config Command

Manage configuration files.

```bash
python3 main.py config [OPTIONS]
```

#### Configuration Operations (Mutually Exclusive)

| Option | Description |
|--------|-------------|
| `--create-default` | Create default configuration file |
| `--validate` | Validate existing configuration |
| `--show` | Display current configuration |

#### Optional Parameters

| Option | Description |
|--------|-------------|
| `--output` | Output file for configuration operations |

#### Examples

```bash
# Create default config with custom name
python3 main.py config --create-default --output my_config.yaml

# Validate specific config file
python3 main.py --config custom_config.yaml config --validate

# Show configuration in readable format
python3 main.py config --show
```

### Status Command

Monitor system status and performance.

```bash
python3 main.py status [OPTIONS]
```

#### Status Options

| Option | Description |
|--------|-------------|
| `--detailed` | Show detailed status information |
| `--refresh` | Auto-refresh interval in seconds |

#### Examples

```bash
# Show current status
python3 main.py status

# Show detailed status with all metrics
python3 main.py status --detailed

# Continuous monitoring with 10-second refresh
python3 main.py status --refresh 10
```

## Configuration File

The system uses YAML configuration files. Here's a sample structure:

```yaml
# Trading mode: paper or live
mode: paper

# API configuration
api:
  timeout: 30
  max_retries: 3
  credentials:
    api_key: "${ANGEL_API_KEY}"
    client_code: "${ANGEL_CLIENT_CODE}"
    pin: "${ANGEL_PIN}"
    totp_secret: "${ANGEL_TOTP_SECRET}"

# Risk management
risk:
  max_daily_loss: 10000.0
  max_concurrent_trades: 5
  profit_target: 2000.0
  stop_loss: 1000.0
  position_size_method: "percentage"
  emergency_stop_file: "emergency_stop.txt"

# Strategy configuration
strategy:
  straddle:
    enabled: true
    min_iv_rank: 30
    max_iv_rank: 80
    min_dte: 0
    max_dte: 7
  
  directional:
    enabled: true
    ema_period: 20
    atr_period: 14
    momentum_threshold: 0.02

# Logging configuration
logging:
  level: INFO
  enable_console: true
  enable_file: true
  log_directory: "logs"
  max_file_size: 10485760  # 10MB
  backup_count: 5

# Notification settings
notification:
  enabled: true
  types: ["webhook"]
  webhook_url: "https://your-webhook-url.com"
```

## Environment Variables

Set these environment variables for secure credential management:

```bash
export ANGEL_API_KEY="your_api_key"
export ANGEL_CLIENT_CODE="your_client_code"
export ANGEL_PIN="your_pin"
export ANGEL_TOTP_SECRET="your_totp_secret"
```

## Emergency Controls

### Emergency Stop File

Create an emergency stop file to immediately halt all trading:

```bash
# Create emergency stop
echo "Manual emergency stop" > emergency_stop.txt

# Remove emergency stop
rm emergency_stop.txt
```

### Safety Mechanisms

The system includes multiple safety mechanisms:

1. **Daily Loss Limits** - Automatic shutdown when daily loss exceeds configured limit
2. **Position Limits** - Maximum concurrent positions enforcement
3. **Market Hours** - Trading only during market hours
4. **System Resources** - Monitoring CPU, memory, and disk usage
5. **API Health** - Monitoring API connectivity and response times

## Logging and Monitoring

### Log Files

Logs are stored in the `logs/` directory with the following structure:

```
logs/
├── 2024-12-09/
│   ├── app.log              # Main application log
│   ├── trades.log           # Trade execution log
│   ├── errors.log           # Error log
│   └── performance.log      # Performance metrics
```

### Log Levels

- `DEBUG` - Detailed debugging information
- `INFO` - General information about system operation
- `WARNING` - Warning messages for potential issues
- `ERROR` - Error messages for failures
- `CRITICAL` - Critical errors requiring immediate attention

### Monitoring Status

Use the status command to monitor:

- Session state and duration
- Active trades and P&L
- Strategy performance
- System resource usage
- Emergency status

## Troubleshooting

### Common Issues

1. **Import Errors**
   ```bash
   # Ensure you're in the correct directory
   cd /path/to/banknifty-options-trading
   python3 main.py --help
   ```

2. **Configuration Errors**
   ```bash
   # Validate configuration
   python3 main.py config --validate
   
   # Create new default config
   python3 main.py config --create-default
   ```

3. **API Connection Issues**
   ```bash
   # Check environment variables
   echo $ANGEL_API_KEY
   
   # Test with paper mode first
   python3 main.py trade --mode paper --once
   ```

4. **Permission Errors**
   ```bash
   # Ensure proper file permissions
   chmod +x main.py
   
   # Check log directory permissions
   mkdir -p logs
   chmod 755 logs
   ```

### Debug Mode

Enable debug logging for troubleshooting:

```bash
python3 main.py --log-level DEBUG trade --mode paper --once
```

### Emergency Recovery

If the system becomes unresponsive:

1. Create emergency stop file: `touch emergency_stop.txt`
2. Use Ctrl+C to interrupt the process
3. Check logs for error details
4. Restart with paper mode for testing

## Best Practices

### Development and Testing

1. **Always start with paper mode** for testing new configurations
2. **Use single evaluation mode** (`--once`) for initial testing
3. **Validate configuration** before starting live trading
4. **Monitor logs** regularly for warnings and errors
5. **Test emergency procedures** in paper mode

### Production Trading

1. **Set appropriate risk limits** based on your capital
2. **Monitor system resources** and performance
3. **Keep emergency stop file** easily accessible
4. **Regular backups** of configuration and logs
5. **Test disaster recovery** procedures periodically

### Security

1. **Use environment variables** for credentials
2. **Secure configuration files** with proper permissions
3. **Regular credential rotation** as per security policy
4. **Monitor access logs** for unauthorized access
5. **Encrypt sensitive data** at rest

## Support and Documentation

For additional help:

1. Check the main README.md for system overview
2. Review configuration examples in `config/` directory
3. Examine test files for usage patterns
4. Check logs for detailed error information

## Version Information

This CLI interface is part of the Bank Nifty Options Trading System v1.0.

For updates and bug reports, please refer to the project repository.