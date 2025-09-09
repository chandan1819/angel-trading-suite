"""
Core trading data models for the Bank Nifty Options Trading System.

This module contains dataclasses for all trading-related entities including
TradingSignal, Trade, TradeLeg, OptionsChain, Strike, and Option.
"""

from dataclasses import dataclass, field
from datetime import datetime
from typing import List, Optional, Dict, Any
from enum import Enum


class SignalType(Enum):
    """Types of trading signals"""
    BUY = "BUY"
    SELL = "SELL"
    STRADDLE = "STRADDLE"
    STRANGLE = "STRANGLE"
    IRON_CONDOR = "IRON_CONDOR"


class OptionType(Enum):
    """Option types"""
    CE = "CE"  # Call European
    PE = "PE"  # Put European


class TradeStatus(Enum):
    """Trade status enumeration"""
    OPEN = "OPEN"
    CLOSED = "CLOSED"
    CANCELLED = "CANCELLED"


class OrderAction(Enum):
    """Order action types"""
    BUY = "BUY"
    SELL = "SELL"


@dataclass
class Option:
    """Represents a single option contract"""
    symbol: str
    token: str
    strike_price: float
    option_type: OptionType
    expiry_date: str
    ltp: float = 0.0
    bid: float = 0.0
    ask: float = 0.0
    volume: int = 0
    oi: int = 0  # Open Interest
    delta: float = 0.0
    theta: float = 0.0
    vega: float = 0.0
    gamma: float = 0.0
    iv: float = 0.0  # Implied Volatility
    lot_size: int = 25  # Default BANKNIFTY lot size
    
    def validate(self) -> bool:
        """Validate option data"""
        if not self.symbol or not self.token:
            return False
        if self.strike_price <= 0:
            return False
        if self.ltp < 0 or self.bid < 0 or self.ask < 0:
            return False
        if self.volume < 0 or self.oi < 0:
            return False
        if self.lot_size <= 0:
            return False
        return True
    
    @property
    def bid_ask_spread(self) -> float:
        """Calculate bid-ask spread"""
        if self.ask > 0 and self.bid > 0:
            return self.ask - self.bid
        return 0.0
    
    @property
    def mid_price(self) -> float:
        """Calculate mid price between bid and ask"""
        if self.ask > 0 and self.bid > 0:
            return (self.bid + self.ask) / 2
        return self.ltp


@dataclass
class Strike:
    """Represents a strike price with call and put options"""
    strike_price: float
    call_option: Optional[Option] = None
    put_option: Optional[Option] = None
    
    def validate(self) -> bool:
        """Validate strike data"""
        if self.strike_price <= 0:
            return False
        
        # At least one option should be present
        if not self.call_option and not self.put_option:
            return False
        
        # Validate present options
        if self.call_option and not self.call_option.validate():
            return False
        if self.put_option and not self.put_option.validate():
            return False
        
        return True


@dataclass
class OptionsChain:
    """Represents the complete options chain for an underlying"""
    underlying_symbol: str
    underlying_price: float
    expiry_date: str
    strikes: List[Strike] = field(default_factory=list)
    atm_strike: float = 0.0
    timestamp: datetime = field(default_factory=datetime.now)
    
    def validate(self) -> bool:
        """Validate options chain data"""
        if not self.underlying_symbol or not self.expiry_date:
            return False
        if self.underlying_price <= 0:
            return False
        if not self.strikes:
            return False
        
        # Validate all strikes
        for strike in self.strikes:
            if not strike.validate():
                return False
        
        return True
    
    def get_strike(self, strike_price: float) -> Optional[Strike]:
        """Get strike by price"""
        for strike in self.strikes:
            if strike.strike_price == strike_price:
                return strike
        return None
    
    def get_atm_strike_object(self) -> Optional[Strike]:
        """Get the ATM strike object"""
        if self.atm_strike > 0:
            return self.get_strike(self.atm_strike)
        return None


@dataclass
class TradeLeg:
    """Represents a single leg of a trade"""
    symbol: str
    token: str
    strike: float
    option_type: OptionType
    action: OrderAction
    quantity: int
    entry_price: float = 0.0
    exit_price: Optional[float] = None
    current_price: float = 0.0
    order_id: Optional[str] = None
    fill_time: Optional[datetime] = None
    
    def validate(self) -> bool:
        """Validate trade leg data"""
        if not self.symbol or not self.token:
            return False
        if self.strike <= 0:
            return False
        if self.quantity <= 0:
            return False
        if self.entry_price < 0:
            return False
        if self.exit_price is not None and self.exit_price < 0:
            return False
        if self.current_price < 0:
            return False
        return True
    
    @property
    def unrealized_pnl(self) -> float:
        """Calculate unrealized P&L for this leg"""
        if self.current_price <= 0:
            return 0.0
        
        if self.action == OrderAction.BUY:
            return (self.current_price - self.entry_price) * self.quantity
        else:  # SELL
            return (self.entry_price - self.current_price) * self.quantity
    
    @property
    def realized_pnl(self) -> float:
        """Calculate realized P&L for this leg"""
        if self.exit_price is None:
            return 0.0
        
        if self.action == OrderAction.BUY:
            return (self.exit_price - self.entry_price) * self.quantity
        else:  # SELL
            return (self.entry_price - self.exit_price) * self.quantity


