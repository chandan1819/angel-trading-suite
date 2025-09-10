# How to Run Bank Nifty Options Trading System

## 🎯 Current Status

✅ **System is ready to run!**  
❌ **Import issues with main.py resolved**  
✅ **Simple trader created for easy usage**  

## 🚀 Quick Start (Recommended)

### 1. Set Up Credentials
```bash
# Set your Angel Broking API credentials
export ANGEL_API_KEY="your_api_key_here"
export ANGEL_CLIENT_CODE="your_client_code_here"  
export ANGEL_PIN="your_pin_here"
export ANGEL_TOTP_SECRET="your_totp_secret_here"
```

### 2. Test the System
```bash
# Test all components (SAFE - no trading)
python3 simple_trader.py --test
```

### 3. Try Paper Trading
```bash
# Paper trading simulation (SAFE - no real money)
python3 simple_trader.py --paper
```

### 4. Live Trading (Only After Testing!)
```bash
# ⚠️ WARNING: Uses real money!
python3 simple_trader.py --live
```

## 📋 Available Commands

### Simple Trader (Recommended)
```bash
python3 simple_trader.py --test     # Test system components
python3 simple_trader.py --paper    # Paper trading simulation  
python3 simple_trader.py --live     # Live trading (DANGEROUS!)
```

### Advanced Scripts
```bash
./start_live_trading.sh             # Full live trading with safety checks
./monitor_trading.sh                # Monitor running system
./emergency_stop.sh                 # Emergency stop all trading
```

### Manual Commands (If simple trader doesn't work)
```bash
# Test configuration
python3 -c "import yaml; print('YAML OK')"

# Check credentials
echo "API Key: $ANGEL_API_KEY"
echo "Client: $ANGEL_CLIENT_CODE"
```

## 🛡️ Safety Features

### Built-in Risk Controls
- **Max Daily Loss**: ₹5,000 (system stops automatically)
- **Profit Target**: ₹2,000 per trade
- **Stop Loss**: ₹1,000 per trade  
- **Max Concurrent Trades**: 2 only
- **Position Size**: 25 lots maximum
- **Conservative Strategy**: Straddle only

### Emergency Controls
```bash
# Immediate stop
echo "STOP" > emergency_stop.txt

# Force kill
Ctrl+C  # In the trading terminal

# Emergency script
./emergency_stop.sh
```

## 📊 What Each Mode Does

### Test Mode (`--test`)
- ✅ Checks API credentials
- ✅ Validates configuration
- ✅ Tests system components
- ❌ **No trading** - completely safe

### Paper Mode (`--paper`)  
- ✅ Simulates trading
- ✅ Uses real market data
- ✅ Tests strategies
- ❌ **No real money** - completely safe

### Live Mode (`--live`)
- ⚠️ **Uses real money**
- ⚠️ **Places actual orders**
- ⚠️ **Can lose money**
- ✅ Full risk controls active

## 🔍 Monitoring Your Trading

### Real-time Monitoring
```bash
# Monitor logs
tail -f logs/simple_trader_*.log

# System status  
python3 simple_trader.py --test

# Advanced monitoring
./monitor_trading.sh
```

### Log Files
- `logs/simple_trader_YYYYMMDD.log` - Main trading log
- `logs/live_YYYYMMDD_HHMMSS.log` - Live trading sessions
- `emergency_stop.txt` - Emergency stop trigger (create to stop)

## ⚠️ Important Warnings

### Before Live Trading
1. **✅ Test thoroughly** with `--test` and `--paper` modes
2. **✅ Verify credentials** are correct
3. **✅ Understand risk settings** (₹5,000 max daily loss)
4. **✅ Have emergency procedures ready**
5. **✅ Start with small amounts**

### During Live Trading
1. **👀 Monitor actively** - don't leave unattended
2. **📱 Watch your Angel Broking account**
3. **🚨 Know how to stop immediately**
4. **📊 Check P&L regularly**

### Risk Management
- **Never risk more than you can afford to lose**
- **Start with minimum position sizes**
- **Test all changes in paper mode first**
- **Have emergency stop procedures ready**

## 🔧 Troubleshooting

### Common Issues

#### "Missing environment variables"
```bash
# Solution: Set your credentials
export ANGEL_API_KEY="your_key"
export ANGEL_CLIENT_CODE="your_code"
export ANGEL_PIN="your_pin"
export ANGEL_TOTP_SECRET="your_secret"
```

#### "Configuration validation failed"
```bash
# Solution: Check config file
cat config/live_trading_config.yaml
```

#### "Import errors"
```bash
# Solution: Use simple trader instead of main.py
python3 simple_trader.py --test
```

#### System won't start
```bash
# Check Python version
python3 --version  # Should be 3.8+

# Check required packages
pip3 install pyyaml

# Test basic functionality
python3 -c "print('Python OK')"
```

## 📞 Getting Help

### Step-by-Step Debugging
1. **Test Python**: `python3 --version`
2. **Test credentials**: `echo $ANGEL_API_KEY`
3. **Test config**: `cat config/live_trading_config.yaml`
4. **Test system**: `python3 simple_trader.py --test`
5. **Check logs**: `tail logs/simple_trader_*.log`

### Emergency Procedures
1. **Immediate stop**: `echo "STOP" > emergency_stop.txt`
2. **Force kill**: Press `Ctrl+C`
3. **Manual intervention**: Log into Angel Broking directly

## 🎯 Recommended Workflow

### First Time Setup
```bash
# 1. Set credentials
export ANGEL_API_KEY="your_key"
# ... (set all 4 credentials)

# 2. Test system
python3 simple_trader.py --test

# 3. Try paper trading
python3 simple_trader.py --paper

# 4. Only then consider live trading
python3 simple_trader.py --live
```

### Daily Trading Routine
```bash
# Morning: Test system
python3 simple_trader.py --test

# If test passes: Start trading
python3 simple_trader.py --live

# Monitor throughout the day
tail -f logs/simple_trader_*.log
```

---

## 🚨 Final Warning

**This system trades real money in live mode. You can lose your entire investment. Only use live mode if you:**

1. ✅ Fully understand the risks
2. ✅ Have tested thoroughly in paper mode  
3. ✅ Can afford to lose the money
4. ✅ Know how to stop the system immediately
5. ✅ Will monitor it actively

**Start small, test thoroughly, and never risk more than you can afford to lose!**