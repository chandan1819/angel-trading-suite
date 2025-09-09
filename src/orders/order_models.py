"""
Data models for order management system.

This module contains all data structures used for order lifecycle management,
position tracking, and order validation.
"""

from dataclasses import dataclass, field
from datetime import datetime
from typing import Optional, Dict, Any, List
from enum import Enum


class OrderType(Enum):
    """Order types supported by the system"""
    MARKET = "MARKET"
    LIMIT = "LIMIT"
    STOP_LOSS = "SL"
    STOP_LOSS_MARKET = "SL-M"


class OrderAction(Enum):
    """Order actions"""
    BUY = "BUY"
    SELL = "SELL"


class OrderValidity(Enum):
    """Order validity types"""
    DAY = "DAY"
    IOC = "IOC"  # Immediate or Cancel
    GTD = "GTD"  # Good Till Date


class OrderStatus(Enum):
    """Order status enumeration"""
    PENDING = "PENDING"
    OPEN = "OPEN"
    COMPLETE = "COMPLETE"
    CANCELLED = "CANCELLED"
    REJECTED = "REJECTED"
    PARTIAL = "PARTIAL"


class PositionType(Enum):
    """Position types"""
    LONG = "LONG"
    SHORT = "SHORT"


@dataclass
class OrderRequest:
    """Represents an order request to be placed"""
    symbol: str
    token: str
    exchange: str
    action: OrderAction
    order_type: OrderType
    quantity: int
    price: Optional[float] = None
    trigger_price: Optional[float] = None
    validity: OrderValidity = OrderValidity.DAY
    product: str = "MIS"  # MIS, CNC, NRML
    variety: str = "NORMAL"  # NORMAL, STOPLOSS, AMO
    disclosed_quantity: int = 0
    tag: Optional[str] = None
    
    # Trading system specific fields
    trade_id: Optional[str] = None
    strategy_name: Optional[str] = None
    leg_index: Optional[int] = None
    parent_order_id: Optional[str] = None
    
    def validate(self) -> bool:
        """Validate order request parameters"""
        if not self.symbol or not self.token or not self.exchange:
            return False
        
        if self.quantity <= 0:
            return False
        
        if self.order_type == OrderType.LIMIT and (not self.price or self.price <= 0):
            return False
        
        if self.order_type in [OrderType.STOP_LOSS, OrderType.STOP_LOSS_MARKET]:
            if not self.trigger_price or self.trigger_price <= 0:
                return False
        
        return True
    
    def to_api_params(self) -> Dict[str, Any]:
        """Convert to API parameters for Angel Broking"""
        params = {
            "variety": self.variety,
            "tradingsymbol": self.symbol,
            "symboltoken": self.token,
            "transactiontype": self.action.value,
            "exchange": self.exchange,
            "ordertype": self.order_type.value,
            "producttype": self.product,
            "duration": self.validity.value,
            "quantity": str(self.quantity)
        }
        
        if self.price is not None:
            params["price"] = str(self.price)
        
        if self.trigger_price is not None:
            params["triggerprice"] = str(self.trigger_price)
        
        if self.disclosed_quantity > 0:
            params["disclosedquantity"] = str(self.disclosed_quantity)
        
        if self.tag:
            params["tag"] = self.tag
        
        return params


@dataclass
class OrderResponse:
    """Response from order placement"""
    order_id: Optional[str] = None
    status: OrderStatus = OrderStatus.PENDING
    message: str = ""
    error_code: Optional[str] = None
    timestamp: datetime = field(default_factory=datetime.now)
    
    @property
    def is_success(self) -> bool:
        """Check if order was successfully placed"""
        return self.order_id is not None and self.status not in [OrderStatus.REJECTED]
    
    @property
    def is_error(self) -> bool:
        """Check if there was an error"""
        return self.status == OrderStatus.REJECTED or self.error_code is not None


@dataclass
class OrderUpdate:
    """Order status update from broker"""
    order_id: str
    status: OrderStatus
    filled_quantity: int = 0
    pending_quantity: int = 0
    average_price: float = 0.0
    last_fill_time: Optional[datetime] = None
    rejection_reason: Optional[str] = None
    update_time: datetime = field(default_factory=datetime.now)
    
    @property
    def is_filled(self) -> bool:
        """Check if order is completely filled"""
        return self.status == OrderStatus.COMPLETE
    
    @property
    def is_partial(self) -> bool:
        """Check if order is partially filled"""
        return self.status == OrderStatus.PARTIAL and self.filled_quantity > 0


@dataclass
class Position:
    """Represents a trading position"""
    symbol: str
    token: str
    exchange: str
    product: str
    quantity: int  # Net quantity (positive for long, negative for short)
    average_price: float
    ltp: float = 0.0
    pnl: float = 0.0
    unrealized_pnl: float = 0.0
    realized_pnl: float = 0.0
    
    # Position metadata
    trade_id: Optional[str] = None
    strategy_name: Optional[str] = None
    entry_time: Optional[datetime] = None
    last_update: datetime = field(default_factory=datetime.now)
    
    @property
    def position_type(self) -> PositionType:
        """Get position type based on quantity"""
        return PositionType.LONG if self.quantity > 0 else PositionType.SHORT
    
    @property
    def market_value(self) -> float:
        """Calculate current market value"""
        return abs(self.quantity) * self.ltp
    
    def update_ltp(self, new_ltp: float) -> None:
        """Update last traded price and recalculate P&L"""
        self.ltp = new_ltp
        self.unrealized_pnl = self.calculate_unrealized_pnl()
        self.pnl = self.realized_pnl + self.unrealized_pnl
        self.last_update = datetime.now()
    
    def calculate_unrealized_pnl(self) -> float:
        """Calculate unrealized P&L"""
        if self.ltp <= 0 or self.average_price <= 0:
            return 0.0
        
        price_diff = self.ltp - self.average_price
        return self.quantity * price_diff
    
    def validate(self) -> bool:
        """Validate position data"""
        if not self.symbol or not self.token or not self.exchange:
            return False
        
        if self.quantity == 0:
            return False
        
        if self.average_price <= 0:
            return False
        
        return True


