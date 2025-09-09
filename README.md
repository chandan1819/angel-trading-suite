# Bank Nifty Options Trading System

A production-quality automated options trading system for Bank Nifty that integrates with Angel Broking API. The system supports multiple trading strategies, comprehensive risk management, and both paper and live trading modes.

## Features

- **Multiple Trading Strategies**: Straddle, directional, iron condor, Greeks-based, and volatility strategies
- **Risk Management**: Hard profit targets (₹2,000) and stop-losses (₹1,000) with daily limits
- **Paper & Live Trading**: Test strategies safely before risking capital
- **Comprehensive Logging**: Detailed trade logs and performance analytics
- **Backtesting Engine**: Historical strategy validation
- **Configuration Management**: YAML/JSON configuration with environment variable support
- **Notification System**: Webhook, email, Slack, and Telegram alerts

## Project Structure

```
banknifty-options-trading/
├── src/                          # Source code
│   ├── models/                   # Data models
│   │   ├── trading_models.py     # Trading entities (Trade, Signal, Option, etc.)
│   │   └── config_models.py      # Configuration models
│   ├── config/                   # Configuration management
│   │   └── config_manager.py     # ConfigManager class
│   ├── interfaces/               # Base interfaces and abstract classes
│   │   └── base_interfaces.py    # Core system interfaces
│   └── __init__.py
├── config/                       # Configuration files
│   └── trading_config.example.yaml  # Example configuration
├── tests/                        # Unit tests
│   └── test_config_manager.py    # Configuration manager tests
├── logs/                         # Log files (created at runtime)
├── demo_setup.py                 # Setup demonstration script
└── README.md                     # This file
```

## Quick Start

### 1. Installation

```bash
# Clone the repository
git clone <repository-url>
cd banknifty-options-trading

# Install dependencies
pip install -r requirements.txt
```

### 2. Configuration

Copy the example configuration and customize it:

```bash
cp config/trading_config.example.yaml config/trading_config.yaml
```

Set up environment variables for API credentials:

```bash
export ANGEL_API_KEY="your_api_key"
export ANGEL_CLIENT_CODE="your_client_code"
export ANGEL_PIN="your_pin"
export ANGEL_TOTP_SECRET="your_totp_secret"
```

### 3. Verify Setup

Run the setup demo to verify everything is working:

```bash
python3 demo_setup.py
```

### 4. Run Tests

Execute the test suite to ensure system integrity:

```bash
python3 -m pytest tests/ -v
```

## Configuration

The system uses YAML configuration files with the following main sections:

- **mode**: `paper` or `live` trading mode
- **api**: Angel Broking API settings and credentials
- **risk**: Risk management parameters (profit targets, stop losses, limits)
- **strategy**: Strategy-specific configurations
- **logging**: Logging levels and output settings
- **notification**: Alert and notification settings
- **backtest**: Backtesting parameters

### Example Configuration

```yaml
mode: paper
underlying_symbol: BANKNIFTY

risk:
  profit_target: 2000.0
  stop_loss: 1000.0
  max_daily_loss: 5000.0
  max_concurrent_trades: 3

strategy:
  enabled_strategies:
    - straddle
    - directional
  
  straddle:
    enabled: true
    min_iv_rank: 0.5
    max_dte: 7
```

## Core Components

### Data Models

- **Option**: Represents an option contract with Greeks and market data
- **Trade**: Multi-leg trade with P&L tracking
- **TradingSignal**: Strategy-generated trading signals
- **TradingConfig**: Complete system configuration

### Interfaces

- **IStrategy**: Base interface for trading strategies
- **IDataProvider**: Market data provider interface
- **IRiskManager**: Risk management interface
- **IOrderManager**: Order execution interface

### Configuration Management

The `ConfigManager` class provides:
- YAML/JSON configuration loading
- Environment variable substitution
- Credential sanitization
- Configuration validation
- Caching and error handling

## Development

### Adding New Strategies

1. Inherit from `BaseStrategy` class
2. Implement the `evaluate()` method
3. Add strategy configuration to config models
4. Register strategy in the strategy manager

### Running Tests

```bash
# Run all tests
python3 -m pytest tests/ -v

# Run specific test file
python3 -m pytest tests/test_config_manager.py -v

# Run with coverage
python3 -m pytest tests/ --cov=src --cov-report=html
```

### Code Style

The project follows Python best practices:
- Type hints for all public methods
- Comprehensive docstrings
- Dataclasses for data models
- Abstract base classes for interfaces
- Comprehensive error handling

## Security

- API credentials are never hardcoded
- Environment variable substitution for sensitive data
- Configuration sanitization before saving
- Secure credential validation

## Risk Management

The system implements multiple layers of risk control:
- Per-trade profit targets and stop losses
- Daily loss limits
- Position size limits
- Emergency stop mechanisms
- Margin requirement validation

## Logging and Monitoring

- Structured JSON/CSV logging
- Trade ledger with detailed records
- Performance metrics calculation
- Real-time P&L tracking
- Configurable notification alerts

## License

This project is for educational and research purposes. Please ensure compliance with all applicable trading regulations and broker terms of service.

## Disclaimer

This software is provided for educational purposes only. Trading in financial markets involves substantial risk of loss. The authors are not responsible for any financial losses incurred through the use of this software. Always test thoroughly in paper trading mode before using real capital.