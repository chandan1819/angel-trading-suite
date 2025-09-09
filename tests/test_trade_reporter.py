"""
Unit tests for the TradeReporter class.

Tests trade ledger management, CSV export, and reporting functionality.
"""

import csv
import json
import tempfile
import pytest
from datetime import datetime, date, timedelta
from pathlib import Path

from src.logging.trade_reporter import TradeReporter
from src.models.config_models import LoggingConfig
from src.models.trading_models import Trade, TradeLeg, OptionType, OrderAction, TradeStatus


class TestTradeReporter:
    """Test cases for TradeReporter."""
    
    @pytest.fixture
    def temp_log_dir(self):
        """Create temporary directory for logs."""
        with tempfile.TemporaryDirectory() as temp_dir:
            yield Path(temp_dir)
    
    @pytest.fixture
    def logging_config(self, temp_log_dir):
        """Create logging configuration for testing."""
        return LoggingConfig(
            log_directory=str(temp_log_dir),
            enable_csv=True
        )
    
    @pytest.fixture
    def trade_reporter(self, logging_config):
        """Create TradeReporter instance for testing."""
        return TradeReporter(logging_config)
    
    @pytest.fixture
    def sample_trade(self):
        """Create sample trade for testing."""
        legs = [
            TradeLeg(
                symbol="BANKNIFTY2412550000CE",
                token="12345",
                strike=50000.0,
                option_type=OptionType.CE,
                action=OrderAction.SELL,
                quantity=25,
                entry_price=100.0,
                exit_price=None,
                current_price=80.0
            ),
            TradeLeg(
                symbol="BANKNIFTY2412550000PE",
                token="12346",
                strike=50000.0,
                option_type=OptionType.PE,
                action=OrderAction.SELL,
                quantity=25,
                entry_price=95.0,
                exit_price=None,
                current_price=75.0
            )
        ]
        
        return Trade(
            trade_id="TEST_001",
            strategy="straddle",
            underlying_symbol="BANKNIFTY",
            entry_time=datetime.now(),
            exit_time=None,
            legs=legs,
            target_pnl=2000.0,
            stop_loss=-1000.0,
            status=TradeStatus.OPEN
        )
    
    def test_initialization(self, trade_reporter, temp_log_dir):
        """Test TradeReporter initialization."""
        assert trade_reporter.log_dir == Path(temp_log_dir)
        assert trade_reporter.reports_dir.exists()
        assert trade_reporter.trade_ledger_file.exists()
        
        # Check CSV headers
        with open(trade_reporter.trade_ledger_file, 'r') as f:
            reader = csv.reader(f)
            headers = next(reader)
            expected_headers = [
                'trade_id', 'strategy', 'entry_time', 'exit_time', 'status',
                'underlying', 'expiry_date', 'total_legs', 'entry_premium',
                'exit_premium', 'realized_pnl', 'unrealized_pnl', 'total_pnl',
                'target_pnl', 'stop_loss', 'max_profit', 'max_loss',
                'holding_period_minutes', 'leg_details', 'metadata'
            ]
            assert headers == expected_headers
    
    def test_record_trade_entry(self, trade_reporter, sample_trade):
        """Test recording trade entry."""
        trade_reporter.record_trade_entry(sample_trade)
        
        # Check that trade is in active trades
        assert sample_trade.trade_id in trade_reporter.active_trades
        
        # Check that entry was written to CSV
        with open(trade_reporter.trade_ledger_file, 'r') as f:
            reader = csv.DictReader(f)
            rows = list(reader)
            assert len(rows) == 1
            
            row = rows[0]
            assert row['trade_id'] == sample_trade.trade_id
            assert row['strategy'] == sample_trade.strategy
            assert row['status'] == sample_trade.status.value
            assert float(row['total_pnl']) == sample_trade.current_pnl
    
    def test_record_trade_update(self, trade_reporter, sample_trade):
        """Test recording trade update."""
        # First record entry
        trade_reporter.record_trade_entry(sample_trade)
        
        # Update trade
        sample_trade.current_pnl = 1500.0
        trade_reporter.record_trade_update(sample_trade)
        
        # Check that trade is still in active trades with updated values
        assert sample_trade.trade_id in trade_reporter.active_trades
        assert trade_reporter.active_trades[sample_trade.trade_id].current_pnl == 1500.0
        
        # Check CSV has two entries
        with open(trade_reporter.trade_ledger_file, 'r') as f:
            reader = csv.DictReader(f)
            rows = list(reader)
            assert len(rows) == 2
    
    def test_record_trade_exit(self, trade_reporter, sample_trade):
        """Test recording trade exit."""
        # First record entry
        trade_reporter.record_trade_entry(sample_trade)
        
        # Exit trade
        sample_trade.status = TradeStatus.CLOSED
        sample_trade.exit_time = datetime.now()
        sample_trade.current_pnl = 1800.0
        
        # Set exit prices for legs
        for leg in sample_trade.legs:
            leg.exit_price = leg.current_price
        
        trade_reporter.record_trade_exit(sample_trade)
        
        # Check that trade is removed from active trades
        assert sample_trade.trade_id not in trade_reporter.active_trades
        
        # Check that trade is in completed trades
        assert len(trade_reporter.completed_trades) == 1
        assert trade_reporter.completed_trades[0].trade_id == sample_trade.trade_id
    
    def test_pnl_calculations(self, trade_reporter, sample_trade):
        """Test P&L calculations in trade recording."""
        # Set exit prices for some legs to test realized P&L
        sample_trade.legs[0].exit_price = 80.0  # SELL at 100, exit at 80 = profit
        
        trade_reporter.record_trade_entry(sample_trade)
        
        # Read the CSV and check P&L calculations
        with open(trade_reporter.trade_ledger_file, 'r') as f:
            reader = csv.DictReader(f)
            row = next(reader)
            
            # Entry premium should be sum of entry prices * quantities
            expected_entry_premium = (100.0 * 25) + (95.0 * 25)  # 4875
            assert float(row['entry_premium']) == expected_entry_premium
            
            # Should have both realized and unrealized P&L
            assert float(row['realized_pnl']) > 0  # First leg closed profitably
            assert float(row['unrealized_pnl']) != 0  # Second leg still open
    
    def test_export_trades_csv(self, trade_reporter, sample_trade):
        """Test CSV export functionality."""
        # Record some trades
        trade_reporter.record_trade_entry(sample_trade)
        
        # Create another trade with different date
        sample_trade.trade_id = "TEST_002"
        sample_trade.entry_time = datetime.now() - timedelta(days=1)
        trade_reporter.record_trade_entry(sample_trade)
        
        # Export all trades
        export_path = trade_reporter.export_trades_csv()
        assert export_path.exists()
        
        # Check export content
        with open(export_path, 'r') as f:
            reader = csv.DictReader(f)
            rows = list(reader)
            assert len(rows) == 2
        
        # Export with date filter
        today = date.today()
        export_path_filtered = trade_reporter.export_trades_csv(
            start_date=today,
            end_date=today,
            filename="filtered_export.csv"
        )
        
        with open(export_path_filtered, 'r') as f:
            reader = csv.DictReader(f)
            rows = list(reader)
            assert len(rows) == 1  # Only today's trade
    
    def test_get_trade_history(self, trade_reporter, sample_trade):
        """Test trade history retrieval."""
        # Record trades
        trade_reporter.record_trade_entry(sample_trade)
        
        sample_trade.trade_id = "TEST_002"
        sample_trade.strategy = "directional"
        trade_reporter.record_trade_entry(sample_trade)
        
        # Get all history
        all_history = trade_reporter.get_trade_history(days=30)
        assert len(all_history) == 2
        
        # Filter by trade ID
        specific_history = trade_reporter.get_trade_history(trade_id="TEST_001")
        assert len(specific_history) == 1
        assert specific_history[0]['trade_id'] == "TEST_001"
        
        # Filter by strategy
        strategy_history = trade_reporter.get_trade_history(strategy="directional")
        assert len(strategy_history) == 1
        assert strategy_history[0]['strategy'] == "directional"
    
    def test_get_active_trades_summary(self, trade_reporter, sample_trade):
        """Test active trades summary."""
        # Initially no active trades
        summary = trade_reporter.get_active_trades_summary()
        assert summary['total_active_trades'] == 0
        assert summary['total_unrealized_pnl'] == 0
        
        # Add active trade
        trade_reporter.record_trade_entry(sample_trade)
        
        summary = trade_reporter.get_active_trades_summary()
        assert summary['total_active_trades'] == 1
        assert summary['total_unrealized_pnl'] == sample_trade.current_pnl
        assert len(summary['strategies_in_use']) == 1
        assert summary['strategies_in_use'][0] == sample_trade.strategy
        assert len(summary['trades']) == 1
        
        trade_summary = summary['trades'][0]
        assert trade_summary['trade_id'] == sample_trade.trade_id
        assert trade_summary['strategy'] == sample_trade.strategy
        assert trade_summary['current_pnl'] == sample_trade.current_pnl
    
    def test_generate_daily_summary(self, trade_reporter, sample_trade):
        """Test daily summary generation."""
        # Record some trades
        trade_reporter.record_trade_entry(sample_trade)
        
        # Create a completed winning trade
        winning_leg = TradeLeg(
            symbol="BANKNIFTY2412550000CE",
            token="12345",
            strike=50000.0,
            option_type=OptionType.CE,
            action=OrderAction.SELL,
            quantity=25,
            entry_price=100.0,
            exit_price=40.0,  # Profitable exit
            current_price=40.0
        )
        
        winning_trade = Trade(
            trade_id="WIN_001",
            strategy="straddle",
            underlying_symbol="BANKNIFTY",
            entry_time=datetime.now(),
            exit_time=datetime.now(),
            legs=[winning_leg],
            target_pnl=2000.0,
            stop_loss=-1000.0,
            status=TradeStatus.CLOSED
        )
        trade_reporter.record_trade_exit(winning_trade)
        
        # Create a completed losing trade
        losing_leg = TradeLeg(
            symbol="BANKNIFTY2412550000PE",
            token="12346",
            strike=50000.0,
            option_type=OptionType.PE,
            action=OrderAction.BUY,
            quantity=25,
            entry_price=100.0,
            exit_price=68.0,  # Loss on exit
            current_price=68.0
        )
        
        losing_trade = Trade(
            trade_id="LOSS_001",
            strategy="directional",
            underlying_symbol="BANKNIFTY",
            entry_time=datetime.now(),
            exit_time=datetime.now(),
            legs=[losing_leg],
            target_pnl=2000.0,
            stop_loss=-1000.0,
            status=TradeStatus.CLOSED
        )
        trade_reporter.record_trade_exit(losing_trade)
        
        # Generate daily summary
        summary = trade_reporter.generate_daily_summary()
        
        assert summary['total_trades'] == 3  # 1 open + 2 closed
        assert summary['completed_trades'] == 2
        assert summary['active_trades'] == 1
        assert summary['winning_trades'] == 1
        assert summary['losing_trades'] == 1
        assert summary['win_rate'] == 50.0  # 1 win out of 2 completed
        
        # Check strategy breakdown
        assert 'straddle' in summary['strategy_breakdown']
        assert 'directional' in summary['strategy_breakdown']
        
        straddle_stats = summary['strategy_breakdown']['straddle']
        assert straddle_stats['trades'] == 2  # 1 open + 1 closed
        assert straddle_stats['wins'] == 1
        assert straddle_stats['losses'] == 0
        
        # Check that summary file was created
        today = date.today()
        summary_file = trade_reporter.reports_dir / f'daily_summary_{today.strftime("%Y%m%d")}.json'
        assert summary_file.exists()
        
        # Verify file content
        with open(summary_file, 'r') as f:
            file_summary = json.load(f)
            assert file_summary['total_trades'] == summary['total_trades']
            assert file_summary['win_rate'] == summary['win_rate']
    
    def test_leg_details_serialization(self, trade_reporter, sample_trade):
        """Test that leg details are properly serialized to JSON."""
        trade_reporter.record_trade_entry(sample_trade)
        
        # Read the CSV and check leg details
        with open(trade_reporter.trade_ledger_file, 'r') as f:
            reader = csv.DictReader(f)
            row = next(reader)
            
            leg_details = json.loads(row['leg_details'])
            assert len(leg_details) == 2
            
            first_leg = leg_details[0]
            assert first_leg['symbol'] == sample_trade.legs[0].symbol
            assert first_leg['strike'] == sample_trade.legs[0].strike
            assert first_leg['option_type'] == sample_trade.legs[0].option_type
            assert first_leg['action'] == sample_trade.legs[0].action
            assert first_leg['quantity'] == sample_trade.legs[0].quantity
            assert first_leg['entry_price'] == sample_trade.legs[0].entry_price