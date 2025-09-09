# Data Management System

This module provides comprehensive data management capabilities for the Bank Nifty Options Trading System.

## Components

### DataManager (`data_manager.py`)
The main data management class that provides:

- **ATM Strike Calculation**: Identifies At-The-Money strikes with configurable tie-breaker logic
- **Expiry Detection**: Automatically detects current month expiry dates with fallback mechanisms
- **Contract Metadata**: Retrieves lot size, strike spacing, and other contract specifications
- **Options Chain Validation**: Validates options chain data for completeness and accuracy
- **Liquidity Analysis**: Analyzes option liquidity based on volume and bid-ask spreads
- **Trading Signals**: Generates basic trading signals from options data

#### Key Features

**ATM Strike Calculation**:
- Finds strike nearest to spot price
- Configurable tie-breaker for equidistant strikes ('lower', 'higher', 'nearest')
- Validates distance within acceptable range
- Comprehensive error handling

**Expiry Detection**:
- Primary detection from API data
- Multiple fallback strategies (next Thursday, last Thursday of month, pattern search)
- Date validation and accuracy checks
- Handles edge cases and market holidays

**Contract Metadata**:
- Dynamic lot size detection
- Strike spacing calculation from available strikes
- Tick size information
- Exchange-specific parameters

### IndicatorCalculator (`indicators.py`)
Technical indicator calculations for historical data analysis:

- **Moving Averages**: SMA and EMA with configurable periods
- **Volatility**: Average True Range (ATR) calculation
- **IV Analysis**: Implied Volatility rank and percentile calculations
- **Spread Analysis**: Bid-ask spread quality assessment
- **Volume Analysis**: Volume patterns and trend detection
- **Data Quality**: Validation of historical data integrity

#### Supported Indicators

**Technical Indicators**:
- Simple Moving Average (SMA)
- Exponential Moving Average (EMA)
- Average True Range (ATR)

**Options-Specific Analysis**:
- IV Rank and Percentile
- Bid-Ask Spread Analysis
- Volume Pattern Analysis

**Data Quality Checks**:
- Price data validation
- Volume consistency checks
- Time series gap detection
- Data completeness assessment

## Usage Examples

### Basic ATM Strike Calculation

```python
from src.data.data_manager import DataManager
from src.api.angel_api_client import AngelAPIClient

# Initialize
api_client = AngelAPIClient(config)
data_manager = DataManager(api_client)

# Get ATM strike
atm_result = data_manager.get_atm_strike("BANKNIFTY")
if atm_result:
    print(f"ATM Strike: {atm_result.atm_strike}")
    print(f"Distance from spot: {atm_result.distance_from_spot}")
    print(f"Tie-breaker used: {atm_result.tie_breaker_used}")
```

### Historical Data with Indicators

```python
# Get historical data with technical indicators
result = data_manager.get_historical_data_with_indicators(
    symbol="BANKNIFTY",
    token="token",
    exchange="NSE",
    days_back=30,
    indicators=['sma_short', 'sma_long', 'ema_short', 'atr']
)

if result:
    print(f"Data points: {result['data_points']}")
    print(f"Indicators calculated: {list(result['indicators'].keys())}")
    print(f"Data quality: {result['data_quality']['valid']}")
```

### Options Chain Analysis

```python
# Get comprehensive options chain summary
summary = data_manager.get_options_chain_summary("BANKNIFTY")
if summary:
    print(f"Total strikes: {summary['total_strikes']}")
    print(f"ATM strike: {summary['atm_info']['atm_strike']}")
    print(f"Liquidity score: {summary.get('liquidity_score', 'N/A')}")
```

### Technical Indicator Calculations

```python
from src.data.indicators import IndicatorCalculator, HistoricalDataPoint

# Initialize calculator
calc = IndicatorCalculator()

# Calculate multiple indicators
indicators = calc.calculate_multiple_indicators(
    historical_data, 
    ['sma_short', 'sma_long', 'ema_short', 'atr']
)

# Get comprehensive summary
summary = calc.get_indicator_summary(historical_data)
print(f"Current price: {summary['price']['current']}")
print(f"SMA signal: {summary.get('signals', {}).get('sma_crossover', 'N/A')}")
```

## Configuration

The DataManager supports configuration through the ConfigManager:

```yaml
data_manager:
  atm_tie_breaker: 'lower'  # 'lower', 'higher', 'nearest'
  max_strike_distance: 0.05  # 5% max distance for ATM
  cache_ttl_seconds: 300     # 5 minutes cache TTL
  default_lot_size: 25       # Default BANKNIFTY lot size
  default_strike_spacing: 100.0  # Default strike spacing
```

## Error Handling

The system includes comprehensive error handling:

- **API Failures**: Graceful handling of API timeouts and errors
- **Data Validation**: Extensive validation of all input data
- **Fallback Mechanisms**: Multiple fallback strategies for critical operations
- **Logging**: Detailed logging for debugging and monitoring

## Testing

Comprehensive unit tests are provided in `tests/test_data_manager.py`:

- ATM strike calculation edge cases
- Expiry detection scenarios
- Contract metadata extraction
- Options chain validation
- Indicator calculations
- Data quality validation

Run tests with:
```bash
python -m pytest tests/test_data_manager.py -v
```

## Dependencies

- `angel_api_client`: For API interactions
- `market_data`: For market data management
- `trading_models`: For data models
- `config_manager`: For configuration management

## Performance Considerations

- **Caching**: Intelligent caching of market data and calculations
- **Validation**: Efficient data validation with early exit on errors
- **Memory**: Optimized data structures for large datasets
- **Concurrency**: Thread-safe operations where applicable

## Future Enhancements

- Real-time data streaming integration
- Advanced volatility surface modeling
- Machine learning-based signal generation
- Enhanced liquidity scoring algorithms
- Multi-underlying support