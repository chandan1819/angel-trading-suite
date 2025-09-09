"""
Pytest configuration and shared fixtures for the Bank Nifty Options Trading System tests.

This module provides common test configuration, fixtures, and utilities
used across all test modules.
"""

import pytest
import os
import sys
import tempfile
import shutil
from datetime import datetime, timedelta
from unittest.mock import Mock, patch

# Add src to Python path for imports
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'src'))

from tests.mock_angel_api import MockAngelAPI, MockAPIFactory
from src.models.config_models import TradingConfig, RiskConfig, StrategyConfig
from src.models.trading_models import TradingSignal, SignalType, OptionType


@pytest.fixture(scope="session")
def test_data_dir():
    """Create temporary directory for test data"""
    temp_dir = tempfile.mkdtemp(prefix="banknifty_tests_")
    yield temp_dir
    shutil.rmtree(temp_dir, ignore_errors=True)


@pytest.fixture
def mock_angel_api():
    """Create mock Angel API for testing"""
    return MockAPIFactory.create_normal_api()


@pytest.fixture
def error_prone_api():
    """Create error-prone mock Angel API"""
    return MockAPIFactory.create_error_prone_api()


@pytest.fixture
def rate_limited_api():
    """Create rate-limited mock Angel API"""
    return MockAPIFactory.create_rate_limited_api()


@pytest.fixture
def trading_config():
    """Create standard trading configuration for tests"""
    config = TradingConfig()
    
    # Risk configuration
    config.risk = RiskConfig(
        max_daily_loss=5000.0,
        max_concurrent_trades=3,
        profit_target=2000.0,
        stop_loss=1000.0,
        position_size_method="fixed",
        margin_buffer=0.2,
        max_position_size=5,
        daily_trade_limit=10,
        emergency_stop_file="test_emergency_stop.txt"
    )
    
    # Strategy configuration
    config.strategy = StrategyConfig(
        enabled_strategies=["straddle", "directional"],
        evaluation_interval=60,
        max_signals_per_cycle=2,
        strategy_parameters={
            "straddle": {
                "min_iv_rank": 70.0,
                "strategy_type": "straddle",
                "enabled": True
            },
            "directional": {
                "ema_fast_period": 9,
                "ema_slow_period": 21,
                "enabled": True
            }
        }
    )
    
    # Trading configuration
    config.mode = "paper"
    config.underlying_symbol = "BANKNIFTY"
    config.polling_interval = 30
    
    return config


@pytest.fixture
def sample_trading_signal():
    """Create sample trading signal for tests"""
    return TradingSignal(
        strategy_name="test_strategy",
        signal_type=SignalType.BUY,
        underlying="BANKNIFTY",
        strikes=[50000.0],
        option_types=[OptionType.CE],
        quantities=[1],
        confidence=0.8,
        target_pnl=2000.0,
        stop_loss=-1000.0,
        timestamp=datetime.now()
    )


@pytest.fixture
def sample_straddle_signal():
    """Create sample straddle signal for tests"""
    return TradingSignal(
        strategy_name="straddle_strategy",
        signal_type=SignalType.STRADDLE,
        underlying="BANKNIFTY",
        strikes=[50000.0, 50000.0],
        option_types=[OptionType.CE, OptionType.PE],
        quantities=[1, 1],
        confidence=0.75,
        target_pnl=2000.0,
        stop_loss=-1000.0,
        timestamp=datetime.now()
    )


