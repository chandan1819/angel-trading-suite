"""
Unit tests for the LoggingManager class.

Tests structured logging, data sanitization, and log management functionality.
"""

import json
import tempfile
import pytest
from datetime import datetime
from pathlib import Path
from unittest.mock import Mock, patch

from src.logging.logging_manager import LoggingManager, JsonFormatter
from src.models.config_models import LoggingConfig
from src.models.trading_models import Trade, TradeLeg, TradingSignal, OptionType, OrderAction, SignalType


class TestLoggingManager:
    """Test cases for LoggingManager."""
    
    @pytest.fixture
    def temp_log_dir(self):
        """Create temporary directory for logs."""
        with tempfile.TemporaryDirectory() as temp_dir:
            yield Path(temp_dir)
    
    @pytest.fixture
    def logging_config(self, temp_log_dir):
        """Create logging configuration for testing."""
        return LoggingConfig(
            log_level="INFO",
            log_directory=str(temp_log_dir),
            console_logging=False,
            enable_json=True,
            enable_csv=True
        )
    
    @pytest.fixture
    def logging_manager(self, logging_config):
        """Create LoggingManager instance for testing."""
        return LoggingManager(logging_config)
    
    def test_initialization(self, logging_manager, temp_log_dir):
        """Test LoggingManager initialization."""
        assert logging_manager.config.log_directory == str(temp_log_dir)
        assert logging_manager.log_dir.exists()
        assert logging_manager.daily_log_dir.exists()
        
        # Check that loggers are created
        assert logging_manager.system_logger is not None
        assert logging_manager.trade_logger is not None
        assert logging_manager.error_logger is not None
    
    def test_log_system_event(self, logging_manager, temp_log_dir):
        """Test system event logging."""
        test_data = {"key": "value", "number": 123}
        
        logging_manager.log_system_event(
            "TEST_EVENT",
            "Test message",
            test_data,
            "INFO"
        )
        
        # Check that log file was created
        log_files = list(logging_manager.daily_log_dir.glob("system.log"))
        assert len(log_files) == 1
        
        # Read and verify log content
        with open(log_files[0], 'r') as f:
            log_content = f.read()
            log_entry = json.loads(log_content.strip())
            
            assert log_entry["event_type"] == "TEST_EVENT"
            assert log_entry["message"] == "Test message"
            assert log_entry["data"]["key"] == "value"
            assert log_entry["data"]["number"] == 123
    
    def test_data_sanitization(self, logging_manager):
        """Test sensitive data sanitization."""
        sensitive_data = {
            "api_key": "secret123",
            "client_code": "user123",
            "pin": "1234",
            "normal_field": "normal_value",
            "nested": {
                "password": "secret",
                "safe_field": "safe_value"
            }
        }
        
        sanitized = logging_manager._sanitize_data(sensitive_data)
        
        assert sanitized["api_key"] == "***REDACTED***"
        assert sanitized["client_code"] == "***REDACTED***"
        assert sanitized["pin"] == "***REDACTED***"
        assert sanitized["normal_field"] == "normal_value"
        assert sanitized["nested"]["password"] == "***REDACTED***"
        assert sanitized["nested"]["safe_field"] == "safe_value"
    
    def test_log_trade_event(self, logging_manager):
        """Test trade event logging."""
        # Create test trade
        trade = Trade(
            trade_id="TEST_001",
            strategy="test_strategy",
            underlying_symbol="BANKNIFTY",
            entry_time=datetime.now(),
            exit_time=None,
            legs=[],
            target_pnl=2000.0,
            stop_loss=-1000.0
        )
        
        logging_manager.log_trade_event(trade, "TRADE_OPENED", {"extra": "data"})
        
        # Verify log was created (we can't easily verify content without mocking)
        log_files = list(logging_manager.daily_log_dir.glob("system.log"))
        assert len(log_files) == 1
    
    def test_log_error(self, logging_manager):
        """Test error logging."""
        test_error = ValueError("Test error message")
        
        logging_manager.log_error(test_error, "test_context", {"extra": "info"})
        
        # Verify error log was created
        log_files = list(logging_manager.daily_log_dir.glob("errors.log"))
        assert len(log_files) == 1
    
    def test_log_strategy_signal(self, logging_manager):
        """Test strategy signal logging."""
        signal = TradingSignal(
            strategy_name="test_strategy",
            signal_type=SignalType.BUY,
            underlying="BANKNIFTY",
            strikes=[50000.0],
            option_types=[OptionType.CE],
            quantities=[1],
            confidence=0.8,
            timestamp=datetime.now(),
            metadata={"test": "data"}
        )
        
        logging_manager.log_strategy_signal(signal)
        
        # Verify log was created
        log_files = list(logging_manager.daily_log_dir.glob("system.log"))
        assert len(log_files) == 1
    
    def test_log_performance_metrics(self, logging_manager):
        """Test performance metrics logging."""
        metrics = {
            "total_trades": 10,
            "win_rate": 70.0,
            "total_pnl": 5000.0
        }
        
        logging_manager.log_performance_metrics(metrics)
        
        # Verify log was created
        log_files = list(logging_manager.daily_log_dir.glob("system.log"))
        assert len(log_files) == 1
    
    def test_get_log_files(self, logging_manager):
        """Test getting log files for a date."""
        # Create a log entry to ensure files exist
        logging_manager.log_system_event("TEST", "Test message")
        
        # Get log files for today
        log_files = logging_manager.get_log_files()
        assert len(log_files) >= 1
        
        # Test with specific date
        today = datetime.now().strftime('%Y-%m-%d')
        log_files_today = logging_manager.get_log_files(today)
        assert len(log_files_today) >= 1
        
        # Test with non-existent date
        log_files_none = logging_manager.get_log_files("2020-01-01")
        assert len(log_files_none) == 0
    
    @patch('shutil.rmtree')
    def test_rotate_logs(self, mock_rmtree, logging_manager, temp_log_dir):
        """Test log rotation functionality."""
        # Create old directory structure
        old_date_dir = temp_log_dir / "2020-01-01"
        old_date_dir.mkdir()
        
        # Run log rotation
        logging_manager.rotate_logs(days_to_keep=1)
        
        # Verify old directory was removed
        mock_rmtree.assert_called_once_with(old_date_dir)


