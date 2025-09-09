"""
Data management module for the Bank Nifty Options Trading System.

This module provides data management capabilities including:
- Options chain processing and ATM strike identification
- Historical data processing and indicator calculations
- Market data caching and validation
"""

from .data_manager import DataManager
from .indicators import IndicatorCalculator

__all__ = ['DataManager', 'IndicatorCalculator']