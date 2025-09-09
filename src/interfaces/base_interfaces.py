"""
Base interfaces and abstract classes for the Bank Nifty Options Trading System.

This module defines the core interfaces that all major components must implement,
providing a consistent contract for the trading system architecture.
"""

from abc import ABC, abstractmethod
from typing import List, Optional, Dict, Any
from datetime import datetime

from ..models.trading_models import (
    TradingSignal, Trade, OptionsChain, Option, TradeLeg
)
from ..models.config_models import TradingConfig


class IDataProvider(ABC):
    """Interface for market data providers"""
    
    @abstractmethod
    def get_options_chain(self, underlying: str, expiry_date: str) -> OptionsChain:
        """Get options chain for the given underlying and expiry"""
        pass
    
    @abstractmethod
    def get_current_price(self, symbol: str) -> float:
        """Get current price for a symbol"""
        pass
    
    @abstractmethod
    def get_historical_data(self, symbol: str, period: str, interval: str) -> List[Dict]:
        """Get historical data for a symbol"""
        pass
    
    @abstractmethod
    def authenticate(self) -> bool:
        """Authenticate with the data provider"""
        pass
    
    @abstractmethod
    def is_connected(self) -> bool:
        """Check if connected to the data provider"""
        pass


class IOrderManager(ABC):
    """Interface for order management"""
    
    @abstractmethod
    def place_order(self, symbol: str, quantity: int, order_type: str, 
                   price: Optional[float] = None) -> str:
        """Place an order and return order ID"""
        pass
    
    @abstractmethod
    def cancel_order(self, order_id: str) -> bool:
        """Cancel an order"""
        pass
    
    @abstractmethod
    def get_order_status(self, order_id: str) -> Dict:
        """Get order status"""
        pass
    
    @abstractmethod
    def get_positions(self) -> List[Dict]:
        """Get current positions"""
        pass
    
    @abstractmethod
    def get_order_history(self) -> List[Dict]:
        """Get order history"""
        pass


class IStrategy(ABC):
    """Interface for trading strategies"""
    
    @abstractmethod
    def evaluate(self, market_data: Dict[str, Any]) -> Optional[TradingSignal]:
        """Evaluate market conditions and generate trading signal"""
        pass
    
    @abstractmethod
    def get_name(self) -> str:
        """Get strategy name"""
        pass
    
    @abstractmethod
    def get_parameters(self) -> Dict[str, Any]:
        """Get strategy parameters"""
        pass
    
    @abstractmethod
    def update_parameters(self, parameters: Dict[str, Any]) -> None:
        """Update strategy parameters"""
        pass
    
    @abstractmethod
    def validate_signal(self, signal: TradingSignal) -> bool:
        """Validate a trading signal"""
        pass


class IRiskManager(ABC):
    """Interface for risk management"""
    
    @abstractmethod
    def validate_trade(self, signal: TradingSignal) -> bool:
        """Validate if a trade can be placed based on risk rules"""
        pass
    
    @abstractmethod
    def calculate_position_size(self, signal: TradingSignal) -> int:
        """Calculate appropriate position size"""
        pass
    
    @abstractmethod
    def check_daily_limits(self) -> bool:
        """Check if daily limits are exceeded"""
        pass
    
    @abstractmethod
    def monitor_positions(self, trades: List[Trade]) -> List[str]:
        """Monitor positions and return list of actions needed"""
        pass
    
    @abstractmethod
    def should_close_position(self, trade: Trade) -> bool:
        """Check if a position should be closed"""
        pass


class ILogger(ABC):
    """Interface for logging"""
    
    @abstractmethod
    def log_trade_entry(self, trade: Trade) -> None:
        """Log trade entry"""
        pass
    
    @abstractmethod
    def log_trade_exit(self, trade: Trade) -> None:
        """Log trade exit"""
        pass
    
    @abstractmethod
    def log_error(self, error: Exception, context: str) -> None:
        """Log error with context"""
        pass
    
    @abstractmethod
    def log_info(self, message: str, data: Optional[Dict] = None) -> None:
        """Log informational message"""
        pass
    
    @abstractmethod
    def get_trade_history(self) -> List[Dict]:
        """Get trade history"""
        pass


class INotificationManager(ABC):
    """Interface for notifications"""
    
    @abstractmethod
    def send_trade_notification(self, trade: Trade, event_type: str) -> None:
        """Send trade-related notification"""
        pass
    
    @abstractmethod
    def send_error_notification(self, error: Exception, context: str) -> None:
        """Send error notification"""
        pass
    
    @abstractmethod
    def send_daily_summary(self, summary: Dict[str, Any]) -> None:
        """Send daily summary notification"""
        pass
    
    @abstractmethod
    def test_connection(self) -> bool:
        """Test notification system connection"""
        pass


