"""
Unit tests for the NotificationManager class.

Tests notification delivery, message formatting, and rate limiting functionality.
"""

import json
import pytest
from datetime import datetime, timedelta
from unittest.mock import Mock, patch, MagicMock

from src.logging.notification_manager import NotificationManager
from src.models.config_models import NotificationConfig, NotificationType
from src.models.trading_models import Trade, TradeLeg, TradingSignal, OptionType, OrderAction, TradeStatus, SignalType


class TestNotificationManager:
    """Test cases for NotificationManager."""
    
    @pytest.fixture
    def notification_config(self):
        """Create notification configuration for testing."""
        return NotificationConfig(
            enabled=True,
            types=[NotificationType.WEBHOOK, NotificationType.SLACK],
            webhook_url="https://example.com/webhook",
            slack_webhook_url="https://hooks.slack.com/test",
            notify_on_trade_entry=True,
            notify_on_trade_exit=True,
            notify_on_profit_target=True,
            notify_on_stop_loss=True,
            notify_on_daily_limit=True,
            notify_on_error=True
        )
    
    @pytest.fixture
    def notification_manager(self, notification_config):
        """Create NotificationManager instance for testing."""
        return NotificationManager(notification_config)
    
    @pytest.fixture
    def sample_trade(self):
        """Create sample trade for testing."""
        legs = [
            TradeLeg(
                symbol="BANKNIFTY2412550000CE",
                token="12345",
                strike=50000.0,
                option_type=OptionType.CE,
                action=OrderAction.SELL,
                quantity=25,
                entry_price=100.0,
                exit_price=80.0,
                current_price=80.0
            )
        ]
        
        return Trade(
            trade_id="TEST_001",
            strategy="straddle",
            underlying_symbol="BANKNIFTY",
            entry_time=datetime.now(),
            exit_time=datetime.now() + timedelta(minutes=30),
            legs=legs,
            target_pnl=2000.0,
            stop_loss=-1000.0,
            status=TradeStatus.CLOSED
        )
    
    @pytest.fixture
    def sample_signal(self):
        """Create sample trading signal for testing."""
        return TradingSignal(
            strategy_name="test_strategy",
            signal_type=SignalType.BUY,
            underlying="BANKNIFTY",
            strikes=[50000.0],
            option_types=[OptionType.CE],
            quantities=[25],
            confidence=0.8,
            timestamp=datetime.now(),
            metadata={"test": "data"}
        )
    
    def test_initialization(self, notification_manager, notification_config):
        """Test NotificationManager initialization."""
        assert notification_manager.config == notification_config
        assert notification_manager.rate_limit_window == 300
        assert notification_manager.max_notifications_per_window == 10
        assert len(notification_manager.last_notification_times) == 0
        assert len(notification_manager.notification_counts) == 0
    
    @patch('requests.post')
    def test_send_webhook_notification(self, mock_post, notification_manager):
        """Test webhook notification sending."""
        mock_response = Mock()
        mock_response.raise_for_status.return_value = None
        mock_post.return_value = mock_response
        
        notification_manager._send_webhook("Test Title", "Test Message", "info")
        
        # Verify webhook was called
        mock_post.assert_called_once()
        call_args = mock_post.call_args
        
        assert call_args[1]['json']['title'] == "Test Title"
        assert call_args[1]['json']['message'] == "Test Message"
        assert call_args[1]['json']['alert_type'] == "info"
        assert call_args[1]['json']['source'] == "banknifty-trading-system"
        assert 'timestamp' in call_args[1]['json']
    
    @patch('smtplib.SMTP')
    def test_send_email_notification(self, mock_smtp, notification_manager):
        """Test email notification sending."""
        # Configure email settings
        notification_manager.config.email_smtp_server = "smtp.example.com"
        notification_manager.config.email_smtp_port = 587
        notification_manager.config.email_username = "test@example.com"
        notification_manager.config.email_password = "password"
        notification_manager.config.email_to = ["recipient@example.com"]
        
        # Mock SMTP server
        mock_server = Mock()
        mock_smtp.return_value.__enter__.return_value = mock_server
        
        notification_manager._send_email("Test Title", "Test Message", "info")
        
        # Verify SMTP operations
        mock_server.starttls.assert_called_once()
        mock_server.login.assert_called_once_with("test@example.com", "password")
        mock_server.sendmail.assert_called_once()
    
    @patch('requests.post')
    def test_send_slack_notification(self, mock_post, notification_manager):
        """Test Slack notification sending."""
        mock_response = Mock()
        mock_response.raise_for_status.return_value = None
        mock_post.return_value = mock_response
        
        notification_manager._send_slack("Test Title", "Test Message", "success")
        
        # Verify Slack webhook was called
        mock_post.assert_called_once()
        call_args = mock_post.call_args
        
        payload = call_args[1]['json']
        assert len(payload['attachments']) == 1
        
        attachment = payload['attachments'][0]
        assert attachment['title'] == "Test Title"
        assert attachment['text'] == "Test Message"
        assert attachment['color'] == "#2eb886"  # Success color
        assert attachment['footer'] == "Bank Nifty Trading System"
    
    @patch('requests.post')
    def test_send_telegram_notification(self, mock_post, notification_manager):
        """Test Telegram notification sending."""
        # Configure Telegram settings
        notification_manager.config.telegram_bot_token = "test_token"
        notification_manager.config.telegram_chat_id = "test_chat_id"
        
        mock_response = Mock()
        mock_response.raise_for_status.return_value = None
        mock_post.return_value = mock_response
        
        notification_manager._send_telegram("Test Title", "Test Message", "warning")
        
        # Verify Telegram API was called
        mock_post.assert_called_once()
        call_args = mock_post.call_args
        
        assert "bot" in call_args[0][0]  # URL contains bot token
        payload = call_args[1]['json']
        assert payload['chat_id'] == "test_chat_id"
        assert "⚠️ *Test Title*" in payload['text']
        assert "Test Message" in payload['text']
        assert payload['parse_mode'] == "Markdown"
    
    @patch.object(NotificationManager, '_send_notification')
    def test_send_trade_entry_notification(self, mock_send, notification_manager, sample_trade):
        """Test trade entry notification."""
        sample_trade.status = TradeStatus.OPEN
        sample_trade.exit_time = None
        
        notification_manager.send_trade_entry_notification(sample_trade)
        
        mock_send.assert_called_once()
        call_args = mock_send.call_args[0]
        
        assert call_args[0] == "Trade Entry"
        assert sample_trade.trade_id in call_args[1]
        assert sample_trade.strategy in call_args[1]
        assert call_args[2] == "info"
    
    @patch.object(NotificationManager, '_send_notification')
    def test_send_trade_exit_notification(self, mock_send, notification_manager, sample_trade):
        """Test trade exit notification."""
        notification_manager.send_trade_exit_notification(sample_trade)
        
        mock_send.assert_called_once()
        call_args = mock_send.call_args[0]
        
        assert call_args[0] == "Trade Exit"
        assert sample_trade.trade_id in call_args[1]
        assert "Final P&L" in call_args[1]
        assert call_args[2] == "success"  # Positive P&L
    
    @patch.object(NotificationManager, '_send_notification')
    def test_send_profit_target_notification(self, mock_send, notification_manager, sample_trade):
        """Test profit target notification."""
        notification_manager.send_profit_target_notification(sample_trade)
        
        mock_send.assert_called_once()
        call_args = mock_send.call_args[0]
        
        assert "Profit Target Hit" in call_args[0]
        assert "Profit Target:" in call_args[1]
        assert "automatically closed" in call_args[1]
        assert call_args[2] == "success"
    
    @patch.object(NotificationManager, '_send_notification')
    def test_send_stop_loss_notification(self, mock_send, notification_manager, sample_trade):
        """Test stop loss notification."""
        sample_trade.current_pnl = -800.0
        
        notification_manager.send_stop_loss_notification(sample_trade)
        
        mock_send.assert_called_once()
        call_args = mock_send.call_args[0]
        
        assert "Stop Loss Triggered" in call_args[0]
        assert "Stop Loss:" in call_args[1]
        assert "limit further losses" in call_args[1]
        assert call_args[2] == "error"
    
    @patch.object(NotificationManager, '_send_notification')
    def test_send_daily_limit_notification(self, mock_send, notification_manager):
        """Test daily limit notification."""
        notification_manager.send_daily_limit_notification("daily_loss", 5500.0, 5000.0)
        
        mock_send.assert_called_once()
        call_args = mock_send.call_args[0]
        
        assert "Daily Limit Reached" in call_args[0]
        assert "Daily Loss Limit" in call_args[1]
        assert "5500" in call_args[1]
        assert "5000" in call_args[1]
        assert call_args[2] == "warning"
    
    @patch.object(NotificationManager, '_send_notification')
    def test_send_error_notification(self, mock_send, notification_manager):
        """Test error notification."""
        test_error = ValueError("Test error message")
        
        notification_manager.send_error_notification(
            test_error, 
            "test_context", 
            {"additional": "data"}
        )
        
        mock_send.assert_called_once()
        call_args = mock_send.call_args[0]
        
        assert "System Error" in call_args[0]
        assert "ValueError" in call_args[1]
        assert "Test error message" in call_args[1]
        assert "test_context" in call_args[1]
        assert call_args[2] == "error"
    
    @patch.object(NotificationManager, '_send_notification')
    def test_send_strategy_signal_notification(self, mock_send, notification_manager, sample_signal):
        """Test strategy signal notification."""
        notification_manager.send_strategy_signal_notification(sample_signal)
        
        mock_send.assert_called_once()
        call_args = mock_send.call_args[0]
        
        assert "Strategy Signal" in call_args[0]
        assert sample_signal.strategy_name in call_args[1]
        assert sample_signal.signal_type in call_args[1]
        assert str(sample_signal.confidence) in call_args[1]
        assert call_args[2] == "info"
    
    @patch.object(NotificationManager, '_send_notification')
    def test_send_daily_summary_notification(self, mock_send, notification_manager):
        """Test daily summary notification."""
        summary = {
            'date': '2024-12-26',
            'total_trades': 5,
            'completed_trades': 4,
            'active_trades': 1,
            'win_rate': 75.0,
            'winning_trades': 3,
            'losing_trades': 1,
            'total_pnl': 2500.0,
            'realized_pnl': 2000.0,
            'unrealized_pnl': 500.0,
            'average_win': 1000.0,
            'average_loss': -500.0,
            'profit_factor': 2.0
        }
        
        notification_manager.send_daily_summary_notification(summary)
        
        mock_send.assert_called_once()
        call_args = mock_send.call_args[0]
        
        assert "Daily Summary" in call_args[0]
        assert "2024-12-26" in call_args[1]
        assert "Total Trades: 5" in call_args[1]
        assert "Win Rate: 75.0%" in call_args[1]
        assert "₹2,500.00" in call_args[1]
        assert call_args[2] == "info"
    
    def test_rate_limiting(self, notification_manager):
        """Test notification rate limiting."""
        # Should not be rate limited initially
        assert not notification_manager._is_rate_limited("test_type")
        
        # Add notifications up to the limit
        for i in range(notification_manager.max_notifications_per_window):
            assert not notification_manager._is_rate_limited("test_type")
        
        # Should be rate limited now
        assert notification_manager._is_rate_limited("test_type")
        
        # Different type should not be rate limited
        assert not notification_manager._is_rate_limited("other_type")
    
    def test_rate_limit_reset(self, notification_manager):
        """Test rate limit reset functionality."""
        # Trigger rate limit
        for i in range(notification_manager.max_notifications_per_window + 1):
            notification_manager._is_rate_limited("test_type")
        
        assert notification_manager._is_rate_limited("test_type")
        
        # Reset rate limits
        notification_manager.reset_rate_limits()
        
        # Should not be rate limited anymore
        assert not notification_manager._is_rate_limited("test_type")
    
    def test_disabled_notifications(self, notification_config, sample_trade):
        """Test that notifications are not sent when disabled."""
        notification_config.enabled = False
        notification_manager = NotificationManager(notification_config)
        
        with patch.object(notification_manager, '_send_notification') as mock_send:
            notification_manager.send_trade_entry_notification(sample_trade)
            notification_manager.send_trade_exit_notification(sample_trade)
            notification_manager.send_profit_target_notification(sample_trade)
            
            # No notifications should be sent
            mock_send.assert_not_called()
    
    def test_specific_notification_disabled(self, notification_manager, sample_trade):
        """Test that specific notification types can be disabled."""
        notification_manager.config.notify_on_trade_entry = False
        
        with patch.object(notification_manager, '_send_notification') as mock_send:
            notification_manager.send_trade_entry_notification(sample_trade)
            mock_send.assert_not_called()
            
            # Other notifications should still work
            notification_manager.send_trade_exit_notification(sample_trade)
            mock_send.assert_called_once()
    
    def test_message_formatting(self, notification_manager, sample_trade):
        """Test message formatting functions."""
        # Test trade entry message
        entry_message = notification_manager._format_trade_entry_message(sample_trade)
        assert sample_trade.trade_id in entry_message
        assert sample_trade.strategy in entry_message
        assert "Target P&L" in entry_message
        assert "Stop Loss" in entry_message
        
        # Test trade exit message
        exit_message = notification_manager._format_trade_exit_message(sample_trade)
        assert sample_trade.trade_id in exit_message
        assert "Final P&L" in exit_message
        assert "₹500.00" in exit_message  # Current P&L
        
        # Test profit target message
        profit_message = notification_manager._format_profit_target_message(sample_trade)
        assert "Profit Target" in profit_message
        assert "automatically closed" in profit_message
        
        # Test stop loss message
        stop_message = notification_manager._format_stop_loss_message(sample_trade)
        assert "Stop Loss" in stop_message
        assert "limit further losses" in stop_message
    
    @patch('requests.post')
    def test_notification_error_handling(self, mock_post, notification_manager, sample_trade):
        """Test error handling in notification sending."""
        # Make webhook fail
        mock_post.side_effect = Exception("Network error")
        
        # Should not raise exception
        notification_manager.send_trade_entry_notification(sample_trade)
        
        # Verify webhook was attempted
        mock_post.assert_called()
    
    @patch.object(NotificationManager, '_send_webhook')
    @patch.object(NotificationManager, '_send_slack')
    def test_test_notifications(self, mock_slack, mock_webhook, notification_manager):
        """Test notification testing functionality."""
        # Make webhook succeed and Slack fail
        mock_webhook.return_value = None
        mock_slack.side_effect = Exception("Slack error")
        
        results = notification_manager.test_notifications()
        
        assert results[NotificationType.WEBHOOK.value] == True
        assert results[NotificationType.SLACK.value] == False
        
        mock_webhook.assert_called_once()
        mock_slack.assert_called_once()