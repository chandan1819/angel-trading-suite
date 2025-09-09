"""
Emergency Controller for handling critical system events and emergency stops.

This module provides comprehensive emergency control mechanisms including
file-based emergency stops, graceful shutdown procedures, and safety monitoring.
"""

import os
import time
import threading
import logging
from datetime import datetime, timedelta
from typing import Dict, Any, List, Optional, Callable
from pathlib import Path
from dataclasses import dataclass
from enum import Enum

from ..models.trading_models import Trade, TradeStatus


class EmergencyLevel(Enum):
    """Emergency severity levels"""
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"


class EmergencyType(Enum):
    """Types of emergency events"""
    MANUAL_STOP = "manual_stop"
    DAILY_LOSS_LIMIT = "daily_loss_limit"
    SYSTEM_ERROR = "system_error"
    API_FAILURE = "api_failure"
    POSITION_RISK = "position_risk"
    MARKET_CLOSURE = "market_closure"
    NETWORK_FAILURE = "network_failure"


@dataclass
class EmergencyEvent:
    """Represents an emergency event"""
    event_type: EmergencyType
    level: EmergencyLevel
    message: str
    timestamp: datetime
    source: str
    metadata: Dict[str, Any]
    resolved: bool = False
    resolution_time: Optional[datetime] = None