@pytest.fixture
def sample_market_data():
    """Create comprehensive sample market data"""
    from src.api.market_data import OptionsChainData
    
    # Create realistic options chain
    strikes_data = []
    for strike in range(49000, 51100, 100):
        distance_from_atm = abs(strike - 50000)
        
        call_premium = max(5.0, 150 - distance_from_atm * 0.1)
        put_premium = max(5.0, 140 - distance_from_atm * 0.1)
        
        strike_data = {
            'strike': strike,
            'call': {
                'symbol': f'BANKNIFTY2412{strike}CE',
                'token': f'{strike}1',
                'ltp': round(call_premium, 2),
                'bid': round(call_premium * 0.98, 2),
                'ask': round(call_premium * 1.02, 2),
                'volume': max(100, 2000 - distance_from_atm * 2),
                'oi': max(500, 10000 - distance_from_atm * 5),
                'delta': max(0.01, 0.5 - distance_from_atm * 0.001),
                'theta': -0.5,
                'vega': 0.3,
                'gamma': 0.001,
                'iv': 0.25
            },
            'put': {
                'symbol': f'BANKNIFTY2412{strike}PE',
                'token': f'{strike}2',
                'ltp': round(put_premium, 2),
                'bid': round(put_premium * 0.98, 2),
                'ask': round(put_premium * 1.02, 2),
                'volume': max(100, 1800 - distance_from_atm * 2),
                'oi': max(500, 9500 - distance_from_atm * 5),
                'delta': min(-0.01, -0.5 + distance_from_atm * 0.001),
                'theta': -0.5,
                'vega': 0.3,
                'gamma': 0.001,
                'iv': 0.24
            }
        }
        strikes_data.append(strike_data)
    
    options_chain = OptionsChainData(
        underlying_symbol="BANKNIFTY",
        underlying_price=50000.0,
        expiry_date=(datetime.now() + timedelta(days=7)).strftime('%Y-%m-%d'),
        strikes=strikes_data,
        timestamp=datetime.now(),
        atm_strike=50000.0
    )
    
    # Create historical data
    historical_data = []
    base_price = 50000.0
    current_time = datetime.now()
    
    for i in range(100):
        timestamp = current_time - timedelta(minutes=100-i)
        price_change = (i % 10 - 5) * 10
        price = base_price + price_change + (i * 2)
        
        historical_data.append({
            'timestamp': timestamp.isoformat(),
            'open': round(price - 5, 2),
            'high': round(price + 15, 2),
            'low': round(price - 10, 2),
            'close': round(price, 2),
            'volume': 10000 + (i % 5) * 2000
        })
    
    return {
        'options_chain': options_chain,
        'historical_data': historical_data,
        'indicators': {
            'iv_rank': 75.0,
            'iv_percentile': 80.0,
            'ema_9': 49950.0,
            'ema_21': 49900.0,
            'ema_cross_signal': 'bullish',
            'atr': 250.0,
            'atr_breakout_signal': 'neutral',
            'rsi': 65.0,
            'momentum': 1.5,
            'volume_confirmation': True,
            'bid_ask_spread_avg': 2.5,
            'option_volume_ratio': 1.2
        },
        'current_time': datetime.now(),
        'market_hours': True,
        'volatility_regime': 'high'
    }


@pytest.fixture(autouse=True)
def cleanup_test_files():
    """Automatically cleanup test files after each test"""
    yield
    
    # Clean up any test files
    test_files = [
        "test_emergency_stop.txt",
        "test_emergency.txt",
        "test_config.yaml",
        "test_log.txt"
    ]
    
    for file_path in test_files:
        if os.path.exists(file_path):
            try:
                os.unlink(file_path)
            except:
                pass


@pytest.fixture
def mock_datetime():
    """Mock datetime for consistent testing"""
    with patch('src.models.trading_models.datetime') as mock_dt:
        mock_dt.now.return_value = datetime(2024, 12, 25, 10, 30, 0)
        mock_dt.strptime = datetime.strptime
        mock_dt.side_effect = lambda *args, **kwargs: datetime(*args, **kwargs)
        yield mock_dt


# Test markers for categorizing tests
def pytest_configure(config):
    """Configure pytest markers"""
    config.addinivalue_line(
        "markers", "unit: mark test as a unit test"
    )
    config.addinivalue_line(
        "markers", "integration: mark test as an integration test"
    )
    config.addinivalue_line(
        "markers", "slow: mark test as slow running"
    )
    config.addinivalue_line(
        "markers", "api: mark test as requiring API mocking"
    )
    config.addinivalue_line(
        "markers", "risk: mark test as testing risk management"
    )
    config.addinivalue_line(
        "markers", "strategy: mark test as testing trading strategies"
    )