@dataclass
class Trade:
    """Represents a complete trade with multiple legs"""
    trade_id: str
    strategy: str
    underlying_symbol: str
    entry_time: datetime
    legs: List[TradeLeg] = field(default_factory=list)
    exit_time: Optional[datetime] = None
    target_pnl: float = 2000.0  # Default profit target
    stop_loss: float = -1000.0  # Default stop loss
    status: TradeStatus = TradeStatus.OPEN
    metadata: Dict[str, Any] = field(default_factory=dict)
    
    def validate(self) -> bool:
        """Validate trade data"""
        if not self.trade_id or not self.strategy or not self.underlying_symbol:
            return False
        if not self.legs:
            return False
        if self.target_pnl <= 0:
            return False
        if self.stop_loss >= 0:
            return False
        
        # Validate all legs
        for leg in self.legs:
            if not leg.validate():
                return False
        
        return True
    
    @property
    def current_pnl(self) -> float:
        """Calculate current total P&L for the trade"""
        total_pnl = 0.0
        for leg in self.legs:
            if self.status == TradeStatus.CLOSED:
                total_pnl += leg.realized_pnl
            else:
                total_pnl += leg.unrealized_pnl
        return total_pnl
    
    @property
    def is_target_hit(self) -> bool:
        """Check if profit target is hit"""
        return self.current_pnl >= self.target_pnl
    
    @property
    def is_stop_loss_hit(self) -> bool:
        """Check if stop loss is hit"""
        return self.current_pnl <= self.stop_loss
    
    def add_leg(self, leg: TradeLeg) -> None:
        """Add a leg to the trade"""
        if leg.validate():
            self.legs.append(leg)
    
    def close_trade(self, exit_time: datetime) -> None:
        """Close the trade"""
        self.exit_time = exit_time
        self.status = TradeStatus.CLOSED


@dataclass
class TradingSignal:
    """Represents a trading signal generated by a strategy"""
    strategy_name: str
    signal_type: SignalType
    underlying: str
    strikes: List[float]
    option_types: List[OptionType]
    quantities: List[int]
    confidence: float
    timestamp: datetime = field(default_factory=datetime.now)
    expiry_date: str = ""
    target_pnl: float = 2000.0
    stop_loss: float = -1000.0
    metadata: Dict[str, Any] = field(default_factory=dict)
    
    def validate(self) -> bool:
        """Validate trading signal data"""
        if not self.strategy_name or not self.underlying:
            return False
        if not self.strikes or not self.option_types or not self.quantities:
            return False
        if len(self.strikes) != len(self.option_types) or len(self.strikes) != len(self.quantities):
            return False
        if not (0.0 <= self.confidence <= 1.0):
            return False
        if self.target_pnl <= 0:
            return False
        if self.stop_loss >= 0:
            return False
        
        # Validate individual components
        for strike in self.strikes:
            if strike <= 0:
                return False
        
        for quantity in self.quantities:
            if quantity <= 0:
                return False
        
        return True
    
    @property
    def total_quantity(self) -> int:
        """Get total quantity across all legs"""
        return sum(self.quantities)
    
    def to_trade(self, trade_id: str) -> Trade:
        """Convert signal to a Trade object"""
        trade = Trade(
            trade_id=trade_id,
            strategy=self.strategy_name,
            underlying_symbol=self.underlying,
            entry_time=self.timestamp,
            target_pnl=self.target_pnl,
            stop_loss=self.stop_loss,
            metadata=self.metadata.copy()
        )
        
        # Create trade legs from signal
        for i, (strike, option_type, quantity) in enumerate(zip(self.strikes, self.option_types, self.quantities)):
            # Determine action based on signal type
            if self.signal_type in [SignalType.BUY]:
                action = OrderAction.BUY
            elif self.signal_type in [SignalType.SELL]:
                action = OrderAction.SELL
            else:
                # For complex strategies, determine action from metadata or default logic
                action = OrderAction.SELL if i == 0 else OrderAction.BUY
            
            leg = TradeLeg(
                symbol=f"{self.underlying}{self.expiry_date}{strike}{option_type.value}",
                token="",  # To be filled by order manager
                strike=strike,
                option_type=option_type,
                action=action,
                quantity=quantity
            )
            trade.add_leg(leg)
        
        return trade