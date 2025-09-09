"""
Backtesting models and data structures.

This module contains shared data structures used across
the backtesting components to avoid circular imports.
"""

from dataclasses import dataclass, field
from typing import Dict, List, Any, Tuple
from datetime import datetime

# Forward reference to avoid circular import
from typing import TYPE_CHECKING
if TYPE_CHECKING:
    from .historical_simulator import SimulatedTrade


@dataclass
class PerformanceMetrics:
    """Performance metrics for backtest results"""
    total_pnl: float = 0.0
    total_return_pct: float = 0.0
    max_drawdown: float = 0.0
    max_drawdown_pct: float = 0.0
    win_rate: float = 0.0
    avg_trade_return: float = 0.0
    avg_winning_trade: float = 0.0
    avg_losing_trade: float = 0.0
    total_trades: int = 0
    winning_trades: int = 0
    losing_trades: int = 0
    sharpe_ratio: float = 0.0
    profit_factor: float = 0.0
    max_consecutive_wins: int = 0
    max_consecutive_losses: int = 0
    avg_trade_duration_hours: float = 0.0
    largest_win: float = 0.0
    largest_loss: float = 0.0
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert metrics to dictionary"""
        return {
            'total_pnl': self.total_pnl,
            'total_return_pct': self.total_return_pct,
            'max_drawdown': self.max_drawdown,
            'max_drawdown_pct': self.max_drawdown_pct,
            'win_rate': self.win_rate,
            'avg_trade_return': self.avg_trade_return,
            'avg_winning_trade': self.avg_winning_trade,
            'avg_losing_trade': self.avg_losing_trade,
            'total_trades': self.total_trades,
            'winning_trades': self.winning_trades,
            'losing_trades': self.losing_trades,
            'sharpe_ratio': self.sharpe_ratio,
            'profit_factor': self.profit_factor,
            'max_consecutive_wins': self.max_consecutive_wins,
            'max_consecutive_losses': self.max_consecutive_losses,
            'avg_trade_duration_hours': self.avg_trade_duration_hours,
            'largest_win': self.largest_win,
            'largest_loss': self.largest_loss
        }


@dataclass
class BacktestResult:
    """Complete backtest result with trades and metrics"""
    strategy_name: str
    start_date: str
    end_date: str
    initial_capital: float
    final_capital: float
    trades: List['SimulatedTrade'] = field(default_factory=list)
    performance_metrics: PerformanceMetrics = field(default_factory=PerformanceMetrics)
    daily_pnl: List[Tuple[str, float]] = field(default_factory=list)
    equity_curve: List[Tuple[str, float]] = field(default_factory=list)
    metadata: Dict[str, Any] = field(default_factory=dict)
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert result to dictionary"""
        return {
            'strategy_name': self.strategy_name,
            'start_date': self.start_date,
            'end_date': self.end_date,
            'initial_capital': self.initial_capital,
            'final_capital': self.final_capital,
            'performance_metrics': self.performance_metrics.to_dict(),
            'total_trades': len(self.trades),
            'daily_pnl_points': len(self.daily_pnl),
            'metadata': self.metadata
        }