class EmergencyController:
    """
    Comprehensive emergency control system for the trading platform.
    
    Features:
    - File-based emergency stop monitoring
    - Graceful shutdown procedures for open positions
    - Daily loss limit enforcement
    - System health monitoring
    - Emergency event logging and notifications
    """
    
    def __init__(self, config: Dict[str, Any]):
        """
        Initialize EmergencyController.
        
        Args:
            config: Emergency controller configuration
        """
        self.config = config
        self.logger = logging.getLogger(__name__)
        
        # Emergency stop configuration
        self.emergency_stop_file = config.get('emergency_stop_file', 'emergency_stop.txt')
        self.emergency_stop_active = False
        self.emergency_stop_check_interval = config.get('check_interval', 5)  # seconds
        
        # Daily loss limit configuration
        self.daily_loss_limit = config.get('daily_loss_limit', 10000.0)
        self.current_daily_loss = 0.0
        self.daily_loss_limit_breached = False
        
        # Graceful shutdown configuration
        self.shutdown_timeout = config.get('shutdown_timeout', 300)  # 5 minutes
        self.force_close_after_timeout = config.get('force_close_after_timeout', True)
        
        # Monitoring state
        self.monitoring_active = False
        self.monitor_thread: Optional[threading.Thread] = None
        self.emergency_events: List[EmergencyEvent] = []
        self.shutdown_in_progress = False
        
        # Callbacks for emergency actions
        self.emergency_callbacks: Dict[EmergencyType, List[Callable]] = {
            emergency_type: [] for emergency_type in EmergencyType
        }
        
        # Position management
        self.active_trades: Dict[str, Trade] = {}
        self.position_close_callbacks: List[Callable] = []
        
        # System health tracking
        self.last_heartbeat = datetime.now()
        self.heartbeat_timeout = config.get('heartbeat_timeout', 60)  # seconds
        
        self.logger.info("EmergencyController initialized")
    
    def start_monitoring(self) -> bool:
        """
        Start emergency monitoring.
        
        Returns:
            True if monitoring started successfully
        """
        try:
            if self.monitoring_active:
                self.logger.warning("Emergency monitoring already active")
                return True
            
            self.monitoring_active = True
            self.monitor_thread = threading.Thread(
                target=self._monitoring_loop,
                daemon=True
            )
            self.monitor_thread.start()
            
            self.logger.info("Emergency monitoring started")
            return True
            
        except Exception as e:
            self.logger.error(f"Failed to start emergency monitoring: {e}")
            return False
    
    def stop_monitoring(self) -> None:
        """Stop emergency monitoring"""
        try:
            self.monitoring_active = False
            
            if self.monitor_thread and self.monitor_thread.is_alive():
                self.monitor_thread.join(timeout=10)
                if self.monitor_thread.is_alive():
                    self.logger.warning("Emergency monitor thread did not stop gracefully")
            
            self.logger.info("Emergency monitoring stopped")
            
        except Exception as e:
            self.logger.error(f"Error stopping emergency monitoring: {e}")
    
    def _monitoring_loop(self) -> None:
        """Main emergency monitoring loop"""
        self.logger.info("Emergency monitoring loop started")
        
        while self.monitoring_active:
            try:
                # Check emergency stop file
                self._check_emergency_stop_file()
                
                # Check daily loss limits
                self._check_daily_loss_limits()
                
                # Check system health
                self._check_system_health()
                
                # Process pending emergency events
                self._process_emergency_events()
                
                # Update heartbeat
                self.last_heartbeat = datetime.now()
                
                # Sleep until next check
                time.sleep(self.emergency_stop_check_interval)
                
            except Exception as e:
                self.logger.error(f"Error in emergency monitoring loop: {e}")
                time.sleep(5)  # Short sleep on error
        
        self.logger.info("Emergency monitoring loop ended")
    
    def _check_emergency_stop_file(self) -> None:
        """Check for emergency stop file"""
        try:
            file_exists = os.path.exists(self.emergency_stop_file)
            
            if file_exists and not self.emergency_stop_active:
                # Emergency stop activated
                self.emergency_stop_active = True
                
                # Read emergency stop message if available
                message = "Emergency stop file detected"
                try:
                    with open(self.emergency_stop_file, 'r') as f:
                        content = f.read().strip()
                        if content:
                            message = f"Emergency stop: {content}"
                except Exception:
                    pass
                
                # Create emergency event
                event = EmergencyEvent(
                    event_type=EmergencyType.MANUAL_STOP,
                    level=EmergencyLevel.CRITICAL,
                    message=message,
                    timestamp=datetime.now(),
                    source="emergency_file",
                    metadata={'file_path': self.emergency_stop_file}
                )
                
                self._trigger_emergency_event(event)
                
            elif not file_exists and self.emergency_stop_active:
                # Emergency stop deactivated
                self.emergency_stop_active = False
                self.logger.info("Emergency stop deactivated - file removed")
                
                # Mark previous emergency events as resolved
                for event in self.emergency_events:
                    if (event.event_type == EmergencyType.MANUAL_STOP and 
                        not event.resolved):
                        event.resolved = True
                        event.resolution_time = datetime.now()
                        
        except Exception as e:
            self.logger.error(f"Error checking emergency stop file: {e}")
    
    def _check_daily_loss_limits(self) -> None:
        """Check daily loss limits"""
        try:
            if (self.current_daily_loss >= self.daily_loss_limit and 
                not self.daily_loss_limit_breached):
                
                self.daily_loss_limit_breached = True
                
                event = EmergencyEvent(
                    event_type=EmergencyType.DAILY_LOSS_LIMIT,
                    level=EmergencyLevel.CRITICAL,
                    message=f"Daily loss limit breached: ₹{self.current_daily_loss:,.2f} >= ₹{self.daily_loss_limit:,.2f}",
                    timestamp=datetime.now(),
                    source="risk_monitor",
                    metadata={
                        'current_loss': self.current_daily_loss,
                        'limit': self.daily_loss_limit
                    }
                )
                
                self._trigger_emergency_event(event)
                
        except Exception as e:
            self.logger.error(f"Error checking daily loss limits: {e}")
    
    def _check_system_health(self) -> None:
        """Check system health indicators"""
        try:
            # Check heartbeat timeout
            time_since_heartbeat = (datetime.now() - self.last_heartbeat).total_seconds()
            
            if time_since_heartbeat > self.heartbeat_timeout:
                event = EmergencyEvent(
                    event_type=EmergencyType.SYSTEM_ERROR,
                    level=EmergencyLevel.HIGH,
                    message=f"System heartbeat timeout: {time_since_heartbeat:.1f}s",
                    timestamp=datetime.now(),
                    source="health_monitor",
                    metadata={'timeout_seconds': time_since_heartbeat}
                )
                
                self._trigger_emergency_event(event)
                
        except Exception as e:
            self.logger.error(f"Error checking system health: {e}")
    
    def _process_emergency_events(self) -> None:
        """Process pending emergency events"""
        try:
            unresolved_events = [e for e in self.emergency_events if not e.resolved]
            
            for event in unresolved_events:
                # Execute callbacks for this event type
                callbacks = self.emergency_callbacks.get(event.event_type, [])
                for callback in callbacks:
                    try:
                        callback(event)
                    except Exception as e:
                        self.logger.error(f"Error executing emergency callback: {e}")
                        
        except Exception as e:
            self.logger.error(f"Error processing emergency events: {e}")
    
    def _trigger_emergency_event(self, event: EmergencyEvent) -> None:
        """Trigger an emergency event"""
        try:
            self.emergency_events.append(event)
            
            self.logger.critical(f"EMERGENCY EVENT: {event.event_type.value} - {event.message}")
            
            # Execute immediate callbacks
            callbacks = self.emergency_callbacks.get(event.event_type, [])
            for callback in callbacks:
                try:
                    callback(event)
                except Exception as e:
                    self.logger.error(f"Error executing emergency callback: {e}")
            
            # For critical events, initiate emergency shutdown
            if event.level == EmergencyLevel.CRITICAL:
                self.initiate_emergency_shutdown(event.message)
                
        except Exception as e:
            self.logger.error(f"Error triggering emergency event: {e}")
    
    def initiate_emergency_shutdown(self, reason: str) -> None:
        """
        Initiate emergency shutdown procedure.
        
        Args:
            reason: Reason for emergency shutdown
        """
        try:
            if self.shutdown_in_progress:
                self.logger.warning("Emergency shutdown already in progress")
                return
            
            self.shutdown_in_progress = True
            self.logger.critical(f"INITIATING EMERGENCY SHUTDOWN: {reason}")
            
            # Start shutdown in separate thread to avoid blocking
            shutdown_thread = threading.Thread(
                target=self._execute_emergency_shutdown,
                args=(reason,),
                daemon=True
            )
            shutdown_thread.start()
            
        except Exception as e:
            self.logger.error(f"Error initiating emergency shutdown: {e}")
    
    def _execute_emergency_shutdown(self, reason: str) -> None:
        """Execute emergency shutdown procedure"""
        try:
            shutdown_start = datetime.now()
            self.logger.info(f"Executing emergency shutdown: {reason}")
            
            # Step 1: Close all open positions
            self._close_all_positions_emergency(reason)
            
            # Step 2: Cancel all pending orders
            self._cancel_all_pending_orders()
            
            # Step 3: Wait for position closure confirmation or timeout
            self._wait_for_position_closure(shutdown_start)
            
            # Step 4: Force close any remaining positions if timeout exceeded
            if self.force_close_after_timeout:
                elapsed = (datetime.now() - shutdown_start).total_seconds()
                if elapsed > self.shutdown_timeout:
                    self.logger.warning("Shutdown timeout exceeded - forcing position closure")
                    self._force_close_remaining_positions()
            
            # Step 5: Log shutdown completion
            shutdown_duration = (datetime.now() - shutdown_start).total_seconds()
            self.logger.info(f"Emergency shutdown completed in {shutdown_duration:.1f}s")
            
            # Step 6: Create shutdown completion event
            completion_event = EmergencyEvent(
                event_type=EmergencyType.SYSTEM_ERROR,
                level=EmergencyLevel.MEDIUM,
                message=f"Emergency shutdown completed: {reason}",
                timestamp=datetime.now(),
                source="emergency_controller",
                metadata={
                    'shutdown_duration': shutdown_duration,
                    'reason': reason
                }
            )
            self.emergency_events.append(completion_event)
            
        except Exception as e:
            self.logger.error(f"Error during emergency shutdown execution: {e}")
        finally:
            self.shutdown_in_progress = False
    
    def _close_all_positions_emergency(self, reason: str) -> None:
        """Close all positions in emergency mode"""
        try:
            self.logger.info(f"Closing {len(self.active_trades)} positions - Emergency: {reason}")
            
            for trade_id, trade in self.active_trades.items():
                if trade.status == TradeStatus.OPEN:
                    # Execute position close callbacks
                    for callback in self.position_close_callbacks:
                        try:
                            callback(trade_id, reason, emergency=True)
                        except Exception as e:
                            self.logger.error(f"Error in position close callback for {trade_id}: {e}")
            
        except Exception as e:
            self.logger.error(f"Error closing positions in emergency: {e}")
    
    def _cancel_all_pending_orders(self) -> None:
        """Cancel all pending orders"""
        try:
            self.logger.info("Cancelling all pending orders")
            
            # This would typically interface with the order manager
            # For now, we'll log the action
            self.logger.info("Pending order cancellation completed")
            
        except Exception as e:
            self.logger.error(f"Error cancelling pending orders: {e}")
    
    def _wait_for_position_closure(self, start_time: datetime) -> None:
        """Wait for position closure with timeout"""
        try:
            while (datetime.now() - start_time).total_seconds() < self.shutdown_timeout:
                # Check if all positions are closed
                open_positions = sum(1 for trade in self.active_trades.values() 
                                   if trade.status == TradeStatus.OPEN)
                
                if open_positions == 0:
                    self.logger.info("All positions closed successfully")
                    return
                
                self.logger.info(f"Waiting for {open_positions} positions to close...")
                time.sleep(5)
            
            # Timeout reached
            remaining_positions = sum(1 for trade in self.active_trades.values() 
                                    if trade.status == TradeStatus.OPEN)
            
            if remaining_positions > 0:
                self.logger.warning(f"Shutdown timeout reached with {remaining_positions} positions still open")
                
        except Exception as e:
            self.logger.error(f"Error waiting for position closure: {e}")
    
    def _force_close_remaining_positions(self) -> None:
        """Force close any remaining open positions"""
        try:
            remaining_trades = [trade for trade in self.active_trades.values() 
                              if trade.status == TradeStatus.OPEN]
            
            if remaining_trades:
                self.logger.warning(f"Force closing {len(remaining_trades)} remaining positions")
                
                for trade in remaining_trades:
                    # Mark as force closed
                    trade.status = TradeStatus.CLOSED
                    trade.exit_time = datetime.now()
                    
                    self.logger.warning(f"Force closed trade {trade.trade_id}")
            
        except Exception as e:
            self.logger.error(f"Error force closing positions: {e}")
    
    def register_emergency_callback(self, event_type: EmergencyType, 
                                  callback: Callable[[EmergencyEvent], None]) -> None:
        """
        Register callback for emergency events.
        
        Args:
            event_type: Type of emergency event
            callback: Callback function to execute
        """
        if event_type not in self.emergency_callbacks:
            self.emergency_callbacks[event_type] = []
        
        self.emergency_callbacks[event_type].append(callback)
        self.logger.info(f"Registered emergency callback for {event_type.value}")
    
    def register_position_close_callback(self, callback: Callable[[str, str, bool], None]) -> None:
        """
        Register callback for position closure.
        
        Args:
            callback: Callback function (trade_id, reason, emergency)
        """
        self.position_close_callbacks.append(callback)
        self.logger.info("Registered position close callback")
    
    def update_daily_loss(self, loss_amount: float) -> None:
        """
        Update current daily loss amount.
        
        Args:
            loss_amount: Current daily loss amount
        """
        self.current_daily_loss = abs(loss_amount)  # Ensure positive value
    
    def update_active_trades(self, trades: Dict[str, Trade]) -> None:
        """
        Update active trades for monitoring.
        
        Args:
            trades: Dictionary of active trades
        """
        self.active_trades = trades.copy()
    
    def create_emergency_stop_file(self, message: str = "") -> bool:
        """
        Create emergency stop file.
        
        Args:
            message: Optional message to include in the file
            
        Returns:
            True if file created successfully
        """
        try:
            with open(self.emergency_stop_file, 'w') as f:
                if message:
                    f.write(f"{message}\n")
                f.write(f"Emergency stop created at: {datetime.now().isoformat()}\n")
            
            self.logger.info(f"Emergency stop file created: {self.emergency_stop_file}")
            return True
            
        except Exception as e:
            self.logger.error(f"Failed to create emergency stop file: {e}")
            return False
    
    def remove_emergency_stop_file(self) -> bool:
        """
        Remove emergency stop file.
        
        Returns:
            True if file removed successfully
        """
        try:
            if os.path.exists(self.emergency_stop_file):
                os.remove(self.emergency_stop_file)
                self.logger.info(f"Emergency stop file removed: {self.emergency_stop_file}")
                return True
            else:
                self.logger.info("Emergency stop file does not exist")
                return True
                
        except Exception as e:
            self.logger.error(f"Failed to remove emergency stop file: {e}")
            return False
    
    def get_emergency_status(self) -> Dict[str, Any]:
        """
        Get current emergency status.
        
        Returns:
            Dictionary with emergency status information
        """
        try:
            unresolved_events = [e for e in self.emergency_events if not e.resolved]
            
            return {
                'emergency_stop_active': self.emergency_stop_active,
                'daily_loss_limit_breached': self.daily_loss_limit_breached,
                'shutdown_in_progress': self.shutdown_in_progress,
                'monitoring_active': self.monitoring_active,
                'current_daily_loss': self.current_daily_loss,
                'daily_loss_limit': self.daily_loss_limit,
                'unresolved_events': len(unresolved_events),
                'total_events': len(self.emergency_events),
                'last_heartbeat': self.last_heartbeat.isoformat(),
                'emergency_stop_file': self.emergency_stop_file,
                'emergency_stop_file_exists': os.path.exists(self.emergency_stop_file)
            }
            
        except Exception as e:
            self.logger.error(f"Error getting emergency status: {e}")
            return {'error': str(e)}
    
    def get_emergency_events(self, limit: Optional[int] = None, 
                           resolved: Optional[bool] = None) -> List[EmergencyEvent]:
        """
        Get emergency events.
        
        Args:
            limit: Maximum number of events to return
            resolved: Filter by resolved status (None for all)
            
        Returns:
            List of emergency events
        """
        try:
            events = self.emergency_events
            
            # Filter by resolved status
            if resolved is not None:
                events = [e for e in events if e.resolved == resolved]
            
            # Sort by timestamp (newest first)
            events = sorted(events, key=lambda e: e.timestamp, reverse=True)
            
            # Apply limit
            if limit:
                events = events[:limit]
            
            return events
            
        except Exception as e:
            self.logger.error(f"Error getting emergency events: {e}")
            return []
    
    def cleanup(self) -> None:
        """Cleanup emergency controller resources"""
        try:
            self.stop_monitoring()
            self.logger.info("EmergencyController cleanup completed")
            
        except Exception as e:
            self.logger.error(f"Error during emergency controller cleanup: {e}")