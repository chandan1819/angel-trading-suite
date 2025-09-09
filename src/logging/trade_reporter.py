"""
Trade reporting and ledger management for the trading system.

Provides detailed trade tracking, CSV export functionality, and trade ledger management.
"""

import csv
import json
from datetime import datetime, date
from typing import List, Dict, Any, Optional
from pathlib import Path
from dataclasses import asdict

from ..models.trading_models import Trade, TradeLeg
from ..models.config_models import LoggingConfig


class TradeReporter:
    """
    Manages trade ledger and reporting functionality.
    
    Features:
    - Detailed trade ledger with all transaction records
    - CSV export functionality
    - Trade history tracking
    - P&L tracking and reporting
    """
    
    def __init__(self, config: LoggingConfig):
        """
        Initialize the trade reporter.
        
        Args:
            config: Logging configuration settings
        """
        self.config = config
        self.log_dir = Path(config.log_directory)
        self.reports_dir = self.log_dir / 'reports'
        self.reports_dir.mkdir(parents=True, exist_ok=True)
        
        # Trade ledger file paths
        self.trade_ledger_file = self.reports_dir / 'trade_ledger.csv'
        self.daily_summary_file = self.reports_dir / f'daily_summary_{date.today().strftime("%Y%m%d")}.json'
        
        # Initialize trade ledger if it doesn't exist
        self._initialize_trade_ledger()
        
        # In-memory trade tracking
        self.active_trades: Dict[str, Trade] = {}
        self.completed_trades: List[Trade] = []
    
    def _initialize_trade_ledger(self) -> None:
        """Initialize the trade ledger CSV file with headers if it doesn't exist."""
        if not self.trade_ledger_file.exists():
            headers = [
                'trade_id', 'strategy', 'entry_time', 'exit_time', 'status',
                'underlying', 'expiry_date', 'total_legs', 'entry_premium',
                'exit_premium', 'realized_pnl', 'unrealized_pnl', 'total_pnl',
                'target_pnl', 'stop_loss', 'max_profit', 'max_loss',
                'holding_period_minutes', 'leg_details', 'metadata'
            ]
            
            with open(self.trade_ledger_file, 'w', newline='', encoding='utf-8') as f:
                writer = csv.writer(f)
                writer.writerow(headers)
    
    def record_trade_entry(self, trade: Trade) -> None:
        """
        Record a new trade entry in the ledger.
        
        Args:
            trade: Trade object to record
        """
        self.active_trades[trade.trade_id] = trade
        self._write_trade_to_ledger(trade, 'ENTRY')
    
    def record_trade_update(self, trade: Trade) -> None:
        """
        Record a trade update (P&L changes, partial exits, etc.).
        
        Args:
            trade: Updated trade object
        """
        if trade.trade_id in self.active_trades:
            self.active_trades[trade.trade_id] = trade
            self._write_trade_to_ledger(trade, 'UPDATE')
    
    def record_trade_exit(self, trade: Trade) -> None:
        """
        Record a trade exit in the ledger.
        
        Args:
            trade: Completed trade object
        """
        if trade.trade_id in self.active_trades:
            del self.active_trades[trade.trade_id]
        
        self.completed_trades.append(trade)
        self._write_trade_to_ledger(trade, 'EXIT')
    
    def _write_trade_to_ledger(self, trade: Trade, action: str) -> None:
        """
        Write trade data to the CSV ledger.
        
        Args:
            trade: Trade object to write
            action: Action type (ENTRY, UPDATE, EXIT)
        """
        # Calculate holding period
        holding_period = None
        if trade.entry_time and trade.exit_time:
            holding_period = (trade.exit_time - trade.entry_time).total_seconds() / 60
        elif trade.entry_time:
            holding_period = (datetime.now() - trade.entry_time).total_seconds() / 60
        
        # Calculate entry and exit premiums
        entry_premium = sum(leg.entry_price * leg.quantity for leg in trade.legs if leg.entry_price)
        exit_premium = sum(leg.exit_price * leg.quantity for leg in trade.legs if leg.exit_price)
        
        # Calculate realized and unrealized P&L
        realized_pnl = 0
        unrealized_pnl = 0
        
        for leg in trade.legs:
            if leg.exit_price:
                # Realized P&L for closed legs
                if leg.action == 'BUY':
                    realized_pnl += (leg.exit_price - leg.entry_price) * leg.quantity
                else:  # SELL
                    realized_pnl += (leg.entry_price - leg.exit_price) * leg.quantity
            else:
                # Unrealized P&L for open legs
                if leg.action == 'BUY':
                    unrealized_pnl += (leg.current_price - leg.entry_price) * leg.quantity
                else:  # SELL
                    unrealized_pnl += (leg.entry_price - leg.current_price) * leg.quantity
        
        # Prepare leg details as JSON
        leg_details = []
        for leg in trade.legs:
            leg_detail = {
                'symbol': leg.symbol,
                'strike': leg.strike,
                'option_type': leg.option_type.value if hasattr(leg.option_type, 'value') else str(leg.option_type),
                'action': leg.action.value if hasattr(leg.action, 'value') else str(leg.action),
                'quantity': leg.quantity,
                'entry_price': leg.entry_price,
                'exit_price': leg.exit_price,
                'current_price': leg.current_price
            }
            leg_details.append(leg_detail)
        
        # Prepare row data
        row_data = [
            trade.trade_id,
            trade.strategy,
            trade.entry_time.isoformat() if trade.entry_time else '',
            trade.exit_time.isoformat() if trade.exit_time else '',
            trade.status.value if hasattr(trade.status, 'value') else str(trade.status),
            getattr(trade, 'underlying', 'BANKNIFTY'),  # Default to BANKNIFTY
            getattr(trade, 'expiry_date', ''),
            len(trade.legs),
            round(entry_premium, 2),
            round(exit_premium, 2),
            round(realized_pnl, 2),
            round(unrealized_pnl, 2),
            round(trade.current_pnl, 2),
            round(trade.target_pnl, 2),
            round(trade.stop_loss, 2),
            round(getattr(trade, 'max_profit', 0), 2),
            round(getattr(trade, 'max_loss', 0), 2),
            round(holding_period, 2) if holding_period else '',
            json.dumps(leg_details),
            json.dumps(getattr(trade, 'metadata', {}))
        ]
        
        # Write to CSV
        with open(self.trade_ledger_file, 'a', newline='', encoding='utf-8') as f:
            writer = csv.writer(f)
            writer.writerow(row_data)
    
    def export_trades_csv(self, start_date: Optional[date] = None, 
                         end_date: Optional[date] = None,
                         filename: Optional[str] = None) -> Path:
        """
        Export trades to CSV file for a specific date range.
        
        Args:
            start_date: Start date for export (inclusive)
            end_date: End date for export (inclusive)
            filename: Custom filename for export
            
        Returns:
            Path to the exported CSV file
        """
        if filename is None:
            date_suffix = f"{start_date or 'all'}_{end_date or 'all'}"
            filename = f"trades_export_{date_suffix}.csv"
        
        export_path = self.reports_dir / filename
        
        # Read existing ledger and filter by date range
        trades_data = []
        
        if self.trade_ledger_file.exists():
            with open(self.trade_ledger_file, 'r', encoding='utf-8') as f:
                reader = csv.DictReader(f)
                for row in reader:
                    # Parse entry time for date filtering
                    if row['entry_time']:
                        try:
                            entry_date = datetime.fromisoformat(row['entry_time']).date()
                            
                            # Apply date filters
                            if start_date and entry_date < start_date:
                                continue
                            if end_date and entry_date > end_date:
                                continue
                            
                            trades_data.append(row)
                        except ValueError:
                            # Skip rows with invalid dates
                            continue
        
        # Write filtered data to export file
        if trades_data:
            with open(export_path, 'w', newline='', encoding='utf-8') as f:
                if trades_data:
                    writer = csv.DictWriter(f, fieldnames=trades_data[0].keys())
                    writer.writeheader()
                    writer.writerows(trades_data)
        
        return export_path
    
    def get_trade_history(self, trade_id: Optional[str] = None,
                         strategy: Optional[str] = None,
                         days: int = 30) -> List[Dict[str, Any]]:
        """
        Get trade history with optional filtering.
        
        Args:
            trade_id: Specific trade ID to filter
            strategy: Strategy name to filter
            days: Number of days to look back
            
        Returns:
            List of trade records
        """
        cutoff_date = datetime.now().date() - datetime.timedelta(days=days)
        trades = []
        
        if self.trade_ledger_file.exists():
            with open(self.trade_ledger_file, 'r', encoding='utf-8') as f:
                reader = csv.DictReader(f)
                for row in reader:
                    # Apply filters
                    if trade_id and row['trade_id'] != trade_id:
                        continue
                    
                    if strategy and row['strategy'] != strategy:
                        continue
                    
                    # Date filter
                    if row['entry_time']:
                        try:
                            entry_date = datetime.fromisoformat(row['entry_time']).date()
                            if entry_date < cutoff_date:
                                continue
                        except ValueError:
                            continue
                    
                    trades.append(row)
        
        return trades
    
    def get_active_trades_summary(self) -> Dict[str, Any]:
        """
        Get summary of currently active trades.
        
        Returns:
            Summary dictionary with active trade statistics
        """
        if not self.active_trades:
            return {
                'total_active_trades': 0,
                'total_unrealized_pnl': 0,
                'strategies_in_use': [],
                'trades': []
            }
        
        total_unrealized_pnl = sum(trade.current_pnl for trade in self.active_trades.values())
        strategies = list(set(trade.strategy for trade in self.active_trades.values()))
        
        trades_summary = []
        for trade in self.active_trades.values():
            trades_summary.append({
                'trade_id': trade.trade_id,
                'strategy': trade.strategy,
                'status': trade.status,
                'current_pnl': trade.current_pnl,
                'target_pnl': trade.target_pnl,
                'stop_loss': trade.stop_loss,
                'entry_time': trade.entry_time.isoformat() if trade.entry_time else None
            })
        
        return {
            'total_active_trades': len(self.active_trades),
            'total_unrealized_pnl': round(total_unrealized_pnl, 2),
            'strategies_in_use': strategies,
            'trades': trades_summary
        }
    
    def generate_daily_summary(self, target_date: Optional[date] = None) -> Dict[str, Any]:
        """
        Generate daily trading summary.
        
        Args:
            target_date: Date for summary, defaults to today
            
        Returns:
            Daily summary dictionary
        """
        if target_date is None:
            target_date = date.today()
        
        # Get trades for the target date
        daily_trades = []
        
        if self.trade_ledger_file.exists():
            with open(self.trade_ledger_file, 'r', encoding='utf-8') as f:
                reader = csv.DictReader(f)
                for row in reader:
                    if row['entry_time']:
                        try:
                            entry_date = datetime.fromisoformat(row['entry_time']).date()
                            if entry_date == target_date:
                                daily_trades.append(row)
                        except ValueError:
                            continue
        
        # Calculate summary statistics
        total_trades = len(daily_trades)
        completed_trades = [t for t in daily_trades if t['status'] == 'CLOSED']
        winning_trades = [t for t in completed_trades if float(t['total_pnl']) > 0]
        losing_trades = [t for t in completed_trades if float(t['total_pnl']) < 0]
        
        total_pnl = sum(float(t['total_pnl']) for t in daily_trades if t['total_pnl'])
        realized_pnl = sum(float(t['realized_pnl']) for t in daily_trades if t['realized_pnl'])
        unrealized_pnl = sum(float(t['unrealized_pnl']) for t in daily_trades if t['unrealized_pnl'])
        
        win_rate = (len(winning_trades) / len(completed_trades) * 100) if completed_trades else 0
        avg_win = sum(float(t['total_pnl']) for t in winning_trades) / len(winning_trades) if winning_trades else 0
        avg_loss = sum(float(t['total_pnl']) for t in losing_trades) / len(losing_trades) if losing_trades else 0
        
        # Strategy breakdown
        strategy_stats = {}
        for trade in daily_trades:
            strategy = trade['strategy']
            if strategy not in strategy_stats:
                strategy_stats[strategy] = {
                    'trades': 0,
                    'pnl': 0,
                    'wins': 0,
                    'losses': 0
                }
            
            strategy_stats[strategy]['trades'] += 1
            strategy_stats[strategy]['pnl'] += float(trade['total_pnl']) if trade['total_pnl'] else 0
            
            if trade['status'] == 'CLOSED' and trade['total_pnl']:
                if float(trade['total_pnl']) > 0:
                    strategy_stats[strategy]['wins'] += 1
                else:
                    strategy_stats[strategy]['losses'] += 1
        
        summary = {
            'date': target_date.isoformat(),
            'total_trades': total_trades,
            'completed_trades': len(completed_trades),
            'active_trades': total_trades - len(completed_trades),
            'winning_trades': len(winning_trades),
            'losing_trades': len(losing_trades),
            'win_rate': round(win_rate, 2),
            'total_pnl': round(total_pnl, 2),
            'realized_pnl': round(realized_pnl, 2),
            'unrealized_pnl': round(unrealized_pnl, 2),
            'average_win': round(avg_win, 2),
            'average_loss': round(avg_loss, 2),
            'profit_factor': round(abs(avg_win / avg_loss), 2) if avg_loss != 0 else 0,
            'strategy_breakdown': strategy_stats,
            'generated_at': datetime.now().isoformat()
        }
        
        # Save daily summary to file
        summary_file = self.reports_dir / f'daily_summary_{target_date.strftime("%Y%m%d")}.json'
        with open(summary_file, 'w', encoding='utf-8') as f:
            json.dump(summary, f, indent=2, ensure_ascii=False)
        
        return summary