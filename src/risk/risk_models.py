"""
Risk management data models for the Bank Nifty Options Trading System.

This module contains dataclasses and enums for risk management operations
including risk alerts, validation results, and position sizing calculations.
"""

from dataclasses import dataclass, field
from datetime import datetime
from typing import Dict, List, Optional, Any
from enum import Enum


class RiskAlertType(Enum):
    """Types of risk alerts"""
    PROFIT_TARGET_HIT = "PROFIT_TARGET_HIT"
    STOP_LOSS_HIT = "STOP_LOSS_HIT"
    DAILY_LOSS_LIMIT = "DAILY_LOSS_LIMIT"
    POSITION_LIMIT_EXCEEDED = "POSITION_LIMIT_EXCEEDED"
    MARGIN_INSUFFICIENT = "MARGIN_INSUFFICIENT"
    EMERGENCY_STOP = "EMERGENCY_STOP"
    POSITION_SIZE_VIOLATION = "POSITION_SIZE_VIOLATION"
    TRADE_LIMIT_EXCEEDED = "TRADE_LIMIT_EXCEEDED"


class RiskLevel(Enum):
    """Risk severity levels"""
    LOW = "LOW"
    MEDIUM = "MEDIUM"
    HIGH = "HIGH"
    CRITICAL = "CRITICAL"


@dataclass
class RiskAlert:
    """Represents a risk management alert"""
    alert_type: RiskAlertType
    level: RiskLevel
    message: str
    trade_id: Optional[str] = None
    current_value: Optional[float] = None
    threshold_value: Optional[float] = None
    timestamp: datetime = field(default_factory=datetime.now)
    metadata: Dict[str, Any] = field(default_factory=dict)
    
    def __str__(self) -> str:
        return f"RiskAlert({self.alert_type.value}, {self.level.value}): {self.message}"


@dataclass
class ValidationResult:
    """Result of risk validation operations"""
    is_valid: bool
    message: str = ""
    alerts: List[RiskAlert] = field(default_factory=list)
    metadata: Dict[str, Any] = field(default_factory=dict)
    
    def __bool__(self) -> bool:
        return self.is_valid
    
    def add_alert(self, alert: RiskAlert) -> None:
        """Add a risk alert to the validation result"""
        self.alerts.append(alert)
        if alert.level in [RiskLevel.HIGH, RiskLevel.CRITICAL]:
            self.is_valid = False


@dataclass
class PositionSizeResult:
    """Result of position sizing calculations"""
    recommended_size: int
    max_allowed_size: int
    risk_amount: float
    margin_required: float
    confidence_factor: float
    calculation_method: str
    warnings: List[str] = field(default_factory=list)
    metadata: Dict[str, Any] = field(default_factory=dict)
    
    def is_valid(self) -> bool:
        """Check if position size is valid"""
        return self.recommended_size > 0 and self.recommended_size <= self.max_allowed_size


@dataclass
class MarginRequirement:
    """Margin requirement calculation result"""
    total_margin: float
    span_margin: float
    exposure_margin: float
    premium_margin: float
    additional_margin: float
    available_margin: float
    margin_utilization: float  # Percentage
    is_sufficient: bool
    buffer_amount: float
    
    def get_margin_shortage(self) -> float:
        """Get margin shortage amount if any"""
        if self.is_sufficient:
            return 0.0
        return self.total_margin - self.available_margin


@dataclass
class DailyRiskMetrics:
    """Daily risk tracking metrics"""
    date: str
    total_pnl: float
    realized_pnl: float
    unrealized_pnl: float
    max_drawdown: float
    trades_count: int
    winning_trades: int
    losing_trades: int
    largest_win: float
    largest_loss: float
    daily_loss_limit: float
    remaining_loss_capacity: float
    risk_utilization: float  # Percentage of daily limit used
    
    @property
    def win_rate(self) -> float:
        """Calculate win rate"""
        if self.trades_count == 0:
            return 0.0
        return self.winning_trades / self.trades_count
    
    @property
    def is_daily_limit_breached(self) -> bool:
        """Check if daily loss limit is breached"""
        return abs(self.total_pnl) >= self.daily_loss_limit
    
    @property
    def risk_level(self) -> RiskLevel:
        """Determine current risk level based on utilization"""
        if self.risk_utilization >= 0.9:
            return RiskLevel.CRITICAL
        elif self.risk_utilization >= 0.7:
            return RiskLevel.HIGH
        elif self.risk_utilization >= 0.5:
            return RiskLevel.MEDIUM
        else:
            return RiskLevel.LOW


@dataclass
class PositionRisk:
    """Risk metrics for a specific position"""
    trade_id: str
    current_pnl: float
    max_profit: float
    max_loss: float
    profit_target: float
    stop_loss: float
    time_decay_risk: float  # Theta exposure
    volatility_risk: float  # Vega exposure
    delta_exposure: float
    gamma_exposure: float
    days_to_expiry: int
    position_size: int
    margin_used: float
    
    @property
    def profit_distance(self) -> float:
        """Distance to profit target"""
        return self.profit_target - self.current_pnl
    
    @property
    def loss_distance(self) -> float:
        """Distance to stop loss"""
        return self.current_pnl - self.stop_loss
    
    @property
    def risk_reward_ratio(self) -> float:
        """Current risk-reward ratio"""
        if self.loss_distance <= 0:
            return float('inf')
        return self.profit_distance / self.loss_distance
    
    def get_risk_level(self) -> RiskLevel:
        """Determine risk level for this position"""
        if self.current_pnl <= self.stop_loss * 0.9:
            return RiskLevel.CRITICAL
        elif self.current_pnl <= self.stop_loss * 0.7:
            return RiskLevel.HIGH
        elif self.days_to_expiry <= 1:
            return RiskLevel.HIGH
        elif self.current_pnl <= self.stop_loss * 0.5:
            return RiskLevel.MEDIUM
        else:
            return RiskLevel.LOW