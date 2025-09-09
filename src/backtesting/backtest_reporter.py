"""
BacktestReporter for generating comprehensive backtest reports.

This module provides CSV output generation, JSON summaries,
and trade-by-trade analysis reporting for backtest results.
"""

import logging
from typing import Dict, List, Any
from datetime import datetime
import json
import csv
from pathlib import Path

from .models import BacktestResult, PerformanceMetrics
from .historical_simulator import SimulatedTrade

logger = logging.getLogger(__name__)


class BacktestReporter:
    """
    BacktestReporter for generating comprehensive backtest reports.
    
    Provides:
    - CSV output generation for backtest results
    - JSON summary with key performance metrics
    - Trade-by-trade analysis and reporting
    """
    
    def __init__(self):
        """Initialize BacktestReporter."""
        logger.info("BacktestReporter initialized")
    
    def generate_report(self, result: BacktestResult, output_dir: str = "reports") -> None:
        """
        Generate comprehensive backtest report.
        
        Args:
            result: Backtest result to report
            output_dir: Output directory for reports
        """
        try:
            # Create output directory
            output_path = Path(output_dir)
            output_path.mkdir(parents=True, exist_ok=True)
            
            # Generate timestamp for unique filenames
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            strategy_name = result.strategy_name.replace(" ", "_").lower()
            
            # Generate different report formats
            self._generate_csv_report(result, output_path, timestamp, strategy_name)
            self._generate_json_summary(result, output_path, timestamp, strategy_name)
            self._generate_trade_analysis(result, output_path, timestamp, strategy_name)
            self._generate_daily_pnl_report(result, output_path, timestamp, strategy_name)
            self._generate_equity_curve_report(result, output_path, timestamp, strategy_name)
            
            logger.info(f"Backtest reports generated in {output_path}")
            
        except Exception as e:
            logger.error(f"Failed to generate backtest report: {e}")
            raise
    
    def _generate_csv_report(self, result: BacktestResult, output_path: Path,
                           timestamp: str, strategy_name: str) -> None:
        """
        Generate CSV report with trade-by-trade results.
        
        Args:
            result: Backtest result
            output_path: Output directory path
            timestamp: Timestamp for filename
            strategy_name: Strategy name for filename
        """
        try:
            filename = f"backtest_trades_{strategy_name}_{timestamp}.csv"
            filepath = output_path / filename
            
            with open(filepath, 'w', newline='', encoding='utf-8') as csvfile:
                fieldnames = [
                    'trade_id', 'strategy', 'underlying_symbol', 'entry_time', 'exit_time',
                    'duration_hours', 'num_legs', 'target_pnl', 'stop_loss', 'realized_pnl',
                    'commission', 'slippage', 'net_pnl', 'exit_reason', 'status',
                    'leg_details'
                ]
                
                writer = csv.DictWriter(csvfile, fieldnames=fieldnames)
                writer.writeheader()
                
                for trade in result.trades:
                    # Calculate trade duration
                    duration_hours = 0.0
                    if trade.exit_time and trade.entry_time:
                        duration_hours = (trade.exit_time - trade.entry_time).total_seconds() / 3600
                    
                    # Create leg details string
                    leg_details = []
                    for leg in trade.legs:
                        leg_info = (f"{leg.strike}{leg.option_type.value}:"
                                  f"{leg.action.value}:{leg.quantity}@{leg.entry_price:.2f}")
                        if leg.exit_price:
                            leg_info += f"->{leg.exit_price:.2f}"
                        leg_details.append(leg_info)
                    
                    # Calculate net P&L
                    net_pnl = trade.realized_pnl - trade.commission - trade.slippage
                    
                    writer.writerow({
                        'trade_id': trade.trade_id,
                        'strategy': trade.strategy,
                        'underlying_symbol': trade.underlying_symbol,
                        'entry_time': trade.entry_time.strftime('%Y-%m-%d %H:%M:%S'),
                        'exit_time': trade.exit_time.strftime('%Y-%m-%d %H:%M:%S') if trade.exit_time else '',
                        'duration_hours': f"{duration_hours:.2f}",
                        'num_legs': len(trade.legs),
                        'target_pnl': trade.target_pnl,
                        'stop_loss': trade.stop_loss,
                        'realized_pnl': f"{trade.realized_pnl:.2f}",
                        'commission': f"{trade.commission:.2f}",
                        'slippage': f"{trade.slippage:.2f}",
                        'net_pnl': f"{net_pnl:.2f}",
                        'exit_reason': trade.exit_reason,
                        'status': trade.status.value,
                        'leg_details': '; '.join(leg_details)
                    })
            
            logger.info(f"CSV report generated: {filepath}")
            
        except Exception as e:
            logger.error(f"Failed to generate CSV report: {e}")
            raise
    
    def _generate_json_summary(self, result: BacktestResult, output_path: Path,
                             timestamp: str, strategy_name: str) -> None:
        """
        Generate JSON summary with key performance metrics.
        
        Args:
            result: Backtest result
            output_path: Output directory path
            timestamp: Timestamp for filename
            strategy_name: Strategy name for filename
        """
        try:
            filename = f"backtest_summary_{strategy_name}_{timestamp}.json"
            filepath = output_path / filename
            
            # Create comprehensive summary
            summary = {
                'backtest_info': {
                    'strategy_name': result.strategy_name,
                    'start_date': result.start_date,
                    'end_date': result.end_date,
                    'duration_days': (
                        datetime.strptime(result.end_date, '%Y-%m-%d') - 
                        datetime.strptime(result.start_date, '%Y-%m-%d')
                    ).days,
                    'generated_at': datetime.now().isoformat()
                },
                'capital_summary': {
                    'initial_capital': result.initial_capital,
                    'final_capital': result.final_capital,
                    'total_pnl': result.performance_metrics.total_pnl,
                    'total_return_pct': result.performance_metrics.total_return_pct
                },
                'performance_metrics': result.performance_metrics.to_dict(),
                'trade_summary': {
                    'total_trades': len(result.trades),
                    'completed_trades': len([t for t in result.trades if t.status.value == 'CLOSED']),
                    'open_trades': len([t for t in result.trades if t.status.value == 'OPEN']),
                    'cancelled_trades': len([t for t in result.trades if t.status.value == 'CANCELLED'])
                },
                'risk_metrics': {
                    'max_drawdown': result.performance_metrics.max_drawdown,
                    'max_drawdown_pct': result.performance_metrics.max_drawdown_pct,
                    'largest_win': result.performance_metrics.largest_win,
                    'largest_loss': result.performance_metrics.largest_loss,
                    'profit_factor': result.performance_metrics.profit_factor
                },
                'metadata': result.metadata
            }
            
            with open(filepath, 'w', encoding='utf-8') as jsonfile:
                json.dump(summary, jsonfile, indent=2, default=str)
            
            logger.info(f"JSON summary generated: {filepath}")
            
        except Exception as e:
            logger.error(f"Failed to generate JSON summary: {e}")
            raise
    
    def _generate_trade_analysis(self, result: BacktestResult, output_path: Path,
                               timestamp: str, strategy_name: str) -> None:
        """
        Generate detailed trade-by-trade analysis.
        
        Args:
            result: Backtest result
            output_path: Output directory path
            timestamp: Timestamp for filename
            strategy_name: Strategy name for filename
        """
        try:
            filename = f"trade_analysis_{strategy_name}_{timestamp}.csv"
            filepath = output_path / filename
            
            with open(filepath, 'w', newline='', encoding='utf-8') as csvfile:
                fieldnames = [
                    'trade_id', 'leg_index', 'symbol', 'token', 'strike', 'option_type',
                    'action', 'quantity', 'entry_price', 'exit_price', 'current_price',
                    'unrealized_pnl', 'realized_pnl', 'entry_time', 'exit_time'
                ]
                
                writer = csv.DictWriter(csvfile, fieldnames=fieldnames)
                writer.writeheader()
                
                for trade in result.trades:
                    for i, leg in enumerate(trade.legs):
                        writer.writerow({
                            'trade_id': trade.trade_id,
                            'leg_index': i,
                            'symbol': leg.symbol,
                            'token': leg.token,
                            'strike': leg.strike,
                            'option_type': leg.option_type.value,
                            'action': leg.action.value,
                            'quantity': leg.quantity,
                            'entry_price': f"{leg.entry_price:.2f}",
                            'exit_price': f"{leg.exit_price:.2f}" if leg.exit_price else '',
                            'current_price': f"{leg.current_price:.2f}",
                            'unrealized_pnl': f"{leg.unrealized_pnl:.2f}",
                            'realized_pnl': f"{leg.realized_pnl:.2f}",
                            'entry_time': leg.fill_time.strftime('%Y-%m-%d %H:%M:%S') if leg.fill_time else '',
                            'exit_time': trade.exit_time.strftime('%Y-%m-%d %H:%M:%S') if trade.exit_time else ''
                        })
            
            logger.info(f"Trade analysis generated: {filepath}")
            
        except Exception as e:
            logger.error(f"Failed to generate trade analysis: {e}")
            raise
    
    def _generate_daily_pnl_report(self, result: BacktestResult, output_path: Path,
                                 timestamp: str, strategy_name: str) -> None:
        """
        Generate daily P&L report.
        
        Args:
            result: Backtest result
            output_path: Output directory path
            timestamp: Timestamp for filename
            strategy_name: Strategy name for filename
        """
        try:
            filename = f"daily_pnl_{strategy_name}_{timestamp}.csv"
            filepath = output_path / filename
            
            with open(filepath, 'w', newline='', encoding='utf-8') as csvfile:
                fieldnames = ['date', 'daily_pnl', 'cumulative_pnl', 'trades_count']
                
                writer = csv.DictWriter(csvfile, fieldnames=fieldnames)
                writer.writeheader()
                
                cumulative_pnl = 0.0
                
                # Group trades by date
                daily_trades = {}
                for trade in result.trades:
                    if trade.exit_time and trade.status.value == 'CLOSED':
                        date_str = trade.exit_time.strftime('%Y-%m-%d')
                        if date_str not in daily_trades:
                            daily_trades[date_str] = []
                        daily_trades[date_str].append(trade)
                
                # Sort by date and write daily P&L
                for date_str in sorted(daily_trades.keys()):
                    trades = daily_trades[date_str]
                    daily_pnl = sum(trade.realized_pnl for trade in trades)
                    cumulative_pnl += daily_pnl
                    
                    writer.writerow({
                        'date': date_str,
                        'daily_pnl': f"{daily_pnl:.2f}",
                        'cumulative_pnl': f"{cumulative_pnl:.2f}",
                        'trades_count': len(trades)
                    })
            
            logger.info(f"Daily P&L report generated: {filepath}")
            
        except Exception as e:
            logger.error(f"Failed to generate daily P&L report: {e}")
            raise
    
    def _generate_equity_curve_report(self, result: BacktestResult, output_path: Path,
                                    timestamp: str, strategy_name: str) -> None:
        """
        Generate equity curve report.
        
        Args:
            result: Backtest result
            output_path: Output directory path
            timestamp: Timestamp for filename
            strategy_name: Strategy name for filename
        """
        try:
            filename = f"equity_curve_{strategy_name}_{timestamp}.csv"
            filepath = output_path / filename
            
            with open(filepath, 'w', newline='', encoding='utf-8') as csvfile:
                fieldnames = ['date', 'equity', 'drawdown', 'drawdown_pct']
                
                writer = csv.DictWriter(csvfile, fieldnames=fieldnames)
                writer.writeheader()
                
                peak_equity = result.initial_capital
                
                for date_str, equity in result.equity_curve:
                    # Update peak
                    if equity > peak_equity:
                        peak_equity = equity
                    
                    # Calculate drawdown
                    drawdown = peak_equity - equity
                    drawdown_pct = (drawdown / peak_equity) * 100 if peak_equity > 0 else 0
                    
                    writer.writerow({
                        'date': date_str,
                        'equity': f"{equity:.2f}",
                        'drawdown': f"{drawdown:.2f}",
                        'drawdown_pct': f"{drawdown_pct:.2f}"
                    })
            
            logger.info(f"Equity curve report generated: {filepath}")
            
        except Exception as e:
            logger.error(f"Failed to generate equity curve report: {e}")
            raise
    
    def generate_performance_summary(self, result: BacktestResult) -> str:
        """
        Generate a text summary of performance metrics.
        
        Args:
            result: Backtest result
            
        Returns:
            Formatted performance summary string
        """
        try:
            metrics = result.performance_metrics
            
            summary = f"""
BACKTEST PERFORMANCE SUMMARY
============================
Strategy: {result.strategy_name}
Period: {result.start_date} to {result.end_date}
Duration: {(datetime.strptime(result.end_date, '%Y-%m-%d') - datetime.strptime(result.start_date, '%Y-%m-%d')).days} days

CAPITAL SUMMARY
---------------
Initial Capital: ₹{result.initial_capital:,.2f}
Final Capital: ₹{result.final_capital:,.2f}
Total P&L: ₹{metrics.total_pnl:,.2f}
Total Return: {metrics.total_return_pct:.2f}%

TRADE STATISTICS
----------------
Total Trades: {metrics.total_trades}
Winning Trades: {metrics.winning_trades}
Losing Trades: {metrics.losing_trades}
Win Rate: {metrics.win_rate:.2f}%
Average Trade Return: ₹{metrics.avg_trade_return:.2f}
Average Winning Trade: ₹{metrics.avg_winning_trade:.2f}
Average Losing Trade: ₹{metrics.avg_losing_trade:.2f}

RISK METRICS
------------
Maximum Drawdown: ₹{metrics.max_drawdown:,.2f} ({metrics.max_drawdown_pct:.2f}%)
Largest Win: ₹{metrics.largest_win:,.2f}
Largest Loss: ₹{metrics.largest_loss:,.2f}
Profit Factor: {metrics.profit_factor:.2f}
Sharpe Ratio: {metrics.sharpe_ratio:.2f}

CONSISTENCY METRICS
-------------------
Max Consecutive Wins: {metrics.max_consecutive_wins}
Max Consecutive Losses: {metrics.max_consecutive_losses}
Average Trade Duration: {metrics.avg_trade_duration_hours:.2f} hours
"""
            
            return summary
            
        except Exception as e:
            logger.error(f"Failed to generate performance summary: {e}")
            return f"Error generating summary: {e}"