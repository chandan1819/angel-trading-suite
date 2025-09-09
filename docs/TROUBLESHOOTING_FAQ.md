# Troubleshooting Guide and FAQ

This guide provides solutions to common issues and frequently asked questions about the Bank Nifty Options Trading System.

## Table of Contents

1. [Installation and Setup Issues](#installation-and-setup-issues)
2. [Configuration Problems](#configuration-problems)
3. [API Connection Issues](#api-connection-issues)
4. [Trading Execution Problems](#trading-execution-problems)
5. [Strategy Issues](#strategy-issues)
6. [Risk Management Problems](#risk-management-problems)
7. [Performance Issues](#performance-issues)
8. [Logging and Monitoring Issues](#logging-and-monitoring-issues)
9. [Emergency Procedures](#emergency-procedures)
10. [Frequently Asked Questions](#frequently-asked-questions)

## Installation and Setup Issues

### Issue: Import Errors When Running the System

**Symptoms:**
```
ModuleNotFoundError: No module named 'src'
ImportError: cannot import name 'TradingManager'
```

**Solutions:**

1. **Check Python Path:**
   ```bash
   # Ensure you're in the correct directory
   cd /path/to/banknifty-options-trading
   pwd  # Should show the project root directory
   ```

2. **Install Dependencies:**
   ```bash
   pip install -r requirements.txt
   # or
   pip install -r requirements_dev.txt  # for development
   ```

3. **Check Python Version:**
   ```bash
   python --version  # Should be 3.8 or higher
   python3 --version
   ```

4. **Use Correct Python Interpreter:**
   ```bash
   # Try with python3 explicitly
   python3 main.py --help
   
   # Or use module execution
   python -m src.cli.cli_interface --help
   ```

### Issue: Permission Denied Errors

**Symptoms:**
```
PermissionError: [Errno 13] Permission denied: 'logs/trading.log'
FileNotFoundError: [Errno 2] No such file or directory: 'config/trading_config.yaml'
```

**Solutions:**

1. **Create Required Directories:**
   ```bash
   mkdir -p logs
   mkdir -p config
   mkdir -p backtest_results
   ```

2. **Set Proper Permissions:**
   ```bash
   chmod 755 logs config backtest_results
   chmod +x main.py
   chmod 644 config/*.yaml
   ```

3. **Check File Ownership:**
   ```bash
   ls -la logs/
   # If owned by root, change ownership:
   sudo chown -R $USER:$USER logs/
   ```

### Issue: Virtual Environment Problems

**Symptoms:**
```
Command 'python' not found
Package versions conflict
```

**Solutions:**

1. **Create Virtual Environment:**
   ```bash
   python3 -m venv trading_env
   source trading_env/bin/activate  # Linux/Mac
   # or
   trading_env\Scripts\activate  # Windows
   ```

2. **Install in Virtual Environment:**
   ```bash
   pip install --upgrade pip
   pip install -r requirements.txt
   ```

3. **Verify Installation:**
   ```bash
   pip list
   python -c "import pandas; print('OK')"
   ```

## Configuration Problems

### Issue: Configuration File Not Found

**Symptoms:**
```
FileNotFoundError: Configuration file 'trading_config.yaml' not found
```

**Solutions:**

1. **Create Default Configuration:**
   ```bash
   python main.py config --create-default
   ```

2. **Copy Example Configuration:**
   ```bash
   cp config/trading_config.example.yaml config/trading_config.yaml
   ```

3. **Specify Configuration Path:**
   ```bash
   python main.py --config /path/to/your/config.yaml trade --mode paper
   ```

### Issue: Invalid YAML Syntax

**Symptoms:**
```
yaml.scanner.ScannerError: while parsing a block mapping
ParserError: could not determine a constructor for the tag
```

**Solutions:**

1. **Validate YAML Syntax:**
   ```bash
   python -c "import yaml; yaml.safe_load(open('config/trading_config.yaml'))"
   ```

2. **Common YAML Issues:**
   ```yaml
   # Wrong (missing quotes for special characters)
   password: my@password
   
   # Correct
   password: "my@password"
   
   # Wrong (inconsistent indentation)
   strategy:
     straddle:
       enabled: true
      weight: 1.0  # Wrong indentation
   
   # Correct
   strategy:
     straddle:
       enabled: true
       weight: 1.0
   ```

3. **Use Online YAML Validator:**
   - Copy your YAML content to an online validator
   - Fix syntax errors before using

### Issue: Environment Variables Not Loading

**Symptoms:**
```
ValueError: API key not found in environment variables
KeyError: 'ANGEL_API_KEY'
```

**Solutions:**

1. **Set Environment Variables:**
   ```bash
   export ANGEL_API_KEY="your_api_key"
   export ANGEL_CLIENT_CODE="your_client_code"
   export ANGEL_PIN="your_pin"
   export ANGEL_TOTP_SECRET="your_totp_secret"
   ```

2. **Create .env File:**
   ```bash
   # Create .env file in project root
   cat > .env << EOF
   ANGEL_API_KEY=your_api_key
   ANGEL_CLIENT_CODE=your_client_code
   ANGEL_PIN=your_pin
   ANGEL_TOTP_SECRET=your_totp_secret
   EOF
   
   # Load environment variables
   source .env
   ```

3. **Verify Environment Variables:**
   ```bash
   echo $ANGEL_API_KEY
   env | grep ANGEL
   ```

4. **Use Configuration Validation:**
   ```bash
   python main.py config --validate
   ```

## API Connection Issues

### Issue: Authentication Failures

**Symptoms:**
```
AuthenticationError: Invalid API credentials
HTTPError: 401 Unauthorized
```

**Solutions:**

1. **Verify Credentials:**
   ```bash
   # Check if credentials are set
   echo "API Key: $ANGEL_API_KEY"
   echo "Client Code: $ANGEL_CLIENT_CODE"
   # Don't echo PIN or TOTP secret for security
   ```

2. **Test API Connection:**
   ```bash
   # Run in paper mode first
   python main.py trade --mode paper --once
   ```

3. **Check Angel Broking Account:**
   - Ensure API access is enabled in your Angel account
   - Verify TOTP secret is correctly configured
   - Check if account is active and funded

4. **Manual Authentication Test:**
   ```python
   from SmartApi import SmartConnect
   import os
   
   api_key = os.getenv('ANGEL_API_KEY')
   client_code = os.getenv('ANGEL_CLIENT_CODE')
   pin = os.getenv('ANGEL_PIN')
   
   obj = SmartConnect(api_key=api_key)
   data = obj.generateSession(client_code, pin)
   print(data)
   ```

### Issue: Rate Limiting Errors

**Symptoms:**
```
HTTPError: 429 Too Many Requests
RateLimitExceeded: API rate limit exceeded
```

**Solutions:**

1. **Adjust Rate Limiting Configuration:**
   ```yaml
   api:
     rate_limit_calls: 50  # Reduce from 100
     rate_limit_period: 60
     retry_delay: 2.0      # Increase delay
   ```

2. **Implement Exponential Backoff:**
   ```yaml
   api:
     max_retries: 5
     retry_backoff_factor: 2.0
   ```

3. **Reduce Polling Frequency:**
   ```bash
   # Increase interval from 30 to 60 seconds
   python main.py trade --mode paper --continuous --interval 60
   ```

### Issue: Network Connectivity Problems

**Symptoms:**
```
ConnectionError: Failed to establish a new connection
TimeoutError: Request timed out
```

**Solutions:**

1. **Check Internet Connection:**
   ```bash
   ping google.com
   curl -I https://apiconnect.angelbroking.com
   ```

2. **Adjust Timeout Settings:**
   ```yaml
   api:
     timeout: 60  # Increase from 30
     connection_pool_size: 5  # Reduce pool size
   ```

3. **Use Proxy if Required:**
   ```yaml
   api:
     proxy_url: "http://your-proxy:8080"
     verify_ssl: false  # Only if necessary
   ```

## Trading Execution Problems

### Issue: Orders Not Being Placed

**Symptoms:**
```
No orders placed despite signals generated
OrderValidationError: Invalid order parameters
```

**Solutions:**

1. **Check Trading Mode:**
   ```bash
   # Ensure you're in the correct mode
   python main.py trade --mode paper --once  # For testing
   python main.py trade --mode live --once   # For actual trading
   ```

2. **Verify Market Hours:**
   ```yaml
   strategy:
     market_start_time: "09:15"
     market_end_time: "15:30"
     timezone: Asia/Kolkata
   ```

3. **Check Risk Limits:**
   ```bash
   # Check if daily limits are reached
   python main.py status --detailed
   ```

4. **Validate Order Parameters:**
   ```python
   # Check logs for order validation errors
   tail -f logs/trading.log | grep -i "order"
   ```

### Issue: Partial Fills or Order Rejections

**Symptoms:**
```
OrderRejected: Insufficient margin
PartialFill: Only 50 of 100 shares filled
```

**Solutions:**

1. **Check Margin Requirements:**
   ```yaml
   risk:
     margin_buffer: 0.3  # Increase buffer to 30%
     max_position_size: 50  # Reduce position size
   ```

2. **Use Market Orders for Better Fills:**
   ```yaml
   orders:
     default_order_type: "MARKET"
     limit_order_buffer: 0.5  # 0.5% buffer for limit orders
   ```

3. **Implement Order Retry Logic:**
   ```yaml
   orders:
     retry_attempts: 3
     retry_delay: 5
     partial_fill_handling: "complete_or_cancel"
   ```

### Issue: Position Tracking Errors

**Symptoms:**
```
PositionMismatch: System position differs from broker position
P&L calculation errors
```

**Solutions:**

1. **Enable Position Reconciliation:**
   ```yaml
   orders:
     position_reconciliation: true
     reconciliation_interval: 300  # 5 minutes
   ```

2. **Manual Position Check:**
   ```bash
   python main.py status --detailed
   ```

3. **Reset Position Tracking:**
   ```bash
   # Stop system and restart
   touch emergency_stop.txt
   # Wait for graceful shutdown
   rm emergency_stop.txt
   python main.py trade --mode paper --once
   ```

## Strategy Issues

### Issue: No Trading Signals Generated

**Symptoms:**
```
No signals generated for the last hour
Strategy evaluation completed with 0 signals
```

**Solutions:**

1. **Check Strategy Configuration:**
   ```yaml
   strategy:
     straddle:
       enabled: true
       min_confidence: 0.5  # Lower threshold
       min_iv_rank: 0.3     # Lower threshold
   ```

2. **Verify Market Conditions:**
   ```bash
   # Check if market data is available
   python main.py trade --mode paper --once --log-level DEBUG
   ```

3. **Review Signal Criteria:**
   ```python
   # Check logs for strategy evaluation details
   grep -i "strategy" logs/trading.log | tail -20
   ```

4. **Test Individual Strategies:**
   ```bash
   # Test only straddle strategy
   python main.py trade --mode paper --strategies straddle --once
   ```

### Issue: Strategy Performance Issues

**Symptoms:**
```
High number of losing trades
Strategies not meeting expected performance
```

**Solutions:**

1. **Run Backtesting Analysis:**
   ```bash
   python main.py backtest --strategy straddle --start 2024-01-01 --end 2024-12-31
   ```

2. **Adjust Strategy Parameters:**
   ```yaml
   strategy:
     straddle:
       min_confidence: 0.7  # Increase selectivity
       min_iv_rank: 0.6     # Higher IV requirement
       exit_time_minutes: 45 # Earlier exit
   ```

3. **Enable Multiple Strategies:**
   ```yaml
   strategy:
     enabled_strategies:
       - straddle
       - directional
       - volatility
   ```

### Issue: Strategy Conflicts

**Symptoms:**
```
Multiple strategies generating conflicting signals
Position limits exceeded due to multiple strategies
```

**Solutions:**

1. **Implement Strategy Prioritization:**
   ```yaml
   strategy:
     straddle:
       weight: 1.0
     directional:
       weight: 0.8
     volatility:
       weight: 0.6
   ```

2. **Set Strategy-Specific Limits:**
   ```yaml
   risk:
     max_concurrent_trades: 5
     max_trades_per_strategy: 2
   ```

## Risk Management Problems

### Issue: Risk Limits Not Being Enforced

**Symptoms:**
```
Trades executed beyond daily loss limit
Position sizes larger than configured
```

**Solutions:**

1. **Verify Risk Configuration:**
   ```bash
   python main.py config --show | grep -A 10 "risk:"
   ```

2. **Check Risk Manager Logs:**
   ```bash
   grep -i "risk" logs/trading.log | tail -10
   ```

3. **Test Risk Limits:**
   ```bash
   # Set very low limits for testing
   python main.py trade --mode paper --daily-loss-limit 100 --once
   ```

4. **Enable Strict Risk Mode:**
   ```yaml
   risk:
     strict_mode: true
     pre_trade_validation: true
     real_time_monitoring: true
   ```

### Issue: Emergency Stop Not Working

**Symptoms:**
```
System continues trading despite emergency stop file
Emergency procedures not triggered
```

**Solutions:**

1. **Verify Emergency Stop File:**
   ```bash
   # Create emergency stop
   echo "Emergency stop activated" > emergency_stop.txt
   
   # Check if file exists
   ls -la emergency_stop.txt
   ```

2. **Check Emergency Stop Configuration:**
   ```yaml
   risk:
     emergency_stop_file: emergency_stop.txt
     emergency_check_interval: 10  # Check every 10 seconds
   ```

3. **Manual Emergency Stop:**
   ```bash
   # Use Ctrl+C to interrupt
   # Or kill the process
   pkill -f "python.*main.py"
   ```

## Performance Issues

### Issue: Slow System Response

**Symptoms:**
```
Strategy evaluation taking > 30 seconds
API calls timing out frequently
High CPU/memory usage
```

**Solutions:**

1. **Optimize Configuration:**
   ```yaml
   api:
     connection_pool_size: 20
     timeout: 15
   
   data_cache_ttl: 600  # Cache data for 10 minutes
   ```

2. **Reduce Polling Frequency:**
   ```bash
   python main.py trade --mode paper --continuous --interval 120
   ```

3. **Enable Performance Monitoring:**
   ```yaml
   logging:
     performance_logging: true
     slow_query_threshold: 2.0
   ```

4. **Check System Resources:**
   ```bash
   top -p $(pgrep -f "python.*main.py")
   free -h
   df -h
   ```

### Issue: Memory Leaks

**Symptoms:**
```
Memory usage continuously increasing
System becomes unresponsive over time
```

**Solutions:**

1. **Enable Memory Monitoring:**
   ```python
   import psutil
   import os
   
   process = psutil.Process(os.getpid())
   print(f"Memory usage: {process.memory_info().rss / 1024 / 1024:.2f} MB")
   ```

2. **Implement Data Cleanup:**
   ```yaml
   data_cache_ttl: 300  # Reduce cache time
   max_log_entries: 10000  # Limit log entries in memory
   ```

3. **Restart Periodically:**
   ```bash
   # Add to crontab for daily restart
   0 6 * * * /path/to/restart_trading_system.sh
   ```

## Logging and Monitoring Issues

### Issue: Logs Not Being Generated

**Symptoms:**
```
Empty log files
No console output
Missing trade records
```

**Solutions:**

1. **Check Logging Configuration:**
   ```yaml
   logging:
     level: INFO
     enable_console: true
     enable_file: true
     log_dir: logs
   ```

2. **Verify Log Directory Permissions:**
   ```bash
   mkdir -p logs
   chmod 755 logs
   touch logs/test.log
   ```

3. **Test Logging:**
   ```bash
   python main.py --log-level DEBUG trade --mode paper --once
   ```

### Issue: Log Files Too Large

**Symptoms:**
```
Log files consuming excessive disk space
System running out of disk space
```

**Solutions:**

1. **Configure Log Rotation:**
   ```yaml
   logging:
     max_file_size: 10485760  # 10MB
     backup_count: 5
     rotation_when: midnight
   ```

2. **Clean Old Logs:**
   ```bash
   # Remove logs older than 30 days
   find logs/ -name "*.log" -mtime +30 -delete
   ```

3. **Compress Old Logs:**
   ```bash
   # Compress logs older than 7 days
   find logs/ -name "*.log" -mtime +7 -exec gzip {} \;
   ```

## Emergency Procedures

### Emergency Stop Procedures

1. **Immediate Stop:**
   ```bash
   # Create emergency stop file
   echo "Manual emergency stop - $(date)" > emergency_stop.txt
   ```

2. **Force Kill Process:**
   ```bash
   # Find and kill the process
   ps aux | grep "python.*main.py"
   kill -9 <process_id>
   ```

3. **Manual Position Closure:**
   ```bash
   # Log into Angel Broking web/app
   # Manually close all open positions
   # Document all actions taken
   ```

### System Recovery Procedures

1. **Check System State:**
   ```bash
   python main.py status --detailed
   ```

2. **Validate Configuration:**
   ```bash
   python main.py config --validate
   ```

3. **Test in Paper Mode:**
   ```bash
   python main.py trade --mode paper --once
   ```

4. **Gradual Restart:**
   ```bash
   # Start with single strategy
   python main.py trade --mode live --strategies straddle --once
   ```

### Data Recovery Procedures

1. **Backup Current State:**
   ```bash
   cp -r logs/ logs_backup_$(date +%Y%m%d_%H%M%S)
   cp config/trading_config.yaml config_backup_$(date +%Y%m%d_%H%M%S).yaml
   ```

2. **Restore from Backup:**
   ```bash
   # Restore configuration
   cp config_backup_YYYYMMDD_HHMMSS.yaml config/trading_config.yaml
   
   # Restore logs if needed
   cp -r logs_backup_YYYYMMDD_HHMMSS/* logs/
   ```

## Frequently Asked Questions

### Q: Can I run multiple instances of the system?

**A:** No, running multiple instances simultaneously can cause conflicts and duplicate orders. Use the emergency stop mechanism to ensure only one instance runs at a time.

### Q: How do I update strategy parameters without restarting?

**A:** Currently, you need to restart the system to apply configuration changes. Future versions may support hot reloading.

### Q: What happens if my internet connection drops?

**A:** The system will attempt to reconnect automatically. If reconnection fails, it will log errors and may trigger emergency procedures depending on configuration.

### Q: Can I trade multiple underlying symbols?

**A:** Currently, the system is designed for BANKNIFTY only. Support for multiple symbols may be added in future versions.

### Q: How do I know if my strategies are profitable?

**A:** Use the backtesting feature and monitor daily P&L reports. Regular performance analysis is recommended.

### Q: What should I do if I suspect a bug?

**A:** 
1. Enable DEBUG logging
2. Reproduce the issue
3. Collect logs and configuration
4. Create emergency stop if trading live
5. Report the issue with detailed information

### Q: How often should I update the system?

**A:** Check for updates regularly, but test thoroughly in paper mode before deploying to live trading.

### Q: Can I customize the risk management rules?

**A:** Yes, risk parameters are fully configurable. However, ensure you understand the implications before making changes.

### Q: What's the minimum capital required?

**A:** This depends on your risk parameters and position sizes. Ensure you have sufficient margin for your configured strategies.

### Q: How do I optimize strategy parameters?

**A:** Use the backtesting feature to test different parameter combinations. Consider using walk-forward analysis for robust optimization.

## Getting Help

If you continue to experience issues:

1. **Check the logs** for detailed error messages
2. **Review the configuration** for any misconfigurations
3. **Test in paper mode** to isolate issues
4. **Consult the documentation** for detailed explanations
5. **Create a minimal reproduction case** for complex issues

Remember: When in doubt, use paper mode and emergency stop procedures to ensure safety.