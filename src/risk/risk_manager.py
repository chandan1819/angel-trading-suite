"""
Risk Manager implementation for the Bank Nifty Options Trading System.

This module provides comprehensive risk management including position sizing,
margin validation, daily limits enforcement, and real-time risk monitoring.
"""

import os
import math
from datetime import datetime, date
from typing import List, Dict, Optional, Any
from dataclasses import dataclass

from ..interfaces.base_interfaces import IRiskManager, BaseComponent
from ..models.trading_models import TradingSignal, Trade, TradeLeg, OptionType, OrderAction
from ..models.config_models import TradingConfig, RiskConfig
from ..constants import BANKNIFTY_LOT_SIZE, validate_quantity, round_to_lot_size
from .risk_models import (
    RiskAlert, RiskAlertType, RiskLevel, ValidationResult, 
    PositionSizeResult, MarginRequirement, DailyRiskMetrics, PositionRisk
)


class RiskManager(BaseComponent, IRiskManager):
    """
    Comprehensive risk management system for options trading.
    
    Handles position sizing, margin validation, daily limits, and real-time monitoring.
    """
    
    def __init__(self, config: TradingConfig):
        super().__init__(config)
        self.risk_config = config.risk
        self.daily_metrics: Dict[str, DailyRiskMetrics] = {}
        self.active_trades: Dict[str, Trade] = {}
        self.emergency_stop_active = False
        
    def initialize(self) -> bool:
        """Initialize the risk manager"""
        try:
            # Initialize daily metrics for today
            today = date.today().isoformat()
            if today not in self.daily_metrics:
                self.daily_metrics[today] = DailyRiskMetrics(
                    date=today,
                    total_pnl=0.0,
                    realized_pnl=0.0,
                    unrealized_pnl=0.0,
                    max_drawdown=0.0,
                    trades_count=0,
                    winning_trades=0,
                    losing_trades=0,
                    largest_win=0.0,
                    largest_loss=0.0,
                    daily_loss_limit=self.risk_config.max_daily_loss,
                    remaining_loss_capacity=self.risk_config.max_daily_loss,
                    risk_utilization=0.0
                )
            
            self._initialized = True
            if self.logger:
                self.logger.log_info("RiskManager initialized successfully")
            return True
            
        except Exception as e:
            if self.logger:
                self.logger.log_error(e, "RiskManager initialization failed")
            return False
    
    def cleanup(self) -> None:
        """Cleanup risk manager resources"""
        self.active_trades.clear()
        self._initialized = False
    
    def validate_trade(self, signal: TradingSignal) -> ValidationResult:
        """
        Validate if a trade can be placed based on all risk rules.
        
        Args:
            signal: Trading signal to validate
            
        Returns:
            ValidationResult with validation status and any alerts
        """
        result = ValidationResult(is_valid=True, message="Trade validation passed")
        
        try:
            # Check emergency stop
            if self._check_emergency_stop():
                alert = RiskAlert(
                    alert_type=RiskAlertType.EMERGENCY_STOP,
                    level=RiskLevel.CRITICAL,
                    message="Emergency stop is active - no new trades allowed"
                )
                result.add_alert(alert)
                result.message = "Emergency stop active"
                return result
            
            # Check daily limits
            if not self.check_daily_limits():
                alert = RiskAlert(
                    alert_type=RiskAlertType.DAILY_LOSS_LIMIT,
                    level=RiskLevel.CRITICAL,
                    message="Daily loss limit exceeded"
                )
                result.add_alert(alert)
                result.message = "Daily loss limit exceeded"
                return result
            
            # Check position limits
            if not self._check_position_limits():
                alert = RiskAlert(
                    alert_type=RiskAlertType.POSITION_LIMIT_EXCEEDED,
                    level=RiskLevel.HIGH,
                    message=f"Maximum concurrent trades limit ({self.risk_config.max_concurrent_trades}) reached"
                )
                result.add_alert(alert)
                result.message = "Position limit exceeded"
                return result
            
            # Check trade count limits
            today_metrics = self._get_today_metrics()
            if today_metrics.trades_count >= self.risk_config.daily_trade_limit:
                alert = RiskAlert(
                    alert_type=RiskAlertType.TRADE_LIMIT_EXCEEDED,
                    level=RiskLevel.HIGH,
                    message=f"Daily trade limit ({self.risk_config.daily_trade_limit}) reached"
                )
                result.add_alert(alert)
                result.message = "Daily trade limit exceeded"
                return result
            
            # Validate signal structure
            if not signal.validate():
                result.is_valid = False
                result.message = "Invalid trading signal structure"
                return result
            
            # Calculate and validate position size
            position_size_result = self.calculate_position_size(signal)
            if not position_size_result.is_valid():
                alert = RiskAlert(
                    alert_type=RiskAlertType.POSITION_SIZE_VIOLATION,
                    level=RiskLevel.HIGH,
                    message=f"Invalid position size: {position_size_result.recommended_size}"
                )
                result.add_alert(alert)
                result.message = "Invalid position size"
                return result
            
            # Add position size info to metadata
            result.metadata['position_size'] = position_size_result.recommended_size
            result.metadata['margin_required'] = position_size_result.margin_required
            
            if self.logger:
                self.logger.log_info(f"Trade validation passed for {signal.strategy_name}", {
                    'signal_type': signal.signal_type.value,
                    'position_size': position_size_result.recommended_size,
                    'margin_required': position_size_result.margin_required
                })
            
            return result
            
        except Exception as e:
            if self.logger:
                self.logger.log_error(e, "Trade validation failed")
            result.is_valid = False
            result.message = f"Validation error: {str(e)}"
            return result
    
    def calculate_position_size(self, signal: TradingSignal) -> PositionSizeResult:
        """
        Calculate appropriate position size based on risk parameters.
        
        Args:
            signal: Trading signal to calculate position size for
            
        Returns:
            PositionSizeResult with recommended size and risk metrics
        """
        try:
            # Get base parameters
            method = self.risk_config.position_size_method
            max_size = self.risk_config.max_position_size
            confidence = signal.confidence
            
            # Calculate risk amount (how much we're willing to lose)
            risk_amount = min(
                abs(signal.stop_loss),  # Signal's stop loss
                self.risk_config.stop_loss,  # Config stop loss
                self._get_remaining_daily_risk()  # Remaining daily risk capacity
            )
            
            # Estimate premium per lot (simplified calculation)
            # In real implementation, this would use actual option prices
            estimated_premium_per_lot = self._estimate_premium_per_lot(signal)
            
            if estimated_premium_per_lot <= 0:
                return PositionSizeResult(
                    recommended_size=0,
                    max_allowed_size=max_size,
                    risk_amount=risk_amount,
                    margin_required=0.0,
                    confidence_factor=confidence,
                    calculation_method=method,
                    warnings=["Could not estimate premium per lot"]
                )
            
            # Calculate position size based on method
            if method == "fixed":
                recommended_size = 1  # Fixed 1 lot
            elif method == "percentage":
                # Risk a percentage of available capital
                recommended_size = max(1, int(risk_amount / estimated_premium_per_lot))
            elif method == "kelly":
                # Simplified Kelly criterion
                win_rate = self._get_historical_win_rate()
                avg_win = self._get_average_win()
                avg_loss = self._get_average_loss()
                
                if avg_loss > 0:
                    kelly_fraction = (win_rate * avg_win - (1 - win_rate) * avg_loss) / avg_loss
                    kelly_fraction = max(0, min(kelly_fraction, 0.25))  # Cap at 25%
                    recommended_size = max(1, int(kelly_fraction * risk_amount / estimated_premium_per_lot))
                else:
                    recommended_size = 1
            else:
                recommended_size = 1
            
            # Apply confidence factor
            recommended_size = int(recommended_size * confidence)
            recommended_size = max(1, recommended_size)  # Minimum 1 lot
            
            # Ensure quantity is multiple of lot size
            recommended_quantity = recommended_size * BANKNIFTY_LOT_SIZE
            
            # Cap at maximum allowed size
            recommended_size = min(recommended_size, max_size)
            
            # Calculate margin requirement
            margin_required = self._calculate_margin_requirement(signal, recommended_size)
            
            # Create result
            result = PositionSizeResult(
                recommended_size=recommended_size,
                max_allowed_size=max_size,
                risk_amount=risk_amount,
                margin_required=margin_required,
                confidence_factor=confidence,
                calculation_method=method
            )
            
            # Add warnings if needed
            if recommended_size >= max_size:
                result.warnings.append(f"Position size capped at maximum: {max_size}")
            
            if margin_required > risk_amount * 2:
                result.warnings.append("High margin requirement relative to risk amount")
            
            return result
            
        except Exception as e:
            if self.logger:
                self.logger.log_error(e, "Position size calculation failed")
            
            return PositionSizeResult(
                recommended_size=0,
                max_allowed_size=max_size,
                risk_amount=0.0,
                margin_required=0.0,
                confidence_factor=confidence,
                calculation_method=method,
                warnings=[f"Calculation error: {str(e)}"]
            )
    
    def check_daily_limits(self) -> bool:
        """
        Check if daily loss limits are exceeded.
        
        Returns:
            True if within limits, False if limits exceeded
        """
        today_metrics = self._get_today_metrics()
        return not today_metrics.is_daily_limit_breached
    
    def monitor_positions(self, trades: List[Trade]) -> List[RiskAlert]:
        """
        Monitor positions and return list of risk alerts.
        
        Args:
            trades: List of active trades to monitor
            
        Returns:
            List of risk alerts for positions requiring action
        """
        alerts = []
        
        try:
            # Update active trades
            self.active_trades = {trade.trade_id: trade for trade in trades}
            
            # Check each position
            for trade in trades:
                position_alerts = self._monitor_single_position(trade)
                alerts.extend(position_alerts)
            
            # Update daily metrics
            self._update_daily_metrics(trades)
            
            # Check emergency stop
            if self._check_emergency_stop():
                alerts.append(RiskAlert(
                    alert_type=RiskAlertType.EMERGENCY_STOP,
                    level=RiskLevel.CRITICAL,
                    message="Emergency stop file detected - close all positions"
                ))
            
            return alerts
            
        except Exception as e:
            if self.logger:
                self.logger.log_error(e, "Position monitoring failed")
            return []
    
    def should_close_position(self, trade: Trade) -> bool:
        """
        Check if a position should be closed based on risk rules.
        
        Args:
            trade: Trade to check
            
        Returns:
            True if position should be closed
        """
        try:
            # Check profit target
            if trade.is_target_hit:
                return True
            
            # Check stop loss
            if trade.is_stop_loss_hit:
                return True
            
            # Check emergency stop
            if self._check_emergency_stop():
                return True
            
            # Check daily limits
            if not self.check_daily_limits():
                return True
            
            return False
            
        except Exception as e:
            if self.logger:
                self.logger.log_error(e, f"Error checking position closure for trade {trade.trade_id}")
            return False
    
    def get_daily_metrics(self, date_str: Optional[str] = None) -> DailyRiskMetrics:
        """
        Get daily risk metrics for a specific date.
        
        Args:
            date_str: Date string in YYYY-MM-DD format, defaults to today
            
        Returns:
            DailyRiskMetrics for the specified date
        """
        if date_str is None:
            date_str = date.today().isoformat()
        
        return self.daily_metrics.get(date_str, DailyRiskMetrics(
            date=date_str,
            total_pnl=0.0,
            realized_pnl=0.0,
            unrealized_pnl=0.0,
            max_drawdown=0.0,
            trades_count=0,
            winning_trades=0,
            losing_trades=0,
            largest_win=0.0,
            largest_loss=0.0,
            daily_loss_limit=self.risk_config.max_daily_loss,
            remaining_loss_capacity=self.risk_config.max_daily_loss,
            risk_utilization=0.0
        ))
    
    def validate_margin_requirement(self, signal: TradingSignal, position_size: int) -> MarginRequirement:
        """
        Validate margin requirements for a trade.
        
        Args:
            signal: Trading signal
            position_size: Proposed position size
            
        Returns:
            MarginRequirement with detailed margin analysis
        """
        try:
            # Calculate margin components (simplified calculation)
            # In real implementation, this would use broker's margin calculator
            
            total_margin = self._calculate_margin_requirement(signal, position_size)
            span_margin = total_margin * 0.7  # Approximate SPAN margin
            exposure_margin = total_margin * 0.2  # Approximate exposure margin
            premium_margin = total_margin * 0.1  # Premium margin
            additional_margin = 0.0
            
            # Get available margin (simplified - would query broker in real implementation)
            available_margin = self._get_available_margin()
            
            # Apply buffer
            required_with_buffer = total_margin * (1 + self.risk_config.margin_buffer)
            is_sufficient = available_margin >= required_with_buffer
            
            margin_utilization = (required_with_buffer / available_margin * 100) if available_margin > 0 else 100
            
            return MarginRequirement(
                total_margin=total_margin,
                span_margin=span_margin,
                exposure_margin=exposure_margin,
                premium_margin=premium_margin,
                additional_margin=additional_margin,
                available_margin=available_margin,
                margin_utilization=margin_utilization,
                is_sufficient=is_sufficient,
                buffer_amount=total_margin * self.risk_config.margin_buffer
            )
            
        except Exception as e:
            if self.logger:
                self.logger.log_error(e, "Margin validation failed")
            
            return MarginRequirement(
                total_margin=0.0,
                span_margin=0.0,
                exposure_margin=0.0,
                premium_margin=0.0,
                additional_margin=0.0,
                available_margin=0.0,
                margin_utilization=100.0,
                is_sufficient=False,
                buffer_amount=0.0
            )
    
    # Private helper methods
    
    def _get_today_metrics(self) -> DailyRiskMetrics:
        """Get today's risk metrics"""
        today = date.today().isoformat()
        if today not in self.daily_metrics:
            self.daily_metrics[today] = DailyRiskMetrics(
                date=today,
                total_pnl=0.0,
                realized_pnl=0.0,
                unrealized_pnl=0.0,
                max_drawdown=0.0,
                trades_count=0,
                winning_trades=0,
                losing_trades=0,
                largest_win=0.0,
                largest_loss=0.0,
                daily_loss_limit=self.risk_config.max_daily_loss,
                remaining_loss_capacity=self.risk_config.max_daily_loss,
                risk_utilization=0.0
            )
        return self.daily_metrics[today]
    
    def _check_emergency_stop(self) -> bool:
        """Check if emergency stop file exists"""
        try:
            emergency_file = self.risk_config.emergency_stop_file
            exists = os.path.exists(emergency_file)
            
            if exists and not self.emergency_stop_active:
                self.emergency_stop_active = True
                if self.logger:
                    self.logger.log_info(f"Emergency stop activated - file {emergency_file} detected")
            elif not exists and self.emergency_stop_active:
                self.emergency_stop_active = False
                if self.logger:
                    self.logger.log_info("Emergency stop deactivated")
            
            return exists
            
        except Exception as e:
            if self.logger:
                self.logger.log_error(e, "Error checking emergency stop file")
            return False
    
    def _check_position_limits(self) -> bool:
        """Check if position limits are exceeded"""
        active_count = len(self.active_trades)
        return active_count < self.risk_config.max_concurrent_trades
    
    def _get_remaining_daily_risk(self) -> float:
        """Get remaining daily risk capacity"""
        today_metrics = self._get_today_metrics()
        used_risk = abs(today_metrics.total_pnl) if today_metrics.total_pnl < 0 else 0
        return max(0, self.risk_config.max_daily_loss - used_risk)
    
    def _estimate_premium_per_lot(self, signal: TradingSignal) -> float:
        """Estimate premium per lot for position sizing"""
        # Simplified estimation - in real implementation would use actual option prices
        # This is a rough estimate based on typical BANKNIFTY option premiums
        
        if signal.signal_type.value in ['STRADDLE', 'STRANGLE']:
            return 150.0  # Typical straddle premium per lot
        elif signal.signal_type.value == 'IRON_CONDOR':
            return 75.0   # Typical iron condor credit per lot
        else:
            return 100.0  # Typical single option premium per lot
    
    def _calculate_margin_requirement(self, signal: TradingSignal, position_size: int) -> float:
        """Calculate margin requirement for a signal"""
        # Simplified margin calculation - in real implementation would use broker's calculator
        
        base_margin_per_lot = 50000.0  # Approximate BANKNIFTY margin per lot
        
        if signal.signal_type.value in ['STRADDLE', 'STRANGLE']:
            # Short straddle/strangle - higher margin
            return base_margin_per_lot * position_size * 1.5
        elif signal.signal_type.value == 'IRON_CONDOR':
            # Defined risk spread - lower margin
            return base_margin_per_lot * position_size * 0.3
        else:
            # Single leg - standard margin
            return base_margin_per_lot * position_size
    
    def _get_available_margin(self) -> float:
        """Get available margin (simplified)"""
        # In real implementation, this would query the broker
        return 500000.0  # Assume 5 lakh available margin
    
    def _get_historical_win_rate(self) -> float:
        """Get historical win rate for Kelly calculation"""
        # Simplified - would calculate from actual trade history
        return 0.6  # Assume 60% win rate
    
    def _get_average_win(self) -> float:
        """Get average winning trade amount"""
        # Simplified - would calculate from actual trade history
        return 1500.0  # Average win
    
    def _get_average_loss(self) -> float:
        """Get average losing trade amount"""
        # Simplified - would calculate from actual trade history
        return 800.0  # Average loss
    
    def _monitor_single_position(self, trade: Trade) -> List[RiskAlert]:
        """Monitor a single position and return alerts"""
        alerts = []
        
        try:
            # Check profit target
            if trade.is_target_hit:
                alerts.append(RiskAlert(
                    alert_type=RiskAlertType.PROFIT_TARGET_HIT,
                    level=RiskLevel.HIGH,
                    message=f"Profit target hit for trade {trade.trade_id}",
                    trade_id=trade.trade_id,
                    current_value=trade.current_pnl,
                    threshold_value=trade.target_pnl
                ))
            
            # Check stop loss
            if trade.is_stop_loss_hit:
                alerts.append(RiskAlert(
                    alert_type=RiskAlertType.STOP_LOSS_HIT,
                    level=RiskLevel.CRITICAL,
                    message=f"Stop loss hit for trade {trade.trade_id}",
                    trade_id=trade.trade_id,
                    current_value=trade.current_pnl,
                    threshold_value=trade.stop_loss
                ))
            
            return alerts
            
        except Exception as e:
            if self.logger:
                self.logger.log_error(e, f"Error monitoring position {trade.trade_id}")
            return []
    
    def _update_daily_metrics(self, trades: List[Trade]) -> None:
        """Update daily risk metrics based on current trades"""
        try:
            today_metrics = self._get_today_metrics()
            
            # Calculate current P&L
            total_pnl = sum(trade.current_pnl for trade in trades)
            realized_pnl = sum(trade.current_pnl for trade in trades if trade.status.value == 'CLOSED')
            unrealized_pnl = sum(trade.current_pnl for trade in trades if trade.status.value == 'OPEN')
            
            # Update metrics
            today_metrics.total_pnl = total_pnl
            today_metrics.realized_pnl = realized_pnl
            today_metrics.unrealized_pnl = unrealized_pnl
            today_metrics.trades_count = len(trades)
            
            # Update win/loss counts
            winning_trades = sum(1 for trade in trades if trade.current_pnl > 0)
            losing_trades = sum(1 for trade in trades if trade.current_pnl < 0)
            today_metrics.winning_trades = winning_trades
            today_metrics.losing_trades = losing_trades
            
            # Update largest win/loss
            if trades:
                pnls = [trade.current_pnl for trade in trades]
                today_metrics.largest_win = max(pnls)
                today_metrics.largest_loss = min(pnls)
            
            # Update risk utilization
            if total_pnl < 0:
                today_metrics.risk_utilization = abs(total_pnl) / today_metrics.daily_loss_limit
                today_metrics.remaining_loss_capacity = max(0, today_metrics.daily_loss_limit - abs(total_pnl))
            else:
                today_metrics.risk_utilization = 0.0
                today_metrics.remaining_loss_capacity = today_metrics.daily_loss_limit
            
        except Exception as e:
            if self.logger:
                self.logger.log_error(e, "Error updating daily metrics")