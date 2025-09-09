# Deployment Guide

This guide provides step-by-step instructions for deploying the Bank Nifty Options Trading System to production.

## Table of Contents

1. [Pre-Deployment Checklist](#pre-deployment-checklist)
2. [System Requirements](#system-requirements)
3. [Installation Steps](#installation-steps)
4. [Configuration Setup](#configuration-setup)
5. [Security Configuration](#security-configuration)
6. [Testing and Validation](#testing-and-validation)
7. [Go-Live Procedures](#go-live-procedures)
8. [Monitoring and Maintenance](#monitoring-and-maintenance)
9. [Troubleshooting](#troubleshooting)
10. [Rollback Procedures](#rollback-procedures)

## Pre-Deployment Checklist

### ✅ Environment Preparation

- [ ] **Server/System Requirements Met**
  - Python 3.8+ installed
  - Minimum 4GB RAM available
  - At least 2 CPU cores
  - 10GB+ free disk space
  - Stable internet connection (>10 Mbps)

- [ ] **Dependencies Installed**
  - All required Python packages
  - System-level dependencies
  - Virtual environment configured

- [ ] **Network Configuration**
  - Firewall rules configured for API access
  - Proxy settings (if applicable)
  - DNS resolution working
  - NTP synchronization enabled

### ✅ Credentials and Access

- [ ] **Angel Broking API Credentials**
  - API Key obtained and validated
  - Client Code confirmed
  - PIN configured
  - TOTP Secret generated and tested

- [ ] **System Access**
  - User accounts created with appropriate permissions
  - SSH keys configured (if remote deployment)
  - Sudo/admin access available for installation

### ✅ Configuration Files

- [ ] **Trading Configuration**
  - Configuration file created and validated
  - Risk parameters reviewed and approved
  - Strategy settings configured
  - Logging configuration set up

- [ ] **Security Configuration**
  - Environment variables configured
  - File permissions set correctly
  - Sensitive data encrypted/protected

### ✅ Testing and Validation

- [ ] **System Testing**
  - Unit tests passed
  - Integration tests completed
  - Performance tests satisfactory
  - Security audit completed

- [ ] **Paper Trading Validation**
  - Paper trading tested successfully
  - All strategies validated
  - Risk management verified
  - Emergency procedures tested

## System Requirements

### Minimum Requirements

```
Operating System: Linux (Ubuntu 20.04+), macOS (10.15+), Windows 10+
Python Version: 3.8 or higher
Memory: 4GB RAM
CPU: 2 cores, 2.0 GHz
Storage: 10GB free space
Network: Stable internet connection (10+ Mbps)
```

### Recommended Requirements

```
Operating System: Linux (Ubuntu 22.04 LTS)
Python Version: 3.10 or higher
Memory: 8GB RAM
CPU: 4 cores, 2.5 GHz
Storage: 50GB SSD
Network: Dedicated internet connection (50+ Mbps)
Backup: Secondary internet connection
```

### Software Dependencies

```bash
# Core Python packages
pandas>=1.5.0
numpy>=1.21.0
requests>=2.28.0
pyyaml>=6.0
psutil>=5.9.0

# Testing packages (development)
pytest>=7.0.0
pytest-cov>=4.0.0
pytest-mock>=3.10.0

# Optional packages
matplotlib>=3.5.0  # For backtesting charts
jupyter>=1.0.0     # For analysis notebooks
```

## Installation Steps

### Step 1: System Preparation

```bash
# Update system packages (Ubuntu/Debian)
sudo apt update && sudo apt upgrade -y

# Install Python and pip
sudo apt install python3 python3-pip python3-venv -y

# Install system dependencies
sudo apt install build-essential curl wget git -y
```

### Step 2: Create Project Directory

```bash
# Create project directory
sudo mkdir -p /opt/banknifty-trading
sudo chown $USER:$USER /opt/banknifty-trading
cd /opt/banknifty-trading

# Clone or copy project files
# (Assuming files are already available)
```

### Step 3: Python Environment Setup

```bash
# Create virtual environment
python3 -m venv trading_env

# Activate virtual environment
source trading_env/bin/activate

# Upgrade pip
pip install --upgrade pip

# Install requirements
pip install -r requirements.txt
```

### Step 4: Directory Structure Setup

```bash
# Create required directories
mkdir -p logs
mkdir -p config
mkdir -p backtest_results
mkdir -p data/cache

# Set permissions
chmod 755 logs config backtest_results data
chmod 644 config/*.yaml
```

### Step 5: Configuration Files

```bash
# Copy configuration template
cp config/trading_config.example.yaml config/trading_config.yaml

# Edit configuration
nano config/trading_config.yaml
```

## Configuration Setup

### Basic Configuration

1. **Copy and customize configuration:**
   ```bash
   cp config/trading_config.example.yaml config/production_config.yaml
   ```

2. **Edit key settings:**
   ```yaml
   # Set to live mode for production
   mode: live
   
   # Configure risk parameters
   risk:
     max_daily_loss: 5000.0
     max_concurrent_trades: 3
     profit_target: 2000.0
     stop_loss: 1000.0
   
   # Enable logging
   logging:
     level: INFO
     enable_file: true
     log_dir: logs
   
   # Configure notifications
   notification:
     enabled: true
     types: [webhook, email]
   ```

### Strategy Configuration

```yaml
strategy:
  enabled_strategies:
    - straddle      # Start with conservative strategies
    # - directional # Enable after validation
  
  straddle:
    enabled: true
    min_confidence: 0.7  # Conservative threshold
    min_iv_rank: 0.6     # High IV requirement
    max_dte: 7
```

### Logging Configuration

```yaml
logging:
  level: INFO
  enable_console: false  # Disable for production
  enable_file: true
  log_dir: /opt/banknifty-trading/logs
  max_file_size: 10485760  # 10MB
  backup_count: 30         # 30 days retention
```

## Security Configuration

### Environment Variables

1. **Create environment file:**
   ```bash
   sudo nano /etc/environment
   ```

2. **Add credentials (replace with actual values):**
   ```bash
   ANGEL_API_KEY="your_api_key_here"
   ANGEL_CLIENT_CODE="your_client_code_here"
   ANGEL_PIN="your_pin_here"
   ANGEL_TOTP_SECRET="your_totp_secret_here"
   ```

3. **Secure the environment file:**
   ```bash
   sudo chmod 600 /etc/environment
   ```

### File Permissions

```bash
# Set secure permissions
chmod 600 config/production_config.yaml
chmod 755 logs
chmod 644 src/**/*.py
chmod +x main.py

# Create trading user (optional)
sudo useradd -r -s /bin/false trading
sudo chown -R trading:trading /opt/banknifty-trading
```

### Firewall Configuration

```bash
# Allow outbound HTTPS (for API calls)
sudo ufw allow out 443/tcp

# Allow SSH (if remote access needed)
sudo ufw allow ssh

# Enable firewall
sudo ufw enable
```

## Testing and Validation

### Step 1: Configuration Validation

```bash
# Validate configuration
python3 main.py config --validate

# Test configuration loading
python3 main.py config --show
```

### Step 2: Paper Trading Test

```bash
# Run single paper trading cycle
python3 main.py trade --mode paper --once

# Run extended paper trading session
python3 main.py trade --mode paper --continuous --interval 60
```

### Step 3: System Validation

```bash
# Run comprehensive system validation
python3 scripts/system_validation.py --config config/production_config.yaml

# Run performance tests
python3 scripts/performance_test.py --config config/production_config.yaml

# Run deployment checklist
python3 scripts/deployment_checklist.py --config config/production_config.yaml
```

### Step 4: Emergency Procedures Test

```bash
# Test emergency stop
echo "Emergency stop test" > emergency_stop.txt
python3 main.py trade --mode paper --once
rm emergency_stop.txt

# Test graceful shutdown
python3 main.py trade --mode paper --continuous &
PID=$!
sleep 10
kill -TERM $PID
```

## Go-Live Procedures

### Phase 1: Pre-Market Preparation

**Time: 30 minutes before market open**

1. **System Health Check:**
   ```bash
   # Check system resources
   python3 main.py status --detailed
   
   # Validate configuration
   python3 main.py config --validate
   
   # Test API connectivity
   python3 -c "
   from src.api.angel_api_client import AngelAPIClient
   from src.config.config_manager import ConfigManager
   config = ConfigManager().load_config('config/production_config.yaml')
   client = AngelAPIClient(config.api)
   print('API Status:', client.initialize())
   "
   ```

2. **Final Configuration Review:**
   ```bash
   # Review risk parameters
   grep -A 10 "risk:" config/production_config.yaml
   
   # Confirm trading mode
   grep "mode:" config/production_config.yaml
   
   # Check enabled strategies
   grep -A 5 "enabled_strategies:" config/production_config.yaml
   ```

3. **Backup Current State:**
   ```bash
   # Backup configuration
   cp config/production_config.yaml config/backup_$(date +%Y%m%d_%H%M%S).yaml
   
   # Clear old logs (optional)
   find logs/ -name "*.log" -mtime +7 -delete
   ```

### Phase 2: Market Open (9:15 AM)

1. **Start Trading System:**
   ```bash
   # Start in screen/tmux session for persistence
   screen -S trading_session
   
   # Start trading with logging
   python3 main.py --log-file logs/live_$(date +%Y%m%d).log \
                   trade --mode live --continuous --interval 30
   ```

2. **Initial Monitoring (First 30 minutes):**
   ```bash
   # In another terminal, monitor status
   watch -n 30 "python3 main.py status --detailed"
   
   # Monitor logs
   tail -f logs/live_$(date +%Y%m%d).log
   
   # Check system resources
   htop
   ```

### Phase 3: Ongoing Monitoring

1. **Regular Health Checks:**
   ```bash
   # Every hour during trading hours
   python3 main.py status --detailed
   
   # Check for emergency stop file
   ls -la emergency_stop.txt 2>/dev/null || echo "No emergency stop"
   
   # Monitor system resources
   free -h && df -h
   ```

2. **Performance Monitoring:**
   ```bash
   # Check trading performance
   grep -i "trade" logs/live_$(date +%Y%m%d).log | tail -10
   
   # Monitor P&L
   grep -i "pnl\|profit\|loss" logs/live_$(date +%Y%m%d).log | tail -5
   ```

### Phase 4: Market Close (3:30 PM)

1. **Graceful Shutdown:**
   ```bash
   # The system should automatically stop placing new trades near market close
   # Monitor for position closures
   
   # If manual shutdown needed:
   echo "Market close - manual shutdown" > emergency_stop.txt
   ```

2. **End-of-Day Procedures:**
   ```bash
   # Generate daily report
   python3 scripts/generate_daily_report.py --date $(date +%Y-%m-%d)
   
   # Backup logs
   cp logs/live_$(date +%Y%m%d).log logs/archive/
   
   # System cleanup
   python3 -c "
   import gc
   gc.collect()
   print('Memory cleanup completed')
   "
   ```

## Monitoring and Maintenance

### Daily Monitoring Tasks

1. **Morning Checklist (Before 9:00 AM):**
   - [ ] Check system resources (CPU, memory, disk)
   - [ ] Validate configuration hasn't changed
   - [ ] Test API connectivity
   - [ ] Review previous day's performance
   - [ ] Check for system updates

2. **During Trading Hours:**
   - [ ] Monitor system status every 30 minutes
   - [ ] Check P&L and position status
   - [ ] Watch for error messages in logs
   - [ ] Verify emergency stop procedures work

3. **End of Day:**
   - [ ] Review trading performance
   - [ ] Check log files for errors
   - [ ] Backup important data
   - [ ] Plan next day's configuration changes

### Weekly Maintenance

1. **Performance Review:**
   ```bash
   # Generate weekly performance report
   python3 scripts/weekly_performance.py --week $(date +%Y-%W)
   
   # Analyze strategy performance
   python3 scripts/strategy_analysis.py --period 7days
   ```

2. **System Maintenance:**
   ```bash
   # Update system packages
   sudo apt update && sudo apt list --upgradable
   
   # Clean old log files
   find logs/ -name "*.log" -mtime +30 -delete
   
   # Check disk usage
   du -sh logs/ config/ backtest_results/
   ```

3. **Configuration Review:**
   - Review risk parameters based on performance
   - Adjust strategy settings if needed
   - Update notification settings
   - Review and rotate API credentials if required

### Monthly Tasks

1. **Comprehensive System Review:**
   - Full system performance analysis
   - Security audit and updates
   - Backup and recovery testing
   - Documentation updates

2. **Strategy Optimization:**
   - Backtest strategies with recent data
   - Analyze performance metrics
   - Consider parameter adjustments
   - Test new strategy configurations

## Troubleshooting

### Common Issues and Solutions

#### Issue: System Won't Start

**Symptoms:**
- Import errors
- Configuration validation failures
- API connection errors

**Solutions:**
```bash
# Check Python environment
which python3
python3 --version

# Verify virtual environment
source trading_env/bin/activate
pip list

# Test configuration
python3 main.py config --validate

# Check API credentials
echo $ANGEL_API_KEY | wc -c  # Should be > 10
```

#### Issue: Trading System Stops Unexpectedly

**Symptoms:**
- Process terminates without warning
- No new trades being placed
- System becomes unresponsive

**Solutions:**
```bash
# Check system resources
free -h
df -h
top

# Review error logs
tail -100 logs/live_$(date +%Y%m%d).log | grep -i error

# Check for emergency stop
ls -la emergency_stop.txt

# Restart system
python3 main.py trade --mode live --continuous
```

#### Issue: Poor Trading Performance

**Symptoms:**
- High number of losing trades
- Frequent stop-loss triggers
- Low profit generation

**Solutions:**
```bash
# Analyze recent performance
python3 scripts/performance_analysis.py --days 7

# Review strategy parameters
grep -A 20 "strategy:" config/production_config.yaml

# Run backtesting with current parameters
python3 main.py backtest --strategy all --start $(date -d '30 days ago' +%Y-%m-%d) --end $(date +%Y-%m-%d)

# Consider parameter adjustments
# Increase confidence thresholds
# Adjust risk parameters
# Review market conditions
```

### Emergency Procedures

#### Immediate System Stop

```bash
# Create emergency stop file
echo "EMERGENCY STOP - $(date)" > emergency_stop.txt

# Force kill if unresponsive
pkill -f "python.*main.py"

# Check for open positions
python3 -c "
from src.orders.order_manager import OrderManager
# Check positions and close if necessary
"
```

#### System Recovery

```bash
# Remove emergency stop
rm emergency_stop.txt

# Validate system state
python3 main.py config --validate
python3 main.py status --detailed

# Restart in paper mode for testing
python3 main.py trade --mode paper --once

# If successful, restart live trading
python3 main.py trade --mode live --continuous
```

## Rollback Procedures

### Configuration Rollback

```bash
# Restore previous configuration
cp config/backup_YYYYMMDD_HHMMSS.yaml config/production_config.yaml

# Validate restored configuration
python3 main.py config --validate

# Test with paper trading
python3 main.py trade --mode paper --once
```

### System Rollback

```bash
# Stop current system
echo "Rollback in progress" > emergency_stop.txt

# Restore from backup
tar -xzf backups/system_backup_YYYYMMDD.tar.gz

# Validate restored system
python3 scripts/system_validation.py

# Restart system
python3 main.py trade --mode live --continuous
```

### Emergency Contact Procedures

1. **Technical Issues:**
   - Check system logs first
   - Attempt automated recovery
   - Contact system administrator
   - Document all actions taken

2. **Trading Issues:**
   - Activate emergency stop immediately
   - Review open positions
   - Contact risk management team
   - Prepare incident report

3. **API Issues:**
   - Check Angel Broking system status
   - Verify network connectivity
   - Test with paper mode
   - Contact Angel Broking support if needed

## Best Practices

### Security Best Practices

1. **Credential Management:**
   - Use environment variables for sensitive data
   - Rotate API credentials regularly
   - Never commit credentials to version control
   - Use encrypted storage for backups

2. **System Security:**
   - Keep system packages updated
   - Use firewall to restrict access
   - Monitor system logs for suspicious activity
   - Regular security audits

3. **Access Control:**
   - Limit user access to production systems
   - Use SSH keys instead of passwords
   - Implement audit logging
   - Regular access reviews

### Operational Best Practices

1. **Change Management:**
   - Test all changes in paper mode first
   - Maintain configuration version control
   - Document all changes
   - Have rollback procedures ready

2. **Monitoring:**
   - Set up automated alerts
   - Regular health checks
   - Performance monitoring
   - Log analysis

3. **Backup and Recovery:**
   - Regular system backups
   - Test recovery procedures
   - Offsite backup storage
   - Documented recovery processes

This deployment guide provides a comprehensive framework for safely deploying and operating the Bank Nifty Options Trading System in production. Always prioritize safety and thorough testing before going live with real capital.