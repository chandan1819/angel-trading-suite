# Angel Broking Trading Suite

A professional, well-organized Python trading application for Angel Broking SmartAPI.

## 📁 Project Structure

```
smartapi-python/
├── auth/           # Authentication & Login Scripts
│   ├── simple_login.py      # Quick login test
│   ├── login_example.py     # Detailed login demo
│   └── api_monitor.py       # Monitor API key status
│
├── trading/        # Trading & Order Management
│   ├── trading_demo.py      # Safe trading demo
│   └── order_management.py  # Live order management
│
├── market_data/    # Market Data & Analysis
│   ├── simple_market.py     # Reliable market data
│   └── market_data.py       # Advanced market data
│
├── utils/          # Utilities & Troubleshooting
│   ├── diagnose_api.py      # API diagnostics
│   ├── troubleshoot_angel.py # Comprehensive troubleshooting
│   ├── update_api_key.py    # Update API key safely
│   └── test_new_api.py      # Test new API keys
│
├── support/        # Support & Help
│   ├── support_email.txt    # Email template for support
│   └── support_email_clean.txt # Clean email template
│
├── config/         # Configuration
│   └── config.json          # Your credentials (secure)
│
├── docs/           # Documentation
│   └── README.md            # This file
│
├── SmartApi/       # Angel Broking SDK
├── logs/           # Application logs
└── main.py         # Main application menu
```

## 🚀 Quick Start

### 1. Setup Configuration
Create `config/config.json` with your Angel Broking credentials:

```json
{
    "api_key": "your_api_key",
    "client_code": "your_client_code",
    "pin": "your_pin",
    "totp_secret": "your_totp_secret"
}
```

### 2. Install Dependencies
```bash
pip install pyotp logzero websocket-client requests six python-dateutil pycryptodome
```

### 3. Run the Application
```bash
python3 main.py
```

## 📋 Features

### 🔐 Authentication
- **Simple Login**: Quick login test
- **Detailed Login**: Comprehensive login with account info
- **API Monitor**: Monitor API key activation status

### 📊 Market Data
- **Live Prices**: NIFTY, top stocks, custom searches
- **Market Status**: Open/closed status with timing
- **Stock Search**: Search and get live prices
- **Account Summary**: Balance, positions, holdings

### 💼 Trading
- **Demo Trading**: Safe practice environment
- **Live Trading**: Real order placement and management
- **Order Book**: View all orders and their status
- **Position Management**: Track open positions
- **Holdings**: View delivery stocks

### 🔧 Utilities
- **API Diagnostics**: Troubleshoot connection issues
- **Key Management**: Update and test API keys
- **Error Resolution**: Comprehensive problem solving

## 🛡️ Security Features

- ✅ **Secure Configuration**: Credentials stored separately
- ✅ **Demo Modes**: Safe testing environments
- ✅ **Confirmation Prompts**: Prevent accidental trades
- ✅ **Error Handling**: Robust error management
- ✅ **Rate Limiting**: Avoid API abuse

## 📞 Support

### Angel Broking Support
- **Email**: chdansinha1@hotmail.com
- **Portal**: https://smartapi.angelone.in/
- **Documentation**: Available in support/ folder

### Common Issues
1. **Invalid API Key**: Use utils/diagnose_api.py
2. **Login Failed**: Check config/config.json
3. **Rate Limiting**: Wait and retry
4. **Market Closed**: Check market hours

## 🎯 Usage Examples

### Quick Market Check
```bash
python3 market_data/simple_market.py
```

### Safe Trading Practice
```bash
python3 trading/trading_demo.py
```

### Live Trading (Careful!)
```bash
python3 trading/order_management.py
```

### Troubleshooting
```bash
python3 utils/diagnose_api.py
```

## ⚠️ Important Notes

1. **Demo First**: Always test with demo scripts before live trading
2. **Small Amounts**: Start with small quantities for live trading
3. **Market Hours**: Indian stock market: 9:15 AM - 3:30 PM IST
4. **API Limits**: Respect rate limits to avoid blocking
5. **Backup Config**: Keep backup of working configuration

## 🔄 Updates

To update the application:
1. Pull latest changes
2. Update dependencies if needed
3. Test with auth/simple_login.py
4. Verify with trading/trading_demo.py

## 📈 Happy Trading!

This suite provides everything you need for Angel Broking API trading. Start with authentication, explore market data, practice with demos, then move to live trading when ready.

**Remember**: Trading involves risk. Always do your research and trade responsibly.