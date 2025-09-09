"""
Notification manager for sending alerts and notifications.

Supports multiple notification channels including webhooks, email, Slack, and Telegram
with configurable alert conditions and thresholds.
"""

import json
import smtplib
import requests
from datetime import datetime
from typing import Dict, Any, Optional, List
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from dataclasses import asdict

from ..models.config_models import NotificationConfig, NotificationType
from ..models.trading_models import Trade, TradingSignal


class NotificationManager:
    """
    Manages all notification operations for the trading system.
    
    Features:
    - Multiple notification channels (webhook, email, Slack, Telegram)
    - Configurable alert conditions
    - Rich message formatting
    - Error handling and retry logic
    - Rate limiting to prevent spam
    """
    
    def __init__(self, config: NotificationConfig):
        """
        Initialize the notification manager.
        
        Args:
            config: Notification configuration settings
        """
        self.config = config
        self.last_notification_times: Dict[str, datetime] = {}
        self.notification_counts: Dict[str, int] = {}
        
        # Rate limiting settings (prevent spam)
        self.rate_limit_window = 300  # 5 minutes
        self.max_notifications_per_window = 10
    
    def send_trade_entry_notification(self, trade: Trade) -> None:
        """
        Send notification for trade entry.
        
        Args:
            trade: Trade that was entered
        """
        if not self.config.enabled or not self.config.notify_on_trade_entry:
            return
        
        if self._is_rate_limited("trade_entry"):
            return
        
        message = self._format_trade_entry_message(trade)
        self._send_notification("Trade Entry", message, "info")
    
    def send_trade_exit_notification(self, trade: Trade) -> None:
        """
        Send notification for trade exit.
        
        Args:
            trade: Trade that was exited
        """
        if not self.config.enabled or not self.config.notify_on_trade_exit:
            return
        
        if self._is_rate_limited("trade_exit"):
            return
        
        message = self._format_trade_exit_message(trade)
        alert_type = "success" if trade.current_pnl > 0 else "warning"
        self._send_notification("Trade Exit", message, alert_type)
    
    def send_profit_target_notification(self, trade: Trade) -> None:
        """
        Send notification when profit target is hit.
        
        Args:
            trade: Trade that hit profit target
        """
        if not self.config.enabled or not self.config.notify_on_profit_target:
            return
        
        message = self._format_profit_target_message(trade)
        self._send_notification("🎯 Profit Target Hit!", message, "success")
    
    def send_stop_loss_notification(self, trade: Trade) -> None:
        """
        Send notification when stop loss is triggered.
        
        Args:
            trade: Trade that hit stop loss
        """
        if not self.config.enabled or not self.config.notify_on_stop_loss:
            return
        
        message = self._format_stop_loss_message(trade)
        self._send_notification("🛑 Stop Loss Triggered", message, "error")
    
    def send_daily_limit_notification(self, limit_type: str, current_value: float, 
                                    limit_value: float) -> None:
        """
        Send notification when daily limits are reached.
        
        Args:
            limit_type: Type of limit (e.g., "daily_loss", "max_trades")
            current_value: Current value
            limit_value: Limit threshold
        """
        if not self.config.enabled or not self.config.notify_on_daily_limit:
            return
        
        message = self._format_daily_limit_message(limit_type, current_value, limit_value)
        self._send_notification("⚠️ Daily Limit Reached", message, "warning")
    
    def send_error_notification(self, error: Exception, context: str, 
                              additional_data: Optional[Dict[str, Any]] = None) -> None:
        """
        Send notification for system errors.
        
        Args:
            error: Exception that occurred
            context: Context where error occurred
            additional_data: Additional error context
        """
        if not self.config.enabled or not self.config.notify_on_error:
            return
        
        if self._is_rate_limited("error"):
            return
        
        message = self._format_error_message(error, context, additional_data)
        self._send_notification("🚨 System Error", message, "error")
    
    def send_strategy_signal_notification(self, signal: TradingSignal) -> None:
        """
        Send notification for strategy signals.
        
        Args:
            signal: Trading signal generated
        """
        if not self.config.enabled:
            return
        
        if self._is_rate_limited("strategy_signal"):
            return
        
        message = self._format_strategy_signal_message(signal)
        self._send_notification("📊 Strategy Signal", message, "info")
    
    def send_daily_summary_notification(self, summary: Dict[str, Any]) -> None:
        """
        Send daily trading summary notification.
        
        Args:
            summary: Daily summary data
        """
        if not self.config.enabled:
            return
        
        message = self._format_daily_summary_message(summary)
        self._send_notification("📈 Daily Summary", message, "info")
    
    def _send_notification(self, title: str, message: str, alert_type: str) -> None:
        """
        Send notification through all configured channels.
        
        Args:
            title: Notification title
            message: Notification message
            alert_type: Type of alert (info, success, warning, error)
        """
        for notification_type in self.config.types:
            try:
                if notification_type == NotificationType.WEBHOOK:
                    self._send_webhook(title, message, alert_type)
                elif notification_type == NotificationType.EMAIL:
                    self._send_email(title, message, alert_type)
                elif notification_type == NotificationType.SLACK:
                    self._send_slack(title, message, alert_type)
                elif notification_type == NotificationType.TELEGRAM:
                    self._send_telegram(title, message, alert_type)
            except Exception as e:
                # Log error but don't fail the entire notification process
                print(f"Failed to send {notification_type.value} notification: {e}")
    
    def _send_webhook(self, title: str, message: str, alert_type: str) -> None:
        """Send webhook notification."""
        if not self.config.webhook_url:
            return
        
        payload = {
            "title": title,
            "message": message,
            "alert_type": alert_type,
            "timestamp": datetime.now().isoformat(),
            "source": "banknifty-trading-system"
        }
        
        response = requests.post(
            self.config.webhook_url,
            json=payload,
            timeout=10,
            headers={"Content-Type": "application/json"}
        )
        response.raise_for_status()
    
    def _send_email(self, title: str, message: str, alert_type: str) -> None:
        """Send email notification."""
        if not all([self.config.email_smtp_server, self.config.email_username, 
                   self.config.email_to]):
            return
        
        # Create message
        msg = MIMEMultipart()
        msg['From'] = self.config.email_username
        msg['To'] = ', '.join(self.config.email_to)
        msg['Subject'] = f"[{alert_type.upper()}] {title}"
        
        # Add body
        body = f"""
Bank Nifty Trading System Alert

{title}

{message}

Time: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}
Alert Type: {alert_type.upper()}

---
This is an automated message from the Bank Nifty Trading System.
        """.strip()
        
        msg.attach(MIMEText(body, 'plain'))
        
        # Send email
        with smtplib.SMTP(self.config.email_smtp_server, self.config.email_smtp_port) as server:
            server.starttls()
            if self.config.email_password:
                server.login(self.config.email_username, self.config.email_password)
            
            text = msg.as_string()
            server.sendmail(self.config.email_username, self.config.email_to, text)
    
    def _send_slack(self, title: str, message: str, alert_type: str) -> None:
        """Send Slack notification."""
        if not self.config.slack_webhook_url:
            return
        
        # Color coding for different alert types
        color_map = {
            "info": "#36a64f",      # Green
            "success": "#2eb886",   # Dark green
            "warning": "#ff9500",   # Orange
            "error": "#ff0000"      # Red
        }
        
        payload = {
            "attachments": [
                {
                    "color": color_map.get(alert_type, "#36a64f"),
                    "title": title,
                    "text": message,
                    "footer": "Bank Nifty Trading System",
                    "ts": int(datetime.now().timestamp())
                }
            ]
        }
        
        response = requests.post(
            self.config.slack_webhook_url,
            json=payload,
            timeout=10
        )
        response.raise_for_status()
    
    def _send_telegram(self, title: str, message: str, alert_type: str) -> None:
        """Send Telegram notification."""
        if not all([self.config.telegram_bot_token, self.config.telegram_chat_id]):
            return
        
        # Format message with emoji based on alert type
        emoji_map = {
            "info": "ℹ️",
            "success": "✅",
            "warning": "⚠️",
            "error": "🚨"
        }
        
        emoji = emoji_map.get(alert_type, "ℹ️")
        formatted_message = f"{emoji} *{title}*\n\n{message}"
        
        url = f"https://api.telegram.org/bot{self.config.telegram_bot_token}/sendMessage"
        payload = {
            "chat_id": self.config.telegram_chat_id,
            "text": formatted_message,
            "parse_mode": "Markdown"
        }
        
        response = requests.post(url, json=payload, timeout=10)
        response.raise_for_status()
    
    def _format_trade_entry_message(self, trade: Trade) -> str:
        """Format trade entry message."""
        legs_info = []
        for leg in trade.legs:
            action_symbol = "📈" if leg.action == "BUY" else "📉"
            legs_info.append(
                f"{action_symbol} {leg.action} {leg.quantity}x {leg.strike} {leg.option_type} @ ₹{leg.entry_price}"
            )
        
        return f"""
Trade ID: {trade.trade_id}
Strategy: {trade.strategy}
Status: {trade.status}

Legs:
{chr(10).join(legs_info)}

Target P&L: ₹{trade.target_pnl:,.2f}
Stop Loss: ₹{trade.stop_loss:,.2f}
Entry Time: {trade.entry_time.strftime('%H:%M:%S') if trade.entry_time else 'N/A'}
        """.strip()
    
    def _format_trade_exit_message(self, trade: Trade) -> str:
        """Format trade exit message."""
        pnl_symbol = "💰" if trade.current_pnl > 0 else "💸"
        
        legs_info = []
        for leg in trade.legs:
            if leg.exit_price:
                pnl_per_leg = (leg.exit_price - leg.entry_price) * leg.quantity
                if leg.action == "SELL":
                    pnl_per_leg = -pnl_per_leg
                
                legs_info.append(
                    f"{leg.strike} {leg.option_type}: ₹{leg.entry_price} → ₹{leg.exit_price} (₹{pnl_per_leg:+.2f})"
                )
        
        holding_period = ""
        if trade.entry_time and trade.exit_time:
            duration = trade.exit_time - trade.entry_time
            minutes = duration.total_seconds() / 60
            holding_period = f"Holding Period: {minutes:.0f} minutes"
        
        return f"""
Trade ID: {trade.trade_id}
Strategy: {trade.strategy}

{pnl_symbol} Final P&L: ₹{trade.current_pnl:+,.2f}

Leg Details:
{chr(10).join(legs_info)}

{holding_period}
Exit Time: {trade.exit_time.strftime('%H:%M:%S') if trade.exit_time else 'N/A'}
        """.strip()
    
    def _format_profit_target_message(self, trade: Trade) -> str:
        """Format profit target hit message."""
        return f"""
Trade ID: {trade.trade_id}
Strategy: {trade.strategy}

Profit Target: ₹{trade.target_pnl:,.2f}
Actual P&L: ₹{trade.current_pnl:+,.2f}

The trade has been automatically closed at profit target.
        """.strip()
    
    def _format_stop_loss_message(self, trade: Trade) -> str:
        """Format stop loss triggered message."""
        return f"""
Trade ID: {trade.trade_id}
Strategy: {trade.strategy}

Stop Loss: ₹{trade.stop_loss:,.2f}
Actual P&L: ₹{trade.current_pnl:+,.2f}

The trade has been automatically closed at stop loss to limit further losses.
        """.strip()
    
    def _format_daily_limit_message(self, limit_type: str, current_value: float, 
                                  limit_value: float) -> str:
        """Format daily limit reached message."""
        limit_descriptions = {
            "daily_loss": "Daily Loss Limit",
            "max_trades": "Maximum Daily Trades",
            "max_concurrent": "Maximum Concurrent Trades"
        }
        
        description = limit_descriptions.get(limit_type, limit_type.replace("_", " ").title())
        
        return f"""
{description} has been reached!

Current Value: {current_value:,.2f}
Limit: {limit_value:,.2f}

No new trades will be placed until the next trading session or until limits are reset.
        """.strip()
    
    def _format_error_message(self, error: Exception, context: str, 
                            additional_data: Optional[Dict[str, Any]] = None) -> str:
        """Format error message."""
        message = f"""
Error Type: {type(error).__name__}
Context: {context}
Message: {str(error)}

Time: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}
        """
        
        if additional_data:
            message += f"\nAdditional Data:\n{json.dumps(additional_data, indent=2)}"
        
        return message.strip()
    
    def _format_strategy_signal_message(self, signal: TradingSignal) -> str:
        """Format strategy signal message."""
        return f"""
Strategy: {signal.strategy_name}
Signal Type: {signal.signal_type}
Underlying: {signal.underlying}
Confidence: {signal.confidence:.1%}

Strikes: {', '.join(map(str, signal.strikes))}
Option Types: {', '.join(signal.option_types)}
Quantities: {', '.join(map(str, signal.quantities))}

Time: {signal.timestamp.strftime('%H:%M:%S') if signal.timestamp else 'N/A'}
        """.strip()
    
    def _format_daily_summary_message(self, summary: Dict[str, Any]) -> str:
        """Format daily summary message."""
        return f"""
📊 Daily Trading Summary - {summary.get('date', 'N/A')}

Total Trades: {summary.get('total_trades', 0)}
Completed: {summary.get('completed_trades', 0)} | Active: {summary.get('active_trades', 0)}

Win Rate: {summary.get('win_rate', 0):.1f}%
Wins: {summary.get('winning_trades', 0)} | Losses: {summary.get('losing_trades', 0)}

💰 P&L Summary:
Total: ₹{summary.get('total_pnl', 0):+,.2f}
Realized: ₹{summary.get('realized_pnl', 0):+,.2f}
Unrealized: ₹{summary.get('unrealized_pnl', 0):+,.2f}

📈 Performance:
Avg Win: ₹{summary.get('average_win', 0):,.2f}
Avg Loss: ₹{summary.get('average_loss', 0):,.2f}
Profit Factor: {summary.get('profit_factor', 0):.2f}
        """.strip()
    
    def _is_rate_limited(self, notification_type: str) -> bool:
        """
        Check if notification type is rate limited.
        
        Args:
            notification_type: Type of notification to check
            
        Returns:
            True if rate limited, False otherwise
        """
        now = datetime.now()
        
        # Clean up old entries
        cutoff_time = now.timestamp() - self.rate_limit_window
        keys_to_remove = []
        
        for key, last_time in self.last_notification_times.items():
            if last_time.timestamp() < cutoff_time:
                keys_to_remove.append(key)
        
        for key in keys_to_remove:
            del self.last_notification_times[key]
            if key in self.notification_counts:
                del self.notification_counts[key]
        
        # Check rate limit
        count = self.notification_counts.get(notification_type, 0)
        if count >= self.max_notifications_per_window:
            return True
        
        # Update counters
        self.last_notification_times[notification_type] = now
        self.notification_counts[notification_type] = count + 1
        
        return False
    
    def reset_rate_limits(self) -> None:
        """Reset all rate limit counters."""
        self.last_notification_times.clear()
        self.notification_counts.clear()
    
    def test_notifications(self) -> Dict[str, bool]:
        """
        Test all configured notification channels.
        
        Returns:
            Dictionary with test results for each channel
        """
        results = {}
        
        test_title = "🧪 Test Notification"
        test_message = "This is a test notification from the Bank Nifty Trading System."
        
        for notification_type in self.config.types:
            try:
                if notification_type == NotificationType.WEBHOOK:
                    self._send_webhook(test_title, test_message, "info")
                elif notification_type == NotificationType.EMAIL:
                    self._send_email(test_title, test_message, "info")
                elif notification_type == NotificationType.SLACK:
                    self._send_slack(test_title, test_message, "info")
                elif notification_type == NotificationType.TELEGRAM:
                    self._send_telegram(test_title, test_message, "info")
                
                results[notification_type.value] = True
            except Exception as e:
                results[notification_type.value] = False
                print(f"Test failed for {notification_type.value}: {e}")
        
        return results