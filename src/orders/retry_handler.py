"""
Advanced retry and fallback mechanisms for order management.

This module provides sophisticated retry strategies, partial fill handling,
and fallback mechanisms for order execution issues.
"""

import logging
import time
import threading
from typing import Dict, Any, Optional, List, Callable, Union
from datetime import datetime, timedelta
from enum import Enum
from dataclasses import dataclass, field

from .order_models import OrderRequest, OrderResponse, OrderStatus, OrderType, OrderAction

logger = logging.getLogger(__name__)


class RetryStrategy(Enum):
    """Retry strategy types"""
    EXPONENTIAL_BACKOFF = "exponential_backoff"
    LINEAR_BACKOFF = "linear_backoff"
    FIXED_DELAY = "fixed_delay"
    IMMEDIATE = "immediate"


class FallbackAction(Enum):
    """Fallback action types"""
    CONVERT_TO_MARKET = "convert_to_market"
    ADJUST_PRICE = "adjust_price"
    REDUCE_QUANTITY = "reduce_quantity"
    SPLIT_ORDER = "split_order"
    CANCEL_AND_RETRY = "cancel_and_retry"
    MANUAL_INTERVENTION = "manual_intervention"


@dataclass
class RetryConfig:
    """Configuration for retry mechanisms"""
    strategy: RetryStrategy = RetryStrategy.EXPONENTIAL_BACKOFF
    max_attempts: int = 3
    base_delay: float = 1.0
    max_delay: float = 60.0
    backoff_multiplier: float = 2.0
    jitter: bool = True
    timeout: float = 300.0  # 5 minutes total timeout


@dataclass
class FallbackConfig:
    """Configuration for fallback mechanisms"""
    enabled: bool = True
    max_price_adjustment: float = 0.05  # 5% price adjustment
    min_quantity_reduction: int = 1  # Minimum lots to reduce
    split_threshold: int = 100  # Split orders larger than this
    manual_intervention_threshold: int = 5  # Failures before manual intervention


@dataclass
class RetryAttempt:
    """Record of a retry attempt"""
    attempt_number: int
    timestamp: datetime
    error_message: str
    delay_used: float
    fallback_applied: Optional[FallbackAction] = None


@dataclass
class OrderRetryContext:
    """Context for order retry operations"""
    original_order: OrderRequest
    current_order: OrderRequest
    attempts: List[RetryAttempt] = field(default_factory=list)
    total_filled: int = 0
    remaining_quantity: int = 0
    start_time: datetime = field(default_factory=datetime.now)
    last_error: Optional[str] = None
    fallbacks_applied: List[FallbackAction] = field(default_factory=list)
    
    def __post_init__(self):
        self.remaining_quantity = self.original_order.quantity


