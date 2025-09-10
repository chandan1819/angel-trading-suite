"""
Configuration data models for the Bank Nifty Options Trading System.

This module contains dataclasses for all configuration-related entities including
TradingConfig, RiskConfig, StrategyConfig, APIConfig, LoggingConfig, and NotificationConfig.
"""

from dataclasses import dataclass, field
from typing import Dict, List, Optional, Any
from enum import Enum
import os


class TradingMode(Enum):
    """Trading modes"""
    PAPER = "paper"
    LIVE = "live"


class LogLevel(Enum):
    """Logging levels"""
    DEBUG = "DEBUG"
    INFO = "INFO"
    WARNING = "WARNING"
    ERROR = "ERROR"
    CRITICAL = "CRITICAL"


class NotificationType(Enum):
    """Notification types"""
    WEBHOOK = "webhook"
    EMAIL = "email"
    SLACK = "slack"
    TELEGRAM = "telegram"


@dataclass
class APICredentials:
    """API credentials for Angel Broking"""
    api_key: str = ""
    client_code: str = ""
    pin: str = ""
    totp_secret: str = ""
    
    def __post_init__(self):
        """Load credentials from environment variables if not provided"""
        if not self.api_key:
            self.api_key = os.getenv('ANGEL_API_KEY', '')
        if not self.client_code:
            self.client_code = os.getenv('ANGEL_CLIENT_CODE', '')
        if not self.pin:
            self.pin = os.getenv('ANGEL_PIN', '')
        if not self.totp_secret:
            self.totp_secret = os.getenv('ANGEL_TOTP_SECRET', '')
    
    def validate(self) -> bool:
        """Validate that all required credentials are present"""
        required_fields = [self.api_key, self.client_code, self.pin, self.totp_secret]
        return all(field.strip() for field in required_fields)
    
    def is_complete(self) -> bool:
        """Check if all credentials are provided"""
        return self.validate()


@dataclass
class APIConfig:
    """API configuration settings"""
    credentials: APICredentials = field(default_factory=APICredentials)
    base_url: str = "https://apiconnect.angelbroking.com"
    timeout: int = 30
    max_retries: int = 3
    retry_delay: float = 1.0
    rate_limit_calls: int = 100
    rate_limit_period: int = 60  # seconds
    connection_pool_size: int = 10
    
    def validate(self) -> bool:
        """Validate API configuration"""
        if not self.credentials.validate():
            return False
        if self.timeout <= 0 or self.max_retries < 0:
            return False
        if self.retry_delay < 0:
            return False
        if self.rate_limit_calls <= 0 or self.rate_limit_period <= 0:
            return False
        if self.connection_pool_size <= 0:
            return False
        return True
    
    def validate_structure_only(self) -> bool:
        """Validate API configuration structure without credentials"""
        if self.timeout <= 0 or self.max_retries < 0:
            return False
        if self.retry_delay < 0:
            return False
        if self.rate_limit_calls <= 0 or self.rate_limit_period <= 0:
            return False
        if self.connection_pool_size <= 0:
            return False
        return True


@dataclass
class RiskConfig:
    """Risk management configuration"""
    max_daily_loss: float = 5000.0
    max_concurrent_trades: int = 3
    profit_target: float = 2000.0
    stop_loss: float = 1000.0
    position_size_method: str = "fixed"  # "fixed", "percentage", "kelly"
    margin_buffer: float = 0.2  # 20% buffer
    max_position_size: int = 105  # Maximum lots per position (3 lots with current lot size 35)
    daily_trade_limit: int = 10
    emergency_stop_file: str = "emergency_stop.txt"
    
    def validate(self) -> bool:
        """Validate risk configuration"""
        if self.max_daily_loss <= 0:
            return False
        if self.max_concurrent_trades <= 0:
            return False
        if self.profit_target <= 0:
            return False
        if self.stop_loss <= 0:
            return False
        if self.margin_buffer < 0 or self.margin_buffer > 1:
            return False
        if self.max_position_size <= 0:
            return False
        if self.daily_trade_limit <= 0:
            return False
        if self.position_size_method not in ["fixed", "percentage", "kelly"]:
            return False
        return True
    
    @property
    def stop_loss_negative(self) -> float:
        """Return stop loss as negative value for calculations"""
        return -abs(self.stop_loss)


