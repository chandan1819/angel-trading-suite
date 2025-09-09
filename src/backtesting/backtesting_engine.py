"""
BacktestingEngine class for historical strategy analysis.

This module provides comprehensive backtesting capabilities including
historical data simulation, trade execution, and performance metrics calculation.
"""

import logging
from typing import Dict, List, Optional, Any, Tuple
from datetime import datetime, timedelta
from dataclasses import dataclass, field
import json
import csv
from pathlib import Path

from ..models.trading_models import Trade, TradingSignal, TradeStatus
from ..strategies.base_strategy import BaseStrategy
from ..data.data_manager import DataManager
from .historical_simulator import HistoricalSimulator, SimulatedTrade

logger = logging.getLogger(__name__)


# Import shared models
from .models import PerformanceMetrics, BacktestResult


class BacktestingEngine:
    """
    BacktestingEngine for historical strategy analysis.
    
    Provides comprehensive backtesting capabilities including:
    - Historical market data replay
    - Strategy signal generation on historical data  
    - Simulated trade execution with realistic fills
    - Performance metrics calculation
    """
    
    def __init__(self, data_manager: DataManager, config: Optional[Dict[str, Any]] = None):
        """
        Initialize BacktestingEngine.
        
        Args:
            data_manager: DataManager instance for historical data
            config: Backtesting configuration
        """
        self.data_manager = data_manager
        self.config = config or {}
        
        # Default configuration
        self.default_config = {
            'initial_capital': 100000.0,  # ₹1,00,000
            'commission_per_trade': 20.0,  # ₹20 per trade
            'slippage_pct': 0.1,  # 0.1% slippage
            'fill_probability': 0.95,  # 95% fill probability
            'max_trades_per_day': 5,
            'risk_free_rate': 0.06,  # 6% annual risk-free rate
            'trading_hours': {'start': '09:15', 'end': '15:30'},
            'early_exit_time': '15:00'
        }
        
        # Merge with provided config
        self.config = {**self.default_config, **self.config}
        
        # Initialize components
        self.simulator = HistoricalSimulator(self.config)
        # Import here to avoid circular import
        from .backtest_reporter import BacktestReporter
        self.reporter = BacktestReporter()
        
        logger.info(f"BacktestingEngine initialized with config: {self.config}")
    
    def run_backtest(self, strategy: BaseStrategy, start_date: str, end_date: str,
                    underlying_symbol: str = "BANKNIFTY") -> BacktestResult:
        """
        Run backtest for a strategy over specified date range.
        
        Args:
            strategy: Strategy to backtest
            start_date: Start date (YYYY-MM-DD)
            end_date: End date (YYYY-MM-DD)
            underlying_symbol: Underlying symbol to trade
            
        Returns:
            BacktestResult with complete analysis
        """
        try:
            logger.info(f"Starting backtest for {strategy.get_name()} "
                       f"from {start_date} to {end_date}")
            
            # Initialize backtest result
            result = BacktestResult(
                strategy_name=strategy.get_name(),
                start_date=start_date,
                end_date=end_date,
                initial_capital=self.config['initial_capital'],
                final_capital=self.config['initial_capital']
            )
            
            # Get historical data for the period
            historical_data = self._get_historical_data_range(
                underlying_symbol, start_date, end_date
            )
            
            if not historical_data:
                logger.error(f"No historical data available for {underlying_symbol}")
                return result
            
            # Run simulation
            trades = self._simulate_trading_period(
                strategy, historical_data, underlying_symbol
            )
            
            result.trades = trades
            
            # Calculate performance metrics
            result.performance_metrics = self._calculate_performance_metrics(trades)
            result.daily_pnl = self._calculate_daily_pnl(trades)
            result.equity_curve = self._calculate_equity_curve(trades, result.initial_capital)
            result.final_capital = result.initial_capital + result.performance_metrics.total_pnl
            
            # Add metadata
            result.metadata = {
                'strategy_config': strategy.get_parameters(),
                'backtest_config': self.config,
                'data_points': len(historical_data),
                'backtest_duration_days': (
                    datetime.strptime(end_date, '%Y-%m-%d') - 
                    datetime.strptime(start_date, '%Y-%m-%d')
                ).days
            }
            
            logger.info(f"Backtest completed: {len(trades)} trades, "
                       f"Total P&L: ₹{result.performance_metrics.total_pnl:.2f}")
            
            return result
            
        except Exception as e:
            logger.error(f"Backtest failed for {strategy.get_name()}: {e}")
            raise
    
    def _get_historical_data_range(self, underlying_symbol: str, 
                                 start_date: str, end_date: str) -> List[Dict[str, Any]]:
        """
        Get historical data for the specified date range.
        
        Args:
            underlying_symbol: Underlying symbol
            start_date: Start date (YYYY-MM-DD)
            end_date: End date (YYYY-MM-DD)
            
        Returns:
            List of historical data points
        """
        try:
            # Convert dates to datetime objects
            start_dt = datetime.strptime(start_date, '%Y-%m-%d')
            end_dt = datetime.strptime(end_date, '%Y-%m-%d')
            
            # Get historical data from data manager
            historical_data = self.data_manager.get_historical_data(
                underlying_symbol, 
                start_date=start_date,
                end_date=end_date,
                interval='1day'
            )
            
            if not historical_data:
                logger.warning(f"No historical data found for {underlying_symbol}")
                return []
            
            # Filter data within date range and add metadata
            filtered_data = []
            for data_point in historical_data:
                try:
                    point_date = datetime.strptime(data_point['date'], '%Y-%m-%d')
                    if start_dt <= point_date <= end_dt:
                        # Add additional fields needed for backtesting
                        data_point['timestamp'] = point_date
                        data_point['underlying_symbol'] = underlying_symbol
                        filtered_data.append(data_point)
                except (ValueError, KeyError) as e:
                    logger.warning(f"Invalid data point: {e}")
                    continue
            
            logger.info(f"Retrieved {len(filtered_data)} historical data points")
            return filtered_data
            
        except Exception as e:
            logger.error(f"Failed to get historical data: {e}")
            return []
    
    def _simulate_trading_period(self, strategy: BaseStrategy, 
                               historical_data: List[Dict[str, Any]],
                               underlying_symbol: str) -> List[SimulatedTrade]:
        """
        Simulate trading over the historical period.
        
        Args:
            strategy: Strategy to simulate
            historical_data: Historical market data
            underlying_symbol: Underlying symbol
            
        Returns:
            List of simulated trades
        """
        trades = []
        open_trades = []
        
        try:
            for i, data_point in enumerate(historical_data):
                current_date = data_point['timestamp']
                
                # Skip weekends (assuming data doesn't include weekends)
                if current_date.weekday() >= 5:
                    continue
                
                # Get market data for this date
                market_data = self._prepare_market_data(data_point, underlying_symbol)
                
                if not market_data:
                    continue
                
                # Update open trades with current prices
                self._update_open_trades(open_trades, market_data, current_date)
                
                # Check for trade exits (targets/stop-losses hit)
                closed_trades = self._check_trade_exits(open_trades, current_date)
                trades.extend(closed_trades)
                
                # Remove closed trades from open trades
                open_trades = [t for t in open_trades if t.status == TradeStatus.OPEN]
                
                # Check daily trade limits
                daily_trades = len([t for t in trades if t.entry_time.date() == current_date.date()])
                if daily_trades >= self.config['max_trades_per_day']:
                    continue
                
                # Generate new signals
                signal = strategy.evaluate(market_data)
                
                if signal and signal.validate():
                    # Create simulated trade from signal
                    simulated_trade = self.simulator.create_trade_from_signal(
                        signal, market_data, current_date
                    )
                    
                    if simulated_trade:
                        open_trades.append(simulated_trade)
                        logger.debug(f"New trade opened: {simulated_trade.trade_id}")
            
            # Close any remaining open trades at end of period
            final_date = historical_data[-1]['timestamp'] if historical_data else datetime.now()
            for trade in open_trades:
                self.simulator.close_trade(trade, final_date, "End of backtest period")
                trades.append(trade)
            
            logger.info(f"Simulation completed: {len(trades)} total trades")
            return trades
            
        except Exception as e:
            logger.error(f"Trading simulation failed: {e}")
            return trades
    
    def _prepare_market_data(self, data_point: Dict[str, Any], 
                           underlying_symbol: str) -> Optional[Dict[str, Any]]:
        """
        Prepare market data for strategy evaluation.
        
        Args:
            data_point: Historical data point
            underlying_symbol: Underlying symbol
            
        Returns:
            Market data dictionary or None
        """
        try:
            # Get options chain for this date (simulated)
            options_chain = self._simulate_options_chain(data_point, underlying_symbol)
            
            if not options_chain:
                return None
            
            # Prepare market data structure expected by strategies
            market_data = {
                'options_chain': options_chain,
                'underlying_price': data_point.get('close', 0),
                'current_time': data_point['timestamp'],
                'historical_data': [data_point],  # Single point for simplicity
                'indicators': self._calculate_indicators([data_point]),
                'volume': data_point.get('volume', 0),
                'volatility': data_point.get('volatility', 0.2)  # Default 20% volatility
            }
            
            return market_data
            
        except Exception as e:
            logger.error(f"Failed to prepare market data: {e}")
            return None
    
    def _simulate_options_chain(self, data_point: Dict[str, Any], 
                              underlying_symbol: str) -> Optional[Dict[str, Any]]:
        """
        Simulate options chain data for historical date.
        
        Args:
            data_point: Historical data point
            underlying_symbol: Underlying symbol
            
        Returns:
            Simulated options chain data or None
        """
        try:
            spot_price = data_point.get('close', 0)
            if spot_price <= 0:
                return None
            
            # Generate strikes around spot price
            strike_spacing = 100.0  # BANKNIFTY typical spacing
            num_strikes = 20  # 10 strikes each side of ATM
            
            atm_strike = round(spot_price / strike_spacing) * strike_spacing
            
            strikes = []
            for i in range(-num_strikes//2, num_strikes//2 + 1):
                strike = atm_strike + (i * strike_spacing)
                if strike > 0:
                    strikes.append(strike)
            
            # Simulate options chain structure
            options_chain = {
                'underlying_symbol': underlying_symbol,
                'underlying_price': spot_price,
                'expiry_date': self._get_next_expiry_date(data_point['timestamp']),
                'atm_strike': atm_strike,
                'strikes': []
            }
            
            # Generate option data for each strike
            for strike in strikes:
                strike_data = {
                    'strike': strike,
                    'call': self._simulate_option_data(spot_price, strike, 'CE', data_point),
                    'put': self._simulate_option_data(spot_price, strike, 'PE', data_point)
                }
                options_chain['strikes'].append(strike_data)
            
            return options_chain
            
        except Exception as e:
            logger.error(f"Failed to simulate options chain: {e}")
            return None
    
    def _simulate_option_data(self, spot_price: float, strike: float, 
                            option_type: str, data_point: Dict[str, Any]) -> Dict[str, Any]:
        """
        Simulate individual option data using Black-Scholes approximation.
        
        Args:
            spot_price: Current spot price
            strike: Strike price
            option_type: 'CE' or 'PE'
            data_point: Historical data point
            
        Returns:
            Simulated option data
        """
        try:
            # Simple option pricing simulation (not actual Black-Scholes)
            # This is a simplified model for backtesting purposes
            
            volatility = data_point.get('volatility', 0.2)  # 20% default
            time_to_expiry = 7.0 / 365.0  # Assume 7 days to expiry
            
            # Calculate intrinsic value
            if option_type == 'CE':
                intrinsic = max(0, spot_price - strike)
            else:  # PE
                intrinsic = max(0, strike - spot_price)
            
            # Calculate time value (simplified)
            moneyness = abs(spot_price - strike) / spot_price
            time_value = spot_price * volatility * (time_to_expiry ** 0.5) * (1 - moneyness)
            time_value = max(0, time_value)
            
            # Option price
            option_price = intrinsic + time_value
            option_price = max(0.05, option_price)  # Minimum price
            
            # Simulate bid-ask spread (1-3% of price)
            spread_pct = 0.02  # 2% spread
            spread = option_price * spread_pct
            
            bid = max(0.05, option_price - spread/2)
            ask = option_price + spread/2
            
            # Simulate Greeks (simplified)
            if option_type == 'CE':
                delta = 0.5 if spot_price == strike else (0.8 if spot_price > strike else 0.2)
            else:
                delta = -0.5 if spot_price == strike else (-0.2 if spot_price > strike else -0.8)
            
            theta = -option_price * 0.1  # Simplified theta
            vega = spot_price * 0.01  # Simplified vega
            gamma = 0.01  # Simplified gamma
            
            return {
                'symbol': f"{data_point['underlying_symbol']}{strike}{option_type}",
                'token': f"token_{strike}_{option_type}",
                'ltp': option_price,
                'bid': bid,
                'ask': ask,
                'volume': int(data_point.get('volume', 1000) * 0.1),  # 10% of underlying volume
                'oi': int(data_point.get('volume', 1000) * 0.5),  # 50% of underlying volume
                'delta': delta,
                'theta': theta,
                'vega': vega,
                'gamma': gamma,
                'iv': volatility
            }
            
        except Exception as e:
            logger.error(f"Failed to simulate option data: {e}")
            return {
                'symbol': f"ERROR_{strike}_{option_type}",
                'token': '',
                'ltp': 0.05,
                'bid': 0.05,
                'ask': 0.05,
                'volume': 0,
                'oi': 0,
                'delta': 0,
                'theta': 0,
                'vega': 0,
                'gamma': 0,
                'iv': 0.2
            }
    
    def _get_next_expiry_date(self, current_date: datetime) -> str:
        """
        Get next Thursday expiry date from current date.
        
        Args:
            current_date: Current date
            
        Returns:
            Next expiry date string (YYYY-MM-DD)
        """
        try:
            # Find next Thursday
            days_ahead = 3 - current_date.weekday()  # Thursday = 3
            if days_ahead <= 0:  # Target day already happened this week
                days_ahead += 7
            
            next_thursday = current_date + timedelta(days=days_ahead)
            return next_thursday.strftime('%Y-%m-%d')
            
        except Exception as e:
            logger.error(f"Failed to calculate next expiry: {e}")
            return (current_date + timedelta(days=7)).strftime('%Y-%m-%d')
    
    def _calculate_indicators(self, historical_data: List[Dict[str, Any]]) -> Dict[str, Any]:
        """
        Calculate technical indicators for strategy evaluation.
        
        Args:
            historical_data: Historical data points
            
        Returns:
            Dictionary of calculated indicators
        """
        try:
            if not historical_data:
                return {}
            
            # For single data point, return basic indicators
            data_point = historical_data[-1]
            
            return {
                'sma_20': data_point.get('close', 0),  # Not enough data for real SMA
                'ema_20': data_point.get('close', 0),  # Not enough data for real EMA
                'atr': data_point.get('high', 0) - data_point.get('low', 0),
                'volatility': data_point.get('volatility', 0.2),
                'volume': data_point.get('volume', 0),
                'rsi': 50.0,  # Neutral RSI
                'iv_rank': 0.5,  # Neutral IV rank
                'iv_percentile': 50.0  # Neutral IV percentile
            }
            
        except Exception as e:
            logger.error(f"Failed to calculate indicators: {e}")
            return {}
    
    def _update_open_trades(self, open_trades: List[SimulatedTrade], 
                          market_data: Dict[str, Any], current_date: datetime) -> None:
        """
        Update open trades with current market prices.
        
        Args:
            open_trades: List of open trades
            market_data: Current market data
            current_date: Current date
        """
        try:
            for trade in open_trades:
                if trade.status != TradeStatus.OPEN:
                    continue
                
                # Update trade with current prices
                self.simulator.update_trade_prices(trade, market_data, current_date)
                
        except Exception as e:
            logger.error(f"Failed to update open trades: {e}")
    
    def _check_trade_exits(self, open_trades: List[SimulatedTrade], 
                         current_date: datetime) -> List[SimulatedTrade]:
        """
        Check if any trades should be closed due to targets/stop-losses.
        
        Args:
            open_trades: List of open trades
            current_date: Current date
            
        Returns:
            List of trades that were closed
        """
        closed_trades = []
        
        try:
            for trade in open_trades:
                if trade.status != TradeStatus.OPEN:
                    continue
                
                # Check profit target
                if trade.current_pnl >= trade.target_pnl:
                    self.simulator.close_trade(trade, current_date, "Profit target hit")
                    closed_trades.append(trade)
                    continue
                
                # Check stop loss
                if trade.current_pnl <= trade.stop_loss:
                    self.simulator.close_trade(trade, current_date, "Stop loss hit")
                    closed_trades.append(trade)
                    continue
                
                # Check time-based exit (end of day)
                if self._should_exit_time_based(trade, current_date):
                    self.simulator.close_trade(trade, current_date, "Time-based exit")
                    closed_trades.append(trade)
                    continue
            
            return closed_trades
            
        except Exception as e:
            logger.error(f"Failed to check trade exits: {e}")
            return closed_trades
    
    def _should_exit_time_based(self, trade: SimulatedTrade, current_date: datetime) -> bool:
        """
        Check if trade should be exited based on time rules.
        
        Args:
            trade: Trade to check
            current_date: Current date
            
        Returns:
            True if should exit, False otherwise
        """
        try:
            # Exit if it's the early exit time (15:00)
            early_exit_time = datetime.strptime(self.config['early_exit_time'], '%H:%M').time()
            if current_date.time() >= early_exit_time:
                return True
            
            # Exit if trade is same day and near market close
            if trade.entry_time.date() == current_date.date():
                market_close = datetime.strptime(self.config['trading_hours']['end'], '%H:%M').time()
                if current_date.time() >= market_close:
                    return True
            
            return False
            
        except Exception as e:
            logger.error(f"Error checking time-based exit: {e}")
            return False 
   
    def _calculate_performance_metrics(self, trades: List[SimulatedTrade]) -> PerformanceMetrics:
        """
        Calculate comprehensive performance metrics from trades.
        
        Args:
            trades: List of completed trades
            
        Returns:
            PerformanceMetrics object
        """
        try:
            if not trades:
                return PerformanceMetrics()
            
            metrics = PerformanceMetrics()
            
            # Basic trade statistics
            metrics.total_trades = len(trades)
            
            # Calculate P&L statistics
            pnls = [trade.realized_pnl for trade in trades if trade.status == TradeStatus.CLOSED]
            
            if pnls:
                metrics.total_pnl = sum(pnls)
                metrics.avg_trade_return = metrics.total_pnl / len(pnls)
                
                winning_pnls = [pnl for pnl in pnls if pnl > 0]
                losing_pnls = [pnl for pnl in pnls if pnl < 0]
                
                metrics.winning_trades = len(winning_pnls)
                metrics.losing_trades = len(losing_pnls)
                metrics.win_rate = (metrics.winning_trades / len(pnls)) * 100
                
                if winning_pnls:
                    metrics.avg_winning_trade = sum(winning_pnls) / len(winning_pnls)
                    metrics.largest_win = max(winning_pnls)
                
                if losing_pnls:
                    metrics.avg_losing_trade = sum(losing_pnls) / len(losing_pnls)
                    metrics.largest_loss = min(losing_pnls)
                
                # Calculate profit factor
                total_wins = sum(winning_pnls) if winning_pnls else 0
                total_losses = abs(sum(losing_pnls)) if losing_pnls else 0
                metrics.profit_factor = total_wins / total_losses if total_losses > 0 else float('inf')
                
                # Calculate return percentage
                initial_capital = self.config['initial_capital']
                metrics.total_return_pct = (metrics.total_pnl / initial_capital) * 100
            
            # Calculate drawdown
            metrics.max_drawdown, metrics.max_drawdown_pct = self._calculate_drawdown(trades)
            
            # Calculate Sharpe ratio (simplified)
            metrics.sharpe_ratio = self._calculate_sharpe_ratio(pnls)
            
            # Calculate consecutive wins/losses
            metrics.max_consecutive_wins, metrics.max_consecutive_losses = self._calculate_consecutive_stats(pnls)
            
            # Calculate average trade duration
            metrics.avg_trade_duration_hours = self._calculate_avg_trade_duration(trades)
            
            return metrics
            
        except Exception as e:
            logger.error(f"Failed to calculate performance metrics: {e}")
            return PerformanceMetrics()
    
    def _calculate_drawdown(self, trades: List[SimulatedTrade]) -> Tuple[float, float]:
        """
        Calculate maximum drawdown in absolute and percentage terms.
        
        Args:
            trades: List of trades
            
        Returns:
            Tuple of (max_drawdown_absolute, max_drawdown_percentage)
        """
        try:
            if not trades:
                return 0.0, 0.0
            
            # Calculate running P&L
            running_pnl = 0.0
            peak_pnl = 0.0
            max_drawdown = 0.0
            
            for trade in trades:
                if trade.status == TradeStatus.CLOSED:
                    running_pnl += trade.realized_pnl
                    
                    # Update peak
                    if running_pnl > peak_pnl:
                        peak_pnl = running_pnl
                    
                    # Calculate current drawdown
                    current_drawdown = peak_pnl - running_pnl
                    if current_drawdown > max_drawdown:
                        max_drawdown = current_drawdown
            
            # Calculate percentage drawdown
            initial_capital = self.config['initial_capital']
            max_drawdown_pct = (max_drawdown / (initial_capital + peak_pnl)) * 100 if (initial_capital + peak_pnl) > 0 else 0.0
            
            return max_drawdown, max_drawdown_pct
            
        except Exception as e:
            logger.error(f"Failed to calculate drawdown: {e}")
            return 0.0, 0.0
    
    def _calculate_sharpe_ratio(self, pnls: List[float]) -> float:
        """
        Calculate Sharpe ratio (simplified version).
        
        Args:
            pnls: List of trade P&Ls
            
        Returns:
            Sharpe ratio
        """
        try:
            if len(pnls) < 2:
                return 0.0
            
            # Calculate mean and standard deviation of returns
            mean_return = sum(pnls) / len(pnls)
            
            variance = sum((pnl - mean_return) ** 2 for pnl in pnls) / (len(pnls) - 1)
            std_dev = variance ** 0.5
            
            if std_dev == 0:
                return 0.0
            
            # Risk-free rate (daily)
            risk_free_rate_daily = self.config['risk_free_rate'] / 365
            
            # Sharpe ratio
            sharpe = (mean_return - risk_free_rate_daily) / std_dev
            
            return sharpe
            
        except Exception as e:
            logger.error(f"Failed to calculate Sharpe ratio: {e}")
            return 0.0
    
    def _calculate_consecutive_stats(self, pnls: List[float]) -> Tuple[int, int]:
        """
        Calculate maximum consecutive wins and losses.
        
        Args:
            pnls: List of trade P&Ls
            
        Returns:
            Tuple of (max_consecutive_wins, max_consecutive_losses)
        """
        try:
            if not pnls:
                return 0, 0
            
            max_wins = 0
            max_losses = 0
            current_wins = 0
            current_losses = 0
            
            for pnl in pnls:
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
            
        except Exception as e:
            logger.error(f"Failed to calculate consecutive stats: {e}")
            return 0, 0
    
    def _calculate_avg_trade_duration(self, trades: List[SimulatedTrade]) -> float:
        """
        Calculate average trade duration in hours.
        
        Args:
            trades: List of trades
            
        Returns:
            Average duration in hours
        """
        try:
            durations = []
            
            for trade in trades:
                if trade.status == TradeStatus.CLOSED and trade.exit_time:
                    duration = (trade.exit_time - trade.entry_time).total_seconds() / 3600
                    durations.append(duration)
            
            if durations:
                return sum(durations) / len(durations)
            
            return 0.0
            
        except Exception as e:
            logger.error(f"Failed to calculate average trade duration: {e}")
            return 0.0
    
    def _calculate_daily_pnl(self, trades: List[SimulatedTrade]) -> List[Tuple[str, float]]:
        """
        Calculate daily P&L from trades.
        
        Args:
            trades: List of trades
            
        Returns:
            List of (date, daily_pnl) tuples
        """
        try:
            daily_pnl = {}
            
            for trade in trades:
                if trade.status == TradeStatus.CLOSED and trade.exit_time:
                    date_str = trade.exit_time.strftime('%Y-%m-%d')
                    if date_str not in daily_pnl:
                        daily_pnl[date_str] = 0.0
                    daily_pnl[date_str] += trade.realized_pnl
            
            # Sort by date and return as list of tuples
            sorted_daily_pnl = sorted(daily_pnl.items())
            
            return sorted_daily_pnl
            
        except Exception as e:
            logger.error(f"Failed to calculate daily P&L: {e}")
            return []
    
    def _calculate_equity_curve(self, trades: List[SimulatedTrade], 
                              initial_capital: float) -> List[Tuple[str, float]]:
        """
        Calculate equity curve from trades.
        
        Args:
            trades: List of trades
            initial_capital: Starting capital
            
        Returns:
            List of (date, equity) tuples
        """
        try:
            equity_curve = []
            running_equity = initial_capital
            
            # Sort trades by exit time
            closed_trades = [t for t in trades if t.status == TradeStatus.CLOSED and t.exit_time]
            closed_trades.sort(key=lambda x: x.exit_time)
            
            for trade in closed_trades:
                running_equity += trade.realized_pnl
                date_str = trade.exit_time.strftime('%Y-%m-%d')
                equity_curve.append((date_str, running_equity))
            
            return equity_curve
            
        except Exception as e:
            logger.error(f"Failed to calculate equity curve: {e}")
            return []
    
    def generate_report(self, result: BacktestResult, output_dir: str = "reports") -> None:
        """
        Generate comprehensive backtest report.
        
        Args:
            result: Backtest result
            output_dir: Output directory for reports
        """
        try:
            self.reporter.generate_report(result, output_dir)
            logger.info(f"Backtest report generated in {output_dir}")
            
        except Exception as e:
            logger.error(f"Failed to generate report: {e}")
            raise