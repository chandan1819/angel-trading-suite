"""
Safety Monitor for continuous system health and safety checks.

This module provides comprehensive safety monitoring including position limits,
market hours validation, system resource monitoring, and automated safety actions.
"""

import psutil
import threading
import time
import logging
from datetime import datetime, time as dt_time
from typing import Dict, Any, List, Optional, Callable
from dataclasses import dataclass
from enum import Enum

from ..models.trading_models import Trade, TradeStatus
from .emergency_controller import EmergencyController, EmergencyEvent, EmergencyType, EmergencyLevel


class SafetyCheckType(Enum):
    """Types of safety checks"""
    POSITION_LIMITS = "position_limits"
    MARKET_HOURS = "market_hours"
    SYSTEM_RESOURCES = "system_resources"
    NETWORK_CONNECTIVITY = "network_connectivity"
    API_HEALTH = "api_health"
    RISK_THRESHOLDS = "risk_thresholds"


@dataclass
class SafetyViolation:
    """Represents a safety violation"""
    check_type: SafetyCheckType
    severity: EmergencyLevel
    message: str
    timestamp: datetime
    current_value: Any
    threshold_value: Any
    metadata: Dict[str, Any]


class SafetyMonitor:
    """
    Comprehensive safety monitoring system.
    
    Monitors various system aspects and triggers safety actions when
    violations are detected.
    """
    
    def __init__(self, config: Dict[str, Any], emergency_controller: EmergencyController):
        """
        Initialize SafetyMonitor.
        
        Args:
            config: Safety monitor configuration
            emergency_controller: Emergency controller instance
        """
        self.config = config
        self.emergency_controller = emergency_controller
        self.logger = logging.getLogger(__name__)
        
        # Monitoring configuration
        self.check_interval = config.get('check_interval', 10)  # seconds
        self.enabled_checks = config.get('enabled_checks', list(SafetyCheckType))
        
        # Position limits
        self.max_concurrent_positions = config.get('max_concurrent_positions', 5)
        self.max_position_value = config.get('max_position_value', 100000.0)
        self.max_single_position_size = config.get('max_single_position_size', 50000.0)
        
        # Market hours (IST)
        self.market_open_time = dt_time(9, 15)  # 9:15 AM
        self.market_close_time = dt_time(15, 30)  # 3:30 PM
        self.pre_market_buffer = config.get('pre_market_buffer', 15)  # minutes
        self.post_market_buffer = config.get('post_market_buffer', 15)  # minutes
        
        # System resource limits
        self.max_cpu_usage = config.get('max_cpu_usage', 80.0)  # percentage
        self.max_memory_usage = config.get('max_memory_usage', 80.0)  # percentage
        self.min_disk_space = config.get('min_disk_space', 1.0)  # GB
        
        # Network and API health
        self.api_timeout_threshold = config.get('api_timeout_threshold', 30.0)  # seconds
        self.max_consecutive_api_failures = config.get('max_consecutive_api_failures', 5)
        
        # Risk thresholds
        self.max_daily_loss_percentage = config.get('max_daily_loss_percentage', 0.8)  # 80% of limit
        self.max_drawdown_percentage = config.get('max_drawdown_percentage', 0.15)  # 15%
        
        # Monitoring state
        self.monitoring_active = False
        self.monitor_thread: Optional[threading.Thread] = None
        self.safety_violations: List[SafetyViolation] = []
        
        # Current system state
        self.active_trades: Dict[str, Trade] = {}
        self.current_daily_pnl = 0.0
        self.peak_daily_pnl = 0.0
        self.api_failure_count = 0
        self.last_api_success = datetime.now()
        
        # Safety action callbacks
        self.safety_callbacks: Dict[SafetyCheckType, List[Callable]] = {
            check_type: [] for check_type in SafetyCheckType
        }
        
        self.logger.info("SafetyMonitor initialized")
    
    def start_monitoring(self) -> bool:
        """
        Start safety monitoring.
        
        Returns:
            True if monitoring started successfully
        """
        try:
            if self.monitoring_active:
                self.logger.warning("Safety monitoring already active")
                return True
            
            self.monitoring_active = True
            self.monitor_thread = threading.Thread(
                target=self._monitoring_loop,
                daemon=True
            )
            self.monitor_thread.start()
            
            self.logger.info("Safety monitoring started")
            return True
            
        except Exception as e:
            self.logger.error(f"Failed to start safety monitoring: {e}")
            return False
    
    def stop_monitoring(self) -> None:
        """Stop safety monitoring"""
        try:
            self.monitoring_active = False
            
            if self.monitor_thread and self.monitor_thread.is_alive():
                self.monitor_thread.join(timeout=10)
                if self.monitor_thread.is_alive():
                    self.logger.warning("Safety monitor thread did not stop gracefully")
            
            self.logger.info("Safety monitoring stopped")
            
        except Exception as e:
            self.logger.error(f"Error stopping safety monitoring: {e}")
    
    def _monitoring_loop(self) -> None:
        """Main safety monitoring loop"""
        self.logger.info("Safety monitoring loop started")
        
        while self.monitoring_active:
            try:
                # Perform all enabled safety checks
                for check_type in self.enabled_checks:
                    if isinstance(check_type, str):
                        check_type = SafetyCheckType(check_type)
                    
                    self._perform_safety_check(check_type)
                
                # Process any violations
                self._process_safety_violations()
                
                # Sleep until next check
                time.sleep(self.check_interval)
                
            except Exception as e:
                self.logger.error(f"Error in safety monitoring loop: {e}")
                time.sleep(5)  # Short sleep on error
        
        self.logger.info("Safety monitoring loop ended")
    
    def _perform_safety_check(self, check_type: SafetyCheckType) -> None:
        """Perform a specific safety check"""
        try:
            if check_type == SafetyCheckType.POSITION_LIMITS:
                self._check_position_limits()
            elif check_type == SafetyCheckType.MARKET_HOURS:
                self._check_market_hours()
            elif check_type == SafetyCheckType.SYSTEM_RESOURCES:
                self._check_system_resources()
            elif check_type == SafetyCheckType.NETWORK_CONNECTIVITY:
                self._check_network_connectivity()
            elif check_type == SafetyCheckType.API_HEALTH:
                self._check_api_health()
            elif check_type == SafetyCheckType.RISK_THRESHOLDS:
                self._check_risk_thresholds()
                
        except Exception as e:
            self.logger.error(f"Error performing safety check {check_type.value}: {e}")
    
    def _check_position_limits(self) -> None:
        """Check position-related safety limits"""
        try:
            open_trades = [trade for trade in self.active_trades.values() 
                          if trade.status == TradeStatus.OPEN]
            
            # Check concurrent position limit
            if len(open_trades) > self.max_concurrent_positions:
                violation = SafetyViolation(
                    check_type=SafetyCheckType.POSITION_LIMITS,
                    severity=EmergencyLevel.HIGH,
                    message=f"Too many concurrent positions: {len(open_trades)} > {self.max_concurrent_positions}",
                    timestamp=datetime.now(),
                    current_value=len(open_trades),
                    threshold_value=self.max_concurrent_positions,
                    metadata={'open_trades': [t.trade_id for t in open_trades]}
                )
                self._record_safety_violation(violation)
            
            # Check individual position sizes
            for trade in open_trades:
                position_value = abs(trade.current_pnl) + sum(
                    leg.quantity * leg.current_price for leg in trade.legs
                )
                
                if position_value > self.max_single_position_size:
                    violation = SafetyViolation(
                        check_type=SafetyCheckType.POSITION_LIMITS,
                        severity=EmergencyLevel.MEDIUM,
                        message=f"Position size too large: {trade.trade_id} = ₹{position_value:,.2f}",
                        timestamp=datetime.now(),
                        current_value=position_value,
                        threshold_value=self.max_single_position_size,
                        metadata={'trade_id': trade.trade_id, 'strategy': trade.strategy}
                    )
                    self._record_safety_violation(violation)
            
            # Check total position value
            total_position_value = sum(
                abs(trade.current_pnl) + sum(leg.quantity * leg.current_price for leg in trade.legs)
                for trade in open_trades
            )
            
            if total_position_value > self.max_position_value:
                violation = SafetyViolation(
                    check_type=SafetyCheckType.POSITION_LIMITS,
                    severity=EmergencyLevel.HIGH,
                    message=f"Total position value too large: ₹{total_position_value:,.2f}",
                    timestamp=datetime.now(),
                    current_value=total_position_value,
                    threshold_value=self.max_position_value,
                    metadata={'total_positions': len(open_trades)}
                )
                self._record_safety_violation(violation)
                
        except Exception as e:
            self.logger.error(f"Error checking position limits: {e}")
    
    def _check_market_hours(self) -> None:
        """Check if trading is within allowed market hours"""
        try:
            now = datetime.now()
            current_time = now.time()
            
            # Check if it's a weekday (Monday=0, Sunday=6)
            if now.weekday() >= 5:  # Weekend
                violation = SafetyViolation(
                    check_type=SafetyCheckType.MARKET_HOURS,
                    severity=EmergencyLevel.MEDIUM,
                    message=f"Trading attempted on weekend: {now.strftime('%A')}",
                    timestamp=now,
                    current_value=now.weekday(),
                    threshold_value=4,  # Friday
                    metadata={'day_name': now.strftime('%A')}
                )
                self._record_safety_violation(violation)
                return
            
            # Calculate extended market hours with buffers
            extended_open = (datetime.combine(now.date(), self.market_open_time) - 
                           timedelta(minutes=self.pre_market_buffer)).time()
            extended_close = (datetime.combine(now.date(), self.market_close_time) + 
                            timedelta(minutes=self.post_market_buffer)).time()
            
            # Check if outside extended market hours
            if not (extended_open <= current_time <= extended_close):
                violation = SafetyViolation(
                    check_type=SafetyCheckType.MARKET_HOURS,
                    severity=EmergencyLevel.MEDIUM,
                    message=f"Trading outside market hours: {current_time}",
                    timestamp=now,
                    current_value=current_time.strftime('%H:%M:%S'),
                    threshold_value=f"{extended_open}-{extended_close}",
                    metadata={
                        'market_open': self.market_open_time.strftime('%H:%M'),
                        'market_close': self.market_close_time.strftime('%H:%M')
                    }
                )
                self._record_safety_violation(violation)
                
        except Exception as e:
            self.logger.error(f"Error checking market hours: {e}")
    
    def _check_system_resources(self) -> None:
        """Check system resource usage"""
        try:
            # Check CPU usage
            cpu_percent = psutil.cpu_percent(interval=1)
            if cpu_percent > self.max_cpu_usage:
                violation = SafetyViolation(
                    check_type=SafetyCheckType.SYSTEM_RESOURCES,
                    severity=EmergencyLevel.MEDIUM,
                    message=f"High CPU usage: {cpu_percent:.1f}%",
                    timestamp=datetime.now(),
                    current_value=cpu_percent,
                    threshold_value=self.max_cpu_usage,
                    metadata={'resource_type': 'cpu'}
                )
                self._record_safety_violation(violation)
            
            # Check memory usage
            memory = psutil.virtual_memory()
            memory_percent = memory.percent
            if memory_percent > self.max_memory_usage:
                violation = SafetyViolation(
                    check_type=SafetyCheckType.SYSTEM_RESOURCES,
                    severity=EmergencyLevel.MEDIUM,
                    message=f"High memory usage: {memory_percent:.1f}%",
                    timestamp=datetime.now(),
                    current_value=memory_percent,
                    threshold_value=self.max_memory_usage,
                    metadata={
                        'resource_type': 'memory',
                        'available_gb': memory.available / (1024**3)
                    }
                )
                self._record_safety_violation(violation)
            
            # Check disk space
            disk = psutil.disk_usage('/')
            free_gb = disk.free / (1024**3)
            if free_gb < self.min_disk_space:
                violation = SafetyViolation(
                    check_type=SafetyCheckType.SYSTEM_RESOURCES,
                    severity=EmergencyLevel.HIGH,
                    message=f"Low disk space: {free_gb:.1f} GB",
                    timestamp=datetime.now(),
                    current_value=free_gb,
                    threshold_value=self.min_disk_space,
                    metadata={'resource_type': 'disk'}
                )
                self._record_safety_violation(violation)
                
        except Exception as e:
            self.logger.error(f"Error checking system resources: {e}")
    
    def _check_network_connectivity(self) -> None:
        """Check network connectivity"""
        try:
            import socket
            
            # Test connectivity to a reliable host
            test_host = "8.8.8.8"  # Google DNS
            test_port = 53
            timeout = 5
            
            sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            sock.settimeout(timeout)
            
            try:
                result = sock.connect_ex((test_host, test_port))
                if result != 0:
                    violation = SafetyViolation(
                        check_type=SafetyCheckType.NETWORK_CONNECTIVITY,
                        severity=EmergencyLevel.HIGH,
                        message=f"Network connectivity test failed to {test_host}:{test_port}",
                        timestamp=datetime.now(),
                        current_value=result,
                        threshold_value=0,
                        metadata={'test_host': test_host, 'test_port': test_port}
                    )
                    self._record_safety_violation(violation)
            finally:
                sock.close()
                
        except Exception as e:
            self.logger.error(f"Error checking network connectivity: {e}")
    
    def _check_api_health(self) -> None:
        """Check API health and responsiveness"""
        try:
            # Check consecutive API failures
            if self.api_failure_count >= self.max_consecutive_api_failures:
                violation = SafetyViolation(
                    check_type=SafetyCheckType.API_HEALTH,
                    severity=EmergencyLevel.CRITICAL,
                    message=f"Too many consecutive API failures: {self.api_failure_count}",
                    timestamp=datetime.now(),
                    current_value=self.api_failure_count,
                    threshold_value=self.max_consecutive_api_failures,
                    metadata={'last_success': self.last_api_success.isoformat()}
                )
                self._record_safety_violation(violation)
            
            # Check time since last successful API call
            time_since_success = (datetime.now() - self.last_api_success).total_seconds()
            if time_since_success > self.api_timeout_threshold:
                violation = SafetyViolation(
                    check_type=SafetyCheckType.API_HEALTH,
                    severity=EmergencyLevel.HIGH,
                    message=f"No successful API calls for {time_since_success:.1f}s",
                    timestamp=datetime.now(),
                    current_value=time_since_success,
                    threshold_value=self.api_timeout_threshold,
                    metadata={'last_success': self.last_api_success.isoformat()}
                )
                self._record_safety_violation(violation)
                
        except Exception as e:
            self.logger.error(f"Error checking API health: {e}")
    
    def _check_risk_thresholds(self) -> None:
        """Check risk-related thresholds"""
        try:
            # Check daily loss percentage
            daily_loss_limit = self.emergency_controller.daily_loss_limit
            daily_loss_threshold = daily_loss_limit * self.max_daily_loss_percentage
            
            if abs(self.current_daily_pnl) > daily_loss_threshold and self.current_daily_pnl < 0:
                violation = SafetyViolation(
                    check_type=SafetyCheckType.RISK_THRESHOLDS,
                    severity=EmergencyLevel.HIGH,
                    message=f"Daily loss approaching limit: ₹{abs(self.current_daily_pnl):,.2f} / ₹{daily_loss_limit:,.2f}",
                    timestamp=datetime.now(),
                    current_value=abs(self.current_daily_pnl),
                    threshold_value=daily_loss_threshold,
                    metadata={'daily_loss_limit': daily_loss_limit}
                )
                self._record_safety_violation(violation)
            
            # Check drawdown from peak
            if self.peak_daily_pnl > 0:
                current_drawdown = (self.peak_daily_pnl - self.current_daily_pnl) / self.peak_daily_pnl
                
                if current_drawdown > self.max_drawdown_percentage:
                    violation = SafetyViolation(
                        check_type=SafetyCheckType.RISK_THRESHOLDS,
                        severity=EmergencyLevel.MEDIUM,
                        message=f"High drawdown from peak: {current_drawdown:.1%}",
                        timestamp=datetime.now(),
                        current_value=current_drawdown,
                        threshold_value=self.max_drawdown_percentage,
                        metadata={
                            'peak_pnl': self.peak_daily_pnl,
                            'current_pnl': self.current_daily_pnl
                        }
                    )
                    self._record_safety_violation(violation)
                    
        except Exception as e:
            self.logger.error(f"Error checking risk thresholds: {e}")
    
    def _record_safety_violation(self, violation: SafetyViolation) -> None:
        """Record a safety violation and trigger appropriate actions"""
        try:
            self.safety_violations.append(violation)
            
            self.logger.warning(f"SAFETY VIOLATION: {violation.check_type.value} - {violation.message}")
            
            # Execute callbacks for this violation type
            callbacks = self.safety_callbacks.get(violation.check_type, [])
            for callback in callbacks:
                try:
                    callback(violation)
                except Exception as e:
                    self.logger.error(f"Error executing safety callback: {e}")
            
            # For critical violations, trigger emergency event
            if violation.severity == EmergencyLevel.CRITICAL:
                emergency_event = EmergencyEvent(
                    event_type=EmergencyType.SYSTEM_ERROR,
                    level=violation.severity,
                    message=f"Safety violation: {violation.message}",
                    timestamp=violation.timestamp,
                    source="safety_monitor",
                    metadata=violation.metadata
                )
                
                self.emergency_controller._trigger_emergency_event(emergency_event)
                
        except Exception as e:
            self.logger.error(f"Error recording safety violation: {e}")
    
    def _process_safety_violations(self) -> None:
        """Process recent safety violations and take automated actions"""
        try:
            # Get recent violations (last 5 minutes)
            recent_time = datetime.now() - timedelta(minutes=5)
            recent_violations = [v for v in self.safety_violations 
                               if v.timestamp > recent_time]
            
            # Group violations by type
            violation_counts = {}
            for violation in recent_violations:
                violation_counts[violation.check_type] = violation_counts.get(violation.check_type, 0) + 1
            
            # Take action on repeated violations
            for check_type, count in violation_counts.items():
                if count >= 3:  # 3 violations in 5 minutes
                    self.logger.warning(f"Repeated safety violations: {check_type.value} ({count} times)")
                    
                    # Could implement automated remediation actions here
                    # For example, reducing position sizes, pausing trading, etc.
                    
        except Exception as e:
            self.logger.error(f"Error processing safety violations: {e}")
    
    def register_safety_callback(self, check_type: SafetyCheckType, 
                               callback: Callable[[SafetyViolation], None]) -> None:
        """
        Register callback for safety violations.
        
        Args:
            check_type: Type of safety check
            callback: Callback function to execute
        """
        if check_type not in self.safety_callbacks:
            self.safety_callbacks[check_type] = []
        
        self.safety_callbacks[check_type].append(callback)
        self.logger.info(f"Registered safety callback for {check_type.value}")
    
    def update_trading_state(self, trades: Dict[str, Trade], daily_pnl: float) -> None:
        """
        Update current trading state for monitoring.
        
        Args:
            trades: Dictionary of active trades
            daily_pnl: Current daily P&L
        """
        self.active_trades = trades.copy()
        self.current_daily_pnl = daily_pnl
        
        # Update peak P&L
        if daily_pnl > self.peak_daily_pnl:
            self.peak_daily_pnl = daily_pnl
    
    def record_api_success(self) -> None:
        """Record successful API call"""
        self.last_api_success = datetime.now()
        self.api_failure_count = 0
    
    def record_api_failure(self) -> None:
        """Record failed API call"""
        self.api_failure_count += 1
    
    def get_safety_status(self) -> Dict[str, Any]:
        """
        Get current safety status.
        
        Returns:
            Dictionary with safety status information
        """
        try:
            recent_violations = [v for v in self.safety_violations 
                               if v.timestamp > datetime.now() - timedelta(hours=1)]
            
            return {
                'monitoring_active': self.monitoring_active,
                'enabled_checks': [check.value for check in self.enabled_checks],
                'recent_violations': len(recent_violations),
                'total_violations': len(self.safety_violations),
                'api_failure_count': self.api_failure_count,
                'last_api_success': self.last_api_success.isoformat(),
                'current_daily_pnl': self.current_daily_pnl,
                'peak_daily_pnl': self.peak_daily_pnl,
                'active_positions': len(self.active_trades),
                'system_resources': {
                    'cpu_percent': psutil.cpu_percent(),
                    'memory_percent': psutil.virtual_memory().percent,
                    'disk_free_gb': psutil.disk_usage('/').free / (1024**3)
                }
            }
            
        except Exception as e:
            self.logger.error(f"Error getting safety status: {e}")
            return {'error': str(e)}
    
    def get_safety_violations(self, limit: Optional[int] = None, 
                            check_type: Optional[SafetyCheckType] = None) -> List[SafetyViolation]:
        """
        Get safety violations.
        
        Args:
            limit: Maximum number of violations to return
            check_type: Filter by check type
            
        Returns:
            List of safety violations
        """
        try:
            violations = self.safety_violations
            
            # Filter by check type
            if check_type:
                violations = [v for v in violations if v.check_type == check_type]
            
            # Sort by timestamp (newest first)
            violations = sorted(violations, key=lambda v: v.timestamp, reverse=True)
            
            # Apply limit
            if limit:
                violations = violations[:limit]
            
            return violations
            
        except Exception as e:
            self.logger.error(f"Error getting safety violations: {e}")
            return []
    
    def cleanup(self) -> None:
        """Cleanup safety monitor resources"""
        try:
            self.stop_monitoring()
            self.logger.info("SafetyMonitor cleanup completed")
            
        except Exception as e:
            self.logger.error(f"Error during safety monitor cleanup: {e}")