@dataclass
class StrategyParameters:
    """Base class for strategy parameters"""
    enabled: bool = True
    weight: float = 1.0
    min_confidence: float = 0.6
    
    def validate(self) -> bool:
        """Validate strategy parameters"""
        if not (0.0 <= self.weight <= 1.0):
            return False
        if not (0.0 <= self.min_confidence <= 1.0):
            return False
        return True


@dataclass
class StraddleStrategyConfig(StrategyParameters):
    """Configuration for straddle strategy"""
    min_iv_rank: float = 0.5
    max_dte: int = 7  # Days to expiry
    min_volume: int = 100
    max_bid_ask_spread: float = 5.0
    exit_time_minutes: int = 30  # Minutes before market close


@dataclass
class DirectionalStrategyConfig(StrategyParameters):
    """Configuration for directional strategy"""
    ema_period: int = 20
    atr_period: int = 14
    atr_multiplier: float = 2.0
    min_momentum: float = 0.02


@dataclass
class IronCondorStrategyConfig(StrategyParameters):
    """Configuration for iron condor strategy"""
    wing_distance: int = 200  # Points from ATM
    max_dte: int = 30
    target_delta: float = 0.15
    min_credit: float = 50.0


@dataclass
class GreeksStrategyConfig(StrategyParameters):
    """Configuration for Greeks-based strategy"""
    target_delta: float = 0.3
    max_theta: float = -10.0
    min_vega: float = 5.0
    max_gamma: float = 0.01


@dataclass
class VolatilityStrategyConfig(StrategyParameters):
    """Configuration for volatility strategy"""
    iv_percentile_threshold: float = 0.8
    min_iv_rank: float = 0.2
    volatility_lookback: int = 30


@dataclass
class StrategyConfig:
    """Strategy configuration settings"""
    enabled_strategies: List[str] = field(default_factory=lambda: ["straddle", "directional"])
    evaluation_interval: int = 60  # seconds
    market_start_time: str = "09:15"
    market_end_time: str = "15:30"
    timezone: str = "Asia/Kolkata"
    
    # Strategy-specific configurations
    straddle: StraddleStrategyConfig = field(default_factory=StraddleStrategyConfig)
    directional: DirectionalStrategyConfig = field(default_factory=DirectionalStrategyConfig)
    iron_condor: IronCondorStrategyConfig = field(default_factory=IronCondorStrategyConfig)
    greeks: GreeksStrategyConfig = field(default_factory=GreeksStrategyConfig)
    volatility: VolatilityStrategyConfig = field(default_factory=VolatilityStrategyConfig)
    
    def validate(self) -> bool:
        """Validate strategy configuration"""
        if not self.enabled_strategies:
            return False
        if self.evaluation_interval <= 0:
            return False
        
        # Validate time formats
        try:
            from datetime import datetime
            datetime.strptime(self.market_start_time, "%H:%M")
            datetime.strptime(self.market_end_time, "%H:%M")
        except ValueError:
            return False
        
        # Validate strategy configs
        strategy_configs = [
            self.straddle, self.directional, self.iron_condor,
            self.greeks, self.volatility
        ]
        
        for config in strategy_configs:
            if not config.validate():
                return False
        
        return True
    
    def get_strategy_config(self, strategy_name: str) -> Optional[StrategyParameters]:
        """Get configuration for a specific strategy"""
        strategy_map = {
            "straddle": self.straddle,
            "directional": self.directional,
            "iron_condor": self.iron_condor,
            "greeks": self.greeks,
            "volatility": self.volatility
        }
        return strategy_map.get(strategy_name)


@dataclass
class LoggingConfig:
    """Logging configuration settings"""
    log_level: str = "INFO"
    log_directory: str = "logs"
    console_logging: bool = True
    max_file_size: int = 10 * 1024 * 1024  # 10MB
    backup_count: int = 5
    format: str = "%(asctime)s - %(name)s - %(levelname)s - %(message)s"
    date_format: str = "%Y-%m-%d %H:%M:%S"
    enable_json: bool = True
    enable_csv: bool = True
    
    def validate(self) -> bool:
        """Validate logging configuration"""
        if self.max_file_size <= 0:
            return False
        if self.backup_count < 0:
            return False
        if not self.log_directory:
            return False
        if self.log_level not in ["DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"]:
            return False
        return True


