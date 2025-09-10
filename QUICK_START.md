# Quick Start Guide - Bank Nifty Options Trading System

## 🚀 Get Started in 5 Minutes

### Step 1: Set Up Your Angel Broking API Credentials

You need to get these from your Angel Broking account:

1. **API Key** - From Angel Broking developer portal
2. **Client Code** - Your Angel Broking client ID
3. **PIN** - Your trading PIN
4. **TOTP Secret** - For two-factor authentication

### Step 2: Set Environment Variables

```bash
# Set your credentials (replace with actual values)
export ANGEL_API_KEY="your_actual_api_key_here"
export ANGEL_CLIENT_CODE="your_actual_client_code_here"
export ANGEL_PIN="your_actual_pin_here"
export ANGEL_TOTP_SECRET="your_actual_totp_secret_here"

# Make them permanent (optional)
echo 'export ANGEL_API_KEY="your_actual_api_key_here"' >> ~/.bashrc
echo 'export ANGEL_CLIENT_CODE="your_actual_client_code_here"' >> ~/.bashrc
echo 'export ANGEL_PIN="your_actual_pin_here"' >> ~/.bashrc
echo 'export ANGEL_TOTP_SECRET="your_actual_totp_secret_here"' >> ~/.bashrc

# Reload your shell
source ~/.bashrc
```

### Step 3: Test the System

```bash
# Test system components
python3 simple_trader.py --test
```

### Step 4: Try Paper Trading (Safe Mode)

```bash
# Run paper trading (no real money)
python3 simple_trader.py --paper
```

### Step 5: Live Trading (ONLY AFTER THOROUGH TESTING!)

```bash
# ⚠️ WARNING: This uses real money!
python3 simple_trader.py --live
```

## 🛡️ Safety Features

- **Paper Mode**: Test without real money
- **Conservative Settings**: Small position sizes, tight risk controls
- **Emergency Stop**: Create `emergency_stop.txt` to stop immediately
- **Daily Loss Limits**: Automatic shutdown at ₹5,000 loss
- **Multiple Confirmations**: Required for live trading

## 📊 Default Risk Settings

- **Max Daily Loss**: ₹5,000
- **Profit Target**: ₹2,000 per trade
- **Stop Loss**: ₹1,000 per trade
- **Max Concurrent Trades**: 2
- **Position Size**: 25 lots maximum
- **Strategy**: Conservative straddle only

## 🆘 Emergency Procedures

### Immediate Stop
```bash
# Create emergency stop file
echo "STOP" > emergency_stop.txt

# Or use the script
./emergency_stop.sh
```

### Force Kill
```bash
# Press Ctrl+C in the trading terminal
# Or kill the process
pkill -f "python.*simple_trader"
```

## 📁 Important Files

- `config/live_trading_config.yaml` - Main configuration
- `simple_trader.py` - Easy-to-use trading runner
- `logs/` - All log files
- `emergency_stop.txt` - Emergency stop trigger

## 🔍 Monitoring

```bash
# Monitor logs
tail -f logs/simple_trader_*.log

# Check system status
python3 simple_trader.py --test

# Monitor in real-time
./monitor_trading.sh
```

## ⚠️ Important Warnings

1. **NEVER start with live trading** - Always test in paper mode first
2. **Start small** - Use minimum position sizes initially
3. **Monitor actively** - Don't leave the system unattended
4. **Have emergency procedures ready** - Know how to stop immediately
5. **Understand the risks** - You can lose money in live trading

## 🆘 Need Help?

1. **Test Issues**: Run `python3 simple_trader.py --test`
2. **Configuration**: Check `config/live_trading_config.yaml`
3. **Credentials**: Verify environment variables are set
4. **Logs**: Check `logs/simple_trader_*.log` for errors

## 📞 Support

- Check the logs first: `tail -f logs/simple_trader_*.log`
- Review configuration: `config/live_trading_config.yaml`
- Test system: `python3 simple_trader.py --test`

---

**Remember: Trading involves risk. Never risk more than you can afford to lose!**