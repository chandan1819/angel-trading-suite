# 🚀 Angel Trading Suite

A professional, well-organized Python trading application for Angel Broking SmartAPI with interactive menu system, comprehensive market data analysis, and safe trading features.

![Python](https://img.shields.io/badge/python-v3.9+-blue.svg)
![License](https://img.shields.io/badge/license-MIT-green.svg)
![Angel Broking](https://img.shields.io/badge/Angel%20Broking-SmartAPI-orange.svg)

## ✨ Features

### 🔐 **Authentication & Security**
- Secure credential management
- TOTP-based two-factor authentication
- API key monitoring and diagnostics
- Comprehensive error handling

### 📊 **Market Data & Analysis**
- Real-time NIFTY 50 data
- Live stock prices with change indicators
- Market status monitoring
- Stock search functionality
- Historical data analysis

### 💼 **Trading & Order Management**
- **Demo Mode**: Safe practice environment
- **Live Trading**: Real order placement and management
- Order book management
- Position tracking
- Holdings analysis
- Risk management features

### 🎯 **Professional Features**
- Interactive menu system
- Organized modular codebase
- Comprehensive logging
- Built-in documentation
- Safety warnings for live trading

## 📁 Project Structure

```
angel-trading-suite/
├── 🔐 auth/           # Authentication & Login
├── 💼 trading/        # Trading & Orders  
├── 📊 market_data/    # Market Data & Analysis
├── 🔧 utils/          # Utilities & Tools
├── 📞 support/        # Support & Help
├── ⚙️  config/         # Configuration
├── 📚 docs/           # Documentation
└── 🚀 main.py         # Main Application
```

## 🚀 Quick Start

### 1. Clone Repository
```bash
git clone https://github.com/yourusername/angel-trading-suite.git
cd angel-trading-suite
```

### 2. Install Dependencies
```bash
pip install pyotp logzero websocket-client requests six python-dateutil pycryptodome
```

### 3. Setup Configuration
Create `config/config.json` with your Angel Broking credentials:

```json
{
    "api_key": "your_api_key",
    "client_code": "your_client_code", 
    "pin": "your_pin",
    "totp_secret": "your_totp_secret"
}
```

### 4. Run Application
```bash
python3 main.py
```

## 📋 Usage Examples

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

## 🛡️ Safety Features

- ✅ **Demo Modes** for safe testing
- ✅ **Confirmation prompts** before live trades
- ✅ **Clear warnings** for real trading functions
- ✅ **Secure credential storage**
- ✅ **Comprehensive error handling**

## 📊 Screenshots

### Main Menu
```
🚀 ANGEL BROKING TRADING SUITE
============================================================
1. 🔐 Authentication & Login
2. 📊 Market Data & Analysis  
3. 💼 Trading & Orders
4. 🔧 Utilities & Tools
5. 📞 Support & Help
```

### Market Data
```
📊 NIFTY 50: 24,773.15 (+0.13%)
🏆 TOP STOCKS DATA
📈 RELIANCE     ₹ 1,378.50 (+0.25%)
📉 TCS          ₹ 3,019.00 (-0.96%)
📈 HDFCBANK     ₹   966.00 (+0.27%)
```

## 🔧 Requirements

- Python 3.9+
- Angel Broking trading account
- Angel Broking API access
- Active internet connection

## 📞 Support

### Angel Broking Support
- **Email**: chdansinha1@hotmail.com
- **Portal**: https://smartapi.angelone.in/

### Common Issues
- **Invalid API Key**: Use `utils/diagnose_api.py`
- **Login Failed**: Check `config/config.json`
- **Rate Limiting**: Wait and retry

## ⚠️ Disclaimer

This software is for educational and personal use only. Trading involves financial risk. Always:
- Test with demo modes first
- Start with small amounts
- Do your own research
- Trade responsibly

## 📄 License

MIT License - see LICENSE file for details.

## 🤝 Contributing

1. Fork the repository
2. Create feature branch (`git checkout -b feature/amazing-feature`)
3. Commit changes (`git commit -m 'Add amazing feature'`)
4. Push to branch (`git push origin feature/amazing-feature`)
5. Open Pull Request

## ⭐ Show Your Support

If this project helped you, please give it a ⭐ star!

---

**Happy Trading! 📈**