"""
Base strategy abstract class for the Bank Nifty Options Trading System.

This module provides the BaseStrategy abstract class that all trading strategies
must inherit from, ensuring a consistent interface and common functionality.
"""

from abc import ABC, abstractmethod
from typing import Optional, Dict, Any, List
from datetime import datetime, time
import logging

from ..models.trading_models import TradingSignal, OptionsChain, SignalType
from ..interfaces.base_interfaces import IStrategy

logger = logging.getLogger(__name__)


class BaseStrategy(IStrategy):
    """
    Abstract base class for all trading strategies.
    
    Provides common functionality and enforces consistent interface
    for all strategy implementations.
    """
    
    def __init__(self, name: str, config: Dict[str, Any]):
        """
        Initialize base strategy.
        
        Args:
            name: Strategy name
            config: Strategy configuration dictionary
        """
        self.name = name
        self.config = config.copy()
        self.enabled = config.get('enabled', True)
        self.weight = config.get('weight', 1.0)
        self.min_confidence = config.get('min_confidence', 0.6)
        self.max_positions = config.get('max_positions', 1)
        self.current_positions = 0
        
        # Market hours configuration
        self.market_open = time(9, 15)  # 9:15 AM
        self.market_close = time(15, 30)  # 3:30 PM
        self.early_exit_time = time(15, 0)  # 3:00 PM (30 min before close)
        
        # Risk parameters
        self.max_loss_per_trade = config.get('max_loss_per_trade', 1000.0)
        self.target_profit_per_trade = config.get('target_profit_per_trade', 2000.0)
        
        # Validation parameters
        self.min_volume = config.get('min_volume', 100)
        self.max_bid_ask_spread_pct = config.get('max_bid_ask_spread_pct', 5.0)
        self.min_open_interest = config.get('min_open_interest', 50)
        
        logger.info(f"Initialized {self.name} strategy with config: {self.config}")
    
    def get_name(self) -> str:
        """Get strategy name."""
        return self.name
    
    def get_parameters(self) -> Dict[str, Any]:
        """Get strategy parameters."""
        return {
            'name': self.name,
            'enabled': self.enabled,
            'weight': self.weight,
            'min_confidence': self.min_confidence,
            'max_positions': self.max_positions,
            'current_positions': self.current_positions,
            'max_loss_per_trade': self.max_loss_per_trade,
            'target_profit_per_trade': self.target_profit_per_trade,
            'min_volume': self.min_volume,
            'max_bid_ask_spread_pct': self.max_bid_ask_spread_pct,
            'min_open_interest': self.min_open_interest,
            **self.config
        }
    
    def update_parameters(self, parameters: Dict[str, Any]) -> None:
        """Update strategy parameters."""
        self.config.update(parameters)
        self.enabled = self.config.get('enabled', self.enabled)
        self.weight = self.config.get('weight', self.weight)
        self.min_confidence = self.config.get('min_confidence', self.min_confidence)
        self.max_positions = self.config.get('max_positions', self.max_positions)
        self.max_loss_per_trade = self.config.get('max_loss_per_trade', self.max_loss_per_trade)
        self.target_profit_per_trade = self.config.get('target_profit_per_trade', self.target_profit_per_trade)
        self.min_volume = self.config.get('min_volume', self.min_volume)
        self.max_bid_ask_spread_pct = self.config.get('max_bid_ask_spread_pct', self.max_bid_ask_spread_pct)
        self.min_open_interest = self.config.get('min_open_interest', self.min_open_interest)
        
        logger.info(f"Updated {self.name} strategy parameters")
    
    def validate_signal(self, signal: TradingSignal) -> bool:
        """
        Validate a trading signal.
        
        Args:
            signal: Trading signal to validate
            
        Returns:
            True if signal is valid, False otherwise
        """
        try:
            # Basic signal validation
            if not signal.validate():
                logger.warning(f"{self.name}: Signal failed basic validation")
                return False
            
            # Check confidence threshold
            if signal.confidence < self.min_confidence:
                logger.debug(f"{self.name}: Signal confidence {signal.confidence:.2f} "
                           f"below threshold {self.min_confidence}")
                return False
            
            # Check if strategy is enabled
            if not self.enabled:
                logger.debug(f"{self.name}: Strategy is disabled")
                return False
            
            # Check position limits
            if self.current_positions >= self.max_positions:
                logger.debug(f"{self.name}: Maximum positions ({self.max_positions}) reached")
                return False
            
            # Check market hours
            if not self.is_market_hours():
                logger.debug(f"{self.name}: Outside market hours")
                return False
            
            return True
            
        except Exception as e:
            logger.error(f"{self.name}: Error validating signal: {e}")
            return False
    
    def is_market_hours(self) -> bool:
        """
        Check if current time is within market hours.
        
        Returns:
            True if within market hours, False otherwise
        """
        try:
            current_time = datetime.now().time()
            return self.market_open <= current_time <= self.market_close
        except Exception as e:
            logger.error(f"Error checking market hours: {e}")
            return False
    
    def is_early_exit_time(self) -> bool:
        """
        Check if current time is within early exit window.
        
        Returns:
            True if within early exit window, False otherwise
        """
        try:
            current_time = datetime.now().time()
            return current_time >= self.early_exit_time
        except Exception as e:
            logger.error(f"Error checking early exit time: {e}")
            return False
    
    def validate_option_liquidity(self, option_data: Dict[str, Any]) -> bool:
        """
        Validate option liquidity based on volume, OI, and bid-ask spread.
        
        Args:
            option_data: Option data dictionary
            
        Returns:
            True if option meets liquidity criteria, False otherwise
        """
        try:
            # Check volume
            volume = option_data.get('volume', 0)
            if volume < self.min_volume:
                logger.debug(f"Option volume {volume} below minimum {self.min_volume}")
                return False
            
            # Check open interest
            oi = option_data.get('oi', 0)
            if oi < self.min_open_interest:
                logger.debug(f"Option OI {oi} below minimum {self.min_open_interest}")
                return False
            
            # Check bid-ask spread
            bid = option_data.get('bid', 0)
            ask = option_data.get('ask', 0)
            ltp = option_data.get('ltp', 0)
            
            if bid > 0 and ask > 0 and ltp > 0:
                spread_pct = ((ask - bid) / ltp) * 100
                if spread_pct > self.max_bid_ask_spread_pct:
                    logger.debug(f"Option bid-ask spread {spread_pct:.2f}% "
                               f"above maximum {self.max_bid_ask_spread_pct}%")
                    return False
            
            return True
            
        except Exception as e:
            logger.error(f"Error validating option liquidity: {e}")
            return False
    
    def calculate_confidence_score(self, market_data: Dict[str, Any], 
                                 signal_strength: float) -> float:
        """
        Calculate confidence score for a trading signal.
        
        Args:
            market_data: Market data dictionary
            signal_strength: Raw signal strength (0.0 to 1.0)
            
        Returns:
            Adjusted confidence score (0.0 to 1.0)
        """
        try:
            confidence = signal_strength
            
            # Adjust based on market conditions
            options_chain = market_data.get('options_chain')
            if options_chain:
                # Reduce confidence if ATM options have poor liquidity
                atm_strike = options_chain.atm_strike
                atm_strike_data = None
                
                for strike_data in options_chain.strikes:
                    if strike_data['strike'] == atm_strike:
                        atm_strike_data = strike_data
                        break
                
                if atm_strike_data:
                    # Check ATM call liquidity
                    call_data = atm_strike_data.get('call', {})
                    if not self.validate_option_liquidity(call_data):
                        confidence *= 0.8  # Reduce confidence by 20%
                    
                    # Check ATM put liquidity
                    put_data = atm_strike_data.get('put', {})
                    if not self.validate_option_liquidity(put_data):
                        confidence *= 0.8  # Reduce confidence by 20%
            
            # Adjust based on time to market close
            if self.is_early_exit_time():
                confidence *= 0.7  # Reduce confidence near market close
            
            # Ensure confidence is within bounds
            confidence = max(0.0, min(1.0, confidence))
            
            return confidence
            
        except Exception as e:
            logger.error(f"Error calculating confidence score: {e}")
            return signal_strength
    
    def get_option_by_strike_type(self, options_chain: OptionsChain, 
                                strike: float, option_type: str) -> Optional[Dict[str, Any]]:
        """
        Get option data by strike and type from options chain.
        
        Args:
            options_chain: Options chain data
            strike: Strike price
            option_type: 'call' or 'put'
            
        Returns:
            Option data dictionary or None
        """
        try:
            for strike_data in options_chain.strikes:
                if strike_data['strike'] == strike:
                    return strike_data.get(option_type.lower())
            return None
        except Exception as e:
            logger.error(f"Error getting option by strike/type: {e}")
            return None
    
    def increment_position_count(self) -> None:
        """Increment current position count."""
        self.current_positions += 1
        logger.debug(f"{self.name}: Position count incremented to {self.current_positions}")
    
    def decrement_position_count(self) -> None:
        """Decrement current position count."""
        if self.current_positions > 0:
            self.current_positions -= 1
            logger.debug(f"{self.name}: Position count decremented to {self.current_positions}")
    
    def reset_position_count(self) -> None:
        """Reset position count to zero."""
        self.current_positions = 0
        logger.debug(f"{self.name}: Position count reset to 0")
    
    @abstractmethod
    def evaluate(self, market_data: Dict[str, Any]) -> Optional[TradingSignal]:
        """
        Evaluate market conditions and generate trading signal.
        
        This method must be implemented by all concrete strategy classes.
        
        Args:
            market_data: Dictionary containing market data including:
                - options_chain: OptionsChain object
                - historical_data: Historical price data
                - indicators: Technical indicators
                - current_time: Current timestamp
                
        Returns:
            TradingSignal object if conditions are met, None otherwise
        """
        pass
    
    def __str__(self) -> str:
        """String representation of the strategy."""
        return f"{self.name}(enabled={self.enabled}, weight={self.weight}, positions={self.current_positions})"
    
    def __repr__(self) -> str:
        """Detailed string representation of the strategy."""
        return (f"{self.__class__.__name__}(name='{self.name}', enabled={self.enabled}, "
                f"weight={self.weight}, positions={self.current_positions}/{self.max_positions})")