# Custom assertions for trading-specific tests
def assert_valid_signal(signal):
    """Assert that a trading signal is valid"""
    assert signal is not None, "Signal should not be None"
    assert signal.validate(), "Signal should pass validation"
    assert signal.strategy_name, "Signal should have strategy name"
    assert signal.underlying, "Signal should have underlying symbol"
    assert len(signal.strikes) > 0, "Signal should have strikes"
    assert len(signal.option_types) > 0, "Signal should have option types"
    assert len(signal.quantities) > 0, "Signal should have quantities"
    assert 0.0 <= signal.confidence <= 1.0, "Signal confidence should be between 0 and 1"


def assert_valid_trade(trade):
    """Assert that a trade is valid"""
    assert trade is not None, "Trade should not be None"
    assert trade.trade_id, "Trade should have ID"
    assert trade.strategy, "Trade should have strategy"
    assert trade.underlying_symbol, "Trade should have underlying symbol"
    assert trade.entry_time, "Trade should have entry time"
    assert len(trade.legs) > 0, "Trade should have legs"


def assert_pnl_calculation(trade, expected_pnl, tolerance=0.01):
    """Assert P&L calculation is correct within tolerance"""
    actual_pnl = trade.calculate_current_pnl()
    assert abs(actual_pnl - expected_pnl) <= tolerance, \
        f"P&L mismatch: expected {expected_pnl}, got {actual_pnl}"


# Add custom assertions to pytest namespace
pytest.assert_valid_signal = assert_valid_signal
pytest.assert_valid_trade = assert_valid_trade
pytest.assert_pnl_calculation = assert_pnl_calculation


# Performance testing utilities
class PerformanceTimer:
    """Context manager for timing test operations"""
    
    def __init__(self, max_time=None):
        self.max_time = max_time
        self.start_time = None
        self.end_time = None
    
    def __enter__(self):
        import time
        self.start_time = time.time()
        return self
    
    def __exit__(self, exc_type, exc_val, exc_tb):
        import time
        self.end_time = time.time()
        self.elapsed = self.end_time - self.start_time
        
        if self.max_time and self.elapsed > self.max_time:
            pytest.fail(f"Operation took {self.elapsed:.2f}s, expected < {self.max_time}s")
    
    @property
    def elapsed_time(self):
        return self.elapsed if hasattr(self, 'elapsed') else None


@pytest.fixture
def performance_timer():
    """Fixture for performance timing"""
    return PerformanceTimer


# Test data generators
class TestDataGenerator:
    """Generate test data for various scenarios"""
    
    @staticmethod
    def generate_price_series(length=100, start_price=50000.0, volatility=0.02):
        """Generate realistic price series"""
        import random
        prices = [start_price]
        
        for _ in range(length - 1):
            change = random.gauss(0, volatility)
            new_price = prices[-1] * (1 + change)
            prices.append(max(1.0, new_price))  # Ensure positive prices
        
        return prices
    
    @staticmethod
    def generate_option_chain(spot_price=50000.0, strikes_range=(-1000, 1000, 100)):
        """Generate realistic option chain data"""
        strikes = []
        start, end, step = strikes_range
        
        for strike_offset in range(start, end + 1, step):
            strike = spot_price + strike_offset
            distance = abs(strike - spot_price)
            
            # Realistic option pricing
            intrinsic_call = max(0, spot_price - strike)
            intrinsic_put = max(0, strike - spot_price)
            
            time_value = max(5.0, 100 - distance * 0.05)
            
            strikes.append({
                'strike': strike,
                'call': {
                    'ltp': intrinsic_call + time_value,
                    'bid': intrinsic_call + time_value * 0.98,
                    'ask': intrinsic_call + time_value * 1.02,
                    'volume': max(100, 1000 - distance),
                    'oi': max(500, 5000 - distance * 2)
                },
                'put': {
                    'ltp': intrinsic_put + time_value,
                    'bid': intrinsic_put + time_value * 0.98,
                    'ask': intrinsic_put + time_value * 1.02,
                    'volume': max(100, 900 - distance),
                    'oi': max(500, 4500 - distance * 2)
                }
            })
        
        return strikes


@pytest.fixture
def test_data_generator():
    """Fixture for test data generator"""
    return TestDataGenerator