class TestJsonFormatter:
    """Test cases for JsonFormatter."""
    
    @pytest.fixture
    def formatter(self):
        """Create JsonFormatter instance."""
        return JsonFormatter()
    
    def test_format_json_message(self, formatter):
        """Test formatting a JSON message."""
        import logging
        
        # Create log record with JSON message
        record = logging.LogRecord(
            name="test",
            level=logging.INFO,
            pathname="",
            lineno=1,
            msg='{"key": "value", "number": 123}',
            args=(),
            exc_info=None
        )
        
        formatted = formatter.format(record)
        parsed = json.loads(formatted)
        
        assert parsed["key"] == "value"
        assert parsed["number"] == 123
    
    def test_format_regular_message(self, formatter):
        """Test formatting a regular text message."""
        import logging
        
        # Create log record with regular message
        record = logging.LogRecord(
            name="test",
            level=logging.INFO,
            pathname="test.py",
            lineno=10,
            msg="Regular log message",
            args=(),
            exc_info=None,
            func="test_function"
        )
        
        formatted = formatter.format(record)
        parsed = json.loads(formatted)
        
        assert parsed["level"] == "INFO"
        assert parsed["logger"] == "test"
        assert parsed["message"] == "Regular log message"
        assert parsed["module"] == "test"
        assert parsed["function"] == "test_function"
        assert parsed["line"] == 10
        assert "timestamp" in parsed
    
    def test_format_with_exception(self, formatter):
        """Test formatting a message with exception."""
        import logging
        
        try:
            raise ValueError("Test exception")
        except ValueError:
            import sys
            exc_info = sys.exc_info()
        
        record = logging.LogRecord(
            name="test",
            level=logging.ERROR,
            pathname="test.py",
            lineno=10,
            msg="Error occurred",
            args=(),
            exc_info=exc_info,
            func="test_function"
        )
        
        formatted = formatter.format(record)
        parsed = json.loads(formatted)
        
        assert parsed["level"] == "ERROR"
        assert parsed["message"] == "Error occurred"
        assert "exception" in parsed
        assert "ValueError: Test exception" in parsed["exception"]