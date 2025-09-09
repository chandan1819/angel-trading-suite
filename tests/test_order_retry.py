"""
Integration tests for order retry and fallback mechanisms.

Tests cover retry strategies, fallback actions, partial fill handling,
and error recovery scenarios.
"""

import pytest
import unittest
from unittest.mock import Mock, MagicMock, patch
import time
from datetime import datetime

from src.orders.retry_handler import (
    OrderRetryHandler, PartialFillHandler, RetryConfig, FallbackConfig,
    RetryStrategy, FallbackAction, OrderRetryContext
)
from src.orders.order_models import OrderRequest, OrderResponse, OrderStatus, OrderType, OrderAction


class TestRetryHandler(unittest.TestCase):
    """Test OrderRetryHandler functionality"""
    
    def setUp(self):
        self.retry_config = RetryConfig(
            strategy=RetryStrategy.EXPONENTIAL_BACKOFF,
            max_attempts=3,
            base_delay=0.1,  # Short delay for tests
            max_delay=1.0,
            backoff_multiplier=2.0,
            jitter=False  # Disable jitter for predictable tests
        )
        
        self.fallback_config = FallbackConfig(
            enabled=True,
            max_price_adjustment=0.05,
            min_quantity_reduction=1,
            split_threshold=100,
            manual_intervention_threshold=5
        )
        
        self.retry_handler = OrderRetryHandler(self.retry_config, self.fallback_config)
        
        self.test_order = OrderRequest(
            symbol="BANKNIFTY2412545000CE",
            token="12345",
            exchange="NFO",
            action=OrderAction.BUY,
            order_type=OrderType.LIMIT,
            quantity=25,
            price=100.0
        )
    
    def test_successful_execution_first_attempt(self):
        """Test successful order execution on first attempt"""
        def mock_execute(order):
            return OrderResponse(
                order_id="SUCCESS_123",
                status=OrderStatus.COMPLETE,
                message="Order executed successfully"
            )
        
        response = self.retry_handler.execute_with_retry(self.test_order, mock_execute)
        
        self.assertTrue(response.is_success)
        self.assertEqual(response.order_id, "SUCCESS_123")
        self.assertEqual(self.retry_handler.retry_stats['successful_retries'], 1)
        self.assertEqual(self.retry_handler.retry_stats['total_retries'], 0)  # No retries needed
    
    def test_retry_with_eventual_success(self):
        """Test retry mechanism with eventual success"""
        attempt_count = 0
        
        def mock_execute(order):
            nonlocal attempt_count
            attempt_count += 1
            
            if attempt_count < 3:
                return OrderResponse(
                    status=OrderStatus.REJECTED,
                    message="Temporary network error",
                    error_code="NETWORK_ERROR"
                )
            else:
                return OrderResponse(
                    order_id="RETRY_SUCCESS",
                    status=OrderStatus.COMPLETE,
                    message="Order executed successfully"
                )
        
        response = self.retry_handler.execute_with_retry(self.test_order, mock_execute)
        
        self.assertTrue(response.is_success)
        self.assertEqual(response.order_id, "RETRY_SUCCESS")
        self.assertEqual(attempt_count, 3)
        self.assertEqual(self.retry_handler.retry_stats['successful_retries'], 1)
        self.assertEqual(self.retry_handler.retry_stats['total_retries'], 2)
    
    def test_max_retries_exceeded(self):
        """Test behavior when max retries are exceeded"""
        def mock_execute(order):
            return OrderResponse(
                status=OrderStatus.REJECTED,
                message="Persistent error",
                error_code="PERSISTENT_ERROR"
            )
        
        response = self.retry_handler.execute_with_retry(self.test_order, mock_execute)
        
        self.assertFalse(response.is_success)
        self.assertEqual(response.status, OrderStatus.REJECTED)
        self.assertIn("failed after", response.message)
        self.assertEqual(self.retry_handler.retry_stats['failed_retries'], 1)
    
    def test_price_adjustment_fallback(self):
        """Test price adjustment fallback strategy"""
        original_price = self.test_order.price
        
        def mock_execute(order):
            if order.price == original_price:
                return OrderResponse(
                    status=OrderStatus.REJECTED,
                    message="Price limit exceeded",
                    error_code="PRICE_ERROR"
                )
            else:
                # Success after price adjustment
                return OrderResponse(
                    order_id="PRICE_ADJUSTED",
                    status=OrderStatus.COMPLETE,
                    message="Order executed with adjusted price"
                )
        
        response = self.retry_handler.execute_with_retry(self.test_order, mock_execute)
        
        self.assertTrue(response.is_success)
        self.assertEqual(response.order_id, "PRICE_ADJUSTED")
    
    def test_convert_to_market_fallback(self):
        """Test conversion to market order fallback"""
        def mock_execute(order):
            if order.order_type == OrderType.LIMIT:
                return OrderResponse(
                    status=OrderStatus.REJECTED,
                    message="Market order required for liquidity",
                    error_code="LIQUIDITY_ERROR"
                )
            else:
                # Success as market order
                return OrderResponse(
                    order_id="MARKET_ORDER",
                    status=OrderStatus.COMPLETE,
                    message="Market order executed"
                )
        
        response = self.retry_handler.execute_with_retry(self.test_order, mock_execute)
        
        self.assertTrue(response.is_success)
        self.assertEqual(response.order_id, "MARKET_ORDER")
    
    def test_quantity_reduction_fallback(self):
        """Test quantity reduction fallback"""
        original_quantity = self.test_order.quantity
        
        def mock_execute(order):
            if order.quantity == original_quantity:
                return OrderResponse(
                    status=OrderStatus.REJECTED,
                    message="Quantity too large",
                    error_code="QUANTITY_ERROR"
                )
            else:
                # Success with reduced quantity
                return OrderResponse(
                    order_id="REDUCED_QTY",
                    status=OrderStatus.COMPLETE,
                    message="Order executed with reduced quantity"
                )
        
        response = self.retry_handler.execute_with_retry(self.test_order, mock_execute)
        
        self.assertTrue(response.is_success)
        self.assertEqual(response.order_id, "REDUCED_QTY")
    
    def test_delay_calculation(self):
        """Test retry delay calculation"""
        # Test exponential backoff
        delay0 = self.retry_handler._calculate_delay(0)
        delay1 = self.retry_handler._calculate_delay(1)
        delay2 = self.retry_handler._calculate_delay(2)
        
        self.assertEqual(delay0, 0.1)  # base_delay
        self.assertEqual(delay1, 0.2)  # base_delay * 2^1
        self.assertEqual(delay2, 0.4)  # base_delay * 2^2
        
        # Test max delay limit
        self.retry_handler.retry_config.base_delay = 10.0
        delay_large = self.retry_handler._calculate_delay(10)
        self.assertEqual(delay_large, self.retry_handler.retry_config.max_delay)
    
    def test_linear_backoff_strategy(self):
        """Test linear backoff strategy"""
        self.retry_handler.retry_config.strategy = RetryStrategy.LINEAR_BACKOFF
        
        delay0 = self.retry_handler._calculate_delay(0)
        delay1 = self.retry_handler._calculate_delay(1)
        delay2 = self.retry_handler._calculate_delay(2)
        
        self.assertEqual(delay0, 0.1)  # base_delay * 1
        self.assertEqual(delay1, 0.2)  # base_delay * 2
        self.assertEqual(delay2, 0.3)  # base_delay * 3
    
    def test_fixed_delay_strategy(self):
        """Test fixed delay strategy"""
        self.retry_handler.retry_config.strategy = RetryStrategy.FIXED_DELAY
        
        delay0 = self.retry_handler._calculate_delay(0)
        delay1 = self.retry_handler._calculate_delay(1)
        delay2 = self.retry_handler._calculate_delay(2)
        
        self.assertEqual(delay0, 0.1)
        self.assertEqual(delay1, 0.1)
        self.assertEqual(delay2, 0.1)
    
    def test_immediate_strategy(self):
        """Test immediate retry strategy"""
        self.retry_handler.retry_config.strategy = RetryStrategy.IMMEDIATE
        
        delay0 = self.retry_handler._calculate_delay(0)
        delay1 = self.retry_handler._calculate_delay(1)
        
        self.assertEqual(delay0, 0.0)
        self.assertEqual(delay1, 0.0)
    
    def test_retry_statistics(self):
        """Test retry statistics tracking"""
        def mock_execute_success(order):
            return OrderResponse(
                order_id="STATS_TEST",
                status=OrderStatus.COMPLETE,
                message="Success"
            )
        
        def mock_execute_failure(order):
            return OrderResponse(
                status=OrderStatus.REJECTED,
                message="Failure",
                error_code="TEST_ERROR"
            )
        
        # Execute successful order
        self.retry_handler.execute_with_retry(self.test_order, mock_execute_success)
        
        # Execute failing order
        self.retry_handler.execute_with_retry(self.test_order, mock_execute_failure)
        
        stats = self.retry_handler.get_retry_statistics()
        
        self.assertEqual(stats['successful_retries'], 1)
        self.assertEqual(stats['failed_retries'], 1)
        self.assertGreaterEqual(stats['total_retries'], 2)  # At least 2 retries for the failing order
    
    def test_order_copy(self):
        """Test order copying functionality"""
        copied_order = self.retry_handler._copy_order(self.test_order)
        
        self.assertEqual(copied_order.symbol, self.test_order.symbol)
        self.assertEqual(copied_order.quantity, self.test_order.quantity)
        self.assertEqual(copied_order.price, self.test_order.price)
        
        # Ensure it's a separate object
        copied_order.price = 200.0
        self.assertEqual(self.test_order.price, 100.0)


