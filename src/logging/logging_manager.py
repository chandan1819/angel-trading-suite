"""
Comprehensive logging manager for the trading system.

Provides structured logging in JSON and CSV formats with proper sanitization
of sensitive data and configurable log levels.
"""

import json
import csv
import logging
import os
from datetime import datetime
from typing import Dict, Any, Optional, List
from pathlib import Path
from dataclasses import asdict

from ..models.trading_models import Trade, TradeLeg, TradingSignal
from ..models.config_models import LoggingConfig


class LoggingManager:
    """
    Manages all logging operations for the trading system.
    
    Features:
    - Structured JSON logging for system events
    - CSV logging for trade data
    - Automatic log rotation
    - Sensitive data sanitization
    - Configurable log levels and formats
    """
    
    def __init__(self, config: LoggingConfig):
        """
        Initialize the logging manager.
        
        Args:
            config: Logging configuration settings
        """
        self.config = config
        self.log_dir = Path(config.log_directory)
        self.log_dir.mkdir(parents=True, exist_ok=True)
        
        # Create date-specific subdirectory
        self.daily_log_dir = self.log_dir / datetime.now().strftime('%Y-%m-%d')
        self.daily_log_dir.mkdir(parents=True, exist_ok=True)
        
        # Initialize loggers
        self._setup_loggers()
        
        # Sensitive data patterns to sanitize
        self.sensitive_patterns = [
            'api_key', 'client_code', 'pin', 'totp_secret',
            'password', 'token', 'secret', 'credential'
        ]
    
    def _setup_loggers(self) -> None:
        """Set up different loggers for various purposes."""
        
        # Main system logger (JSON format)
        self.system_logger = logging.getLogger('trading_system')
        self.system_logger.setLevel(getattr(logging, self.config.log_level.upper()))
        
        # Create JSON formatter
        json_formatter = JsonFormatter()
        
        # System log file handler
        system_handler = logging.FileHandler(
            self.daily_log_dir / 'system.log',
            encoding='utf-8'
        )
        system_handler.setFormatter(json_formatter)
        self.system_logger.addHandler(system_handler)
        
        # Console handler if enabled
        if self.config.console_logging:
            console_handler = logging.StreamHandler()
            console_handler.setFormatter(logging.Formatter(
                '%(asctime)s - %(name)s - %(levelname)s - %(message)s'
            ))
            self.system_logger.addHandler(console_handler)
        
        # Trade logger (CSV format)
        self.trade_logger = logging.getLogger('trades')
        self.trade_logger.setLevel(logging.INFO)
        
        # Error logger (JSON format)
        self.error_logger = logging.getLogger('errors')
        self.error_logger.setLevel(logging.ERROR)
        
        error_handler = logging.FileHandler(
            self.daily_log_dir / 'errors.log',
            encoding='utf-8'
        )
        error_handler.setFormatter(json_formatter)
        self.error_logger.addHandler(error_handler)
    
    def log_system_event(self, event_type: str, message: str, 
                        data: Optional[Dict[str, Any]] = None,
                        level: str = 'INFO') -> None:
        """
        Log a system event with structured data.
        
        Args:
            event_type: Type of event (e.g., 'STRATEGY_EVALUATION', 'ORDER_PLACED')
            message: Human-readable message
            data: Additional structured data
            level: Log level (DEBUG, INFO, WARNING, ERROR, CRITICAL)
        """
        log_entry = {
            'timestamp': datetime.now().isoformat(),
            'event_type': event_type,
            'message': message,
            'data': self._sanitize_data(data or {})
        }
        
        log_method = getattr(self.system_logger, level.lower())
        log_method(json.dumps(log_entry))
    
    def log_trade_event(self, trade: Trade, event_type: str, 
                       additional_data: Optional[Dict[str, Any]] = None) -> None:
        """
        Log a trade-related event.
        
        Args:
            trade: Trade object
            event_type: Type of event (e.g., 'TRADE_OPENED', 'TRADE_CLOSED')
            additional_data: Additional event data
        """
        trade_data = {
            'trade_id': trade.trade_id,
            'strategy': trade.strategy,
            'status': trade.status.value if hasattr(trade.status, 'value') else str(trade.status),
            'current_pnl': trade.current_pnl,
            'entry_time': trade.entry_time.isoformat() if trade.entry_time else None,
            'exit_time': trade.exit_time.isoformat() if trade.exit_time else None
        }
        
        if additional_data:
            trade_data.update(additional_data)
        
        self.log_system_event(event_type, f"Trade event: {event_type}", trade_data)
    
    def log_error(self, error: Exception, context: str, 
                  additional_data: Optional[Dict[str, Any]] = None) -> None:
        """
        Log an error with context and additional data.
        
        Args:
            error: Exception that occurred
            context: Context where error occurred
            additional_data: Additional error context
        """
        error_data = {
            'error_type': type(error).__name__,
            'error_message': str(error),
            'context': context,
            'additional_data': self._sanitize_data(additional_data or {})
        }
        
        self.log_system_event('ERROR', f"Error in {context}: {str(error)}", 
                            error_data, 'ERROR')
    
    def log_strategy_signal(self, signal: TradingSignal) -> None:
        """
        Log a trading signal generation.
        
        Args:
            signal: Generated trading signal
        """
        signal_data = asdict(signal)
        # Convert datetime to ISO format
        if 'timestamp' in signal_data and signal_data['timestamp']:
            signal_data['timestamp'] = signal_data['timestamp'].isoformat()
        
        # Convert enums to their values
        if 'signal_type' in signal_data and hasattr(signal_data['signal_type'], 'value'):
            signal_data['signal_type'] = signal_data['signal_type'].value
        
        if 'option_types' in signal_data:
            signal_data['option_types'] = [
                ot.value if hasattr(ot, 'value') else str(ot) 
                for ot in signal_data['option_types']
            ]
        
        self.log_system_event('STRATEGY_SIGNAL', 
                            f"Signal generated by {signal.strategy_name}",
                            signal_data)
    
    def log_performance_metrics(self, metrics: Dict[str, Any]) -> None:
        """
        Log performance metrics.
        
        Args:
            metrics: Performance metrics dictionary
        """
        self.log_system_event('PERFORMANCE_METRICS', 
                            "Performance metrics calculated",
                            metrics)
    
    def _sanitize_data(self, data: Dict[str, Any]) -> Dict[str, Any]:
        """
        Remove or mask sensitive data from log entries.
        
        Args:
            data: Data dictionary to sanitize
            
        Returns:
            Sanitized data dictionary
        """
        if not isinstance(data, dict):
            return data
        
        sanitized = {}
        for key, value in data.items():
            key_lower = key.lower()
            
            # Check if key contains sensitive patterns
            is_sensitive = any(pattern in key_lower for pattern in self.sensitive_patterns)
            
            if is_sensitive:
                sanitized[key] = "***REDACTED***"
            elif isinstance(value, dict):
                sanitized[key] = self._sanitize_data(value)
            elif isinstance(value, list):
                sanitized[key] = [
                    self._sanitize_data(item) if isinstance(item, dict) else item
                    for item in value
                ]
            else:
                sanitized[key] = value
        
        return sanitized
    
    def get_log_files(self, date: Optional[str] = None) -> List[Path]:
        """
        Get list of log files for a specific date.
        
        Args:
            date: Date in YYYY-MM-DD format, defaults to today
            
        Returns:
            List of log file paths
        """
        if date is None:
            date = datetime.now().strftime('%Y-%m-%d')
        
        date_dir = self.log_dir / date
        if not date_dir.exists():
            return []
        
        return list(date_dir.glob('*.log'))
    
    def rotate_logs(self, days_to_keep: int = 30) -> None:
        """
        Rotate old log files, keeping only recent ones.
        
        Args:
            days_to_keep: Number of days of logs to retain
        """
        cutoff_date = datetime.now().timestamp() - (days_to_keep * 24 * 60 * 60)
        
        for date_dir in self.log_dir.iterdir():
            if date_dir.is_dir():
                try:
                    dir_date = datetime.strptime(date_dir.name, '%Y-%m-%d')
                    if dir_date.timestamp() < cutoff_date:
                        # Archive or delete old logs
                        import shutil
                        shutil.rmtree(date_dir)
                        self.log_system_event('LOG_ROTATION', 
                                            f"Deleted old logs for {date_dir.name}")
                except ValueError:
                    # Skip directories that don't match date format
                    continue


class JsonFormatter(logging.Formatter):
    """Custom JSON formatter for structured logging."""
    
    def format(self, record: logging.LogRecord) -> str:
        """Format log record as JSON."""
        # Try to parse message as JSON first
        try:
            message_data = json.loads(record.getMessage())
            return json.dumps(message_data, ensure_ascii=False)
        except (json.JSONDecodeError, ValueError):
            # Fallback to standard format wrapped in JSON
            log_entry = {
                'timestamp': datetime.fromtimestamp(record.created).isoformat(),
                'level': record.levelname,
                'logger': record.name,
                'message': record.getMessage(),
                'module': record.module,
                'function': record.funcName,
                'line': record.lineno
            }
            
            if record.exc_info:
                log_entry['exception'] = self.formatException(record.exc_info)
            
            return json.dumps(log_entry, ensure_ascii=False)