"""
Position Monitor for real-time risk monitoring and automatic position closure.

This module provides real-time monitoring of positions with P&L tracking,
automatic target/stop-loss enforcement, and emergency stop mechanisms.
"""

import threading
import time
from datetime import datetime, timedelta
from typing import List, Dict, Optional, Callable, Any
from dataclasses import dataclass

from ..interfaces.base_interfaces import BaseComponent
from ..models.trading_models import Trade, TradeStatus
from ..models.config_models import TradingConfig
from .risk_models import RiskAlert, RiskAlertType, RiskLevel, PositionRisk


@dataclass
class MonitoringConfig:
    """Configuration for position monitoring"""
    check_interval: int = 30  # seconds
    price_update_interval: int = 10  # seconds
    emergency_check_interval: int = 5  # seconds
    max_monitoring_threads: int = 5
    position_timeout: int = 3600  # seconds (1 hour)


class PositionMonitor(BaseComponent):
    """
    Real-time position monitoring with automatic risk management.
    
    Monitors positions continuously and triggers alerts/actions when
    risk thresholds are breached.
    """
    
    def __init__(self, config: TradingConfig):
        super().__init__(config)
        self.monitoring_config = MonitoringConfig()
        self.active_positions: Dict[str, Trade] = {}
        self.position_risks: Dict[str, PositionRisk] = {}
        self.monitoring_active = False
        self.monitor_thread: Optional[threading.Thread] = None
        self.alert_callbacks: List[Callable[[RiskAlert], None]] = []
        self.position_close_callbacks: List[Callable[[Trade, str], None]] = []
        self._stop_event = threading.Event()
        
    def initialize(self) -> bool:
        """Initialize the position monitor"""
        try:
            self._initialized = True
            if self.logger:
                self.logger.log_info("PositionMonitor initialized successfully")
            return True
            
        except Exception as e:
            if self.logger:
                self.logger.log_error(e, "PositionMonitor initialization failed")
            return False
    
    def cleanup(self) -> None:
        """Cleanup position monitor resources"""
        self.stop_monitoring()
        self.active_positions.clear()
        self.position_risks.clear()
        self.alert_callbacks.clear()
        self.position_close_callbacks.clear()
        self._initialized = False
    
    def start_monitoring(self) -> bool:
        """
        Start real-time position monitoring.
        
        Returns:
            True if monitoring started successfully
        """
        try:
            if self.monitoring_active:
                if self.logger:
                    self.logger.log_info("Position monitoring already active")
                return True
            
            self.monitoring_active = True
            self._stop_event.clear()
            
            # Start monitoring thread
            self.monitor_thread = threading.Thread(
                target=self._monitoring_loop,
                name="PositionMonitor",
                daemon=True
            )
            self.monitor_thread.start()
            
            if self.logger:
                self.logger.log_info("Position monitoring started")
            return True
            
        except Exception as e:
            if self.logger:
                self.logger.log_error(e, "Failed to start position monitoring")
            self.monitoring_active = False
            return False
    
    def stop_monitoring(self) -> None:
        """Stop position monitoring"""
        try:
            if not self.monitoring_active:
                return
            
            self.monitoring_active = False
            self._stop_event.set()
            
            # Wait for monitoring thread to finish
            if self.monitor_thread and self.monitor_thread.is_alive():
                self.monitor_thread.join(timeout=5.0)
            
            if self.logger:
                self.logger.log_info("Position monitoring stopped")
                
        except Exception as e:
            if self.logger:
                self.logger.log_error(e, "Error stopping position monitoring")
    
    def add_position(self, trade: Trade) -> None:
        """
        Add a position to monitoring.
        
        Args:
            trade: Trade to monitor
        """
        try:
            self.active_positions[trade.trade_id] = trade
            
            # Create position risk tracking
            self.position_risks[trade.trade_id] = self._create_position_risk(trade)
            
            if self.logger:
                self.logger.log_info(f"Added position {trade.trade_id} to monitoring", {
                    'strategy': trade.strategy,
                    'target_pnl': trade.target_pnl,
                    'stop_loss': trade.stop_loss
                })
                
        except Exception as e:
            if self.logger:
                self.logger.log_error(e, f"Error adding position {trade.trade_id} to monitoring")
    
    def remove_position(self, trade_id: str) -> None:
        """
        Remove a position from monitoring.
        
        Args:
            trade_id: ID of trade to remove
        """
        try:
            if trade_id in self.active_positions:
                del self.active_positions[trade_id]
            
            if trade_id in self.position_risks:
                del self.position_risks[trade_id]
            
            if self.logger:
                self.logger.log_info(f"Removed position {trade_id} from monitoring")
                
        except Exception as e:
            if self.logger:
                self.logger.log_error(e, f"Error removing position {trade_id} from monitoring")
    
    def update_position(self, trade: Trade) -> None:
        """
        Update position data for monitoring.
        
        Args:
            trade: Updated trade data
        """
        try:
            if trade.trade_id in self.active_positions:
                self.active_positions[trade.trade_id] = trade
                self.position_risks[trade.trade_id] = self._create_position_risk(trade)
                
        except Exception as e:
            if self.logger:
                self.logger.log_error(e, f"Error updating position {trade.trade_id}")
    
    def get_position_risk(self, trade_id: str) -> Optional[PositionRisk]:
        """
        Get risk metrics for a specific position.
        
        Args:
            trade_id: ID of trade
            
        Returns:
            PositionRisk object or None if not found
        """
        return self.position_risks.get(trade_id)
    
    def get_all_position_risks(self) -> Dict[str, PositionRisk]:
        """Get risk metrics for all monitored positions"""
        return self.position_risks.copy()
    
    def add_alert_callback(self, callback: Callable[[RiskAlert], None]) -> None:
        """
        Add callback function for risk alerts.
        
        Args:
            callback: Function to call when alerts are generated
        """
        self.alert_callbacks.append(callback)
    
    def add_position_close_callback(self, callback: Callable[[Trade, str], None]) -> None:
        """
        Add callback function for position closures.
        
        Args:
            callback: Function to call when positions should be closed
        """
        self.position_close_callbacks.append(callback)
    
    def force_close_all_positions(self, reason: str = "Emergency stop") -> List[str]:
        """
        Force close all monitored positions.
        
        Args:
            reason: Reason for closing positions
            
        Returns:
            List of trade IDs that were closed
        """
        closed_positions = []
        
        try:
            for trade_id, trade in self.active_positions.items():
                if trade.status == TradeStatus.OPEN:
                    # Trigger position close callbacks
                    for callback in self.position_close_callbacks:
                        try:
                            callback(trade, reason)
                            closed_positions.append(trade_id)
                        except Exception as e:
                            if self.logger:
                                self.logger.log_error(e, f"Error in position close callback for {trade_id}")
            
            if self.logger:
                self.logger.log_info(f"Force closed {len(closed_positions)} positions", {
                    'reason': reason,
                    'positions': closed_positions
                })
            
            return closed_positions
            
        except Exception as e:
            if self.logger:
                self.logger.log_error(e, "Error force closing positions")
            return closed_positions
    
    def get_monitoring_status(self) -> Dict[str, Any]:
        """Get current monitoring status"""
        return {
            'monitoring_active': self.monitoring_active,
            'active_positions_count': len(self.active_positions),
            'monitored_positions': list(self.active_positions.keys()),
            'check_interval': self.monitoring_config.check_interval,
            'last_check': datetime.now().isoformat()
        }
    
    # Private methods
    
    def _monitoring_loop(self) -> None:
        """Main monitoring loop running in separate thread"""
        try:
            if self.logger:
                self.logger.log_info("Position monitoring loop started")
            
            while self.monitoring_active and not self._stop_event.is_set():
                try:
                    # Check all positions
                    self._check_all_positions()
                    
                    # Wait for next check interval
                    if self._stop_event.wait(self.monitoring_config.check_interval):
                        break  # Stop event was set
                        
                except Exception as e:
                    if self.logger:
                        self.logger.log_error(e, "Error in monitoring loop iteration")
                    
                    # Wait a bit before retrying
                    if self._stop_event.wait(5):
                        break
            
            if self.logger:
                self.logger.log_info("Position monitoring loop ended")
                
        except Exception as e:
            if self.logger:
                self.logger.log_error(e, "Critical error in monitoring loop")
            self.monitoring_active = False
    
    def _check_all_positions(self) -> None:
        """Check all monitored positions for risk conditions"""
        try:
            current_time = datetime.now()
            positions_to_remove = []
            
            for trade_id, trade in self.active_positions.items():
                try:
                    # Skip closed positions
                    if trade.status != TradeStatus.OPEN:
                        positions_to_remove.append(trade_id)
                        continue
                    
                    # Check position timeout
                    if self._is_position_timed_out(trade, current_time):
                        self._trigger_alert(RiskAlert(
                            alert_type=RiskAlertType.POSITION_SIZE_VIOLATION,
                            level=RiskLevel.MEDIUM,
                            message=f"Position {trade_id} has been open for too long",
                            trade_id=trade_id
                        ))
                    
                    # Check profit target
                    if trade.is_target_hit:
                        self._trigger_alert(RiskAlert(
                            alert_type=RiskAlertType.PROFIT_TARGET_HIT,
                            level=RiskLevel.HIGH,
                            message=f"Profit target hit for position {trade_id}",
                            trade_id=trade_id,
                            current_value=trade.current_pnl,
                            threshold_value=trade.target_pnl
                        ))
                        
                        # Trigger position close
                        self._trigger_position_close(trade, "Profit target hit")
                    
                    # Check stop loss
                    elif trade.is_stop_loss_hit:
                        self._trigger_alert(RiskAlert(
                            alert_type=RiskAlertType.STOP_LOSS_HIT,
                            level=RiskLevel.CRITICAL,
                            message=f"Stop loss hit for position {trade_id}",
                            trade_id=trade_id,
                            current_value=trade.current_pnl,
                            threshold_value=trade.stop_loss
                        ))
                        
                        # Trigger position close
                        self._trigger_position_close(trade, "Stop loss hit")
                    
                    # Update position risk metrics
                    self.position_risks[trade_id] = self._create_position_risk(trade)
                    
                except Exception as e:
                    if self.logger:
                        self.logger.log_error(e, f"Error checking position {trade_id}")
            
            # Remove closed positions from monitoring
            for trade_id in positions_to_remove:
                self.remove_position(trade_id)
                
        except Exception as e:
            if self.logger:
                self.logger.log_error(e, "Error checking all positions")
    
    def _create_position_risk(self, trade: Trade) -> PositionRisk:
        """Create position risk metrics for a trade"""
        try:
            # Calculate Greeks exposure (simplified)
            total_delta = sum(self._estimate_delta(leg) for leg in trade.legs)
            total_theta = sum(self._estimate_theta(leg) for leg in trade.legs)
            total_vega = sum(self._estimate_vega(leg) for leg in trade.legs)
            total_gamma = sum(self._estimate_gamma(leg) for leg in trade.legs)
            
            # Calculate days to expiry (simplified)
            days_to_expiry = self._calculate_days_to_expiry(trade)
            
            # Calculate position size
            position_size = sum(leg.quantity for leg in trade.legs)
            
            # Estimate margin used (simplified)
            margin_used = position_size * 50000  # Rough estimate
            
            return PositionRisk(
                trade_id=trade.trade_id,
                current_pnl=trade.current_pnl,
                max_profit=max(trade.current_pnl, trade.target_pnl),
                max_loss=min(trade.current_pnl, trade.stop_loss),
                profit_target=trade.target_pnl,
                stop_loss=trade.stop_loss,
                time_decay_risk=abs(total_theta),
                volatility_risk=abs(total_vega),
                delta_exposure=total_delta,
                gamma_exposure=total_gamma,
                days_to_expiry=days_to_expiry,
                position_size=position_size,
                margin_used=margin_used
            )
            
        except Exception as e:
            if self.logger:
                self.logger.log_error(e, f"Error creating position risk for {trade.trade_id}")
            
            # Return default risk object
            return PositionRisk(
                trade_id=trade.trade_id,
                current_pnl=trade.current_pnl,
                max_profit=trade.target_pnl,
                max_loss=trade.stop_loss,
                profit_target=trade.target_pnl,
                stop_loss=trade.stop_loss,
                time_decay_risk=0.0,
                volatility_risk=0.0,
                delta_exposure=0.0,
                gamma_exposure=0.0,
                days_to_expiry=1,
                position_size=1,
                margin_used=50000.0
            )
    
    def _is_position_timed_out(self, trade: Trade, current_time: datetime) -> bool:
        """Check if position has been open too long"""
        try:
            time_diff = current_time - trade.entry_time
            return time_diff.total_seconds() > self.monitoring_config.position_timeout
        except:
            return False
    
    def _trigger_alert(self, alert: RiskAlert) -> None:
        """Trigger alert callbacks"""
        try:
            for callback in self.alert_callbacks:
                try:
                    callback(alert)
                except Exception as e:
                    if self.logger:
                        self.logger.log_error(e, "Error in alert callback")
        except Exception as e:
            if self.logger:
                self.logger.log_error(e, "Error triggering alerts")
    
    def _trigger_position_close(self, trade: Trade, reason: str) -> None:
        """Trigger position close callbacks"""
        try:
            for callback in self.position_close_callbacks:
                try:
                    callback(trade, reason)
                except Exception as e:
                    if self.logger:
                        self.logger.log_error(e, f"Error in position close callback for {trade.trade_id}")
        except Exception as e:
            if self.logger:
                self.logger.log_error(e, f"Error triggering position close for {trade.trade_id}")
    
    def _estimate_delta(self, leg) -> float:
        """Estimate delta for a trade leg (simplified)"""
        # In real implementation, would use actual option Greeks
        if leg.option_type.value == 'CE':
            return 0.5 if leg.action.value == 'BUY' else -0.5
        else:  # PE
            return -0.5 if leg.action.value == 'BUY' else 0.5
    
    def _estimate_theta(self, leg) -> float:
        """Estimate theta for a trade leg (simplified)"""
        # In real implementation, would use actual option Greeks
        return -10.0 if leg.action.value == 'SELL' else 10.0
    
    def _estimate_vega(self, leg) -> float:
        """Estimate vega for a trade leg (simplified)"""
        # In real implementation, would use actual option Greeks
        return 15.0 if leg.action.value == 'BUY' else -15.0
    
    def _estimate_gamma(self, leg) -> float:
        """Estimate gamma for a trade leg (simplified)"""
        # In real implementation, would use actual option Greeks
        return 0.01 if leg.action.value == 'BUY' else -0.01
    
    def _calculate_days_to_expiry(self, trade: Trade) -> int:
        """Calculate days to expiry for trade (simplified)"""
        # In real implementation, would parse expiry from option symbols
        # For now, assume weekly expiry (max 7 days)
        return 3  # Default to 3 days