class OrderRetryHandler:
    """
    Advanced retry handler for order placement with sophisticated fallback mechanisms.
    
    Features:
    - Multiple retry strategies (exponential, linear, fixed delay)
    - Intelligent fallback actions based on error types
    - Partial fill handling and completion logic
    - Order splitting for large quantities
    - Price adjustment strategies
    - Manual intervention triggers
    """
    
    def __init__(self, retry_config: RetryConfig, fallback_config: FallbackConfig):
        self.retry_config = retry_config
        self.fallback_config = fallback_config
        
        # Active retry contexts
        self.active_retries: Dict[str, OrderRetryContext] = {}
        self.lock = threading.Lock()
        
        # Statistics
        self.retry_stats = {
            'total_retries': 0,
            'successful_retries': 0,
            'failed_retries': 0,
            'fallbacks_used': 0,
            'manual_interventions': 0
        }
    
    def execute_with_retry(self, order: OrderRequest, 
                          execute_func: Callable[[OrderRequest], OrderResponse],
                          context_id: Optional[str] = None) -> OrderResponse:
        """
        Execute order with comprehensive retry and fallback mechanisms.
        
        Args:
            order: Order to execute
            execute_func: Function to execute the order
            context_id: Optional context ID for tracking
            
        Returns:
            Final order response
        """
        if not context_id:
            context_id = f"retry_{int(time.time() * 1000)}"
        
        # Create retry context
        context = OrderRetryContext(
            original_order=order,
            current_order=self._copy_order(order)
        )
        
        with self.lock:
            self.active_retries[context_id] = context
        
        try:
            return self._execute_retry_loop(context, execute_func)
        finally:
            with self.lock:
                self.active_retries.pop(context_id, None)
    
    def _execute_retry_loop(self, context: OrderRetryContext, 
                           execute_func: Callable[[OrderRequest], OrderResponse]) -> OrderResponse:
        """Execute the main retry loop"""
        start_time = time.time()
        
        for attempt in range(self.retry_config.max_attempts):
            # Check timeout
            if time.time() - start_time > self.retry_config.timeout:
                logger.error(f"Order retry timeout after {self.retry_config.timeout}s")
                return OrderResponse(
                    status=OrderStatus.REJECTED,
                    message="Retry timeout exceeded",
                    error_code="RETRY_TIMEOUT"
                )
            
            try:
                # Execute the order
                response = execute_func(context.current_order)
                
                # Handle response
                if response.is_success:
                    self.retry_stats['successful_retries'] += 1
                    logger.info(f"Order executed successfully on attempt {attempt + 1}")
                    return response
                
                elif response.status == OrderStatus.PARTIAL:
                    # Handle partial fill
                    return self._handle_partial_fill(context, response, execute_func)
                
                else:
                    # Order failed, prepare for retry
                    context.last_error = response.message
                    
                    # Record attempt
                    retry_attempt = RetryAttempt(
                        attempt_number=attempt + 1,
                        timestamp=datetime.now(),
                        error_message=response.message,
                        delay_used=0.0
                    )
                    context.attempts.append(retry_attempt)
                    
                    # Check if we should continue retrying
                    if attempt < self.retry_config.max_attempts - 1:
                        # Apply fallback strategy
                        fallback_applied = self._apply_fallback_strategy(context, response)
                        retry_attempt.fallback_applied = fallback_applied
                        
                        # Calculate and apply delay
                        delay = self._calculate_delay(attempt)
                        retry_attempt.delay_used = delay
                        
                        logger.warning(f"Order failed (attempt {attempt + 1}): {response.message}. "
                                     f"Retrying in {delay:.2f}s with fallback: {fallback_applied}")
                        
                        time.sleep(delay)
                        self.retry_stats['total_retries'] += 1
                    
            except Exception as e:
                logger.error(f"Exception during order execution (attempt {attempt + 1}): {e}")
                context.last_error = str(e)
                
                if attempt < self.retry_config.max_attempts - 1:
                    delay = self._calculate_delay(attempt)
                    time.sleep(delay)
                    self.retry_stats['total_retries'] += 1
        
        # All retries exhausted
        self.retry_stats['failed_retries'] += 1
        logger.error(f"Order failed after {self.retry_config.max_attempts} attempts")
        
        return OrderResponse(
            status=OrderStatus.REJECTED,
            message=f"Order failed after {self.retry_config.max_attempts} attempts. Last error: {context.last_error}",
            error_code="MAX_RETRIES_EXCEEDED"
        )
    
    def _handle_partial_fill(self, context: OrderRetryContext, 
                           response: OrderResponse,
                           execute_func: Callable[[OrderRequest], OrderResponse]) -> OrderResponse:
        """Handle partial fill scenarios"""
        logger.info(f"Handling partial fill for order")
        
        # This is a simplified implementation - in reality, you'd need to:
        # 1. Get the actual filled quantity from the broker
        # 2. Update the remaining quantity
        # 3. Decide whether to continue with remaining quantity or accept partial fill
        
        # For now, assume we want to complete the remaining quantity
        filled_quantity = context.current_order.quantity // 2  # Simulate 50% fill
        context.total_filled += filled_quantity
        context.remaining_quantity = context.original_order.quantity - context.total_filled
        
        if context.remaining_quantity > 0:
            # Create new order for remaining quantity
            remaining_order = self._copy_order(context.original_order)
            remaining_order.quantity = context.remaining_quantity
            context.current_order = remaining_order
            
            logger.info(f"Placing order for remaining quantity: {context.remaining_quantity}")
            
            # Recursively retry for remaining quantity
            return self._execute_retry_loop(context, execute_func)
        else:
            # Fully filled through partial fills
            return OrderResponse(
                order_id=response.order_id,
                status=OrderStatus.COMPLETE,
                message="Order completed through partial fills"
            )
    
    def _apply_fallback_strategy(self, context: OrderRetryContext, 
                               response: OrderResponse) -> Optional[FallbackAction]:
        """Apply appropriate fallback strategy based on error"""
        if not self.fallback_config.enabled:
            return None
        
        error_message = response.message.lower()
        
        # Determine appropriate fallback based on error type
        if "price" in error_message or "limit" in error_message:
            return self._apply_price_adjustment(context)
        
        elif "quantity" in error_message or "lot size" in error_message:
            return self._apply_quantity_adjustment(context)
        
        elif "market order" in error_message or "liquidity" in error_message:
            return self._convert_to_market_order(context)
        
        elif "timeout" in error_message or "network" in error_message:
            return self._apply_network_fallback(context)
        
        elif len(context.attempts) >= self.fallback_config.manual_intervention_threshold:
            return self._trigger_manual_intervention(context)
        
        return None
    
    def _apply_price_adjustment(self, context: OrderRetryContext) -> FallbackAction:
        """Adjust order price to improve execution probability"""
        if context.current_order.order_type != OrderType.LIMIT:
            return FallbackAction.CONVERT_TO_MARKET
        
        # Adjust price by small percentage
        adjustment = self.fallback_config.max_price_adjustment
        
        if context.current_order.action == OrderAction.BUY:
            # Increase buy price
            new_price = context.current_order.price * (1 + adjustment)
        else:
            # Decrease sell price
            new_price = context.current_order.price * (1 - adjustment)
        
        context.current_order.price = round(new_price, 2)
        context.fallbacks_applied.append(FallbackAction.ADJUST_PRICE)
        self.fallback_config.fallbacks_used += 1
        
        logger.info(f"Adjusted order price to ₹{new_price:.2f}")
        return FallbackAction.ADJUST_PRICE
    
    def _apply_quantity_adjustment(self, context: OrderRetryContext) -> FallbackAction:
        """Reduce order quantity"""
        reduction = max(self.fallback_config.min_quantity_reduction, 
                       context.current_order.quantity // 4)  # Reduce by 25%
        
        new_quantity = max(1, context.current_order.quantity - reduction)
        context.current_order.quantity = new_quantity
        context.fallbacks_applied.append(FallbackAction.REDUCE_QUANTITY)
        self.fallback_config.fallbacks_used += 1
        
        logger.info(f"Reduced order quantity to {new_quantity}")
        return FallbackAction.REDUCE_QUANTITY
    
    def _convert_to_market_order(self, context: OrderRetryContext) -> FallbackAction:
        """Convert limit order to market order"""
        if context.current_order.order_type == OrderType.LIMIT:
            context.current_order.order_type = OrderType.MARKET
            context.current_order.price = None
            context.fallbacks_applied.append(FallbackAction.CONVERT_TO_MARKET)
            self.fallback_config.fallbacks_used += 1
            
            logger.info("Converted limit order to market order")
            return FallbackAction.CONVERT_TO_MARKET
        
        return None
    
    def _apply_network_fallback(self, context: OrderRetryContext) -> FallbackAction:
        """Apply fallback for network-related issues"""
        # For network issues, we typically just retry with longer delay
        # This is handled by the retry mechanism itself
        return None
    
    def _trigger_manual_intervention(self, context: OrderRetryContext) -> FallbackAction:
        """Trigger manual intervention"""
        self.retry_stats['manual_interventions'] += 1
        context.fallbacks_applied.append(FallbackAction.MANUAL_INTERVENTION)
        
        logger.critical(f"Manual intervention required for order: {context.original_order.symbol}")
        
        # In a real system, this would:
        # 1. Send alert to operators
        # 2. Log to special intervention queue
        # 3. Possibly pause automated trading
        
        return FallbackAction.MANUAL_INTERVENTION
    
    def _calculate_delay(self, attempt: int) -> float:
        """Calculate delay for retry attempt"""
        if self.retry_config.strategy == RetryStrategy.EXPONENTIAL_BACKOFF:
            delay = self.retry_config.base_delay * (self.retry_config.backoff_multiplier ** attempt)
        elif self.retry_config.strategy == RetryStrategy.LINEAR_BACKOFF:
            delay = self.retry_config.base_delay * (attempt + 1)
        elif self.retry_config.strategy == RetryStrategy.FIXED_DELAY:
            delay = self.retry_config.base_delay
        else:  # IMMEDIATE
            delay = 0.0
        
        # Apply maximum delay limit
        delay = min(delay, self.retry_config.max_delay)
        
        # Add jitter to avoid thundering herd
        if self.retry_config.jitter and delay > 0:
            import random
            jitter = random.uniform(0.8, 1.2)
            delay *= jitter
        
        return delay
    
    def _copy_order(self, order: OrderRequest) -> OrderRequest:
        """Create a copy of an order request"""
        return OrderRequest(
            symbol=order.symbol,
            token=order.token,
            exchange=order.exchange,
            action=order.action,
            order_type=order.order_type,
            quantity=order.quantity,
            price=order.price,
            trigger_price=order.trigger_price,
            validity=order.validity,
            product=order.product,
            variety=order.variety,
            disclosed_quantity=order.disclosed_quantity,
            tag=order.tag,
            trade_id=order.trade_id,
            strategy_name=order.strategy_name,
            leg_index=order.leg_index,
            parent_order_id=order.parent_order_id
        )
    
    def get_retry_statistics(self) -> Dict[str, Any]:
        """Get retry handler statistics"""
        return {
            **self.retry_stats,
            'active_retries': len(self.active_retries),
            'config': {
                'retry_strategy': self.retry_config.strategy.value,
                'max_attempts': self.retry_config.max_attempts,
                'fallbacks_enabled': self.fallback_config.enabled
            }
        }
    
    def get_active_retries(self) -> Dict[str, Dict[str, Any]]:
        """Get information about active retry operations"""
        with self.lock:
            return {
                context_id: {
                    'original_symbol': context.original_order.symbol,
                    'attempts': len(context.attempts),
                    'total_filled': context.total_filled,
                    'remaining_quantity': context.remaining_quantity,
                    'elapsed_time': (datetime.now() - context.start_time).total_seconds(),
                    'last_error': context.last_error,
                    'fallbacks_applied': [fb.value for fb in context.fallbacks_applied]
                }
                for context_id, context in self.active_retries.items()
            }


class PartialFillHandler:
    """
    Specialized handler for partial fill scenarios.
    
    Manages the completion of partially filled orders with intelligent
    strategies for handling remaining quantities.
    """
    
    def __init__(self, config: Dict[str, Any]):
        self.config = config
        self.partial_fills: Dict[str, Dict[str, Any]] = {}
        self.completion_strategies = {
            'immediate': self._complete_immediately,
            'time_based': self._complete_time_based,
            'price_based': self._complete_price_based,
            'cancel_remaining': self._cancel_remaining
        }
    
    def handle_partial_fill(self, order_id: str, filled_quantity: int, 
                          remaining_quantity: int, fill_price: float) -> Dict[str, Any]:
        """
        Handle a partial fill event.
        
        Args:
            order_id: Order ID that was partially filled
            filled_quantity: Quantity that was filled
            remaining_quantity: Quantity still pending
            fill_price: Price at which fill occurred
            
        Returns:
            Dictionary with handling instructions
        """
        # Record partial fill
        self.partial_fills[order_id] = {
            'filled_quantity': filled_quantity,
            'remaining_quantity': remaining_quantity,
            'fill_price': fill_price,
            'fill_time': datetime.now(),
            'completion_attempts': 0
        }
        
        # Determine completion strategy
        strategy = self.config.get('partial_fill_strategy', 'immediate')
        completion_func = self.completion_strategies.get(strategy, self._complete_immediately)
        
        return completion_func(order_id)
    
    def _complete_immediately(self, order_id: str) -> Dict[str, Any]:
        """Immediately try to complete remaining quantity"""
        return {
            'action': 'place_remaining_order',
            'order_type': 'MARKET',  # Use market order for quick completion
            'urgency': 'high'
        }
    
    def _complete_time_based(self, order_id: str) -> Dict[str, Any]:
        """Complete based on time elapsed"""
        partial_fill = self.partial_fills[order_id]
        elapsed = (datetime.now() - partial_fill['fill_time']).total_seconds()
        
        if elapsed > self.config.get('partial_fill_timeout', 300):  # 5 minutes
            return {'action': 'cancel_remaining', 'reason': 'timeout'}
        else:
            return {'action': 'wait', 'check_after': 60}  # Check again in 1 minute
    
    def _complete_price_based(self, order_id: str) -> Dict[str, Any]:
        """Complete based on price movement"""
        # This would require current market price comparison
        return {
            'action': 'place_remaining_order',
            'order_type': 'LIMIT',
            'price_adjustment': 0.01  # Adjust price slightly
        }
    
    def _cancel_remaining(self, order_id: str) -> Dict[str, Any]:
        """Cancel remaining quantity"""
        return {
            'action': 'cancel_remaining',
            'reason': 'strategy_decision'
        }