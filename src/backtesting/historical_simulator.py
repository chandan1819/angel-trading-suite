"""
HistoricalSimulator for realistic trade execution simulation.

This module provides simulated trade execution with realistic fills,
slippage, and commission modeling for backtesting purposes.
"""

import logging
from typing import Dict, List, Optional, Any
from datetime import datetime, timedelta
from dataclasses import dataclass, field
import uuid
import random

from ..models.trading_models import (
    TradingSignal, Trade, TradeLeg, TradeStatus, 
    OrderAction, OptionType, SignalType
)

logger = logging.getLogger(__name__)


@dataclass
class SimulatedTrade:
    """Simulated trade with realistic execution modeling"""
    trade_id: str
    strategy: str
    underlying_symbol: str
    entry_time: datetime
    legs: List[TradeLeg] = field(default_factory=list)
    exit_time: Optional[datetime] = None
    target_pnl: float = 2000.0
    stop_loss: float = -1000.0
    status: TradeStatus = TradeStatus.OPEN
    realized_pnl: float = 0.0
    current_pnl: float = 0.0
    commission: float = 0.0
    slippage: float = 0.0
    exit_reason: str = ""
    metadata: Dict[str, Any] = field(default_factory=dict)
    
    def calculate_current_pnl(self) -> float:
        """Calculate current P&L from all legs"""
        total_pnl = 0.0
        for leg in self.legs:
            if self.status == TradeStatus.CLOSED:
                total_pnl += leg.realized_pnl
            else:
                total_pnl += leg.unrealized_pnl
        
        # Subtract commission and slippage
        total_pnl -= (self.commission + self.slippage)
        
        self.current_pnl = total_pnl
        return total_pnl
    
    def close_trade(self, exit_time: datetime, exit_reason: str = "") -> None:
        """Close the trade and calculate final P&L"""
        self.exit_time = exit_time
        self.status = TradeStatus.CLOSED
        self.exit_reason = exit_reason
        self.realized_pnl = self.calculate_current_pnl()


