"""
Order validation module for comprehensive pre-trade checks.

This module provides validation logic for orders before submission to the broker,
including parameter validation, risk checks, and market condition validation.
"""

import logging
from typing import Dict, Any, Optional, List
from datetime import datetime, time

from ..models.trading_models import TradingSignal, OptionType, OrderAction
from ..interfaces.base_interfaces import ValidationResult
from .order_models import OrderRequest, OrderType, OrderValidity

logger = logging.getLogger(__name__)


class OrderValidator:
    """
    Comprehensive order validation system that checks orders before submission.
    
    Validates:
    - Order parameters and format
    - Market hours and trading sessions
    - Symbol and contract validity
    - Price reasonableness
    - Quantity and lot size compliance
    - Risk management rules
    """
    
    def __init__(self, config: Dict[str, Any]):
        self.config = config
        self.market_hours = config.get('market_hours', {
            'start': time(9, 15),
            'end': time(15, 30),
            'pre_market_start': time(9, 0),
            'post_market_end': time(16, 0)
        })
        self.lot_size = config.get('lot_size', 35)  # BANKNIFTY current lot size
        self.max_order_value = config.get('max_order_value', 1000000)  # 10L max
        self.min_price = config.get('min_price', 0.05)
        self.max_price = config.get('max_price', 10000)
        self.price_tolerance = config.get('price_tolerance', 0.20)  # 20% from LTP
        
    def validate_order(self, order: OrderRequest, 
                      current_ltp: Optional[float] = None,
                      market_data: Optional[Dict[str, Any]] = None) -> ValidationResult:
        """
        Comprehensive order validation.
        
        Args:
            order: Order request to validate
            current_ltp: Current last traded price
            market_data: Additional market data for validation
            
        Returns:
            ValidationResult with validation status and details
        """
        try:
            # Basic parameter validation
            basic_validation = self._validate_basic_parameters(order)
            if not basic_validation.is_valid:
                return basic_validation
            
            # Market hours validation
            market_hours_validation = self._validate_market_hours()
            if not market_hours_validation.is_valid:
                return market_hours_validation
            
            # Symbol and contract validation
            symbol_validation = self._validate_symbol(order)
            if not symbol_validation.is_valid:
                return symbol_validation
            
            # Price validation
            if current_ltp:
                price_validation = self._validate_price(order, current_ltp)
                if not price_validation.is_valid:
                    return price_validation
            
            # Quantity and lot size validation
            quantity_validation = self._validate_quantity(order)
            if not quantity_validation.is_valid:
                return quantity_validation
            
            # Order value validation
            value_validation = self._validate_order_value(order, current_ltp)
            if not value_validation.is_valid:
                return value_validation
            
            # Market data validation
            if market_data:
                market_validation = self._validate_market_conditions(order, market_data)
                if not market_validation.is_valid:
                    return market_validation
            
            logger.info(f"Order validation passed for {order.symbol}")
            return ValidationResult(True, "Order validation successful")
            
        except Exception as e:
            logger.error(f"Order validation error: {e}")
            return ValidationResult(False, f"Validation error: {str(e)}")
    
    def _validate_basic_parameters(self, order: OrderRequest) -> ValidationResult:
        """Validate basic order parameters"""
        if not order.validate():
            return ValidationResult(False, "Basic order parameter validation failed")
        
        # Check required fields
        if not order.symbol or not order.token or not order.exchange:
            return ValidationResult(False, "Missing required order fields")
        
        # Validate order type specific requirements
        if order.order_type == OrderType.LIMIT:
            if not order.price or order.price <= 0:
                return ValidationResult(False, "Limit order requires valid price")
        
        if order.order_type in [OrderType.STOP_LOSS, OrderType.STOP_LOSS_MARKET]:
            if not order.trigger_price or order.trigger_price <= 0:
                return ValidationResult(False, "Stop loss order requires valid trigger price")
        
        # Validate quantity
        if order.quantity <= 0:
            return ValidationResult(False, "Order quantity must be positive")
        
        return ValidationResult(True, "Basic parameters valid")
    
    def _validate_market_hours(self) -> ValidationResult:
        """Validate if market is open for trading"""
        now = datetime.now().time()
        
        # Check if within trading hours
        if self.market_hours['start'] <= now <= self.market_hours['end']:
            return ValidationResult(True, "Market is open")
        
        # Check if within extended hours (pre/post market)
        if (self.market_hours.get('pre_market_start', time(9, 0)) <= now < self.market_hours['start'] or
            self.market_hours['end'] < now <= self.market_hours.get('post_market_end', time(16, 0))):
            return ValidationResult(True, "Extended hours trading allowed", 
                                  {"warning": "Trading in extended hours"})
        
        return ValidationResult(False, f"Market is closed. Current time: {now}")
    
    def _validate_symbol(self, order: OrderRequest) -> ValidationResult:
        """Validate symbol format and contract details"""
        # Basic symbol format validation for BANKNIFTY options
        if not order.symbol.startswith('BANKNIFTY'):
            return ValidationResult(False, "Only BANKNIFTY options supported")
        
        # Validate token format
        if not order.token or len(order.token) < 3:
            return ValidationResult(False, "Invalid token format")
        
        # Validate exchange
        if order.exchange not in ['NFO', 'NSE']:
            return ValidationResult(False, f"Unsupported exchange: {order.exchange}")
        
        return ValidationResult(True, "Symbol validation passed")
    
    def _validate_price(self, order: OrderRequest, current_ltp: float) -> ValidationResult:
        """Validate order price against current market price"""
        if current_ltp <= 0:
            return ValidationResult(False, "Invalid current LTP for price validation")
        
        # Validate price range
        if order.price:
            if order.price < self.min_price:
                return ValidationResult(False, f"Price {order.price} below minimum {self.min_price}")
            
            if order.price > self.max_price:
                return ValidationResult(False, f"Price {order.price} above maximum {self.max_price}")
            
            # Check price deviation from LTP
            price_deviation = abs(order.price - current_ltp) / current_ltp
            if price_deviation > self.price_tolerance:
                return ValidationResult(False, 
                    f"Price deviation {price_deviation:.2%} exceeds tolerance {self.price_tolerance:.2%}")
        
        # Validate trigger price for stop orders
        if order.trigger_price:
            if order.trigger_price < self.min_price or order.trigger_price > self.max_price:
                return ValidationResult(False, "Trigger price outside valid range")
            
            # For stop loss orders, validate trigger price logic
            if order.order_type == OrderType.STOP_LOSS:
                if order.action == OrderAction.SELL and order.trigger_price >= current_ltp:
                    return ValidationResult(False, "Stop loss trigger should be below current price for sell orders")
                elif order.action == OrderAction.BUY and order.trigger_price <= current_ltp:
                    return ValidationResult(False, "Stop loss trigger should be above current price for buy orders")
        
        return ValidationResult(True, "Price validation passed")
    
    def _validate_quantity(self, order: OrderRequest) -> ValidationResult:
        """Validate order quantity and lot size compliance"""
        # Check if quantity is multiple of lot size
        if order.quantity % self.lot_size != 0:
            return ValidationResult(False, 
                f"Quantity {order.quantity} must be multiple of lot size {self.lot_size}")
        
        # Check maximum quantity limits
        max_lots = self.config.get('max_lots_per_order', 100)
        max_quantity = max_lots * self.lot_size
        
        if order.quantity > max_quantity:
            return ValidationResult(False, 
                f"Quantity {order.quantity} exceeds maximum {max_quantity}")
        
        return ValidationResult(True, "Quantity validation passed")
    
    def _validate_order_value(self, order: OrderRequest, 
                            current_ltp: Optional[float] = None) -> ValidationResult:
        """Validate total order value"""
        # Calculate order value
        price_for_calculation = order.price or current_ltp or 0
        
        if price_for_calculation <= 0:
            return ValidationResult(False, "Cannot calculate order value without valid price")
        
        order_value = order.quantity * price_for_calculation
        
        if order_value > self.max_order_value:
            return ValidationResult(False, 
                f"Order value ₹{order_value:,.2f} exceeds maximum ₹{self.max_order_value:,.2f}")
        
        # Minimum order value check
        min_order_value = self.config.get('min_order_value', 100)
        if order_value < min_order_value:
            return ValidationResult(False, 
                f"Order value ₹{order_value:,.2f} below minimum ₹{min_order_value:,.2f}")
        
        return ValidationResult(True, "Order value validation passed")
    
    def _validate_market_conditions(self, order: OrderRequest, 
                                  market_data: Dict[str, Any]) -> ValidationResult:
        """Validate market conditions for order placement"""
        # Check bid-ask spread
        bid = market_data.get('bid', 0)
        ask = market_data.get('ask', 0)
        
        if bid > 0 and ask > 0:
            spread = ask - bid
            spread_percentage = spread / ((bid + ask) / 2) if (bid + ask) > 0 else 0
            
            max_spread_percentage = self.config.get('max_bid_ask_spread', 0.10)  # 10%
            if spread_percentage > max_spread_percentage:
                return ValidationResult(False, 
                    f"Bid-ask spread {spread_percentage:.2%} exceeds maximum {max_spread_percentage:.2%}")
        
        # Check volume
        volume = market_data.get('volume', 0)
        min_volume = self.config.get('min_volume', 100)
        
        if volume < min_volume:
            return ValidationResult(False, 
                f"Volume {volume} below minimum {min_volume}")
        
        # Check open interest for options
        oi = market_data.get('oi', 0)
        min_oi = self.config.get('min_open_interest', 50)
        
        if oi < min_oi:
            return ValidationResult(False, 
                f"Open interest {oi} below minimum {min_oi}")
        
        return ValidationResult(True, "Market conditions validation passed")
    
    def validate_signal_to_orders(self, signal: TradingSignal, 
                                orders: List[OrderRequest]) -> ValidationResult:
        """
        Validate that order requests correctly represent the trading signal.
        
        Args:
            signal: Original trading signal
            orders: List of order requests generated from signal
            
        Returns:
            ValidationResult with validation status
        """
        try:
            if not signal.validate():
                return ValidationResult(False, "Invalid trading signal")
            
            if not orders:
                return ValidationResult(False, "No orders generated from signal")
            
            # Check if number of orders matches signal legs
            expected_legs = len(signal.strikes)
            if len(orders) != expected_legs:
                return ValidationResult(False, 
                    f"Order count {len(orders)} doesn't match signal legs {expected_legs}")
            
            # Validate each order corresponds to signal
            for i, order in enumerate(orders):
                if i >= len(signal.strikes):
                    return ValidationResult(False, f"Extra order at index {i}")
                
                # Check symbol consistency
                expected_symbol_part = f"{signal.underlying}"
                if not order.symbol.startswith(expected_symbol_part):
                    return ValidationResult(False, 
                        f"Order symbol {order.symbol} doesn't match signal underlying {signal.underlying}")
                
                # Check quantity
                if order.quantity != signal.quantities[i]:
                    return ValidationResult(False, 
                        f"Order quantity {order.quantity} doesn't match signal quantity {signal.quantities[i]}")
            
            return ValidationResult(True, "Signal to orders validation passed")
            
        except Exception as e:
            logger.error(f"Signal to orders validation error: {e}")
            return ValidationResult(False, f"Validation error: {str(e)}")
    
    def validate_oco_orders(self, target_order: OrderRequest, 
                          stop_order: OrderRequest,
                          position_quantity: int) -> ValidationResult:
        """
        Validate OCO (One-Cancels-Other) order pair.
        
        Args:
            target_order: Target profit order
            stop_order: Stop loss order
            position_quantity: Current position quantity
            
        Returns:
            ValidationResult with validation status
        """
        try:
            # Basic validation for both orders
            target_validation = self._validate_basic_parameters(target_order)
            if not target_validation.is_valid:
                return ValidationResult(False, f"Target order validation failed: {target_validation.message}")
            
            stop_validation = self._validate_basic_parameters(stop_order)
            if not stop_validation.is_valid:
                return ValidationResult(False, f"Stop order validation failed: {stop_validation.message}")
            
            # Check if orders are for the same symbol
            if target_order.symbol != stop_order.symbol:
                return ValidationResult(False, "OCO orders must be for the same symbol")
            
            # Check if quantities match position
            if target_order.quantity != abs(position_quantity):
                return ValidationResult(False, "Target order quantity must match position quantity")
            
            if stop_order.quantity != abs(position_quantity):
                return ValidationResult(False, "Stop order quantity must match position quantity")
            
            # Check if actions are opposite to position
            expected_action = OrderAction.SELL if position_quantity > 0 else OrderAction.BUY
            
            if target_order.action != expected_action:
                return ValidationResult(False, f"Target order action should be {expected_action.value}")
            
            if stop_order.action != expected_action:
                return ValidationResult(False, f"Stop order action should be {expected_action.value}")
            
            # Validate price relationship for long positions
            if position_quantity > 0:  # Long position
                if (target_order.price and stop_order.trigger_price and 
                    target_order.price <= stop_order.trigger_price):
                    return ValidationResult(False, 
                        "Target price should be higher than stop loss trigger for long positions")
            
            # Validate price relationship for short positions  
            elif position_quantity < 0:  # Short position
                if (target_order.price and stop_order.trigger_price and 
                    target_order.price >= stop_order.trigger_price):
                    return ValidationResult(False, 
                        "Target price should be lower than stop loss trigger for short positions")
            
            return ValidationResult(True, "OCO orders validation passed")
            
        except Exception as e:
            logger.error(f"OCO orders validation error: {e}")
            return ValidationResult(False, f"OCO validation error: {str(e)}")