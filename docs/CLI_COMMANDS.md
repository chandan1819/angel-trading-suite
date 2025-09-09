# CLI Commands Reference

Complete reference for all command-line interface commands and options in the Bank Nifty Options Trading System.

## Table of Contents

1. [Global Options](#global-options)
2. [Trade Command](#trade-command)
3. [Backtest Command](#backtest-command)
4. [Config Command](#config-command)
5. [Status Command](#status-command)
6. [Command Examples](#command-examples)
7. [Advanced Usage](#advanced-usage)
8. [Scripting and Automation](#scripting-and-automation)

## Global Options

These options are available for all commands:

### --config, -c
**Description:** Specify configuration file path  
**Default:** `trading_config.yaml`  
**Type:** String  

```bash
python main.py --config custom_config.yaml trade --mode paper
python main.py -c /path/to/config.yaml backtest --strategy straddle
```

### --log-level
**Description:** Set logging verbosity level  
**Choices:** DEBUG, INFO, WARNING, ERROR, CRITICAL  
**Default:** INFO  

```bash
python main.py --log-level DEBUG trade --mode paper --once
python main.py --log-level ERROR trade --mode live --continuous
```

### --log-file
**Description:** Specify log file path (optional)  
**Type:** String  
**Default:** Console output only  

```bash
python main.py --log-file trading_session.log trade --mode paper
python main.py --log-file /var/log/trading.log trade --mode live
```

## Trade Command

Start a trading session with various modes and options.

### Basic Syntax
```bash
python main.py trade [OPTIONS]
```

### Required Options

#### --mode, -m
**Description:** Trading mode  
**Choices:** paper, live  
**Default:** paper  

```bash
python main.py trade --mode paper    # Simulation mode
python main.py trade --mode live     # Real trading mode
python main.py trade -m paper        # Short form
```

### Execution Mode Options (Mutually Exclusive)

#### --continuous
**Description:** Run continuously with polling intervals  
**Type:** Flag  

```bash
python main.py trade --mode paper --continuous
```

#### --once
**Description:** Execute single evaluation and exit  
**Type:** Flag  

```bash
python main.py trade --mode paper --once
```

**Note:** If neither `--continuous` nor `--once` is specified, `--continuous` is used by default.

### Trading Parameters

#### --interval, -i
**Description:** Polling interval in seconds (continuous mode only)  
**Type:** Integer  
**Default:** 30  
**Range:** 10-3600 seconds  

```bash
python main.py trade --mode paper --continuous --interval 60
python main.py trade --mode paper --continuous -i 120
```

#### --strategies
**Description:** Specific strategies to enable (overrides config)  
**Choices:** straddle, directional, iron_condor, greeks, volatility  
**Type:** List  

```bash
# Single strategy
python main.py trade --mode paper --strategies straddle

# Multiple strategies
python main.py trade --mode paper --strategies straddle directional

# All available strategies
python main.py trade --mode paper --strategies straddle directional iron_condor greeks volatility
```

#### --max-trades
**Description:** Maximum concurrent trades (overrides config)  
**Type:** Integer  
**Range:** 1-20  

```bash
python main.py trade --mode paper --max-trades 5
python main.py trade --mode live --max-trades 2
```

#### --daily-loss-limit
**Description:** Daily loss limit in rupees (overrides config)  
**Type:** Float  
**Range:** 100.0-100000.0  

```bash
python main.py trade --mode paper --daily-loss-limit 5000.0
python main.py trade --mode live --daily-loss-limit 2000.0
```

#### --emergency-stop-file
**Description:** Emergency stop file path  
**Type:** String  
**Default:** emergency_stop.txt  

```bash
python main.py trade --mode paper --emergency-stop-file /tmp/emergency_stop
python main.py trade --mode live --emergency-stop-file stop_trading.flag
```

### Trade Command Examples

```bash
# Basic paper trading session
python main.py trade --mode paper --continuous --interval 30

# Single evaluation in live mode
python main.py trade --mode live --once

# Paper trading with specific strategies
python main.py trade --mode paper --strategies straddle directional --continuous

# Live trading with custom limits
python main.py trade --mode live --max-trades 3 --daily-loss-limit 5000 --continuous

# Debug session with detailed logging
python main.py --log-level DEBUG trade --mode paper --once

# High-frequency paper trading
python main.py trade --mode paper --continuous --interval 10

# Conservative live trading
python main.py trade --mode live --strategies straddle --max-trades 1 --continuous
```

## Backtest Command

Run historical backtesting on strategies.

### Basic Syntax
```bash
python main.py backtest [OPTIONS]
```

### Required Options

#### --start, -s
**Description:** Start date for backtesting  
**Format:** YYYY-MM-DD  
**Type:** String  

```bash
python main.py backtest --start 2024-01-01 --end 2024-12-31
python main.py backtest -s 2024-06-01 -e 2024-12-31
```

#### --end, -e
**Description:** End date for backtesting  
**Format:** YYYY-MM-DD  
**Type:** String  

```bash
python main.py backtest --start 2024-01-01 --end 2024-12-31
python main.py backtest -s 2024-06-01 -e 2024-12-31
```

### Optional Parameters

#### --strategy
**Description:** Strategy to backtest  
**Choices:** straddle, directional, iron_condor, greeks, volatility, all  
**Default:** all  

```bash
# Test single strategy
python main.py backtest --strategy straddle --start 2024-01-01 --end 2024-12-31

# Test all strategies
python main.py backtest --strategy all --start 2024-01-01 --end 2024-12-31
```

#### --output-dir
**Description:** Output directory for results  
**Type:** String  
**Default:** backtest_results  

```bash
python main.py backtest --strategy straddle --start 2024-01-01 --end 2024-12-31 --output-dir results/straddle_2024
```

#### --initial-capital
**Description:** Initial capital for backtesting  
**Type:** Float  
**Default:** 100000.0  
**Range:** 10000.0-10000000.0  

```bash
python main.py backtest --strategy all --start 2024-01-01 --end 2024-12-31 --initial-capital 500000
```

#### --format
**Description:** Output format  
**Choices:** csv, json, both  
**Default:** both  

```bash
# CSV output only
python main.py backtest --strategy straddle --start 2024-01-01 --end 2024-12-31 --format csv

# JSON output only
python main.py backtest --strategy straddle --start 2024-01-01 --end 2024-12-31 --format json

# Both formats
python main.py backtest --strategy straddle --start 2024-01-01 --end 2024-12-31 --format both
```

### Backtest Command Examples

```bash
# Basic backtest for all strategies
python main.py backtest --start 2024-01-01 --end 2024-12-31

# Backtest specific strategy with custom capital
python main.py backtest --strategy straddle --start 2024-06-01 --end 2024-12-31 --initial-capital 200000

# Generate only CSV output
python main.py backtest --strategy directional --start 2024-09-01 --end 2024-12-31 --format csv

# Backtest with custom output directory
python main.py backtest --strategy all --start 2024-01-01 --end 2024-06-30 --output-dir quarterly_results

# Quick backtest for recent period
python main.py backtest --strategy straddle --start 2024-11-01 --end 2024-12-31 --format json

# Comprehensive backtest with detailed logging
python main.py --log-level DEBUG backtest --strategy all --start 2024-01-01 --end 2024-12-31 --output-dir comprehensive_analysis
```

## Config Command

Manage configuration files.

### Basic Syntax
```bash
python main.py config [OPTIONS]
```

### Configuration Operations (Mutually Exclusive)

#### --create-default
**Description:** Create default configuration file  
**Type:** Flag  

```bash
python main.py config --create-default
python main.py config --create-default --output my_config.yaml
```

#### --validate
**Description:** Validate existing configuration  
**Type:** Flag  

```bash
python main.py config --validate
python main.py --config custom_config.yaml config --validate
```

#### --show
**Description:** Display current configuration  
**Type:** Flag  

```bash
python main.py config --show
python main.py --config production_config.yaml config --show
```

### Optional Parameters

#### --output
**Description:** Output file for configuration operations  
**Type:** String  

```bash
# Create default config with custom name
python main.py config --create-default --output production_config.yaml

# Show config and save to file
python main.py config --show --output current_config_backup.yaml
```

### Config Command Examples

```bash
# Create default configuration
python main.py config --create-default

# Create configuration with custom name
python main.py config --create-default --output trading_prod.yaml

# Validate current configuration
python main.py config --validate

# Validate specific configuration file
python main.py --config /path/to/config.yaml config --validate

# Show current configuration
python main.py config --show

# Show configuration in readable format
python main.py --config production.yaml config --show

# Backup current configuration
python main.py config --show --output backup_$(date +%Y%m%d).yaml
```

## Status Command

Monitor system status and performance.

### Basic Syntax
```bash
python main.py status [OPTIONS]
```

### Optional Parameters

#### --detailed
**Description:** Show detailed status information  
**Type:** Flag  

```bash
python main.py status --detailed
```

#### --refresh
**Description:** Auto-refresh interval in seconds  
**Type:** Integer  
**Range:** 1-3600  

```bash
# Refresh every 10 seconds
python main.py status --refresh 10

# Refresh every minute
python main.py status --refresh 60
```

### Status Command Examples

```bash
# Show current status
python main.py status

# Show detailed status with all metrics
python main.py status --detailed

# Continuous monitoring with 5-second refresh
python main.py status --refresh 5

# Continuous monitoring with detailed information
python main.py status --detailed --refresh 10

# One-time detailed status check
python main.py status --detailed
```

## Command Examples

### Daily Trading Workflow

```bash
# 1. Validate configuration
python main.py config --validate

# 2. Check system status
python main.py status --detailed

# 3. Start paper trading session for testing
python main.py trade --mode paper --once

# 4. If successful, start live trading
python main.py trade --mode live --continuous --interval 60

# 5. Monitor in another terminal
python main.py status --refresh 30
```

### Strategy Development Workflow

```bash
# 1. Create test configuration
python main.py config --create-default --output test_config.yaml

# 2. Run backtest for strategy development
python main.py --config test_config.yaml backtest --strategy straddle --start 2024-01-01 --end 2024-12-31

# 3. Test strategy in paper mode
python main.py --config test_config.yaml trade --mode paper --strategies straddle --once

# 4. Run extended paper trading
python main.py --config test_config.yaml trade --mode paper --strategies straddle --continuous --interval 30
```

### Performance Analysis Workflow

```bash
# 1. Run comprehensive backtest
python main.py backtest --strategy all --start 2024-01-01 --end 2024-12-31 --output-dir performance_analysis

# 2. Test individual strategies
python main.py backtest --strategy straddle --start 2024-01-01 --end 2024-12-31 --output-dir straddle_analysis
python main.py backtest --strategy directional --start 2024-01-01 --end 2024-12-31 --output-dir directional_analysis

# 3. Compare different time periods
python main.py backtest --strategy straddle --start 2024-01-01 --end 2024-06-30 --output-dir h1_2024
python main.py backtest --strategy straddle --start 2024-07-01 --end 2024-12-31 --output-dir h2_2024
```

## Advanced Usage

### Environment-Specific Configurations

```bash
# Development environment
python main.py --config config/dev_config.yaml trade --mode paper --continuous

# Staging environment
python main.py --config config/staging_config.yaml trade --mode paper --continuous

# Production environment
python main.py --config config/prod_config.yaml trade --mode live --continuous
```

### Logging Configurations

```bash
# Debug logging to file
python main.py --log-level DEBUG --log-file debug_session.log trade --mode paper --once

# Error logging only
python main.py --log-level ERROR trade --mode live --continuous

# Separate log files for different sessions
python main.py --log-file paper_session_$(date +%Y%m%d).log trade --mode paper --continuous
python main.py --log-file live_session_$(date +%Y%m%d).log trade --mode live --continuous
```

### Strategy-Specific Testing

```bash
# Test each strategy individually
for strategy in straddle directional iron_condor greeks volatility; do
    echo "Testing $strategy strategy..."
    python main.py trade --mode paper --strategies $strategy --once
done

# Backtest each strategy for different periods
for strategy in straddle directional; do
    python main.py backtest --strategy $strategy --start 2024-01-01 --end 2024-12-31 --output-dir ${strategy}_results
done
```

## Scripting and Automation

### Bash Script Examples

#### Daily Trading Script
```bash
#!/bin/bash
# daily_trading.sh

CONFIG_FILE="config/production.yaml"
LOG_FILE="logs/daily_$(date +%Y%m%d).log"

# Validate configuration
if ! python main.py --config $CONFIG_FILE config --validate; then
    echo "Configuration validation failed"
    exit 1
fi

# Start trading session
python main.py --config $CONFIG_FILE --log-file $LOG_FILE trade --mode live --continuous --interval 60
```

#### Backtesting Script
```bash
#!/bin/bash
# run_backtest.sh

STRATEGY=${1:-all}
START_DATE=${2:-2024-01-01}
END_DATE=${3:-2024-12-31}
OUTPUT_DIR="backtest_results/$(date +%Y%m%d)_${STRATEGY}"

echo "Running backtest for $STRATEGY from $START_DATE to $END_DATE"
python main.py backtest --strategy $STRATEGY --start $START_DATE --end $END_DATE --output-dir $OUTPUT_DIR

echo "Results saved to $OUTPUT_DIR"
```

#### System Monitoring Script
```bash
#!/bin/bash
# monitor_system.sh

while true; do
    clear
    echo "=== Trading System Status - $(date) ==="
    python main.py status --detailed
    
    # Check for emergency stop
    if [ -f "emergency_stop.txt" ]; then
        echo "⚠️  EMERGENCY STOP ACTIVE"
    fi
    
    sleep 30
done
```

### Cron Job Examples

```bash
# Add to crontab with: crontab -e

# Daily trading session (Monday to Friday at 9:00 AM)
0 9 * * 1-5 cd /path/to/trading && python main.py trade --mode live --continuous >> logs/cron.log 2>&1

# Daily backtest report (every day at 6:00 PM)
0 18 * * * cd /path/to/trading && python main.py backtest --strategy all --start $(date -d '30 days ago' +%Y-%m-%d) --end $(date +%Y-%m-%d) --output-dir daily_reports

# Weekly configuration validation (Sundays at 8:00 AM)
0 8 * * 0 cd /path/to/trading && python main.py config --validate >> logs/validation.log 2>&1

# System status check every hour during trading hours
0 9-15 * * 1-5 cd /path/to/trading && python main.py status --detailed >> logs/hourly_status.log
```

### Python Script Integration

```python
#!/usr/bin/env python3
# automated_trading.py

import subprocess
import sys
import time
from datetime import datetime

def run_command(cmd):
    """Run CLI command and return result"""
    try:
        result = subprocess.run(cmd, shell=True, capture_output=True, text=True)
        return result.returncode == 0, result.stdout, result.stderr
    except Exception as e:
        return False, "", str(e)

def main():
    # Validate configuration
    success, stdout, stderr = run_command("python main.py config --validate")
    if not success:
        print(f"Configuration validation failed: {stderr}")
        sys.exit(1)
    
    # Start trading session
    print(f"Starting trading session at {datetime.now()}")
    success, stdout, stderr = run_command("python main.py trade --mode paper --continuous --interval 60")
    
    if not success:
        print(f"Trading session failed: {stderr}")
        sys.exit(1)

if __name__ == "__main__":
    main()
```

## Exit Codes

The CLI returns standard exit codes:

- **0**: Success
- **1**: General error
- **2**: Configuration error
- **3**: API connection error
- **4**: Trading execution error
- **130**: Interrupted by user (Ctrl+C)

### Using Exit Codes in Scripts

```bash
#!/bin/bash

python main.py trade --mode paper --once
exit_code=$?

case $exit_code in
    0)
        echo "Trading session completed successfully"
        ;;
    1)
        echo "General error occurred"
        ;;
    2)
        echo "Configuration error"
        ;;
    3)
        echo "API connection error"
        ;;
    130)
        echo "Session interrupted by user"
        ;;
    *)
        echo "Unknown error (exit code: $exit_code)"
        ;;
esac
```

## Best Practices

1. **Always validate configuration** before starting live trading
2. **Use paper mode** for testing new configurations
3. **Monitor logs** regularly for warnings and errors
4. **Set appropriate timeouts** for long-running operations
5. **Use emergency stop mechanisms** for safety
6. **Backup configurations** before making changes
7. **Test CLI commands** in development environment first
8. **Use version control** for configuration files
9. **Document custom scripts** and automation
10. **Regular system health checks** using status command