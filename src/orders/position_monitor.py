"""
Position monitoring module for real-time P&L tracking and risk management.

This module provides comprehensive position monitoring capabilities including
real-time P&L calculation, automatic target/stop-loss management, and
position-based risk controls.
"""

import logging
import threading
import time
from typing import Dict, Any, List, Optional, Callable
from datetime import datetime, timedelta
from collections import defaultdict

from ..models.trading_models import Trade, TradeLeg, TradeStatus
from .order_models import Position, OrderRequest, OrderType, OrderAction
from .order_manager import OrderManager

logger = logging.getLogger(__name__)


class PositionMonitor:
    """
    Real-time position monitoring system with automatic risk management.
    
    Features:
    - Real-time P&L calculation and tracking
    - Automatic target and stop-loss order placement
    - Position-based risk alerts
    - Trade lifecycle management
    - Performance metrics calculation
    """
    
    def __init__(self, order_manager: OrderManager, config: Dict[str, Any]):
        self.order_manager = order_manager
        self.config = config
        
        # Position tracking
        self.monitored_trades: Dict[str, Trade] = {}  # trade_id -> Trade
        self.position_cache: Dict[str, Position] = {}  # symbol -> Position
        self.last_update: Dict[str, datetime] = {}  # trade_id -> last_update_time
        
        # Risk thresholds
        self.default_target_pnl = config.get('default_target_pnl', 2000.0)
        self.default_stop_loss = config.get('default_stop_loss', -1000.0)
        self.max_daily_loss = config.get('max_daily_loss', -5000.0)
        self.position_timeout = config.get('position_timeout_hours', 6)
        
        # Monitoring configuration
        self.monitoring_interval = config.get('monitoring_interval', 30)  # seconds
        self.price_update_interval = config.get('price_update_interval', 10)  # seconds
        
        # Threading
        self.monitoring_active = False
        self.monitor_thread: Optional[threading.Thread] = None
        self.lock = threading.Lock()
        
        # Callbacks for events
        self.callbacks: Dict[str, List[Callable]] = defaultdict(list)
        
        # Performance tracking
        self.daily_pnl = 0.0
        self.total_trades = 0
        self.winning_trades = 0
        self.losing_trades = 0
        self.max_drawdown = 0.0
        self.peak_pnl = 0.0
    
    def start_monitoring(self) -> None:
        """Start position monitoring"""
        if not self.monitoring_active:
            self.monitoring_active = True
            self.monitor_thread = threading.Thread(target=self._monitoring_loop, daemon=True)
            self.monitor_thread.start()
            logger.info("Position monitoring started")
    
    def stop_monitoring(self) -> None:
        """Stop position monitoring"""
        self.monitoring_active = False
        if self.monitor_thread and self.monitor_thread.is_alive():
            self.monitor_thread.join(timeout=5)
        logger.info("Position monitoring stopped")
    
    def add_trade(self, trade: Trade) -> None:
        """
        Add a trade for monitoring.
        
        Args:
            trade: Trade object to monitor
        """
        with self.lock:
            self.monitored_trades[trade.trade_id] = trade
            self.last_update[trade.trade_id] = datetime.now()
        
        logger.info(f"Added trade {trade.trade_id} for monitoring")
        
        # Place automatic target and stop-loss orders if configured
        if self.config.get('auto_place_oco_orders', True):
            self._place_automatic_oco_orders(trade)
    
    def remove_trade(self, trade_id: str) -> None:
        """
        Remove a trade from monitoring.
        
        Args:
            trade_id: Trade ID to remove
        """
        with self.lock:
            if trade_id in self.monitored_trades:
                trade = self.monitored_trades.pop(trade_id)
                self.last_update.pop(trade_id, None)
                
                # Update performance metrics
                self._update_performance_metrics(trade)
                
                logger.info(f"Removed trade {trade_id} from monitoring")
    
    def update_trade_prices(self, trade_id: str, price_updates: Dict[str, float]) -> None:
        """
        Update current prices for a trade's legs.
        
        Args:
            trade_id: Trade ID to update
            price_updates: Dictionary of symbol -> current_price
        """
        with self.lock:
            if trade_id not in self.monitored_trades:
                return
            
            trade = self.monitored_trades[trade_id]
            
            for leg in trade.legs:
                if leg.symbol in price_updates:
                    leg.current_price = price_updates[leg.symbol]
            
            self.last_update[trade_id] = datetime.now()
        
        # Check if trade should be closed
        self._check_trade_exit_conditions(trade)
    
    def get_trade_pnl(self, trade_id: str) -> Optional[float]:
        """
        Get current P&L for a trade.
        
        Args:
            trade_id: Trade ID
            
        Returns:
            Current P&L or None if trade not found
        """
        with self.lock:
            if trade_id in self.monitored_trades:
                return self.monitored_trades[trade_id].current_pnl
        return None
    
    def get_position_summary(self) -> Dict[str, Any]:
        """
        Get summary of all monitored positions.
        
        Returns:
            Dictionary with position summary data
        """
        with self.lock:
            total_pnl = 0.0
            open_trades = 0
            positions_by_strategy = defaultdict(list)
            
            for trade in self.monitored_trades.values():
                if trade.status == TradeStatus.OPEN:
                    total_pnl += trade.current_pnl
                    open_trades += 1
                    positions_by_strategy[trade.strategy].append({
                        'trade_id': trade.trade_id,
                        'pnl': trade.current_pnl,
                        'target': trade.target_pnl,
                        'stop_loss': trade.stop_loss
                    })
            
            return {
                'total_unrealized_pnl': total_pnl,
                'daily_pnl': self.daily_pnl,
                'open_trades': open_trades,
                'total_trades': self.total_trades,
                'winning_trades': self.winning_trades,
                'losing_trades': self.losing_trades,
                'win_rate': self.winning_trades / max(self.total_trades, 1),
                'max_drawdown': self.max_drawdown,
                'peak_pnl': self.peak_pnl,
                'positions_by_strategy': dict(positions_by_strategy)
            }
    
    def check_risk_limits(self) -> List[str]:
        """
        Check if any risk limits are breached.
        
        Returns:
            List of risk alerts
        """
        alerts = []
        
        # Check daily loss limit
        if self.daily_pnl <= self.max_daily_loss:
            alerts.append(f"DAILY_LOSS_LIMIT_BREACHED: {self.daily_pnl:.2f}")
        
        # Check individual trade limits
        with self.lock:
            for trade in self.monitored_trades.values():
                if trade.status != TradeStatus.OPEN:
                    continue
                
                # Check if trade has been open too long
                time_open = datetime.now() - trade.entry_time
                if time_open > timedelta(hours=self.position_timeout):
                    alerts.append(f"POSITION_TIMEOUT: {trade.trade_id}")
                
                # Check if stop loss should be triggered
                if trade.current_pnl <= trade.stop_loss:
                    alerts.append(f"STOP_LOSS_TRIGGERED: {trade.trade_id}")
                
                # Check if target should be triggered
                if trade.current_pnl >= trade.target_pnl:
                    alerts.append(f"TARGET_HIT: {trade.trade_id}")
        
        return alerts
    
    def close_trade(self, trade_id: str, reason: str = "MANUAL") -> bool:
        """
        Close a trade by placing exit orders for all legs.
        
        Args:
            trade_id: Trade ID to close
            reason: Reason for closing
            
        Returns:
            True if close orders placed successfully
        """
        with self.lock:
            if trade_id not in self.monitored_trades:
                logger.warning(f"Trade {trade_id} not found for closing")
                return False
            
            trade = self.monitored_trades[trade_id]
            
            if trade.status != TradeStatus.OPEN:
                logger.warning(f"Trade {trade_id} is not open, cannot close")
                return False
        
        try:
            success = True
            
            for leg in trade.legs:
                # Create exit order (opposite action)
                exit_action = OrderAction.SELL if leg.action.value == "BUY" else OrderAction.BUY
                
                exit_order = OrderRequest(
                    symbol=leg.symbol,
                    token=leg.token,
                    exchange="NFO",  # Assuming options exchange
                    action=exit_action,
                    order_type=OrderType.MARKET,
                    quantity=leg.quantity,
                    product="MIS",
                    trade_id=trade_id,
                    strategy_name=trade.strategy,
                    tag=f"EXIT_{reason}"
                )
                
                response = self.order_manager.place_order(exit_order)
                if not response.is_success:
                    logger.error(f"Failed to place exit order for {leg.symbol}: {response.message}")
                    success = False
                else:
                    logger.info(f"Exit order placed for {leg.symbol}: {response.order_id}")
            
            if success:
                trade.status = TradeStatus.CLOSED
                trade.exit_time = datetime.now()
                
                # Trigger callbacks
                self._trigger_callbacks('trade_closed', {
                    'trade_id': trade_id,
                    'reason': reason,
                    'final_pnl': trade.current_pnl
                })
                
                logger.info(f"Trade {trade_id} closed successfully. Reason: {reason}")
            
            return success
            
        except Exception as e:
            logger.error(f"Error closing trade {trade_id}: {e}")
            return False
    
    def add_callback(self, event_type: str, callback: Callable) -> None:
        """
        Add callback for position monitoring events.
        
        Args:
            event_type: Type of event ('trade_closed', 'target_hit', 'stop_loss', etc.)
            callback: Callback function to execute
        """
        self.callbacks[event_type].append(callback)
    
    def _monitoring_loop(self) -> None:
        """Main monitoring loop"""
        logger.info("Position monitoring loop started")
        
        last_price_update = datetime.now()
        
        while self.monitoring_active:
            try:
                current_time = datetime.now()
                
                # Update prices periodically
                if (current_time - last_price_update).total_seconds() >= self.price_update_interval:
                    self._update_all_prices()
                    last_price_update = current_time
                
                # Check exit conditions for all trades
                self._check_all_exit_conditions()
                
                # Check risk limits
                risk_alerts = self.check_risk_limits()
                for alert in risk_alerts:
                    self._handle_risk_alert(alert)
                
                # Sleep for monitoring interval
                time.sleep(self.monitoring_interval)
                
            except Exception as e:
                logger.error(f"Error in position monitoring loop: {e}")
                time.sleep(5)  # Short sleep on error
        
        logger.info("Position monitoring loop stopped")
    
    def _update_all_prices(self) -> None:
        """Update current prices for all monitored positions"""
        try:
            # Get current positions from order manager
            current_positions = self.order_manager.get_positions()
            position_map = {f"{pos.symbol}_{pos.exchange}": pos for pos in current_positions}
            
            with self.lock:
                for trade in self.monitored_trades.values():
                    if trade.status != TradeStatus.OPEN:
                        continue
                    
                    for leg in trade.legs:
                        position_key = f"{leg.symbol}_NFO"  # Assuming NFO exchange
                        position = position_map.get(position_key)
                        
                        if position and position.ltp > 0:
                            leg.current_price = position.ltp
                    
                    self.last_update[trade.trade_id] = datetime.now()
                    
        except Exception as e:
            logger.error(f"Error updating prices: {e}")
    
    def _check_all_exit_conditions(self) -> None:
        """Check exit conditions for all monitored trades"""
        with self.lock:
            trades_to_check = list(self.monitored_trades.values())
        
        for trade in trades_to_check:
            if trade.status == TradeStatus.OPEN:
                self._check_trade_exit_conditions(trade)
    
    def _check_trade_exit_conditions(self, trade: Trade) -> None:
        """Check if a trade should be closed based on exit conditions"""
        try:
            current_pnl = trade.current_pnl
            
            # Check target hit
            if current_pnl >= trade.target_pnl:
                logger.info(f"Target hit for trade {trade.trade_id}: ₹{current_pnl:.2f}")
                self._trigger_callbacks('target_hit', {'trade_id': trade.trade_id, 'pnl': current_pnl})
                
                if self.config.get('auto_close_on_target', True):
                    self.close_trade(trade.trade_id, "TARGET_HIT")
            
            # Check stop loss hit
            elif current_pnl <= trade.stop_loss:
                logger.info(f"Stop loss hit for trade {trade.trade_id}: ₹{current_pnl:.2f}")
                self._trigger_callbacks('stop_loss', {'trade_id': trade.trade_id, 'pnl': current_pnl})
                
                if self.config.get('auto_close_on_stop', True):
                    self.close_trade(trade.trade_id, "STOP_LOSS")
            
            # Check time-based exit
            time_open = datetime.now() - trade.entry_time
            max_time = timedelta(hours=self.position_timeout)
            
            if time_open > max_time:
                logger.info(f"Time-based exit for trade {trade.trade_id} after {time_open}")
                self._trigger_callbacks('time_exit', {'trade_id': trade.trade_id, 'time_open': time_open})
                
                if self.config.get('auto_close_on_timeout', True):
                    self.close_trade(trade.trade_id, "TIME_EXIT")
                    
        except Exception as e:
            logger.error(f"Error checking exit conditions for trade {trade.trade_id}: {e}")
    
    def _place_automatic_oco_orders(self, trade: Trade) -> None:
        """Place automatic OCO orders for a new trade"""
        try:
            # Get positions for this trade
            positions = self.order_manager.get_positions()
            
            for position in positions:
                if position.trade_id == trade.trade_id:
                    # Calculate target and stop prices based on position
                    if position.quantity > 0:  # Long position
                        target_price = position.average_price + (trade.target_pnl / abs(position.quantity))
                        stop_price = position.average_price + (trade.stop_loss / abs(position.quantity))
                    else:  # Short position
                        target_price = position.average_price - (trade.target_pnl / abs(position.quantity))
                        stop_price = position.average_price - (trade.stop_loss / abs(position.quantity))
                    
                    # Place OCO orders
                    success = self.order_manager.place_oco_orders(position, target_price, stop_price)
                    
                    if success:
                        logger.info(f"OCO orders placed for position {position.symbol}")
                    else:
                        logger.warning(f"Failed to place OCO orders for position {position.symbol}")
                        
        except Exception as e:
            logger.error(f"Error placing automatic OCO orders for trade {trade.trade_id}: {e}")
    
    def _handle_risk_alert(self, alert: str) -> None:
        """Handle risk alerts"""
        logger.warning(f"Risk alert: {alert}")
        
        # Trigger callbacks
        self._trigger_callbacks('risk_alert', {'alert': alert})
        
        # Handle specific alerts
        if alert.startswith("DAILY_LOSS_LIMIT_BREACHED"):
            self._handle_daily_loss_limit()
        elif alert.startswith("STOP_LOSS_TRIGGERED"):
            trade_id = alert.split(": ")[1]
            self.close_trade(trade_id, "STOP_LOSS_ALERT")
        elif alert.startswith("TARGET_HIT"):
            trade_id = alert.split(": ")[1]
            self.close_trade(trade_id, "TARGET_ALERT")
        elif alert.startswith("POSITION_TIMEOUT"):
            trade_id = alert.split(": ")[1]
            self.close_trade(trade_id, "TIMEOUT_ALERT")
    
    def _handle_daily_loss_limit(self) -> None:
        """Handle daily loss limit breach"""
        logger.critical("Daily loss limit breached - closing all positions")
        
        with self.lock:
            open_trades = [trade.trade_id for trade in self.monitored_trades.values() 
                          if trade.status == TradeStatus.OPEN]
        
        for trade_id in open_trades:
            self.close_trade(trade_id, "DAILY_LOSS_LIMIT")
    
    def _update_performance_metrics(self, trade: Trade) -> None:
        """Update performance metrics when a trade is closed"""
        if trade.status == TradeStatus.CLOSED:
            final_pnl = trade.current_pnl
            
            self.total_trades += 1
            self.daily_pnl += final_pnl
            
            if final_pnl > 0:
                self.winning_trades += 1
            else:
                self.losing_trades += 1
            
            # Update peak and drawdown
            if self.daily_pnl > self.peak_pnl:
                self.peak_pnl = self.daily_pnl
            
            drawdown = self.peak_pnl - self.daily_pnl
            if drawdown > self.max_drawdown:
                self.max_drawdown = drawdown
    
    def _trigger_callbacks(self, event_type: str, data: Dict[str, Any]) -> None:
        """Trigger callbacks for an event"""
        for callback in self.callbacks.get(event_type, []):
            try:
                callback(data)
            except Exception as e:
                logger.error(f"Error in callback for {event_type}: {e}")
    
    def reset_daily_metrics(self) -> None:
        """Reset daily performance metrics"""
        self.daily_pnl = 0.0
        self.total_trades = 0
        self.winning_trades = 0
        self.losing_trades = 0
        self.max_drawdown = 0.0
        self.peak_pnl = 0.0
        logger.info("Daily metrics reset")
    
    def get_performance_report(self) -> Dict[str, Any]:
        """Get comprehensive performance report"""
        summary = self.get_position_summary()
        
        return {
            **summary,
            'monitoring_active': self.monitoring_active,
            'monitored_trades_count': len(self.monitored_trades),
            'last_update_times': {trade_id: update_time.isoformat() 
                                for trade_id, update_time in self.last_update.items()},
            'config': {
                'default_target_pnl': self.default_target_pnl,
                'default_stop_loss': self.default_stop_loss,
                'max_daily_loss': self.max_daily_loss,
                'position_timeout_hours': self.position_timeout
            }
        }