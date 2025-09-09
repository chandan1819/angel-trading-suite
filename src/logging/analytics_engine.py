"""
Analytics engine for calculating trading performance metrics.

Provides comprehensive performance analysis including win rate, average returns,
drawdown analysis, and other key trading metrics.
"""

import csv
import json
import math
from datetime import datetime, date, timedelta
from typing import List, Dict, Any, Optional, Tuple
from pathlib import Path
from dataclasses import dataclass

from ..models.trading_models import Trade


@dataclass
class PerformanceMetrics:
    """Container for performance metrics."""
    total_trades: int
    winning_trades: int
    losing_trades: int
    win_rate: float
    total_pnl: float
    average_win: float
    average_loss: float
    profit_factor: float
    max_drawdown: float
    max_drawdown_percent: float
    sharpe_ratio: float
    calmar_ratio: float
    total_return: float
    annualized_return: float
    volatility: float
    max_consecutive_wins: int
    max_consecutive_losses: int
    average_holding_period: float
    best_trade: float
    worst_trade: float
    expectancy: float


class AnalyticsEngine:
    """
    Calculates comprehensive trading performance metrics.
    
    Features:
    - Win rate and profit factor calculations
    - Drawdown analysis
    - Risk-adjusted returns (Sharpe ratio)
    - Strategy-specific performance metrics
    - Time-based performance analysis
    """
    
    def __init__(self, trade_ledger_path: Path):
        """
        Initialize the analytics engine.
        
        Args:
            trade_ledger_path: Path to the trade ledger CSV file
        """
        self.trade_ledger_path = trade_ledger_path
    
    def calculate_performance_metrics(self, 
                                    start_date: Optional[date] = None,
                                    end_date: Optional[date] = None,
                                    strategy: Optional[str] = None,
                                    initial_capital: float = 100000) -> PerformanceMetrics:
        """
        Calculate comprehensive performance metrics.
        
        Args:
            start_date: Start date for analysis
            end_date: End date for analysis
            strategy: Specific strategy to analyze
            initial_capital: Initial capital for return calculations
            
        Returns:
            PerformanceMetrics object with all calculated metrics
        """
        trades_data = self._load_trades_data(start_date, end_date, strategy)
        
        if not trades_data:
            return self._empty_metrics()
        
        # Basic trade statistics
        total_trades = len(trades_data)
        completed_trades = [t for t in trades_data if t['status'] == 'CLOSED']
        
        if not completed_trades:
            return self._empty_metrics()
        
        # P&L calculations
        pnl_values = [float(t['total_pnl']) for t in completed_trades if t['total_pnl']]
        winning_trades = [pnl for pnl in pnl_values if pnl > 0]
        losing_trades = [pnl for pnl in pnl_values if pnl < 0]
        
        # Basic metrics
        win_rate = (len(winning_trades) / len(completed_trades)) * 100 if completed_trades else 0
        total_pnl = sum(pnl_values)
        average_win = sum(winning_trades) / len(winning_trades) if winning_trades else 0
        average_loss = sum(losing_trades) / len(losing_trades) if losing_trades else 0
        profit_factor = abs(sum(winning_trades) / sum(losing_trades)) if losing_trades else float('inf')
        
        # Drawdown analysis
        max_drawdown, max_drawdown_percent = self._calculate_drawdown(pnl_values, initial_capital)
        
        # Risk-adjusted metrics
        sharpe_ratio = self._calculate_sharpe_ratio(pnl_values)
        calmar_ratio = self._calculate_calmar_ratio(total_pnl, max_drawdown_percent, len(completed_trades))
        
        # Return calculations
        total_return = (total_pnl / initial_capital) * 100
        annualized_return = self._calculate_annualized_return(total_return, start_date, end_date)
        volatility = self._calculate_volatility(pnl_values)
        
        # Consecutive wins/losses
        max_consecutive_wins, max_consecutive_losses = self._calculate_consecutive_streaks(pnl_values)
        
        # Holding period analysis
        average_holding_period = self._calculate_average_holding_period(completed_trades)
        
        # Best and worst trades
        best_trade = max(pnl_values) if pnl_values else 0
        worst_trade = min(pnl_values) if pnl_values else 0
        
        # Expectancy
        expectancy = (win_rate / 100 * average_win) + ((100 - win_rate) / 100 * average_loss)
        
        return PerformanceMetrics(
            total_trades=total_trades,
            winning_trades=len(winning_trades),
            losing_trades=len(losing_trades),
            win_rate=round(win_rate, 2),
            total_pnl=round(total_pnl, 2),
            average_win=round(average_win, 2),
            average_loss=round(average_loss, 2),
            profit_factor=round(profit_factor, 2),
            max_drawdown=round(max_drawdown, 2),
            max_drawdown_percent=round(max_drawdown_percent, 2),
            sharpe_ratio=round(sharpe_ratio, 2),
            calmar_ratio=round(calmar_ratio, 2),
            total_return=round(total_return, 2),
            annualized_return=round(annualized_return, 2),
            volatility=round(volatility, 2),
            max_consecutive_wins=max_consecutive_wins,
            max_consecutive_losses=max_consecutive_losses,
            average_holding_period=round(average_holding_period, 2),
            best_trade=round(best_trade, 2),
            worst_trade=round(worst_trade, 2),
            expectancy=round(expectancy, 2)
        )
    
    def calculate_strategy_comparison(self, 
                                   start_date: Optional[date] = None,
                                   end_date: Optional[date] = None) -> Dict[str, PerformanceMetrics]:
        """
        Calculate performance metrics for each strategy.
        
        Args:
            start_date: Start date for analysis
            end_date: End date for analysis
            
        Returns:
            Dictionary mapping strategy names to their performance metrics
        """
        trades_data = self._load_trades_data(start_date, end_date)
        
        # Group trades by strategy
        strategy_trades = {}
        for trade in trades_data:
            strategy = trade['strategy']
            if strategy not in strategy_trades:
                strategy_trades[strategy] = []
            strategy_trades[strategy].append(trade)
        
        # Calculate metrics for each strategy
        strategy_metrics = {}
        for strategy, trades in strategy_trades.items():
            # Create temporary CSV data for this strategy
            strategy_metrics[strategy] = self._calculate_metrics_from_trades(trades)
        
        return strategy_metrics
    
    def calculate_monthly_performance(self, year: int) -> Dict[str, Dict[str, Any]]:
        """
        Calculate monthly performance breakdown for a given year.
        
        Args:
            year: Year to analyze
            
        Returns:
            Dictionary with monthly performance data
        """
        monthly_data = {}
        
        for month in range(1, 13):
            start_date = date(year, month, 1)
            if month == 12:
                end_date = date(year + 1, 1, 1) - timedelta(days=1)
            else:
                end_date = date(year, month + 1, 1) - timedelta(days=1)
            
            metrics = self.calculate_performance_metrics(start_date, end_date)
            monthly_data[f"{year}-{month:02d}"] = {
                'total_trades': metrics.total_trades,
                'win_rate': metrics.win_rate,
                'total_pnl': metrics.total_pnl,
                'max_drawdown': metrics.max_drawdown,
                'sharpe_ratio': metrics.sharpe_ratio
            }
        
        return monthly_data
    
    def _load_trades_data(self, start_date: Optional[date] = None,
                         end_date: Optional[date] = None,
                         strategy: Optional[str] = None) -> List[Dict[str, Any]]:
        """Load and filter trades data from CSV."""
        trades_data = []
        
        if not self.trade_ledger_path.exists():
            return trades_data
        
        with open(self.trade_ledger_path, 'r', encoding='utf-8') as f:
            reader = csv.DictReader(f)
            for row in reader:
                # Apply filters
                if strategy and row['strategy'] != strategy:
                    continue
                
                # Date filtering
                if row['entry_time']:
                    try:
                        entry_date = datetime.fromisoformat(row['entry_time']).date()
                        
                        if start_date and entry_date < start_date:
                            continue
                        if end_date and entry_date > end_date:
                            continue
                        
                        trades_data.append(row)
                    except ValueError:
                        continue
        
        return trades_data
    
    def _calculate_metrics_from_trades(self, trades_data: List[Dict[str, Any]]) -> PerformanceMetrics:
        """Calculate metrics from a list of trade records."""
        if not trades_data:
            return self._empty_metrics()
        
        completed_trades = [t for t in trades_data if t['status'] == 'CLOSED']
        
        if not completed_trades:
            return self._empty_metrics()
        
        pnl_values = [float(t['total_pnl']) for t in completed_trades if t['total_pnl']]
        winning_trades = [pnl for pnl in pnl_values if pnl > 0]
        losing_trades = [pnl for pnl in pnl_values if pnl < 0]
        
        # Calculate all metrics (simplified version)
        win_rate = (len(winning_trades) / len(completed_trades)) * 100 if completed_trades else 0
        total_pnl = sum(pnl_values)
        average_win = sum(winning_trades) / len(winning_trades) if winning_trades else 0
        average_loss = sum(losing_trades) / len(losing_trades) if losing_trades else 0
        profit_factor = abs(sum(winning_trades) / sum(losing_trades)) if losing_trades else float('inf')
        
        return PerformanceMetrics(
            total_trades=len(trades_data),
            winning_trades=len(winning_trades),
            losing_trades=len(losing_trades),
            win_rate=round(win_rate, 2),
            total_pnl=round(total_pnl, 2),
            average_win=round(average_win, 2),
            average_loss=round(average_loss, 2),
            profit_factor=round(profit_factor, 2),
            max_drawdown=0,  # Simplified
            max_drawdown_percent=0,
            sharpe_ratio=0,
            calmar_ratio=0,
            total_return=0,
            annualized_return=0,
            volatility=0,
            max_consecutive_wins=0,
            max_consecutive_losses=0,
            average_holding_period=0,
            best_trade=max(pnl_values) if pnl_values else 0,
            worst_trade=min(pnl_values) if pnl_values else 0,
            expectancy=0
        )
    
    def _calculate_drawdown(self, pnl_values: List[float], 
                          initial_capital: float) -> Tuple[float, float]:
        """Calculate maximum drawdown in absolute and percentage terms."""
        if not pnl_values:
            return 0, 0
        
        cumulative_pnl = []
        running_total = initial_capital
        
        for pnl in pnl_values:
            running_total += pnl
            cumulative_pnl.append(running_total)
        
        peak = initial_capital
        max_drawdown = 0
        max_drawdown_percent = 0
        
        for value in cumulative_pnl:
            if value > peak:
                peak = value
            
            drawdown = peak - value
            drawdown_percent = (drawdown / peak) * 100 if peak > 0 else 0
            
            if drawdown > max_drawdown:
                max_drawdown = drawdown
                max_drawdown_percent = drawdown_percent
        
        return max_drawdown, max_drawdown_percent
    
    def _calculate_sharpe_ratio(self, pnl_values: List[float], 
                               risk_free_rate: float = 0.05) -> float:
        """Calculate Sharpe ratio."""
        if len(pnl_values) < 2:
            return 0
        
        # Calculate average return and standard deviation
        avg_return = sum(pnl_values) / len(pnl_values)
        variance = sum((x - avg_return) ** 2 for x in pnl_values) / (len(pnl_values) - 1)
        std_dev = math.sqrt(variance)
        
        if std_dev == 0:
            return 0
        
        # Annualize the metrics (assuming daily trading)
        annual_return = avg_return * 252  # 252 trading days
        annual_std = std_dev * math.sqrt(252)
        
        return (annual_return - risk_free_rate) / annual_std
    
    def _calculate_calmar_ratio(self, total_return: float, 
                               max_drawdown_percent: float,
                               num_trades: int) -> float:
        """Calculate Calmar ratio."""
        if max_drawdown_percent == 0 or num_trades == 0:
            return 0
        
        # Annualize the return (rough approximation)
        annualized_return = total_return * (252 / num_trades) if num_trades > 0 else 0
        
        return annualized_return / max_drawdown_percent
    
    def _calculate_annualized_return(self, total_return: float,
                                   start_date: Optional[date],
                                   end_date: Optional[date]) -> float:
        """Calculate annualized return."""
        if not start_date or not end_date:
            return 0
        
        days = (end_date - start_date).days
        if days <= 0:
            return 0
        
        years = days / 365.25
        return total_return / years
    
    def _calculate_volatility(self, pnl_values: List[float]) -> float:
        """Calculate volatility (standard deviation of returns)."""
        if len(pnl_values) < 2:
            return 0
        
        avg_return = sum(pnl_values) / len(pnl_values)
        variance = sum((x - avg_return) ** 2 for x in pnl_values) / (len(pnl_values) - 1)
        
        return math.sqrt(variance)
    
    def _calculate_consecutive_streaks(self, pnl_values: List[float]) -> Tuple[int, int]:
        """Calculate maximum consecutive wins and losses."""
        if not pnl_values:
            return 0, 0
        
        max_wins = 0
        max_losses = 0
        current_wins = 0
        current_losses = 0
        
        for pnl in pnl_values:
            if pnl > 0:
                current_wins += 1
                current_losses = 0
                max_wins = max(max_wins, current_wins)
            elif pnl < 0:
                current_losses += 1
                current_wins = 0
                max_losses = max(max_losses, current_losses)
            else:
                current_wins = 0
                current_losses = 0
        
        return max_wins, max_losses
    
    def _calculate_average_holding_period(self, completed_trades: List[Dict[str, Any]]) -> float:
        """Calculate average holding period in minutes."""
        holding_periods = []
        
        for trade in completed_trades:
            if trade['holding_period_minutes']:
                try:
                    holding_periods.append(float(trade['holding_period_minutes']))
                except ValueError:
                    continue
        
        return sum(holding_periods) / len(holding_periods) if holding_periods else 0
    
    def _empty_metrics(self) -> PerformanceMetrics:
        """Return empty performance metrics."""
        return PerformanceMetrics(
            total_trades=0,
            winning_trades=0,
            losing_trades=0,
            win_rate=0,
            total_pnl=0,
            average_win=0,
            average_loss=0,
            profit_factor=0,
            max_drawdown=0,
            max_drawdown_percent=0,
            sharpe_ratio=0,
            calmar_ratio=0,
            total_return=0,
            annualized_return=0,
            volatility=0,
            max_consecutive_wins=0,
            max_consecutive_losses=0,
            average_holding_period=0,
            best_trade=0,
            worst_trade=0,
            expectancy=0
        )