@dataclass
class NotificationConfig:
    """Notification configuration settings"""
    enabled: bool = False
    types: List[NotificationType] = field(default_factory=list)
    webhook_url: str = ""
    email_smtp_server: str = ""
    email_smtp_port: int = 587
    email_username: str = ""
    email_password: str = ""
    email_to: List[str] = field(default_factory=list)
    slack_webhook_url: str = ""
    telegram_bot_token: str = ""
    telegram_chat_id: str = ""
    
    # Notification conditions
    notify_on_trade_entry: bool = True
    notify_on_trade_exit: bool = True
    notify_on_profit_target: bool = True
    notify_on_stop_loss: bool = True
    notify_on_daily_limit: bool = True
    notify_on_error: bool = True
    
    def validate(self) -> bool:
        """Validate notification configuration"""
        if not self.enabled:
            return True
        
        if not self.types:
            return False
        
        # Validate specific notification type configurations
        for notification_type in self.types:
            if notification_type == NotificationType.WEBHOOK and not self.webhook_url:
                return False
            elif notification_type == NotificationType.EMAIL:
                if not all([self.email_smtp_server, self.email_username, self.email_to]):
                    return False
            elif notification_type == NotificationType.SLACK and not self.slack_webhook_url:
                return False
            elif notification_type == NotificationType.TELEGRAM:
                if not all([self.telegram_bot_token, self.telegram_chat_id]):
                    return False
        
        return True


@dataclass
class BacktestConfig:
    """Backtesting configuration settings"""
    start_date: str = ""
    end_date: str = ""
    initial_capital: float = 100000.0
    commission_per_trade: float = 20.0
    slippage: float = 0.5  # Points
    data_source: str = "angel_api"
    output_dir: str = "backtest_results"
    generate_csv: bool = True
    generate_json: bool = True
    
    def validate(self) -> bool:
        """Validate backtest configuration"""
        if self.initial_capital <= 0:
            return False
        if self.commission_per_trade < 0:
            return False
        if self.slippage < 0:
            return False
        
        # Validate date formats if provided
        if self.start_date or self.end_date:
            try:
                from datetime import datetime
                if self.start_date:
                    datetime.strptime(self.start_date, "%Y-%m-%d")
                if self.end_date:
                    datetime.strptime(self.end_date, "%Y-%m-%d")
            except ValueError:
                return False
        
        return True


@dataclass
class TradingConfig:
    """Main trading configuration that combines all settings"""
    mode: TradingMode = TradingMode.PAPER
    underlying_symbol: str = "BANKNIFTY"
    
    # Component configurations
    api: APIConfig = field(default_factory=APIConfig)
    risk: RiskConfig = field(default_factory=RiskConfig)
    strategy: StrategyConfig = field(default_factory=StrategyConfig)
    logging: LoggingConfig = field(default_factory=LoggingConfig)
    notification: NotificationConfig = field(default_factory=NotificationConfig)
    backtest: BacktestConfig = field(default_factory=BacktestConfig)
    
    # Additional settings
    data_cache_ttl: int = 300  # seconds
    position_check_interval: int = 30  # seconds
    emergency_stop_check_interval: int = 10  # seconds
    
    def validate(self) -> bool:
        """Validate the complete trading configuration"""
        # Validate all component configurations except API in paper mode
        configs_to_validate = [
            self.risk,
            self.strategy,
            self.logging,
            self.notification,
            self.backtest
        ]
        
        # Only validate API credentials in live mode
        if self.is_live_mode():
            configs_to_validate.append(self.api)
        else:
            # In paper mode, only validate API structure, not credentials
            if self.api.timeout <= 0 or self.api.max_retries < 0:
                return False
            if self.api.retry_delay < 0:
                return False
            if self.api.rate_limit_calls <= 0 or self.api.rate_limit_period <= 0:
                return False
            if self.api.connection_pool_size <= 0:
                return False
        
        for config in configs_to_validate:
            if not config.validate():
                return False
        
        # Validate main config settings
        if not self.underlying_symbol:
            return False
        if self.data_cache_ttl <= 0:
            return False
        if self.position_check_interval <= 0:
            return False
        if self.emergency_stop_check_interval <= 0:
            return False
        
        return True
    
    def is_live_mode(self) -> bool:
        """Check if running in live trading mode"""
        return self.mode == TradingMode.LIVE
    
    def is_paper_mode(self) -> bool:
        """Check if running in paper trading mode"""
        return self.mode == TradingMode.PAPER