class HistoricalSimulator:
    """
    HistoricalSimulator for realistic trade execution simulation.
    
    Provides:
    - Realistic fill simulation with slippage
    - Commission modeling
    - Partial fill handling
    - Market impact simulation
    """
    
    def __init__(self, config: Dict[str, Any]):
        """
        Initialize HistoricalSimulator.
        
        Args:
            config: Simulation configuration
        """
        self.config = config
        
        # Default simulation parameters
        self.commission_per_trade = config.get('commission_per_trade', 20.0)
        self.slippage_pct = config.get('slippage_pct', 0.1)
        self.fill_probability = config.get('fill_probability', 0.95)
        self.market_impact_pct = config.get('market_impact_pct', 0.05)
        
        logger.info(f"HistoricalSimulator initialized with config: {config}")
    
    def create_trade_from_signal(self, signal: TradingSignal, 
                               market_data: Dict[str, Any],
                               entry_time: datetime) -> Optional[SimulatedTrade]:
        """
        Create a simulated trade from a trading signal.
        
        Args:
            signal: Trading signal
            market_data: Current market data
            entry_time: Trade entry time
            
        Returns:
            SimulatedTrade object or None if execution fails
        """
        try:
            # Generate unique trade ID
            trade_id = f"{signal.strategy_name}_{entry_time.strftime('%Y%m%d_%H%M%S')}_{uuid.uuid4().hex[:8]}"
            
            # Create simulated trade
            trade = SimulatedTrade(
                trade_id=trade_id,
                strategy=signal.strategy_name,
                underlying_symbol=signal.underlying,
                entry_time=entry_time,
                target_pnl=signal.target_pnl,
                stop_loss=signal.stop_loss,
                metadata=signal.metadata.copy()
            )
            
            # Create trade legs from signal
            options_chain = market_data.get('options_chain', {})
            
            for i, (strike, option_type, quantity) in enumerate(
                zip(signal.strikes, signal.option_types, signal.quantities)
            ):
                # Get option data from options chain
                option_data = self._get_option_data(options_chain, strike, option_type)
                
                if not option_data:
                    logger.warning(f"Option data not found for {strike} {option_type}")
                    continue
                
                # Determine order action based on signal type
                action = self._determine_order_action(signal.signal_type, i)
                
                # Create trade leg
                leg = self._create_trade_leg(
                    signal, strike, option_type, action, quantity, 
                    option_data, entry_time
                )
                
                if leg:
                    trade.legs.append(leg)
            
            if not trade.legs:
                logger.warning(f"No valid legs created for signal {signal.strategy_name}")
                return None
            
            # Calculate commission and slippage
            trade.commission = self._calculate_commission(trade.legs)
            trade.slippage = self._calculate_slippage(trade.legs)
            
            # Calculate initial P&L
            trade.calculate_current_pnl()
            
            logger.debug(f"Created simulated trade: {trade_id} with {len(trade.legs)} legs")
            return trade
            
        except Exception as e:
            logger.error(f"Failed to create trade from signal: {e}")
            return None
    
    def _get_option_data(self, options_chain: Dict[str, Any], 
                        strike: float, option_type: OptionType) -> Optional[Dict[str, Any]]:
        """
        Get option data from options chain.
        
        Args:
            options_chain: Options chain data
            strike: Strike price
            option_type: Option type (CE/PE)
            
        Returns:
            Option data dictionary or None
        """
        try:
            strikes = options_chain.get('strikes', [])
            
            for strike_data in strikes:
                if strike_data.get('strike') == strike:
                    option_key = 'call' if option_type == OptionType.CE else 'put'
                    return strike_data.get(option_key)
            
            return None
            
        except Exception as e:
            logger.error(f"Failed to get option data: {e}")
            return None
    
    def _determine_order_action(self, signal_type: SignalType, leg_index: int) -> OrderAction:
        """
        Determine order action based on signal type and leg index.
        
        Args:
            signal_type: Type of trading signal
            leg_index: Index of the leg in the strategy
            
        Returns:
            OrderAction (BUY/SELL)
        """
        try:
            if signal_type == SignalType.BUY:
                return OrderAction.BUY
            elif signal_type == SignalType.SELL:
                return OrderAction.SELL
            elif signal_type in [SignalType.STRADDLE, SignalType.STRANGLE]:
                # For straddle/strangle, typically sell both legs
                return OrderAction.SELL
            elif signal_type == SignalType.IRON_CONDOR:
                # For iron condor: sell inner strikes, buy outer strikes
                return OrderAction.SELL if leg_index < 2 else OrderAction.BUY
            else:
                # Default to buy for unknown signal types
                return OrderAction.BUY
                
        except Exception as e:
            logger.error(f"Failed to determine order action: {e}")
            return OrderAction.BUY
    
    def _create_trade_leg(self, signal: TradingSignal, strike: float, 
                         option_type: OptionType, action: OrderAction,
                         quantity: int, option_data: Dict[str, Any],
                         entry_time: datetime) -> Optional[TradeLeg]:
        """
        Create a trade leg with simulated execution.
        
        Args:
            signal: Trading signal
            strike: Strike price
            option_type: Option type
            action: Order action
            quantity: Quantity
            option_data: Option market data
            entry_time: Entry time
            
        Returns:
            TradeLeg object or None
        """
        try:
            # Simulate fill probability
            if random.random() > self.fill_probability:
                logger.debug(f"Simulated fill failure for {strike} {option_type}")
                return None
            
            # Get execution price with slippage
            execution_price = self._get_execution_price(option_data, action)
            
            if execution_price <= 0:
                logger.warning(f"Invalid execution price for {strike} {option_type}")
                return None
            
            # Create trade leg
            leg = TradeLeg(
                symbol=option_data.get('symbol', f"{signal.underlying}{strike}{option_type.value}"),
                token=option_data.get('token', ''),
                strike=strike,
                option_type=option_type,
                action=action,
                quantity=quantity,
                entry_price=execution_price,
                current_price=execution_price,
                order_id=f"order_{uuid.uuid4().hex[:8]}",
                fill_time=entry_time
            )
            
            return leg
            
        except Exception as e:
            logger.error(f"Failed to create trade leg: {e}")
            return None
    
    def _get_execution_price(self, option_data: Dict[str, Any], 
                           action: OrderAction) -> float:
        """
        Get execution price with simulated slippage.
        
        Args:
            option_data: Option market data
            action: Order action (BUY/SELL)
            
        Returns:
            Execution price
        """
        try:
            bid = option_data.get('bid', 0)
            ask = option_data.get('ask', 0)
            ltp = option_data.get('ltp', 0)
            
            # Use mid price as base
            if bid > 0 and ask > 0:
                base_price = (bid + ask) / 2
            else:
                base_price = ltp
            
            if base_price <= 0:
                return 0
            
            # Apply slippage
            slippage_amount = base_price * self.slippage_pct / 100
            
            if action == OrderAction.BUY:
                # Buying: pay slightly more (slippage against us)
                execution_price = base_price + slippage_amount
            else:
                # Selling: receive slightly less (slippage against us)
                execution_price = max(0.05, base_price - slippage_amount)
            
            return execution_price
            
        except Exception as e:
            logger.error(f"Failed to calculate execution price: {e}")
            return 0
    
    def _calculate_commission(self, legs: List[TradeLeg]) -> float:
        """
        Calculate total commission for trade legs.
        
        Args:
            legs: List of trade legs
            
        Returns:
            Total commission
        """
        try:
            # Simple commission model: fixed per trade
            return self.commission_per_trade
            
        except Exception as e:
            logger.error(f"Failed to calculate commission: {e}")
            return 0
    
    def _calculate_slippage(self, legs: List[TradeLeg]) -> float:
        """
        Calculate total slippage cost for trade legs.
        
        Args:
            legs: List of trade legs
            
        Returns:
            Total slippage cost
        """
        try:
            # Slippage is already included in execution price
            # This could be used for additional market impact costs
            total_slippage = 0.0
            
            for leg in legs:
                # Additional market impact for large trades
                if leg.quantity > 100:  # Large trade threshold
                    impact = leg.entry_price * leg.quantity * self.market_impact_pct / 100
                    total_slippage += impact
            
            return total_slippage
            
        except Exception as e:
            logger.error(f"Failed to calculate slippage: {e}")
            return 0
    
    def update_trade_prices(self, trade: SimulatedTrade, 
                          market_data: Dict[str, Any],
                          current_time: datetime) -> None:
        """
        Update trade leg prices with current market data.
        
        Args:
            trade: Simulated trade to update
            market_data: Current market data
            current_time: Current timestamp
        """
        try:
            if trade.status != TradeStatus.OPEN:
                return
            
            options_chain = market_data.get('options_chain', {})
            
            for leg in trade.legs:
                # Get current option data
                option_data = self._get_option_data(
                    options_chain, leg.strike, leg.option_type
                )
                
                if option_data:
                    # Update current price (use LTP or mid price)
                    bid = option_data.get('bid', 0)
                    ask = option_data.get('ask', 0)
                    ltp = option_data.get('ltp', 0)
                    
                    if bid > 0 and ask > 0:
                        leg.current_price = (bid + ask) / 2
                    else:
                        leg.current_price = ltp
                    
                    # Ensure minimum price
                    leg.current_price = max(0.05, leg.current_price)
            
            # Recalculate current P&L
            trade.calculate_current_pnl()
            
        except Exception as e:
            logger.error(f"Failed to update trade prices: {e}")
    
    def close_trade(self, trade: SimulatedTrade, exit_time: datetime, 
                   exit_reason: str = "") -> None:
        """
        Close a simulated trade with exit prices.
        
        Args:
            trade: Trade to close
            exit_time: Exit timestamp
            exit_reason: Reason for exit
        """
        try:
            if trade.status != TradeStatus.OPEN:
                return
            
            # Set exit prices for all legs (use current prices)
            for leg in trade.legs:
                leg.exit_price = leg.current_price
            
            # Close the trade
            trade.close_trade(exit_time, exit_reason)
            
            logger.debug(f"Closed trade {trade.trade_id}: P&L = ₹{trade.realized_pnl:.2f}, "
                        f"Reason: {exit_reason}")
            
        except Exception as e:
            logger.error(f"Failed to close trade: {e}")
    
    def simulate_partial_fill(self, leg: TradeLeg, fill_percentage: float) -> TradeLeg:
        """
        Simulate partial fill for a trade leg.
        
        Args:
            leg: Original trade leg
            fill_percentage: Percentage filled (0.0 to 1.0)
            
        Returns:
            New TradeLeg with partial quantity
        """
        try:
            if not (0.0 <= fill_percentage <= 1.0):
                raise ValueError("Fill percentage must be between 0.0 and 1.0")
            
            filled_quantity = int(leg.quantity * fill_percentage)
            
            if filled_quantity <= 0:
                return None
            
            # Create new leg with filled quantity
            partial_leg = TradeLeg(
                symbol=leg.symbol,
                token=leg.token,
                strike=leg.strike,
                option_type=leg.option_type,
                action=leg.action,
                quantity=filled_quantity,
                entry_price=leg.entry_price,
                current_price=leg.current_price,
                order_id=f"{leg.order_id}_partial",
                fill_time=leg.fill_time
            )
            
            return partial_leg
            
        except Exception as e:
            logger.error(f"Failed to simulate partial fill: {e}")
            return None