"""
Unit tests for BacktestReporter class.

Tests CSV output generation, JSON summaries,
and trade-by-trade analysis reporting.
"""

import unittest
from unittest.mock import Mock, patch
from datetime import datetime
import tempfile
import shutil
import json
import csv
from pathlib import Path

from src.backtesting.backtest_reporter import BacktestReporter
from src.backtesting.models import BacktestResult, PerformanceMetrics
from src.backtesting.historical_simulator import SimulatedTrade
from src.models.trading_models import (
    TradeLeg, OptionType, OrderAction, TradeStatus
)


class TestBacktestReporter(unittest.TestCase):
    """Test cases for BacktestReporter"""
    
    def setUp(self):
        """Set up test fixtures"""
        self.reporter = BacktestReporter()
        
        # Create temporary directory for test reports
        self.temp_dir = tempfile.mkdtemp()
        
        # Create sample backtest result
        self.result = self._create_sample_result()
    
    def tearDown(self):
        """Clean up test fixtures"""
        shutil.rmtree(self.temp_dir, ignore_errors=True)
    
    def _create_sample_result(self) -> BacktestResult:
        """Create a sample backtest result for testing"""
        # Create performance metrics
        metrics = PerformanceMetrics(
            total_pnl=1500.0,
            total_return_pct=1.5,
            max_drawdown=500.0,
            max_drawdown_pct=0.5,
            win_rate=60.0,
            avg_trade_return=300.0,
            avg_winning_trade=750.0,
            avg_losing_trade=-375.0,
            total_trades=5,
            winning_trades=3,
            losing_trades=2,
            sharpe_ratio=1.2,
            profit_factor=2.0,
            max_consecutive_wins=2,
            max_consecutive_losses=1,
            avg_trade_duration_hours=4.5,
            largest_win=1000.0,
            largest_loss=-500.0
        )
        
        # Create sample trades
        trades = []
        
        # Trade 1 - Winning trade
        trade1 = SimulatedTrade(
            trade_id="trade_001",
            strategy="TestStrategy",
            underlying_symbol="BANKNIFTY",
            entry_time=datetime(2024, 1, 1, 10, 0),
            exit_time=datetime(2024, 1, 1, 15, 0),
            target_pnl=2000.0,
            stop_loss=-1000.0,
            status=TradeStatus.CLOSED,
            realized_pnl=750.0,
            commission=20.0,
            slippage=5.0,
            exit_reason="Profit target hit"
        )
        
        # Add legs to trade1
        leg1 = TradeLeg(
            symbol="BANKNIFTY45000CE",
            token="token_45000_CE",
            strike=45000.0,
            option_type=OptionType.CE,
            action=OrderAction.SELL,
            quantity=25,
            entry_price=200.0,
            exit_price=170.0,
            current_price=170.0,
            fill_time=datetime(2024, 1, 1, 10, 0)
        )
        trade1.legs.append(leg1)
        trades.append(trade1)
        
        # Trade 2 - Losing trade
        trade2 = SimulatedTrade(
            trade_id="trade_002",
            strategy="TestStrategy",
            underlying_symbol="BANKNIFTY",
            entry_time=datetime(2024, 1, 2, 10, 0),
            exit_time=datetime(2024, 1, 2, 14, 0),
            target_pnl=2000.0,
            stop_loss=-1000.0,
            status=TradeStatus.CLOSED,
            realized_pnl=-400.0,
            commission=20.0,
            slippage=5.0,
            exit_reason="Stop loss hit"
        )
        
        # Add legs to trade2
        leg2 = TradeLeg(
            symbol="BANKNIFTY45000PE",
            token="token_45000_PE",
            strike=45000.0,
            option_type=OptionType.PE,
            action=OrderAction.SELL,
            quantity=25,
            entry_price=180.0,
            exit_price=200.0,
            current_price=200.0,
            fill_time=datetime(2024, 1, 2, 10, 0)
        )
        trade2.legs.append(leg2)
        trades.append(trade2)
        
        # Create backtest result
        result = BacktestResult(
            strategy_name="TestStrategy",
            start_date="2024-01-01",
            end_date="2024-01-31",
            initial_capital=100000.0,
            final_capital=101500.0,
            trades=trades,
            performance_metrics=metrics,
            daily_pnl=[
                ("2024-01-01", 750.0),
                ("2024-01-02", -400.0)
            ],
            equity_curve=[
                ("2024-01-01", 100750.0),
                ("2024-01-02", 100350.0)
            ],
            metadata={
                "strategy_config": {"enabled": True},
                "backtest_config": {"initial_capital": 100000.0},
                "data_points": 31,
                "backtest_duration_days": 30
            }
        )
        
        return result
    
    def test_initialization(self):
        """Test BacktestReporter initialization"""
        self.assertIsNotNone(self.reporter)
    
    def test_generate_csv_report(self):
        """Test CSV report generation"""
        self.reporter._generate_csv_report(
            self.result, Path(self.temp_dir), "20240101_120000", "teststrategy"
        )
        
        # Check if CSV file was created
        csv_files = list(Path(self.temp_dir).glob("backtest_trades_*.csv"))
        self.assertEqual(len(csv_files), 1)
        
        # Read and verify CSV content
        csv_file = csv_files[0]
        with open(csv_file, 'r', encoding='utf-8') as f:
            reader = csv.DictReader(f)
            rows = list(reader)
        
        self.assertEqual(len(rows), 2)  # Two trades
        
        # Verify first trade data
        trade1_row = rows[0]
        self.assertEqual(trade1_row['trade_id'], 'trade_001')
        self.assertEqual(trade1_row['strategy'], 'TestStrategy')
        self.assertEqual(trade1_row['underlying_symbol'], 'BANKNIFTY')
        self.assertEqual(trade1_row['realized_pnl'], '750.00')
        self.assertEqual(trade1_row['exit_reason'], 'Profit target hit')
        self.assertEqual(trade1_row['status'], 'CLOSED')
        
        # Verify second trade data
        trade2_row = rows[1]
        self.assertEqual(trade2_row['trade_id'], 'trade_002')
        self.assertEqual(trade2_row['realized_pnl'], '-400.00')
        self.assertEqual(trade2_row['exit_reason'], 'Stop loss hit')
    
    def test_generate_json_summary(self):
        """Test JSON summary generation"""
        self.reporter._generate_json_summary(
            self.result, Path(self.temp_dir), "20240101_120000", "teststrategy"
        )
        
        # Check if JSON file was created
        json_files = list(Path(self.temp_dir).glob("backtest_summary_*.json"))
        self.assertEqual(len(json_files), 1)
        
        # Read and verify JSON content
        json_file = json_files[0]
        with open(json_file, 'r', encoding='utf-8') as f:
            data = json.load(f)
        
        # Verify structure
        self.assertIn('backtest_info', data)
        self.assertIn('capital_summary', data)
        self.assertIn('performance_metrics', data)
        self.assertIn('trade_summary', data)
        self.assertIn('risk_metrics', data)
        self.assertIn('metadata', data)
        
        # Verify backtest info
        backtest_info = data['backtest_info']
        self.assertEqual(backtest_info['strategy_name'], 'TestStrategy')
        self.assertEqual(backtest_info['start_date'], '2024-01-01')
        self.assertEqual(backtest_info['end_date'], '2024-01-31')
        self.assertEqual(backtest_info['duration_days'], 30)
        
        # Verify capital summary
        capital_summary = data['capital_summary']
        self.assertEqual(capital_summary['initial_capital'], 100000.0)
        self.assertEqual(capital_summary['final_capital'], 101500.0)
        self.assertEqual(capital_summary['total_pnl'], 1500.0)
        
        # Verify performance metrics
        perf_metrics = data['performance_metrics']
        self.assertEqual(perf_metrics['total_trades'], 5)
        self.assertEqual(perf_metrics['win_rate'], 60.0)
        self.assertEqual(perf_metrics['sharpe_ratio'], 1.2)
        
        # Verify trade summary
        trade_summary = data['trade_summary']
        self.assertEqual(trade_summary['total_trades'], 2)
        self.assertEqual(trade_summary['completed_trades'], 2)
        self.assertEqual(trade_summary['open_trades'], 0)
    
    def test_generate_trade_analysis(self):
        """Test trade analysis report generation"""
        self.reporter._generate_trade_analysis(
            self.result, Path(self.temp_dir), "20240101_120000", "teststrategy"
        )
        
        # Check if analysis file was created
        analysis_files = list(Path(self.temp_dir).glob("trade_analysis_*.csv"))
        self.assertEqual(len(analysis_files), 1)
        
        # Read and verify analysis content
        analysis_file = analysis_files[0]
        with open(analysis_file, 'r', encoding='utf-8') as f:
            reader = csv.DictReader(f)
            rows = list(reader)
        
        self.assertEqual(len(rows), 2)  # Two legs (one per trade)
        
        # Verify first leg data
        leg1_row = rows[0]
        self.assertEqual(leg1_row['trade_id'], 'trade_001')
        self.assertEqual(leg1_row['leg_index'], '0')
        self.assertEqual(leg1_row['symbol'], 'BANKNIFTY45000CE')
        self.assertEqual(leg1_row['strike'], '45000.0')
        self.assertEqual(leg1_row['option_type'], 'CE')
        self.assertEqual(leg1_row['action'], 'SELL')
        self.assertEqual(leg1_row['quantity'], '25')
        self.assertEqual(leg1_row['entry_price'], '200.00')
        self.assertEqual(leg1_row['exit_price'], '170.00')
        
        # Verify second leg data
        leg2_row = rows[1]
        self.assertEqual(leg2_row['trade_id'], 'trade_002')
        self.assertEqual(leg2_row['symbol'], 'BANKNIFTY45000PE')
        self.assertEqual(leg2_row['option_type'], 'PE')
    
    def test_generate_daily_pnl_report(self):
        """Test daily P&L report generation"""
        self.reporter._generate_daily_pnl_report(
            self.result, Path(self.temp_dir), "20240101_120000", "teststrategy"
        )
        
        # Check if daily P&L file was created
        pnl_files = list(Path(self.temp_dir).glob("daily_pnl_*.csv"))
        self.assertEqual(len(pnl_files), 1)
        
        # Read and verify daily P&L content
        pnl_file = pnl_files[0]
        with open(pnl_file, 'r', encoding='utf-8') as f:
            reader = csv.DictReader(f)
            rows = list(reader)
        
        self.assertEqual(len(rows), 2)  # Two trading days
        
        # Verify first day
        day1_row = rows[0]
        self.assertEqual(day1_row['date'], '2024-01-01')
        self.assertEqual(day1_row['daily_pnl'], '750.00')
        self.assertEqual(day1_row['cumulative_pnl'], '750.00')
        self.assertEqual(day1_row['trades_count'], '1')
        
        # Verify second day
        day2_row = rows[1]
        self.assertEqual(day2_row['date'], '2024-01-02')
        self.assertEqual(day2_row['daily_pnl'], '-400.00')
        self.assertEqual(day2_row['cumulative_pnl'], '350.00')  # 750 - 400
        self.assertEqual(day2_row['trades_count'], '1')
    
    def test_generate_equity_curve_report(self):
        """Test equity curve report generation"""
        self.reporter._generate_equity_curve_report(
            self.result, Path(self.temp_dir), "20240101_120000", "teststrategy"
        )
        
        # Check if equity curve file was created
        equity_files = list(Path(self.temp_dir).glob("equity_curve_*.csv"))
        self.assertEqual(len(equity_files), 1)
        
        # Read and verify equity curve content
        equity_file = equity_files[0]
        with open(equity_file, 'r', encoding='utf-8') as f:
            reader = csv.DictReader(f)
            rows = list(reader)
        
        self.assertEqual(len(rows), 2)  # Two equity points
        
        # Verify first equity point
        eq1_row = rows[0]
        self.assertEqual(eq1_row['date'], '2024-01-01')
        self.assertEqual(eq1_row['equity'], '100750.00')
        self.assertEqual(eq1_row['drawdown'], '0.00')  # At peak
        self.assertEqual(eq1_row['drawdown_pct'], '0.00')
        
        # Verify second equity point
        eq2_row = rows[1]
        self.assertEqual(eq2_row['date'], '2024-01-02')
        self.assertEqual(eq2_row['equity'], '100350.00')
        # Drawdown should be 100750 - 100350 = 400
        self.assertEqual(eq2_row['drawdown'], '400.00')
        # Drawdown % should be (400 / 100750) * 100 ≈ 0.40%
        self.assertAlmostEqual(float(eq2_row['drawdown_pct']), 0.40, places=1)
    
    def test_generate_performance_summary(self):
        """Test performance summary text generation"""
        summary = self.reporter.generate_performance_summary(self.result)
        
        self.assertIsInstance(summary, str)
        self.assertIn("BACKTEST PERFORMANCE SUMMARY", summary)
        self.assertIn("TestStrategy", summary)
        self.assertIn("2024-01-01", summary)
        self.assertIn("2024-01-31", summary)
        self.assertIn("₹100,000.00", summary)  # Initial capital
        self.assertIn("₹101,500.00", summary)  # Final capital
        self.assertIn("₹1,500.00", summary)    # Total P&L
        self.assertIn("1.50%", summary)        # Total return
        self.assertIn("60.00%", summary)       # Win rate
        self.assertIn("1.20", summary)         # Sharpe ratio
        
        # Check for all major sections
        self.assertIn("CAPITAL SUMMARY", summary)
        self.assertIn("TRADE STATISTICS", summary)
        self.assertIn("RISK METRICS", summary)
        self.assertIn("CONSISTENCY METRICS", summary)
    
    def test_generate_report_complete(self):
        """Test complete report generation"""
        # Generate all reports
        self.reporter.generate_report(self.result, self.temp_dir)
        
        # Check that all expected files were created
        output_path = Path(self.temp_dir)
        
        # Should have CSV files
        csv_files = list(output_path.glob("*.csv"))
        self.assertGreaterEqual(len(csv_files), 4)  # trades, analysis, daily_pnl, equity_curve
        
        # Should have JSON file
        json_files = list(output_path.glob("*.json"))
        self.assertGreaterEqual(len(json_files), 1)  # summary
        
        # Verify specific files exist
        file_patterns = [
            "backtest_trades_*.csv",
            "backtest_summary_*.json",
            "trade_analysis_*.csv",
            "daily_pnl_*.csv",
            "equity_curve_*.csv"
        ]
        
        for pattern in file_patterns:
            matching_files = list(output_path.glob(pattern))
            self.assertGreater(len(matching_files), 0, f"No files found for pattern: {pattern}")
    
    def test_generate_report_empty_trades(self):
        """Test report generation with empty trades list"""
        # Create result with no trades
        empty_result = BacktestResult(
            strategy_name="EmptyStrategy",
            start_date="2024-01-01",
            end_date="2024-01-31",
            initial_capital=100000.0,
            final_capital=100000.0,
            trades=[],
            performance_metrics=PerformanceMetrics(),
            daily_pnl=[],
            equity_curve=[],
            metadata={}
        )
        
        # Should not raise exception
        try:
            self.reporter.generate_report(empty_result, self.temp_dir)
            
            # Check that files were still created (even if empty)
            output_path = Path(self.temp_dir)
            csv_files = list(output_path.glob("*.csv"))
            json_files = list(output_path.glob("*.json"))
            
            self.assertGreater(len(csv_files), 0)
            self.assertGreater(len(json_files), 0)
            
        except Exception as e:
            self.fail(f"Report generation with empty trades failed: {e}")
    
    def test_file_naming_convention(self):
        """Test that generated files follow naming convention"""
        timestamp = "20240101_120000"
        strategy_name = "test_strategy"
        
        self.reporter._generate_csv_report(
            self.result, Path(self.temp_dir), timestamp, strategy_name
        )
        
        # Check file naming
        csv_files = list(Path(self.temp_dir).glob("*.csv"))
        self.assertEqual(len(csv_files), 1)
        
        filename = csv_files[0].name
        self.assertIn(strategy_name, filename)
        self.assertIn(timestamp, filename)
        self.assertTrue(filename.startswith("backtest_trades_"))
        self.assertTrue(filename.endswith(".csv"))
    
    def test_error_handling(self):
        """Test error handling in report generation"""
        # Test with invalid output directory
        invalid_dir = "/invalid/path/that/does/not/exist"
        
        with self.assertRaises(Exception):
            self.reporter.generate_report(self.result, invalid_dir)
    
    def test_unicode_handling(self):
        """Test handling of unicode characters in reports"""
        # Create result with unicode characters
        unicode_result = self.result
        unicode_result.strategy_name = "Test₹Strategy"
        unicode_result.trades[0].exit_reason = "Profit target hit ✓"
        
        # Should not raise exception
        try:
            self.reporter.generate_report(unicode_result, self.temp_dir)
        except Exception as e:
            self.fail(f"Unicode handling failed: {e}")


if __name__ == '__main__':
    unittest.main()