@dataclass
class OCOOrder:
    """One-Cancels-Other order pair for target and stop-loss"""
    target_order: OrderRequest
    stop_loss_order: OrderRequest
    parent_position: Position
    target_order_id: Optional[str] = None
    stop_loss_order_id: Optional[str] = None
    is_active: bool = True
    created_time: datetime = field(default_factory=datetime.now)
    
    def validate(self) -> bool:
        """Validate OCO order parameters"""
        if not self.target_order.validate() or not self.stop_loss_order.validate():
            return False
        
        if not self.parent_position.validate():
            return False
        
        # Ensure orders are for the same symbol but opposite actions
        if (self.target_order.symbol != self.stop_loss_order.symbol or
            self.target_order.symbol != self.parent_position.symbol):
            return False
        
        return True


@dataclass
class TradeExecution:
    """Represents a completed trade execution"""
    execution_id: str
    order_id: str
    symbol: str
    action: OrderAction
    quantity: int
    price: float
    execution_time: datetime
    trade_id: Optional[str] = None
    strategy_name: Optional[str] = None
    
    @property
    def value(self) -> float:
        """Calculate execution value"""
        return self.quantity * self.price
    
    def validate(self) -> bool:
        """Validate execution data"""
        return (bool(self.execution_id) and bool(self.order_id) and 
                bool(self.symbol) and self.quantity > 0 and self.price > 0)


@dataclass
class OrderBook:
    """Order book entry from broker"""
    order_id: str
    symbol: str
    action: OrderAction
    order_type: OrderType
    quantity: int
    price: float
    trigger_price: Optional[float]
    status: OrderStatus
    filled_quantity: int
    pending_quantity: int
    average_price: float
    order_time: datetime
    update_time: datetime
    tag: Optional[str] = None
    
    @classmethod
    def from_api_response(cls, data: Dict[str, Any]) -> 'OrderBook':
        """Create OrderBook from API response"""
        return cls(
            order_id=data.get('orderid', ''),
            symbol=data.get('tradingsymbol', ''),
            action=OrderAction(data.get('transactiontype', 'BUY')),
            order_type=OrderType(data.get('ordertype', 'MARKET')),
            quantity=int(data.get('quantity', 0)),
            price=float(data.get('price', 0)),
            trigger_price=float(data.get('triggerprice', 0)) if data.get('triggerprice') else None,
            status=OrderStatus(data.get('status', 'PENDING')),
            filled_quantity=int(data.get('filledshares', 0)),
            pending_quantity=int(data.get('unfilledshares', 0)),
            average_price=float(data.get('averageprice', 0)),
            order_time=datetime.fromisoformat(data.get('ordertime', datetime.now().isoformat())),
            update_time=datetime.fromisoformat(data.get('updatetime', datetime.now().isoformat())),
            tag=data.get('tag')
        )


@dataclass
class PositionBook:
    """Position book entry from broker"""
    symbol: str
    token: str
    exchange: str
    product: str
    net_quantity: int
    buy_quantity: int
    sell_quantity: int
    buy_average: float
    sell_average: float
    net_average: float
    ltp: float
    pnl: float
    unrealized_pnl: float
    realized_pnl: float
    
    @classmethod
    def from_api_response(cls, data: Dict[str, Any]) -> 'PositionBook':
        """Create PositionBook from API response"""
        return cls(
            symbol=data.get('tradingsymbol', ''),
            token=data.get('symboltoken', ''),
            exchange=data.get('exchange', ''),
            product=data.get('producttype', ''),
            net_quantity=int(data.get('netqty', 0)),
            buy_quantity=int(data.get('buyqty', 0)),
            sell_quantity=int(data.get('sellqty', 0)),
            buy_average=float(data.get('buyavgprice', 0)),
            sell_average=float(data.get('sellavgprice', 0)),
            net_average=float(data.get('netavgprice', 0)),
            ltp=float(data.get('ltp', 0)),
            pnl=float(data.get('pnl', 0)),
            unrealized_pnl=float(data.get('unrealisedpnl', 0)),
            realized_pnl=float(data.get('realisedpnl', 0))
        )
    
    def to_position(self, trade_id: Optional[str] = None, 
                   strategy_name: Optional[str] = None) -> Position:
        """Convert to Position object"""
        return Position(
            symbol=self.symbol,
            token=self.token,
            exchange=self.exchange,
            product=self.product,
            quantity=self.net_quantity,
            average_price=self.net_average,
            ltp=self.ltp,
            pnl=self.pnl,
            unrealized_pnl=self.unrealized_pnl,
            realized_pnl=self.realized_pnl,
            trade_id=trade_id,
            strategy_name=strategy_name
        )