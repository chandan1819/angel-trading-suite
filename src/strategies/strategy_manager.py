"""
StrategyManager class for coordinating multiple trading strategies.

This module provides the StrategyManager class that handles strategy registration,
evaluation, and coordination for the Bank Nifty Options Trading System.
"""

import logging
from typing import List, Dict, Any, Optional, Type
from datetime import datetime
from concurrent.futures import ThreadPoolExecutor, as_completed
import threading

from .base_strategy import BaseStrategy
from ..models.trading_models import TradingSignal
from ..data.data_manager import DataManager

logger = logging.getLogger(__name__)


class StrategyManager:
    """
    Manages multiple trading strategies and coordinates their evaluation.
    
    Provides strategy registration, evaluation, performance tracking,
    and concurrent strategy execution capabilities.
    """
    
    def __init__(self, data_manager: DataManager, config: Dict[str, Any]):
        """
        Initialize StrategyManager.
        
        Args:
            data_manager: DataManager instance for market data
            config: Strategy manager configuration
        """
        self.data_manager = data_manager
        self.config = config
        self.strategies: Dict[str, BaseStrategy] = {}
        self.strategy_performance: Dict[str, Dict[str, Any]] = {}
        self.evaluation_history: List[Dict[str, Any]] = []
        self.lock = threading.Lock()
        
        # Configuration parameters
        self.max_concurrent_evaluations = config.get('max_concurrent_evaluations', 3)
        self.evaluation_timeout = config.get('evaluation_timeout', 30)  # seconds
        self.enable_concurrent_evaluation = config.get('enable_concurrent_evaluation', True)
        self.signal_aggregation_method = config.get('signal_aggregation_method', 'weighted')
        self.max_signals_per_cycle = config.get('max_signals_per_cycle', 2)
        
        logger.info(f"Initialized StrategyManager with {len(self.strategies)} strategies")
    
    def register_strategy(self, strategy: BaseStrategy) -> bool:
        """
        Register a trading strategy.
        
        Args:
            strategy: BaseStrategy instance to register
            
        Returns:
            True if registration successful, False otherwise
        """
        try:
            with self.lock:
                strategy_name = strategy.get_name()
                
                if strategy_name in self.strategies:
                    logger.warning(f"Strategy {strategy_name} already registered, updating")
                
                self.strategies[strategy_name] = strategy
                
                # Initialize performance tracking
                if strategy_name not in self.strategy_performance:
                    self.strategy_performance[strategy_name] = {
                        'total_signals': 0,
                        'successful_signals': 0,
                        'failed_signals': 0,
                        'total_evaluation_time': 0.0,
                        'avg_evaluation_time': 0.0,
                        'last_evaluation': None,
                        'last_signal': None,
                        'success_rate': 0.0,
                        'avg_confidence': 0.0,
                        'total_confidence': 0.0
                    }
                
                logger.info(f"Registered strategy: {strategy_name}")
                return True
                
        except Exception as e:
            logger.error(f"Failed to register strategy {strategy.get_name()}: {e}")
            return False
    
    def unregister_strategy(self, strategy_name: str) -> bool:
        """
        Unregister a trading strategy.
        
        Args:
            strategy_name: Name of strategy to unregister
            
        Returns:
            True if unregistration successful, False otherwise
        """
        try:
            with self.lock:
                if strategy_name in self.strategies:
                    del self.strategies[strategy_name]
                    logger.info(f"Unregistered strategy: {strategy_name}")
                    return True
                else:
                    logger.warning(f"Strategy {strategy_name} not found for unregistration")
                    return False
                    
        except Exception as e:
            logger.error(f"Failed to unregister strategy {strategy_name}: {e}")
            return False
    
    def get_strategy(self, strategy_name: str) -> Optional[BaseStrategy]:
        """
        Get a registered strategy by name.
        
        Args:
            strategy_name: Name of strategy to retrieve
            
        Returns:
            BaseStrategy instance or None if not found
        """
        with self.lock:
            return self.strategies.get(strategy_name)
    
    def get_all_strategies(self) -> Dict[str, BaseStrategy]:
        """
        Get all registered strategies.
        
        Returns:
            Dictionary of strategy name to BaseStrategy instance
        """
        with self.lock:
            return self.strategies.copy()
    
    def get_enabled_strategies(self) -> Dict[str, BaseStrategy]:
        """
        Get all enabled strategies.
        
        Returns:
            Dictionary of enabled strategies
        """
        with self.lock:
            return {name: strategy for name, strategy in self.strategies.items() 
                   if strategy.enabled}
    
    def evaluate_strategies(self, market_data: Dict[str, Any]) -> List[TradingSignal]:
        """
        Evaluate all enabled strategies and return trading signals.
        
        Args:
            market_data: Market data dictionary containing:
                - options_chain: OptionsChain object
                - historical_data: Historical price data
                - indicators: Technical indicators
                - current_time: Current timestamp
                
        Returns:
            List of TradingSignal objects
        """
        try:
            start_time = datetime.now()
            enabled_strategies = self.get_enabled_strategies()
            
            if not enabled_strategies:
                logger.warning("No enabled strategies found")
                return []
            
            logger.info(f"Evaluating {len(enabled_strategies)} strategies")
            
            # Evaluate strategies (concurrent or sequential)
            if self.enable_concurrent_evaluation and len(enabled_strategies) > 1:
                signals = self._evaluate_strategies_concurrent(enabled_strategies, market_data)
            else:
                signals = self._evaluate_strategies_sequential(enabled_strategies, market_data)
            
            # Filter and aggregate signals
            valid_signals = self._filter_and_aggregate_signals(signals)
            
            # Record evaluation history
            evaluation_time = (datetime.now() - start_time).total_seconds()
            self._record_evaluation_history(enabled_strategies, valid_signals, evaluation_time)
            
            logger.info(f"Strategy evaluation completed: {len(valid_signals)} signals generated "
                       f"in {evaluation_time:.2f}s")
            
            return valid_signals
            
        except Exception as e:
            logger.error(f"Error during strategy evaluation: {e}")
            return []
    
    def _evaluate_strategies_sequential(self, strategies: Dict[str, BaseStrategy], 
                                      market_data: Dict[str, Any]) -> List[TradingSignal]:
        """
        Evaluate strategies sequentially.
        
        Args:
            strategies: Dictionary of strategies to evaluate
            market_data: Market data dictionary
            
        Returns:
            List of TradingSignal objects
        """
        signals = []
        
        for strategy_name, strategy in strategies.items():
            try:
                start_time = datetime.now()
                signal = strategy.evaluate(market_data)
                evaluation_time = (datetime.now() - start_time).total_seconds()
                
                # Update performance metrics
                self._update_strategy_performance(strategy_name, signal, evaluation_time)
                
                if signal and strategy.validate_signal(signal):
                    signals.append(signal)
                    logger.info(f"Strategy {strategy_name} generated signal: "
                               f"{signal.signal_type.value} confidence={signal.confidence:.2f}")
                else:
                    logger.debug(f"Strategy {strategy_name} generated no valid signal")
                    
            except Exception as e:
                logger.error(f"Error evaluating strategy {strategy_name}: {e}")
                self._update_strategy_performance(strategy_name, None, 0.0, error=True)
        
        return signals
    
    def _evaluate_strategies_concurrent(self, strategies: Dict[str, BaseStrategy], 
                                      market_data: Dict[str, Any]) -> List[TradingSignal]:
        """
        Evaluate strategies concurrently using ThreadPoolExecutor.
        
        Args:
            strategies: Dictionary of strategies to evaluate
            market_data: Market data dictionary
            
        Returns:
            List of TradingSignal objects
        """
        signals = []
        
        with ThreadPoolExecutor(max_workers=self.max_concurrent_evaluations) as executor:
            # Submit strategy evaluations
            future_to_strategy = {
                executor.submit(self._evaluate_single_strategy, strategy_name, strategy, market_data): strategy_name
                for strategy_name, strategy in strategies.items()
            }
            
            # Collect results
            for future in as_completed(future_to_strategy, timeout=self.evaluation_timeout):
                strategy_name = future_to_strategy[future]
                try:
                    signal, evaluation_time = future.result()
                    
                    # Update performance metrics
                    self._update_strategy_performance(strategy_name, signal, evaluation_time)
                    
                    if signal:
                        signals.append(signal)
                        logger.info(f"Strategy {strategy_name} generated signal: "
                                   f"{signal.signal_type.value} confidence={signal.confidence:.2f}")
                    else:
                        logger.debug(f"Strategy {strategy_name} generated no valid signal")
                        
                except Exception as e:
                    logger.error(f"Error in concurrent evaluation of {strategy_name}: {e}")
                    self._update_strategy_performance(strategy_name, None, 0.0, error=True)
        
        return signals
    
    def _evaluate_single_strategy(self, strategy_name: str, strategy: BaseStrategy, 
                                market_data: Dict[str, Any]) -> tuple:
        """
        Evaluate a single strategy and return result with timing.
        
        Args:
            strategy_name: Name of strategy
            strategy: BaseStrategy instance
            market_data: Market data dictionary
            
        Returns:
            Tuple of (signal, evaluation_time)
        """
        try:
            start_time = datetime.now()
            signal = strategy.evaluate(market_data)
            evaluation_time = (datetime.now() - start_time).total_seconds()
            
            # Validate signal
            if signal and strategy.validate_signal(signal):
                return signal, evaluation_time
            else:
                return None, evaluation_time
                
        except Exception as e:
            logger.error(f"Error evaluating strategy {strategy_name}: {e}")
            return None, 0.0
    
    def _filter_and_aggregate_signals(self, signals: List[TradingSignal]) -> List[TradingSignal]:
        """
        Filter and aggregate trading signals based on configuration.
        
        Args:
            signals: List of raw trading signals
            
        Returns:
            List of filtered and aggregated signals
        """
        try:
            if not signals:
                return []
            
            # Remove duplicate signals (same strategy, same signal type)
            unique_signals = []
            seen_combinations = set()
            
            for signal in signals:
                combination = (signal.strategy_name, signal.signal_type.value, 
                             tuple(signal.strikes), tuple(signal.option_types))
                if combination not in seen_combinations:
                    unique_signals.append(signal)
                    seen_combinations.add(combination)
            
            # Sort by confidence (descending)
            unique_signals.sort(key=lambda s: s.confidence, reverse=True)
            
            # Apply signal limit
            if len(unique_signals) > self.max_signals_per_cycle:
                logger.info(f"Limiting signals from {len(unique_signals)} to {self.max_signals_per_cycle}")
                unique_signals = unique_signals[:self.max_signals_per_cycle]
            
            # Apply aggregation method if needed
            if self.signal_aggregation_method == 'weighted':
                # For now, just return top signals by confidence
                # Could implement more sophisticated aggregation later
                pass
            
            return unique_signals
            
        except Exception as e:
            logger.error(f"Error filtering and aggregating signals: {e}")
            return signals
    
    def _update_strategy_performance(self, strategy_name: str, signal: Optional[TradingSignal], 
                                   evaluation_time: float, error: bool = False) -> None:
        """
        Update performance metrics for a strategy.
        
        Args:
            strategy_name: Name of strategy
            signal: Generated signal (None if no signal)
            evaluation_time: Time taken for evaluation
            error: Whether an error occurred during evaluation
        """
        try:
            with self.lock:
                if strategy_name not in self.strategy_performance:
                    return
                
                perf = self.strategy_performance[strategy_name]
                
                # Update timing metrics
                perf['total_evaluation_time'] += evaluation_time
                perf['last_evaluation'] = datetime.now()
                
                if perf['total_signals'] > 0:
                    perf['avg_evaluation_time'] = perf['total_evaluation_time'] / perf['total_signals']
                
                # Update signal metrics
                if error:
                    perf['failed_signals'] += 1
                elif signal:
                    perf['total_signals'] += 1
                    perf['successful_signals'] += 1
                    perf['last_signal'] = datetime.now()
                    perf['total_confidence'] += signal.confidence
                    perf['avg_confidence'] = perf['total_confidence'] / perf['successful_signals']
                else:
                    perf['total_signals'] += 1
                
                # Update success rate
                if perf['total_signals'] > 0:
                    perf['success_rate'] = perf['successful_signals'] / perf['total_signals']
                
        except Exception as e:
            logger.error(f"Error updating strategy performance for {strategy_name}: {e}")
    
    def _record_evaluation_history(self, strategies: Dict[str, BaseStrategy], 
                                 signals: List[TradingSignal], evaluation_time: float) -> None:
        """
        Record evaluation history for analysis.
        
        Args:
            strategies: Strategies that were evaluated
            signals: Generated signals
            evaluation_time: Total evaluation time
        """
        try:
            history_entry = {
                'timestamp': datetime.now(),
                'strategies_evaluated': list(strategies.keys()),
                'signals_generated': len(signals),
                'evaluation_time': evaluation_time,
                'signal_details': [
                    {
                        'strategy': signal.strategy_name,
                        'type': signal.signal_type.value,
                        'confidence': signal.confidence,
                        'strikes': signal.strikes
                    }
                    for signal in signals
                ]
            }
            
            self.evaluation_history.append(history_entry)
            
            # Keep only last 100 evaluations
            if len(self.evaluation_history) > 100:
                self.evaluation_history = self.evaluation_history[-100:]
                
        except Exception as e:
            logger.error(f"Error recording evaluation history: {e}")
    
    def get_strategy_performance(self, strategy_name: Optional[str] = None) -> Dict[str, Any]:
        """
        Get performance metrics for strategies.
        
        Args:
            strategy_name: Specific strategy name (None for all strategies)
            
        Returns:
            Performance metrics dictionary
        """
        with self.lock:
            if strategy_name:
                return self.strategy_performance.get(strategy_name, {})
            else:
                return self.strategy_performance.copy()
    
    def get_evaluation_history(self, limit: Optional[int] = None) -> List[Dict[str, Any]]:
        """
        Get evaluation history.
        
        Args:
            limit: Maximum number of entries to return
            
        Returns:
            List of evaluation history entries
        """
        with self.lock:
            history = self.evaluation_history.copy()
            if limit:
                return history[-limit:]
            return history
    
    def reset_strategy_performance(self, strategy_name: Optional[str] = None) -> None:
        """
        Reset performance metrics for strategies.
        
        Args:
            strategy_name: Specific strategy name (None for all strategies)
        """
        try:
            with self.lock:
                if strategy_name:
                    if strategy_name in self.strategy_performance:
                        self.strategy_performance[strategy_name] = {
                            'total_signals': 0,
                            'successful_signals': 0,
                            'failed_signals': 0,
                            'total_evaluation_time': 0.0,
                            'avg_evaluation_time': 0.0,
                            'last_evaluation': None,
                            'last_signal': None,
                            'success_rate': 0.0,
                            'avg_confidence': 0.0,
                            'total_confidence': 0.0
                        }
                        logger.info(f"Reset performance metrics for strategy: {strategy_name}")
                else:
                    for name in self.strategy_performance:
                        self.strategy_performance[name] = {
                            'total_signals': 0,
                            'successful_signals': 0,
                            'failed_signals': 0,
                            'total_evaluation_time': 0.0,
                            'avg_evaluation_time': 0.0,
                            'last_evaluation': None,
                            'last_signal': None,
                            'success_rate': 0.0,
                            'avg_confidence': 0.0,
                            'total_confidence': 0.0
                        }
                    logger.info("Reset performance metrics for all strategies")
                    
        except Exception as e:
            logger.error(f"Error resetting strategy performance: {e}")
    
    def update_strategy_config(self, strategy_name: str, config: Dict[str, Any]) -> bool:
        """
        Update configuration for a specific strategy.
        
        Args:
            strategy_name: Name of strategy to update
            config: New configuration parameters
            
        Returns:
            True if update successful, False otherwise
        """
        try:
            strategy = self.get_strategy(strategy_name)
            if strategy:
                strategy.update_parameters(config)
                logger.info(f"Updated configuration for strategy: {strategy_name}")
                return True
            else:
                logger.warning(f"Strategy {strategy_name} not found for config update")
                return False
                
        except Exception as e:
            logger.error(f"Error updating strategy config for {strategy_name}: {e}")
            return False
    
    def get_summary(self) -> Dict[str, Any]:
        """
        Get summary of strategy manager status.
        
        Returns:
            Summary dictionary
        """
        try:
            with self.lock:
                enabled_strategies = [name for name, strategy in self.strategies.items() 
                                    if strategy.enabled]
                
                total_signals = sum(perf.get('total_signals', 0) 
                                  for perf in self.strategy_performance.values())
                
                successful_signals = sum(perf.get('successful_signals', 0) 
                                       for perf in self.strategy_performance.values())
                
                overall_success_rate = (successful_signals / total_signals 
                                      if total_signals > 0 else 0.0)
                
                return {
                    'total_strategies': len(self.strategies),
                    'enabled_strategies': len(enabled_strategies),
                    'enabled_strategy_names': enabled_strategies,
                    'total_evaluations': len(self.evaluation_history),
                    'total_signals_generated': total_signals,
                    'successful_signals': successful_signals,
                    'overall_success_rate': overall_success_rate,
                    'last_evaluation': (self.evaluation_history[-1]['timestamp'] 
                                      if self.evaluation_history else None)
                }
                
        except Exception as e:
            logger.error(f"Error generating strategy manager summary: {e}")
            return {}
    
    def __str__(self) -> str:
        """String representation of StrategyManager."""
        return f"StrategyManager({len(self.strategies)} strategies, {len(self.get_enabled_strategies())} enabled)"
    
    def __repr__(self) -> str:
        """Detailed string representation of StrategyManager."""
        return (f"StrategyManager(strategies={len(self.strategies)}, "
                f"enabled={len(self.get_enabled_strategies())}, "
                f"evaluations={len(self.evaluation_history)})")