"""
Order Manager for comprehensive order lifecycle management.

This module provides the main OrderManager class that handles order placement,
validation, tracking, and position monitoring with comprehensive error handling
and retry mechanisms.
"""

import logging
import threading
import time
from typing import Dict, Any, Optional, List, Callable
from datetime import datetime, timedelta
from collections import defaultdict
import uuid

from ..api.angel_api_client import AngelAPIClient
from ..models.trading_models import TradingSignal, Trade, TradeLeg, OrderAction as ModelOrderAction
from ..interfaces.base_interfaces import ValidationResult
from .order_models import (
    OrderRequest, OrderResponse, OrderStatus, Position, OrderType, 
    OrderAction, OrderValidity, OCOOrder, TradeExecution, OrderBook, PositionBook
)
from .order_validator import OrderValidator
from .retry_handler import OrderRetryHandler, RetryConfig, FallbackConfig, RetryStrategy

logger = logging.getLogger(__name__)


class OrderManager:
    """
    Comprehensive order management system for the trading platform.
    
    Features:
    - Order placement with validation
    - Order tracking and status monitoring
    - Position monitoring and P&L calculation
    - OCO (One-Cancels-Other) order support
    - Retry mechanisms for failed orders
    - Comprehensive error handling
    """
    
    def __init__(self, api_client: AngelAPIClient, config: Dict[str, Any], mode: str = "paper"):
        self.api_client = api_client
        self.config = config
        self.mode = mode  # "paper" or "live"
        
        # Initialize components
        self.validator = OrderValidator(config.get('validation', {}))
        
        # Initialize retry handler
        retry_config = RetryConfig(
            strategy=RetryStrategy(config.get('retry', {}).get('strategy', 'exponential_backoff')),
            max_attempts=config.get('retry', {}).get('max_attempts', 3),
            base_delay=config.get('retry', {}).get('base_delay', 1.0),
            max_delay=config.get('retry', {}).get('max_delay', 30.0),
            backoff_multiplier=config.get('retry', {}).get('backoff_multiplier', 2.0)
        )
        
        fallback_config = FallbackConfig(
            enabled=config.get('fallback', {}).get('enabled', True),
            max_price_adjustment=config.get('fallback', {}).get('max_price_adjustment', 0.05),
            min_quantity_reduction=config.get('fallback', {}).get('min_quantity_reduction', 1)
        )
        
        self.retry_handler = OrderRetryHandler(retry_config, fallback_config)
        
        # Order tracking
        self.active_orders: Dict[str, OrderRequest] = {}
        self.order_status: Dict[str, OrderStatus] = {}
        self.order_history: List[OrderBook] = []
        self.execution_history: List[TradeExecution] = []
        
        # Position tracking
        self.positions: Dict[str, Position] = {}  # symbol -> Position
        self.trade_positions: Dict[str, List[Position]] = {}  # trade_id -> positions
        
        # OCO order management
        self.oco_orders: Dict[str, OCOOrder] = {}  # position_key -> OCOOrder
        
        # Threading and monitoring
        self.monitoring_active = False
        self.monitor_thread: Optional[threading.Thread] = None
        self.lock = threading.Lock()
        
        # Retry configuration
        self.retry_config = config.get('retry', {
            'max_attempts': 3,
            'base_delay': 1.0,
            'max_delay': 30.0,
            'backoff_multiplier': 2.0
        })
        
        # Paper trading simulation
        if self.mode == "paper":
            self.paper_orders: Dict[str, Dict] = {}
            self.paper_positions: Dict[str, Position] = {}
            self.paper_order_counter = 1
    
    def start_monitoring(self) -> None:
        """Start order and position monitoring thread"""
        if not self.monitoring_active:
            self.monitoring_active = True
            self.monitor_thread = threading.Thread(target=self._monitoring_loop, daemon=True)
            self.monitor_thread.start()
            logger.info("Order monitoring started")
    
    def stop_monitoring(self) -> None:
        """Stop order and position monitoring"""
        self.monitoring_active = False
        if self.monitor_thread and self.monitor_thread.is_alive():
            self.monitor_thread.join(timeout=5)
        logger.info("Order monitoring stopped")
    
    def place_order(self, order: OrderRequest) -> OrderResponse:
        """
        Place a trading order with comprehensive validation and error handling.
        
        Args:
            order: Order request to place
            
        Returns:
            OrderResponse with order ID and status
        """
        try:
            # Get current market data for validation
            current_ltp = None
            market_data = None
            
            try:
                current_ltp = self.api_client.get_ltp(order.exchange, order.symbol, order.token)
                # Could add more market data here if needed
                market_data = {"ltp": current_ltp}
            except Exception as e:
                logger.warning(f"Could not fetch market data for validation: {e}")
            
            # Validate order
            validation = self.validator.validate_order(order, current_ltp, market_data)
            if not validation.is_valid:
                logger.error(f"Order validation failed: {validation.message}")
                return OrderResponse(
                    status=OrderStatus.REJECTED,
                    message=f"Validation failed: {validation.message}",
                    error_code="VALIDATION_ERROR"
                )
            
            # Place order based on mode
            if self.mode == "paper":
                return self._place_paper_order(order, current_ltp)
            else:
                return self._place_live_order(order)
                
        except Exception as e:
            logger.error(f"Error placing order: {e}")
            return OrderResponse(
                status=OrderStatus.REJECTED,
                message=f"Order placement error: {str(e)}",
                error_code="PLACEMENT_ERROR"
            )
    
    def _place_live_order(self, order: OrderRequest) -> OrderResponse:
        """Place order in live trading mode with advanced retry mechanisms"""
        def place_operation(order_to_place):
            api_params = order_to_place.to_api_params()
            response = self.api_client.place_order(api_params)
            
            if response and response.get('status'):
                order_id = response.get('data', {}).get('orderid')
                if order_id:
                    return OrderResponse(
                        order_id=order_id,
                        status=OrderStatus.PENDING,
                        message="Order placed successfully"
                    )
            
            # Return failed response for retry handler
            return OrderResponse(
                status=OrderStatus.REJECTED,
                message=f"Order placement failed: {response}",
                error_code="API_PLACEMENT_ERROR"
            )
        
        try:
            # Use retry handler for sophisticated retry and fallback mechanisms
            response = self.retry_handler.execute_with_retry(order, place_operation)
            
            if response.is_success:
                # Track the order
                with self.lock:
                    self.active_orders[response.order_id] = order
                    self.order_status[response.order_id] = OrderStatus.PENDING
                
                logger.info(f"Order placed successfully: {response.order_id} for {order.symbol}")
            
            return response
            
        except Exception as e:
            logger.error(f"Failed to place live order: {e}")
            return OrderResponse(
                status=OrderStatus.REJECTED,
                message=f"Live order placement failed: {str(e)}",
                error_code="LIVE_PLACEMENT_ERROR"
            )
    
    def _place_paper_order(self, order: OrderRequest, current_ltp: Optional[float]) -> OrderResponse:
        """Simulate order placement in paper trading mode"""
        try:
            # Generate paper order ID
            order_id = f"PAPER_{self.paper_order_counter:06d}"
            self.paper_order_counter += 1
            
            # Simulate order execution
            execution_price = self._simulate_execution_price(order, current_ltp)
            
            # Create paper order record
            paper_order = {
                'order_id': order_id,
                'order': order,
                'status': OrderStatus.COMPLETE,
                'execution_price': execution_price,
                'execution_time': datetime.now(),
                'filled_quantity': order.quantity
            }
            
            self.paper_orders[order_id] = paper_order
            
            # Update paper positions
            self._update_paper_position(order, execution_price)
            
            # Track the order
            with self.lock:
                self.active_orders[order_id] = order
                self.order_status[order_id] = OrderStatus.COMPLETE
            
            logger.info(f"Paper order executed: {order_id} for {order.symbol} at ₹{execution_price}")
            
            return OrderResponse(
                order_id=order_id,
                status=OrderStatus.COMPLETE,
                message=f"Paper order executed at ₹{execution_price}"
            )
            
        except Exception as e:
            logger.error(f"Paper order simulation failed: {e}")
            return OrderResponse(
                status=OrderStatus.REJECTED,
                message=f"Paper order simulation failed: {str(e)}",
                error_code="PAPER_SIMULATION_ERROR"
            )
    
    def _simulate_execution_price(self, order: OrderRequest, current_ltp: Optional[float]) -> float:
        """Simulate realistic execution price for paper trading"""
        if order.order_type == OrderType.MARKET:
            # Market orders execute at LTP with some slippage
            base_price = current_ltp or order.price or 100.0
            slippage_factor = 0.002 if order.action == OrderAction.BUY else -0.002  # 0.2% slippage
            return base_price * (1 + slippage_factor)
        
        elif order.order_type == OrderType.LIMIT:
            # Limit orders execute at limit price (assuming they get filled)
            return order.price
        
        else:
            # For stop orders, use trigger price
            return order.trigger_price or current_ltp or order.price or 100.0
    
    def _update_paper_position(self, order: OrderRequest, execution_price: float) -> None:
        """Update paper trading positions"""
        position_key = f"{order.symbol}_{order.exchange}"
        
        if position_key in self.paper_positions:
            position = self.paper_positions[position_key]
            
            # Calculate new average price and quantity
            if order.action == OrderAction.BUY:
                new_quantity = position.quantity + order.quantity
                if new_quantity != 0:
                    new_avg_price = ((position.quantity * position.average_price) + 
                                   (order.quantity * execution_price)) / new_quantity
                else:
                    new_avg_price = execution_price
            else:  # SELL
                new_quantity = position.quantity - order.quantity
                new_avg_price = position.average_price  # Keep same avg price for sells
            
            position.quantity = new_quantity
            position.average_price = new_avg_price if new_quantity != 0 else 0
            position.last_update = datetime.now()
            
            # Remove position if quantity becomes zero
            if new_quantity == 0:
                del self.paper_positions[position_key]
        else:
            # Create new position
            if order.action == OrderAction.BUY:
                quantity = order.quantity
            else:
                quantity = -order.quantity
            
            position = Position(
                symbol=order.symbol,
                token=order.token,
                exchange=order.exchange,
                product=order.product,
                quantity=quantity,
                average_price=execution_price,
                trade_id=order.trade_id,
                strategy_name=order.strategy_name,
                entry_time=datetime.now()
            )
            
            self.paper_positions[position_key] = position
    
    def cancel_order(self, order_id: str) -> bool:
        """
        Cancel an active order.
        
        Args:
            order_id: Order ID to cancel
            
        Returns:
            True if cancellation successful, False otherwise
        """
        try:
            if self.mode == "paper":
                return self._cancel_paper_order(order_id)
            else:
                return self._cancel_live_order(order_id)
                
        except Exception as e:
            logger.error(f"Error cancelling order {order_id}: {e}")
            return False
    
    def _cancel_live_order(self, order_id: str) -> bool:
        """Cancel order in live trading mode"""
        try:
            order = self.active_orders.get(order_id)
            if not order:
                logger.warning(f"Order {order_id} not found in active orders")
                return False
            
            def cancel_operation():
                response = self.api_client.cancel_order(order_id, order.variety)
                if response and response.get('status'):
                    return True
                raise Exception(f"Cancel order failed: {response}")
            
            success = self._execute_with_retry(cancel_operation, f"Cancel order {order_id}")
            
            if success:
                with self.lock:
                    self.order_status[order_id] = OrderStatus.CANCELLED
                
                logger.info(f"Order cancelled successfully: {order_id}")
                return True
            
            return False
            
        except Exception as e:
            logger.error(f"Failed to cancel live order {order_id}: {e}")
            return False
    
    def _cancel_paper_order(self, order_id: str) -> bool:
        """Cancel paper order (if still pending)"""
        if order_id in self.paper_orders:
            paper_order = self.paper_orders[order_id]
            if paper_order['status'] == OrderStatus.PENDING:
                paper_order['status'] = OrderStatus.CANCELLED
                
                with self.lock:
                    self.order_status[order_id] = OrderStatus.CANCELLED
                
                logger.info(f"Paper order cancelled: {order_id}")
                return True
        
        logger.warning(f"Cannot cancel paper order {order_id} - not found or already executed")
        return False
    
    def get_order_status(self, order_id: str) -> OrderStatus:
        """Get current status of an order"""
        return self.order_status.get(order_id, OrderStatus.PENDING)
    
    def get_positions(self) -> List[Position]:
        """Get current positions"""
        if self.mode == "paper":
            return list(self.paper_positions.values())
        else:
            return self._get_live_positions()
    
    def _get_live_positions(self) -> List[Position]:
        """Get positions from live trading account"""
        try:
            def get_positions_operation():
                return self.api_client.get_positions()
            
            positions_data = self._execute_with_retry(get_positions_operation, "Get positions")
            
            positions = []
            for pos_data in positions_data:
                position_book = PositionBook.from_api_response(pos_data)
                if position_book.net_quantity != 0:  # Only include non-zero positions
                    position = position_book.to_position()
                    positions.append(position)
            
            return positions
            
        except Exception as e:
            logger.error(f"Failed to get live positions: {e}")
            return []
    
    def monitor_positions(self, trades: List[Trade]) -> List[str]:
        """
        Monitor positions and return list of actions needed.
        
        Args:
            trades: List of active trades to monitor
            
        Returns:
            List of action strings (e.g., "CLOSE_TRADE_123", "UPDATE_STOP_LOSS_456")
        """
        actions = []
        
        try:
            current_positions = self.get_positions()
            position_map = {f"{pos.symbol}_{pos.exchange}": pos for pos in current_positions}
            
            for trade in trades:
                if trade.status.value != "OPEN":
                    continue
                
                # Update trade with current position data
                trade_pnl = 0.0
                
                for leg in trade.legs:
                    position_key = f"{leg.symbol}_{trade.underlying_symbol}"  # Assuming NFO exchange
                    position = position_map.get(position_key)
                    
                    if position:
                        # Update leg current price
                        leg.current_price = position.ltp
                        trade_pnl += leg.unrealized_pnl
                
                # Check if trade should be closed
                if trade_pnl >= trade.target_pnl:
                    actions.append(f"CLOSE_TRADE_{trade.trade_id}_TARGET_HIT")
                elif trade_pnl <= trade.stop_loss:
                    actions.append(f"CLOSE_TRADE_{trade.trade_id}_STOP_LOSS")
                
                # Check for time-based exits or other conditions
                # This can be extended based on strategy requirements
                
        except Exception as e:
            logger.error(f"Error monitoring positions: {e}")
        
        return actions
    
    def place_oco_orders(self, position: Position, target_price: float, 
                        stop_loss_price: float) -> bool:
        """
        Place OCO (One-Cancels-Other) orders for target and stop-loss.
        
        Args:
            position: Position to place OCO orders for
            target_price: Target profit price
            stop_loss_price: Stop loss trigger price
            
        Returns:
            True if OCO orders placed successfully
        """
        try:
            # Determine order action based on position
            action = OrderAction.SELL if position.quantity > 0 else OrderAction.BUY
            
            # Create target order
            target_order = OrderRequest(
                symbol=position.symbol,
                token=position.token,
                exchange=position.exchange,
                action=action,
                order_type=OrderType.LIMIT,
                quantity=abs(position.quantity),
                price=target_price,
                product=position.product,
                trade_id=position.trade_id,
                strategy_name=position.strategy_name,
                tag="TARGET"
            )
            
            # Create stop loss order
            stop_order = OrderRequest(
                symbol=position.symbol,
                token=position.token,
                exchange=position.exchange,
                action=action,
                order_type=OrderType.STOP_LOSS_MARKET,
                quantity=abs(position.quantity),
                trigger_price=stop_loss_price,
                product=position.product,
                trade_id=position.trade_id,
                strategy_name=position.strategy_name,
                tag="STOP_LOSS"
            )
            
            # Validate OCO orders
            validation = self.validator.validate_oco_orders(target_order, stop_order, position.quantity)
            if not validation.is_valid:
                logger.error(f"OCO validation failed: {validation.message}")
                return False
            
            # Place both orders
            target_response = self.place_order(target_order)
            if not target_response.is_success:
                logger.error(f"Failed to place target order: {target_response.message}")
                return False
            
            stop_response = self.place_order(stop_order)
            if not stop_response.is_success:
                logger.error(f"Failed to place stop order: {stop_response.message}")
                # Cancel target order if stop order fails
                self.cancel_order(target_response.order_id)
                return False
            
            # Create OCO record
            position_key = f"{position.symbol}_{position.exchange}"
            oco_order = OCOOrder(
                target_order=target_order,
                stop_loss_order=stop_order,
                parent_position=position,
                target_order_id=target_response.order_id,
                stop_loss_order_id=stop_response.order_id
            )
            
            self.oco_orders[position_key] = oco_order
            
            logger.info(f"OCO orders placed for {position.symbol}: Target={target_response.order_id}, Stop={stop_response.order_id}")
            return True
            
        except Exception as e:
            logger.error(f"Failed to place OCO orders: {e}")
            return False
    
    def _execute_with_retry(self, operation: Callable, context: str) -> Any:
        """Execute operation with retry logic"""
        max_attempts = self.retry_config['max_attempts']
        base_delay = self.retry_config['base_delay']
        max_delay = self.retry_config['max_delay']
        backoff_multiplier = self.retry_config['backoff_multiplier']
        
        for attempt in range(max_attempts):
            try:
                return operation()
            except Exception as e:
                if attempt == max_attempts - 1:
                    raise e
                
                delay = min(base_delay * (backoff_multiplier ** attempt), max_delay)
                logger.warning(f"{context} failed (attempt {attempt + 1}/{max_attempts}): {e}. Retrying in {delay}s")
                time.sleep(delay)
        
        raise Exception(f"All retry attempts failed for {context}")
    
    def _monitoring_loop(self) -> None:
        """Main monitoring loop for orders and positions"""
        logger.info("Order monitoring loop started")
        
        while self.monitoring_active:
            try:
                self._update_order_status()
                self._update_position_data()
                self._check_oco_orders()
                
                # Sleep for monitoring interval
                time.sleep(self.config.get('monitoring_interval', 30))
                
            except Exception as e:
                logger.error(f"Error in monitoring loop: {e}")
                time.sleep(5)  # Short sleep on error
        
        logger.info("Order monitoring loop stopped")
    
    def _update_order_status(self) -> None:
        """Update status of active orders"""
        if self.mode == "live":
            try:
                order_book = self.api_client.get_order_book()
                
                for order_data in order_book:
                    order_book_entry = OrderBook.from_api_response(order_data)
                    order_id = order_book_entry.order_id
                    
                    if order_id in self.active_orders:
                        with self.lock:
                            self.order_status[order_id] = order_book_entry.status
                        
                        # Handle filled orders
                        if order_book_entry.status == OrderStatus.COMPLETE:
                            self._handle_order_fill(order_book_entry)
                            
            except Exception as e:
                logger.error(f"Error updating order status: {e}")
    
    def _update_position_data(self) -> None:
        """Update position data with current market prices"""
        try:
            positions = self.get_positions()
            
            for position in positions:
                # Update LTP for position
                try:
                    current_ltp = self.api_client.get_ltp(position.exchange, position.symbol, position.token)
                    if current_ltp:
                        position.update_ltp(current_ltp)
                except Exception as e:
                    logger.warning(f"Could not update LTP for {position.symbol}: {e}")
                    
        except Exception as e:
            logger.error(f"Error updating position data: {e}")
    
    def _check_oco_orders(self) -> None:
        """Check and manage OCO orders"""
        for position_key, oco_order in list(self.oco_orders.items()):
            try:
                if not oco_order.is_active:
                    continue
                
                # Check if either order is filled
                target_status = self.get_order_status(oco_order.target_order_id)
                stop_status = self.get_order_status(oco_order.stop_loss_order_id)
                
                if target_status == OrderStatus.COMPLETE:
                    # Target hit, cancel stop loss
                    self.cancel_order(oco_order.stop_loss_order_id)
                    oco_order.is_active = False
                    logger.info(f"OCO target hit for {position_key}, stop loss cancelled")
                    
                elif stop_status == OrderStatus.COMPLETE:
                    # Stop loss hit, cancel target
                    self.cancel_order(oco_order.target_order_id)
                    oco_order.is_active = False
                    logger.info(f"OCO stop loss hit for {position_key}, target cancelled")
                    
            except Exception as e:
                logger.error(f"Error checking OCO orders for {position_key}: {e}")
    
    def _handle_order_fill(self, order_book_entry: OrderBook) -> None:
        """Handle order fill and update positions"""
        try:
            # Create execution record
            execution = TradeExecution(
                execution_id=f"EXEC_{order_book_entry.order_id}_{int(time.time())}",
                order_id=order_book_entry.order_id,
                symbol=order_book_entry.symbol,
                action=order_book_entry.action,
                quantity=order_book_entry.filled_quantity,
                price=order_book_entry.average_price,
                execution_time=order_book_entry.update_time,
                trade_id=self.active_orders[order_book_entry.order_id].trade_id,
                strategy_name=self.active_orders[order_book_entry.order_id].strategy_name
            )
            
            self.execution_history.append(execution)
            logger.info(f"Order filled: {order_book_entry.order_id} - {execution.quantity} @ ₹{execution.price}")
            
        except Exception as e:
            logger.error(f"Error handling order fill: {e}")
    
    def get_order_history(self) -> List[OrderBook]:
        """Get order history"""
        return self.order_history.copy()
    
    def get_execution_history(self) -> List[TradeExecution]:
        """Get execution history"""
        return self.execution_history.copy()
    
    def get_active_orders(self) -> Dict[str, OrderRequest]:
        """Get currently active orders"""
        return self.active_orders.copy()
    
    def cleanup(self) -> None:
        """Cleanup resources and stop monitoring"""
        self.stop_monitoring()
        logger.info("Order manager cleanup completed")