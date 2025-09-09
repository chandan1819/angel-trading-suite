"""
Unit tests for the AnalyticsEngine class.

Tests performance metrics calculations, strategy comparisons, and analytics functionality.
"""

import csv
import tempfile
import pytest
from datetime import datetime, date, timedelta
from pathlib import Path

from src.logging.analytics_engine import AnalyticsEngine, PerformanceMetrics


class TestAnalyticsEngine:
    """Test cases for AnalyticsEngine."""
    
    @pytest.fixture
    def temp_csv_file(self):
        """Create temporary CSV file with sample trade data."""
        with tempfile.NamedTemporaryFile(mode='w', suffix='.csv', delete=False) as f:
            writer = csv.writer(f)
            
            # Write headers
            headers = [
                'trade_id', 'strategy', 'entry_time', 'exit_time', 'status',
                'underlying', 'expiry_date', 'total_legs', 'entry_premium',
                'exit_premium', 'realized_pnl', 'unrealized_pnl', 'total_pnl',
                'target_pnl', 'stop_loss', 'max_profit', 'max_loss',
                'holding_period_minutes', 'leg_details', 'metadata'
            ]
            writer.writerow(headers)
            
            # Write sample data
            base_time = datetime.now()
            
            # Winning trade
            writer.writerow([
                'WIN_001', 'straddle', base_time.isoformat(), 
                (base_time + timedelta(minutes=30)).isoformat(), 'CLOSED',
                'BANKNIFTY', '2024-12-26', 2, 4875.0, 3000.0, 1875.0, 0.0, 1875.0,
                2000.0, -1000.0, 1875.0, 0.0, 30.0, '[]', '{}'
            ])
            
            # Losing trade
            writer.writerow([
                'LOSS_001', 'straddle', (base_time + timedelta(hours=1)).isoformat(),
                (base_time + timedelta(hours=1, minutes=45)).isoformat(), 'CLOSED',
                'BANKNIFTY', '2024-12-26', 2, 4800.0, 5600.0, -800.0, 0.0, -800.0,
                2000.0, -1000.0, 0.0, -800.0, 45.0, '[]', '{}'
            ])
            
            # Another winning trade (different strategy)
            writer.writerow([
                'WIN_002', 'directional', (base_time + timedelta(hours=2)).isoformat(),
                (base_time + timedelta(hours=2, minutes=20)).isoformat(), 'CLOSED',
                'BANKNIFTY', '2024-12-26', 1, 2500.0, 1800.0, 700.0, 0.0, 700.0,
                2000.0, -1000.0, 700.0, 0.0, 20.0, '[]', '{}'
            ])
            
            # Open trade (should be excluded from most calculations)
            writer.writerow([
                'OPEN_001', 'straddle', (base_time + timedelta(hours=3)).isoformat(),
                '', 'OPEN', 'BANKNIFTY', '2024-12-26', 2, 4900.0, 0.0, 0.0, 500.0, 500.0,
                2000.0, -1000.0, 0.0, 0.0, '', '[]', '{}'
            ])
            
            temp_path = Path(f.name)
        
        yield temp_path
        
        # Cleanup
        temp_path.unlink()
    
    @pytest.fixture
    def analytics_engine(self, temp_csv_file):
        """Create AnalyticsEngine instance for testing."""
        return AnalyticsEngine(temp_csv_file)
    
    def test_calculate_performance_metrics_basic(self, analytics_engine):
        """Test basic performance metrics calculation."""
        metrics = analytics_engine.calculate_performance_metrics()
        
        # Should have 3 completed trades (2 straddle + 1 directional)
        assert metrics.total_trades == 4  # Including open trade
        assert metrics.winning_trades == 2
        assert metrics.losing_trades == 1
        
        # Win rate should be 2/3 = 66.67%
        assert abs(metrics.win_rate - 66.67) < 0.01
        
        # Total P&L should be 1875 - 800 + 700 = 1775
        assert abs(metrics.total_pnl - 1775.0) < 0.01
        
        # Average win should be (1875 + 700) / 2 = 1287.5
        assert abs(metrics.average_win - 1287.5) < 0.01
        
        # Average loss should be -800
        assert abs(metrics.average_loss - (-800.0)) < 0.01
        
        # Profit factor should be 2575 / 800 = 3.22
        assert abs(metrics.profit_factor - 3.22) < 0.01
        
        # Best and worst trades
        assert metrics.best_trade == 1875.0
        assert metrics.worst_trade == -800.0
    
    def test_calculate_performance_metrics_with_date_filter(self, analytics_engine):
        """Test performance metrics with date filtering."""
        # Filter to only today's trades
        today = date.today()
        metrics = analytics_engine.calculate_performance_metrics(
            start_date=today,
            end_date=today
        )
        
        # Should include all trades since they're all from today
        assert metrics.total_trades == 4
        assert metrics.winning_trades == 2
        assert metrics.losing_trades == 1
    
    def test_calculate_performance_metrics_with_strategy_filter(self, analytics_engine):
        """Test performance metrics with strategy filtering."""
        # Filter to only straddle strategy
        metrics = analytics_engine.calculate_performance_metrics(strategy="straddle")
        
        # Should have 2 straddle trades (1 win, 1 loss) + 1 open
        assert metrics.total_trades == 3
        assert metrics.winning_trades == 1
        assert metrics.losing_trades == 1
        
        # Win rate should be 50%
        assert metrics.win_rate == 50.0
        
        # Total P&L should be 1875 - 800 = 1075
        assert abs(metrics.total_pnl - 1075.0) < 0.01
    
    def test_calculate_performance_metrics_empty_data(self, analytics_engine):
        """Test performance metrics with no matching data."""
        # Filter to future date with no trades
        future_date = date.today() + timedelta(days=30)
        metrics = analytics_engine.calculate_performance_metrics(
            start_date=future_date,
            end_date=future_date
        )
        
        # Should return empty metrics
        assert metrics.total_trades == 0
        assert metrics.winning_trades == 0
        assert metrics.losing_trades == 0
        assert metrics.win_rate == 0
        assert metrics.total_pnl == 0
    
    def test_calculate_drawdown(self, analytics_engine):
        """Test drawdown calculation."""
        pnl_values = [1000, -500, 800, -1200, 600]
        initial_capital = 100000
        
        max_drawdown, max_drawdown_percent = analytics_engine._calculate_drawdown(
            pnl_values, initial_capital
        )
        
        # Should calculate correct drawdown
        assert max_drawdown > 0
        assert max_drawdown_percent > 0
        assert max_drawdown_percent < 100
    
    def test_calculate_sharpe_ratio(self, analytics_engine):
        """Test Sharpe ratio calculation."""
        # Test with consistent positive returns
        positive_returns = [100, 150, 120, 180, 110]
        sharpe = analytics_engine._calculate_sharpe_ratio(positive_returns)
        assert sharpe > 0
        
        # Test with mixed returns
        mixed_returns = [100, -50, 80, -30, 60]
        sharpe_mixed = analytics_engine._calculate_sharpe_ratio(mixed_returns)
        
        # Test with insufficient data
        single_return = [100]
        sharpe_single = analytics_engine._calculate_sharpe_ratio(single_return)
        assert sharpe_single == 0
        
        # Test with no variance (all same returns)
        same_returns = [100, 100, 100, 100]
        sharpe_same = analytics_engine._calculate_sharpe_ratio(same_returns)
        assert sharpe_same == 0
    
    def test_calculate_consecutive_streaks(self, analytics_engine):
        """Test consecutive wins/losses calculation."""
        # Test sequence: win, win, loss, win, loss, loss, loss, win
        pnl_sequence = [100, 150, -50, 80, -30, -60, -40, 120]
        
        max_wins, max_losses = analytics_engine._calculate_consecutive_streaks(pnl_sequence)
        
        assert max_wins == 2  # Two consecutive wins at the start
        assert max_losses == 3  # Three consecutive losses in the middle
        
        # Test with all wins
        all_wins = [100, 200, 150, 80]
        max_wins_all, max_losses_all = analytics_engine._calculate_consecutive_streaks(all_wins)
        assert max_wins_all == 4
        assert max_losses_all == 0
        
        # Test with all losses
        all_losses = [-100, -50, -80]
        max_wins_none, max_losses_none = analytics_engine._calculate_consecutive_streaks(all_losses)
        assert max_wins_none == 0
        assert max_losses_none == 3
    
    def test_calculate_volatility(self, analytics_engine):
        """Test volatility calculation."""
        # Test with varying returns
        returns = [100, -50, 80, -30, 60, 120, -40]
        volatility = analytics_engine._calculate_volatility(returns)
        assert volatility > 0
        
        # Test with consistent returns (low volatility)
        consistent_returns = [100, 105, 95, 102, 98]
        low_volatility = analytics_engine._calculate_volatility(consistent_returns)
        assert low_volatility > 0
        assert low_volatility < volatility  # Should be lower than varying returns
        
        # Test with insufficient data
        single_return = [100]
        zero_volatility = analytics_engine._calculate_volatility(single_return)
        assert zero_volatility == 0
    
    def test_calculate_strategy_comparison(self, analytics_engine):
        """Test strategy comparison functionality."""
        comparison = analytics_engine.calculate_strategy_comparison()
        
        # Should have metrics for both strategies
        assert 'straddle' in comparison
        assert 'directional' in comparison
        
        straddle_metrics = comparison['straddle']
        directional_metrics = comparison['directional']
        
        # Straddle should have more trades
        assert straddle_metrics.total_trades > directional_metrics.total_trades
        
        # Both should have valid metrics
        assert straddle_metrics.win_rate >= 0
        assert directional_metrics.win_rate >= 0
    
    def test_calculate_monthly_performance(self, analytics_engine):
        """Test monthly performance calculation."""
        current_year = datetime.now().year
        monthly_data = analytics_engine.calculate_monthly_performance(current_year)
        
        # Should have 12 months
        assert len(monthly_data) == 12
        
        # Check current month has data (since our test data is from today)
        current_month_key = f"{current_year}-{datetime.now().month:02d}"
        assert current_month_key in monthly_data
        
        current_month_data = monthly_data[current_month_key]
        assert current_month_data['total_trades'] > 0
        assert 'win_rate' in current_month_data
        assert 'total_pnl' in current_month_data
    
    def test_calculate_average_holding_period(self, analytics_engine):
        """Test average holding period calculation."""
        completed_trades = [
            {'holding_period_minutes': '30.0'},
            {'holding_period_minutes': '45.0'},
            {'holding_period_minutes': '20.0'},
            {'holding_period_minutes': ''},  # Should be ignored
            {'holding_period_minutes': 'invalid'},  # Should be ignored
        ]
        
        avg_period = analytics_engine._calculate_average_holding_period(completed_trades)
        
        # Should be (30 + 45 + 20) / 3 = 31.67
        expected_avg = (30.0 + 45.0 + 20.0) / 3
        assert abs(avg_period - expected_avg) < 0.01
        
        # Test with no valid data
        empty_trades = [{'holding_period_minutes': ''}]
        zero_avg = analytics_engine._calculate_average_holding_period(empty_trades)
        assert zero_avg == 0
    
    def test_empty_metrics(self, analytics_engine):
        """Test empty metrics creation."""
        empty = analytics_engine._empty_metrics()
        
        assert empty.total_trades == 0
        assert empty.winning_trades == 0
        assert empty.losing_trades == 0
        assert empty.win_rate == 0
        assert empty.total_pnl == 0
        assert empty.average_win == 0
        assert empty.average_loss == 0
        assert empty.profit_factor == 0
        assert empty.best_trade == 0
        assert empty.worst_trade == 0
    
    def test_performance_metrics_dataclass(self):
        """Test PerformanceMetrics dataclass."""
        metrics = PerformanceMetrics(
            total_trades=10,
            winning_trades=6,
            losing_trades=4,
            win_rate=60.0,
            total_pnl=5000.0,
            average_win=1250.0,
            average_loss=-625.0,
            profit_factor=2.0,
            max_drawdown=1000.0,
            max_drawdown_percent=10.0,
            sharpe_ratio=1.5,
            calmar_ratio=0.8,
            total_return=5.0,
            annualized_return=15.0,
            volatility=12.0,
            max_consecutive_wins=3,
            max_consecutive_losses=2,
            average_holding_period=35.5,
            best_trade=2000.0,
            worst_trade=-800.0,
            expectancy=500.0
        )
        
        assert metrics.total_trades == 10
        assert metrics.win_rate == 60.0
        assert metrics.profit_factor == 2.0
        assert metrics.sharpe_ratio == 1.5