class TestPartialFillHandler(unittest.TestCase):
    """Test PartialFillHandler functionality"""
    
    def setUp(self):
        self.config = {
            'partial_fill_strategy': 'immediate',
            'partial_fill_timeout': 300
        }
        self.handler = PartialFillHandler(self.config)
    
    def test_immediate_completion_strategy(self):
        """Test immediate completion strategy"""
        result = self.handler.handle_partial_fill(
            order_id="PARTIAL_123",
            filled_quantity=15,
            remaining_quantity=10,
            fill_price=100.0
        )
        
        self.assertEqual(result['action'], 'place_remaining_order')
        self.assertEqual(result['order_type'], 'MARKET')
        self.assertEqual(result['urgency'], 'high')
    
    def test_time_based_completion_strategy(self):
        """Test time-based completion strategy"""
        self.handler.config['partial_fill_strategy'] = 'time_based'
        
        # Test within timeout
        result = self.handler.handle_partial_fill(
            order_id="TIME_123",
            filled_quantity=15,
            remaining_quantity=10,
            fill_price=100.0
        )
        
        self.assertEqual(result['action'], 'wait')
        self.assertEqual(result['check_after'], 60)
    
    def test_cancel_remaining_strategy(self):
        """Test cancel remaining strategy"""
        self.handler.config['partial_fill_strategy'] = 'cancel_remaining'
        
        result = self.handler.handle_partial_fill(
            order_id="CANCEL_123",
            filled_quantity=15,
            remaining_quantity=10,
            fill_price=100.0
        )
        
        self.assertEqual(result['action'], 'cancel_remaining')
        self.assertEqual(result['reason'], 'strategy_decision')
    
    def test_price_based_completion_strategy(self):
        """Test price-based completion strategy"""
        self.handler.config['partial_fill_strategy'] = 'price_based'
        
        result = self.handler.handle_partial_fill(
            order_id="PRICE_123",
            filled_quantity=15,
            remaining_quantity=10,
            fill_price=100.0
        )
        
        self.assertEqual(result['action'], 'place_remaining_order')
        self.assertEqual(result['order_type'], 'LIMIT')
        self.assertEqual(result['price_adjustment'], 0.01)


