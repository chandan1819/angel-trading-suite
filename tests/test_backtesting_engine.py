"""
Unit tests for BacktestingEngine class.

Tests backtesting logic including historical data simulation,
trade execution, and performance metrics calculation.
"""

import unittest
from unittest.mock import Mock, patch, MagicMock
from datetime import datetime, timedelta
import tempfile
import shutil
from pathlib import Path

from src.backtesting.backtesting_engine import BacktestingEngine
from src.backtesting.models import BacktestResult, PerformanceMetrics
from src.backtesting.historical_simulator import SimulatedTrade
from src.models.trading_models import (
    TradingSignal, SignalType, OptionType, TradeStatus
)
from src.strategies.base_strategy import BaseStrategy
from src.data.data_manager import DataManager


class MockStrategy(BaseStrategy):
    """Mock strategy for testing"""
    
    def __init__(self, name="TestStrategy", config=None):
        super().__init__(name, config or {})
        self.signal_to_return = None
    
    def evaluate(self, market_data):
        return self.signal_to_return


class TestBacktestingEngine(unittest.TestCase):
    """Test cases for BacktestingEngine"""
    
    def setUp(self):
        """Set up test fixtures"""
        self.mock_data_manager = Mock(spec=DataManager)
        self.config = {
            'initial_capital': 100000.0,
            'commission_per_trade': 20.0,
            'slippage_pct': 0.1,
            'fill_probability': 1.0,  # 100% fill for testing
            'max_trades_per_day': 5,
            'risk_free_rate': 0.06,
            'trading_hours': {'start': '09:15', 'end': '15:30'},
            'early_exit_time': '15:00'
        }
        
        self.engine = BacktestingEngine(self.mock_data_manager, self.config)
        self.strategy = MockStrategy()
        
        # Create temporary directory for test reports
        self.temp_dir = tempfile.mkdtemp()
    
    def tearDown(self):
        """Clean up test fixtures"""
        shutil.rmtree(self.temp_dir, ignore_errors=True)
    
    def test_initialization(self):
        """Test BacktestingEngine initialization"""
        self.assertIsNotNone(self.engine)
        self.assertEqual(self.engine.config['initial_capital'], 100000.0)
        self.assertIsNotNone(self.engine.simulator)
        self.assertIsNotNone(self.engine.reporter)
    
    def test_get_historical_data_range(self):
        """Test historical data retrieval"""
        # Mock historical data
        mock_data = [
            {
                'date': '2024-01-01',
                'open': 45000,
                'high': 45500,
                'low': 44800,
                'close': 45200,
                'volume': 1000000
            },
            {
                'date': '2024-01-02',
                'open': 45200,
                'high': 45800,
                'low': 45000,
                'close': 45600,
                'volume': 1200000
            }
        ]
        
        self.mock_data_manager.get_historical_data.return_value = mock_data
        
        result = self.engine._get_historical_data_range(
            "BANKNIFTY", "2024-01-01", "2024-01-02"
        )
        
        self.assertEqual(len(result), 2)
        self.assertIn('timestamp', result[0])
        self.assertIn('underlying_symbol', result[0])
        self.mock_data_manager.get_historical_data.assert_called_once()
    
    def test_simulate_options_chain(self):
        """Test options chain simulation"""
        data_point = {
            'close': 45000,
            'timestamp': datetime(2024, 1, 1),
            'underlying_symbol': 'BANKNIFTY'
        }
        
        options_chain = self.engine._simulate_options_chain(data_point, "BANKNIFTY")
        
        self.assertIsNotNone(options_chain)
        self.assertEqual(options_chain['underlying_symbol'], 'BANKNIFTY')
        self.assertEqual(options_chain['underlying_price'], 45000)
        self.assertIn('strikes', options_chain)
        self.assertGreater(len(options_chain['strikes']), 0)
        
        # Check ATM strike calculation
        self.assertEqual(options_chain['atm_strike'], 45000)  # Should be rounded to nearest 100
    
    def test_simulate_option_data(self):
        """Test individual option data simulation"""
        data_point = {
            'close': 45000,
            'volume': 1000000,
            'underlying_symbol': 'BANKNIFTY'
        }
        
        # Test call option
        call_data = self.engine._simulate_option_data(45000, 45000, 'CE', data_point)
        
        self.assertIn('symbol', call_data)
        self.assertIn('ltp', call_data)
        self.assertIn('bid', call_data)
        self.assertIn('ask', call_data)
        self.assertGreater(call_data['ltp'], 0)
        self.assertGreater(call_data['ask'], call_data['bid'])
        
        # Test put option
        put_data = self.engine._simulate_option_data(45000, 45000, 'PE', data_point)
        
        self.assertIn('symbol', put_data)
        self.assertGreater(put_data['ltp'], 0)
    
    def test_calculate_performance_metrics_empty_trades(self):
        """Test performance metrics calculation with no trades"""
        metrics = self.engine._calculate_performance_metrics([])
        
        self.assertEqual(metrics.total_trades, 0)
        self.assertEqual(metrics.total_pnl, 0.0)
        self.assertEqual(metrics.win_rate, 0.0)
    
    def test_calculate_performance_metrics_with_trades(self):
        """Test performance metrics calculation with sample trades"""
        # Create mock trades
        trades = []
        
        # Winning trade
        winning_trade = Mock(spec=SimulatedTrade)
        winning_trade.status = TradeStatus.CLOSED
        winning_trade.realized_pnl = 1500.0
        winning_trade.entry_time = datetime(2024, 1, 1, 10, 0)
        winning_trade.exit_time = datetime(2024, 1, 1, 14, 0)
        trades.append(winning_trade)
        
        # Losing trade
        losing_trade = Mock(spec=SimulatedTrade)
        losing_trade.status = TradeStatus.CLOSED
        losing_trade.realized_pnl = -800.0
        losing_trade.entry_time = datetime(2024, 1, 2, 10, 0)
        losing_trade.exit_time = datetime(2024, 1, 2, 13, 0)
        trades.append(losing_trade)
        
        metrics = self.engine._calculate_performance_metrics(trades)
        
        self.assertEqual(metrics.total_trades, 2)
        self.assertEqual(metrics.total_pnl, 700.0)
        self.assertEqual(metrics.winning_trades, 1)
        self.assertEqual(metrics.losing_trades, 1)
        self.assertEqual(metrics.win_rate, 50.0)
        self.assertEqual(metrics.avg_winning_trade, 1500.0)
        self.assertEqual(metrics.avg_losing_trade, -800.0)
        self.assertEqual(metrics.largest_win, 1500.0)
        self.assertEqual(metrics.largest_loss, -800.0)
    
    def test_calculate_drawdown(self):
        """Test drawdown calculation"""
        # Create trades with varying P&L
        trades = []
        
        trade1 = Mock(spec=SimulatedTrade)
        trade1.status = TradeStatus.CLOSED
        trade1.realized_pnl = 1000.0
        trades.append(trade1)
        
        trade2 = Mock(spec=SimulatedTrade)
        trade2.status = TradeStatus.CLOSED
        trade2.realized_pnl = -1500.0  # This creates drawdown
        trades.append(trade2)
        
        trade3 = Mock(spec=SimulatedTrade)
        trade3.status = TradeStatus.CLOSED
        trade3.realized_pnl = 800.0
        trades.append(trade3)
        
        max_dd, max_dd_pct = self.engine._calculate_drawdown(trades)
        
        self.assertEqual(max_dd, 500.0)  # Peak was 1000, lowest was 500
        self.assertGreater(max_dd_pct, 0)
    
    def test_calculate_sharpe_ratio(self):
        """Test Sharpe ratio calculation"""
        pnls = [100, -50, 200, -30, 150, -80, 120]
        
        sharpe = self.engine._calculate_sharpe_ratio(pnls)
        
        self.assertIsInstance(sharpe, float)
        # Sharpe ratio should be calculated (exact value depends on implementation)
    
    def test_calculate_consecutive_stats(self):
        """Test consecutive wins/losses calculation"""
        pnls = [100, 200, -50, -30, -20, 150, 80, -40]
        
        max_wins, max_losses = self.engine._calculate_consecutive_stats(pnls)
        
        self.assertEqual(max_wins, 2)  # Two consecutive wins at start
        self.assertEqual(max_losses, 3)  # Three consecutive losses in middle
    
    def test_calculate_daily_pnl(self):
        """Test daily P&L calculation"""
        trades = []
        
        # Trade 1 on day 1
        trade1 = Mock(spec=SimulatedTrade)
        trade1.status = TradeStatus.CLOSED
        trade1.realized_pnl = 1000.0
        trade1.exit_time = datetime(2024, 1, 1, 15, 0)
        trades.append(trade1)
        
        # Trade 2 on day 1
        trade2 = Mock(spec=SimulatedTrade)
        trade2.status = TradeStatus.CLOSED
        trade2.realized_pnl = -300.0
        trade2.exit_time = datetime(2024, 1, 1, 15, 30)
        trades.append(trade2)
        
        # Trade 3 on day 2
        trade3 = Mock(spec=SimulatedTrade)
        trade3.status = TradeStatus.CLOSED
        trade3.realized_pnl = 500.0
        trade3.exit_time = datetime(2024, 1, 2, 14, 0)
        trades.append(trade3)
        
        daily_pnl = self.engine._calculate_daily_pnl(trades)
        
        self.assertEqual(len(daily_pnl), 2)
        self.assertEqual(daily_pnl[0], ('2024-01-01', 700.0))  # 1000 - 300
        self.assertEqual(daily_pnl[1], ('2024-01-02', 500.0))
    
    def test_calculate_equity_curve(self):
        """Test equity curve calculation"""
        initial_capital = 100000.0
        trades = []
        
        trade1 = Mock(spec=SimulatedTrade)
        trade1.status = TradeStatus.CLOSED
        trade1.realized_pnl = 1000.0
        trade1.exit_time = datetime(2024, 1, 1, 15, 0)
        trades.append(trade1)
        
        trade2 = Mock(spec=SimulatedTrade)
        trade2.status = TradeStatus.CLOSED
        trade2.realized_pnl = -500.0
        trade2.exit_time = datetime(2024, 1, 2, 15, 0)
        trades.append(trade2)
        
        equity_curve = self.engine._calculate_equity_curve(trades, initial_capital)
        
        self.assertEqual(len(equity_curve), 2)
        self.assertEqual(equity_curve[0], ('2024-01-01', 101000.0))  # 100000 + 1000
        self.assertEqual(equity_curve[1], ('2024-01-02', 100500.0))  # 101000 - 500
    
    def test_prepare_market_data(self):
        """Test market data preparation"""
        data_point = {
            'close': 45000,
            'high': 45200,
            'low': 44800,
            'volume': 1000000,
            'timestamp': datetime(2024, 1, 1)
        }
        
        market_data = self.engine._prepare_market_data(data_point, "BANKNIFTY")
        
        self.assertIsNotNone(market_data)
        self.assertIn('options_chain', market_data)
        self.assertIn('underlying_price', market_data)
        self.assertIn('current_time', market_data)
        self.assertIn('indicators', market_data)
        self.assertEqual(market_data['underlying_price'], 45000)
    
    def test_get_next_expiry_date(self):
        """Test next expiry date calculation"""
        # Test with Monday (should get Thursday of same week)
        monday = datetime(2024, 1, 1)  # Assuming this is a Monday
        expiry = self.engine._get_next_expiry_date(monday)
        
        self.assertIsInstance(expiry, str)
        self.assertRegex(expiry, r'\d{4}-\d{2}-\d{2}')
        
        # Parse and verify it's a future date
        expiry_date = datetime.strptime(expiry, '%Y-%m-%d')
        self.assertGreater(expiry_date, monday)
    
    def test_should_exit_time_based(self):
        """Test time-based exit logic"""
        trade = Mock(spec=SimulatedTrade)
        trade.entry_time = datetime(2024, 1, 1, 10, 0)
        
        # Test early exit time
        early_exit_time = datetime(2024, 1, 1, 15, 0)
        should_exit = self.engine._should_exit_time_based(trade, early_exit_time)
        self.assertTrue(should_exit)
        
        # Test normal trading time
        normal_time = datetime(2024, 1, 1, 14, 0)
        should_exit = self.engine._should_exit_time_based(trade, normal_time)
        self.assertFalse(should_exit)
    
    @patch('src.backtesting.backtesting_engine.BacktestingEngine._get_historical_data_range')
    @patch('src.backtesting.backtesting_engine.BacktestingEngine._simulate_trading_period')
    def test_run_backtest(self, mock_simulate, mock_get_data):
        """Test complete backtest run"""
        # Mock historical data
        mock_get_data.return_value = [
            {
                'date': '2024-01-01',
                'close': 45000,
                'timestamp': datetime(2024, 1, 1)
            }
        ]
        
        # Mock simulated trades
        mock_trade = Mock(spec=SimulatedTrade)
        mock_trade.status = TradeStatus.CLOSED
        mock_trade.realized_pnl = 1000.0
        mock_trade.entry_time = datetime(2024, 1, 1, 10, 0)
        mock_trade.exit_time = datetime(2024, 1, 1, 15, 0)
        mock_simulate.return_value = [mock_trade]
        
        # Run backtest
        result = self.engine.run_backtest(
            self.strategy, "2024-01-01", "2024-01-31", "BANKNIFTY"
        )
        
        self.assertIsInstance(result, BacktestResult)
        self.assertEqual(result.strategy_name, "TestStrategy")
        self.assertEqual(result.start_date, "2024-01-01")
        self.assertEqual(result.end_date, "2024-01-31")
        self.assertEqual(result.initial_capital, 100000.0)
        self.assertIsNotNone(result.performance_metrics)
        self.assertIsNotNone(result.metadata)
    
    def test_generate_report(self):
        """Test report generation"""
        # Create a simple backtest result
        result = BacktestResult(
            strategy_name="TestStrategy",
            start_date="2024-01-01",
            end_date="2024-01-31",
            initial_capital=100000.0,
            final_capital=101000.0
        )
        
        result.performance_metrics = PerformanceMetrics(
            total_pnl=1000.0,
            total_trades=5,
            win_rate=60.0
        )
        
        # Generate report (should not raise exception)
        try:
            self.engine.generate_report(result, self.temp_dir)
            
            # Check if files were created
            report_files = list(Path(self.temp_dir).glob("*.csv"))
            json_files = list(Path(self.temp_dir).glob("*.json"))
            
            self.assertGreater(len(report_files), 0)
            self.assertGreater(len(json_files), 0)
            
        except Exception as e:
            self.fail(f"Report generation failed: {e}")


if __name__ == '__main__':
    unittest.main()