"""
Backtesting module for the Bank Nifty Options Trading System.

This module provides backtesting capabilities for strategy analysis
including historical data simulation and performance metrics calculation.
"""

from .backtesting_engine import BacktestingEngine
from .models import BacktestResult, PerformanceMetrics
from .historical_simulator import HistoricalSimulator, SimulatedTrade
from .backtest_reporter import BacktestReporter

__all__ = [
    'BacktestingEngine',
    'BacktestResult', 
    'PerformanceMetrics',
    'HistoricalSimulator',
    'SimulatedTrade',
    'BacktestReporter'
]