class IBacktestEngine(ABC):
    """Interface for backtesting"""
    
    @abstractmethod
    def run_backtest(self, strategy: IStrategy, start_date: str, 
                    end_date: str, config: Dict[str, Any]) -> Dict[str, Any]:
        """Run backtest for a strategy"""
        pass
    
    @abstractmethod
    def calculate_metrics(self, trades: List[Trade]) -> Dict[str, float]:
        """Calculate performance metrics"""
        pass
    
    @abstractmethod
    def generate_report(self, results: Dict[str, Any], output_path: str) -> None:
        """Generate backtest report"""
        pass


class ITradingManager(ABC):
    """Interface for the main trading manager"""
    
    @abstractmethod
    def start_trading_session(self) -> None:
        """Start trading session"""
        pass
    
    @abstractmethod
    def stop_trading_session(self) -> None:
        """Stop trading session"""
        pass
    
    @abstractmethod
    def process_trading_cycle(self) -> None:
        """Process one trading cycle"""
        pass
    
    @abstractmethod
    def get_active_trades(self) -> List[Trade]:
        """Get currently active trades"""
        pass
    
    @abstractmethod
    def get_session_summary(self) -> Dict[str, Any]:
        """Get trading session summary"""
        pass
    
    @abstractmethod
    def handle_emergency_stop(self) -> None:
        """Handle emergency stop condition"""
        pass


class BaseStrategy(IStrategy):
    """Base implementation for trading strategies"""
    
    def __init__(self, name: str, config: Dict[str, Any]):
        self.name = name
        self.config = config
        self.enabled = config.get('enabled', True)
        self.weight = config.get('weight', 1.0)
        self.min_confidence = config.get('min_confidence', 0.6)
    
    def get_name(self) -> str:
        """Get strategy name"""
        return self.name
    
    def get_parameters(self) -> Dict[str, Any]:
        """Get strategy parameters"""
        return self.config.copy()
    
    def update_parameters(self, parameters: Dict[str, Any]) -> None:
        """Update strategy parameters"""
        self.config.update(parameters)
        self.enabled = self.config.get('enabled', True)
        self.weight = self.config.get('weight', 1.0)
        self.min_confidence = self.config.get('min_confidence', 0.6)
    
    def validate_signal(self, signal: TradingSignal) -> bool:
        """Validate a trading signal"""
        if not signal.validate():
            return False
        
        # Check confidence threshold
        if signal.confidence < self.min_confidence:
            return False
        
        # Check if strategy is enabled
        if not self.enabled:
            return False
        
        return True
    
    @abstractmethod
    def evaluate(self, market_data: Dict[str, Any]) -> Optional[TradingSignal]:
        """Evaluate market conditions and generate trading signal"""
        pass


class BaseComponent(ABC):
    """Base class for all trading system components"""
    
    def __init__(self, config: TradingConfig):
        self.config = config
        self.logger = None  # Will be set by dependency injection
        self._initialized = False
    
    @abstractmethod
    def initialize(self) -> bool:
        """Initialize the component"""
        pass
    
    @abstractmethod
    def cleanup(self) -> None:
        """Cleanup resources"""
        pass
    
    def is_initialized(self) -> bool:
        """Check if component is initialized"""
        return self._initialized
    
    def set_logger(self, logger: ILogger) -> None:
        """Set logger for the component"""
        self.logger = logger


class ValidationResult:
    """Result of validation operations"""
    
    def __init__(self, is_valid: bool, message: str = "", data: Optional[Dict] = None):
        self.is_valid = is_valid
        self.message = message
        self.data = data or {}
    
    def __bool__(self) -> bool:
        return self.is_valid
    
    def __str__(self) -> str:
        return f"ValidationResult(valid={self.is_valid}, message='{self.message}')"


class TradingSystemError(Exception):
    """Base exception for trading system errors"""
    
    def __init__(self, message: str, component: str = "", error_code: str = ""):
        super().__init__(message)
        self.component = component
        self.error_code = error_code
        self.timestamp = datetime.now()


class DataProviderError(TradingSystemError):
    """Exception for data provider errors"""
    pass


class OrderManagerError(TradingSystemError):
    """Exception for order management errors"""
    pass


class StrategyError(TradingSystemError):
    """Exception for strategy errors"""
    pass


class RiskManagerError(TradingSystemError):
    """Exception for risk management errors"""
    pass