class TestRetryIntegration(unittest.TestCase):
    """Integration tests for retry mechanisms"""
    
    def setUp(self):
        self.retry_config = RetryConfig(
            strategy=RetryStrategy.EXPONENTIAL_BACKOFF,
            max_attempts=3,
            base_delay=0.01,  # Very short for tests
            max_delay=0.1,
            timeout=5.0  # Short timeout for tests
        )
        
        self.fallback_config = FallbackConfig(enabled=True)
        self.retry_handler = OrderRetryHandler(self.retry_config, self.fallback_config)
    
    def test_complex_retry_scenario(self):
        """Test complex scenario with multiple fallbacks"""
        attempt_count = 0
        
        def mock_execute(order):
            nonlocal attempt_count
            attempt_count += 1
            
            if attempt_count == 1:
                return OrderResponse(
                    status=OrderStatus.REJECTED,
                    message="Price limit exceeded",
                    error_code="PRICE_ERROR"
                )
            elif attempt_count == 2:
                return OrderResponse(
                    status=OrderStatus.REJECTED,
                    message="Quantity too large",
                    error_code="QUANTITY_ERROR"
                )
            else:
                return OrderResponse(
                    order_id="COMPLEX_SUCCESS",
                    status=OrderStatus.COMPLETE,
                    message="Order executed after fallbacks"
                )
        
        order = OrderRequest(
            symbol="BANKNIFTY2412545000CE",
            token="12345",
            exchange="NFO",
            action=OrderAction.BUY,
            order_type=OrderType.LIMIT,
            quantity=50,
            price=100.0
        )
        
        response = self.retry_handler.execute_with_retry(order, mock_execute)
        
        self.assertTrue(response.is_success)
        self.assertEqual(response.order_id, "COMPLEX_SUCCESS")
        self.assertEqual(attempt_count, 3)
    
    def test_timeout_handling(self):
        """Test timeout handling in retry mechanism"""
        def mock_execute_slow(order):
            time.sleep(0.1)  # Simulate slow operation
            return OrderResponse(
                status=OrderStatus.REJECTED,
                message="Slow rejection",
                error_code="SLOW_ERROR"
            )
        
        # Set very short timeout
        self.retry_handler.retry_config.timeout = 0.05
        
        response = self.retry_handler.execute_with_retry(self.test_order, mock_execute_slow)
        
        self.assertFalse(response.is_success)
        self.assertIn("timeout", response.message.lower())
    
    def test_exception_handling_in_retry(self):
        """Test exception handling during retry operations"""
        attempt_count = 0
        
        def mock_execute_with_exception(order):
            nonlocal attempt_count
            attempt_count += 1
            
            if attempt_count < 3:
                raise Exception("Network connection failed")
            else:
                return OrderResponse(
                    order_id="EXCEPTION_RECOVERY",
                    status=OrderStatus.COMPLETE,
                    message="Recovered from exceptions"
                )
        
        order = OrderRequest(
            symbol="BANKNIFTY2412545000CE",
            token="12345",
            exchange="NFO",
            action=OrderAction.BUY,
            order_type=OrderType.MARKET,
            quantity=25
        )
        
        response = self.retry_handler.execute_with_retry(order, mock_execute_with_exception)
        
        self.assertTrue(response.is_success)
        self.assertEqual(response.order_id, "EXCEPTION_RECOVERY")
        self.assertEqual(attempt_count, 3)


if __name__ == '__main__':
    unittest.main()