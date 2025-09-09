"""
TradingManager - Central orchestrator for the Bank Nifty Options Trading System.

This module provides the main TradingManager class that coordinates all trading
operations including strategy evaluation, risk management, order execution,
and session management.
"""

import os
import time
import threading
import logging
from datetime import datetime, timedelta
from typing import Dict, Any, List, Optional, Callable
from pathlib import Path
import signal
import sys

from ..config.config_manager import ConfigManager
from ..models.config_models import TradingConfig, TradingMode
from ..models.trading_models import TradingSignal, Trade, TradeStatus
from ..api.angel_api_client import AngelAPIClient
from ..data.data_manager import DataManager
from ..strategies.strategy_manager import StrategyManager
from ..risk.risk_manager import RiskManager
from ..orders.order_manager import OrderManager
from ..logging.logging_manager import LoggingManager
from ..logging.notification_manager import NotificationManager
from ..logging.trade_reporter import TradeReporter
from ..emergency.emergency_controller import EmergencyController, EmergencyType
from ..emergency.safety_monitor import SafetyMonitor

logger = logging.getLogger(__name__)


class TradingSessionState:
    """Represents the current state of a trading session"""
    STOPPED = "stopped"
    STARTING = "starting"
    RUNNING = "running"
    STOPPING = "stopping"
    ERROR = "error"


class TradingManager:
    """
    Central orchestrator for the Bank Nifty Options Trading System.
    
    Coordinates all components including:
    - Strategy evaluation and signal generation
    - Risk management and validation
    - Order placement and execution
    - Position monitoring and management
    - Logging and notifications
    - Emergency controls and safety mechanisms
    """
    
    def __init__(self, config: TradingConfig, mode: str = "paper"):
        """
        Initialize TradingManager.
        
        Args:
            config: Trading configuration
            mode: Trading mode ("paper" or "live")
        """
        self.config = config
        self.mode = mode
        self.session_state = TradingSessionState.STOPPED
        
        # Initialize components
        self.api_client: Optional[AngelAPIClient] = None
        self.data_manager: Optional[DataManager] = None
        self.strategy_manager: Optional[StrategyManager] = None
        self.risk_manager: Optional[RiskManager] = None
        self.order_manager: Optional[OrderManager] = None
        self.logging_manager: Optional[LoggingManager] = None
        self.notification_manager: Optional[NotificationManager] = None
        self.trade_reporter: Optional[TradeReporter] = None
        self.emergency_controller: Optional[EmergencyController] = None
        self.safety_monitor: Optional[SafetyMonitor] = None
        
        # Session management
        self.session_start_time: Optional[datetime] = None
        self.session_end_time: Optional[datetime] = None
        self.continuous_mode = False
        self.polling_interval = 30  # seconds
        self.session_thread: Optional[threading.Thread] = None
        self.stop_event = threading.Event()
        
        # Trading state
        self.active_trades: Dict[str, Trade] = {}
        self.daily_pnl = 0.0
        self.session_pnl = 0.0
        self.trade_count = 0
        
        # Emergency controls
        self.emergency_stop_file = "emergency_stop.txt"
        self.emergency_stop_active = False
        
        # Performance tracking
        self.last_evaluation_time: Optional[datetime] = None
        self.evaluation_count = 0
        self.error_count = 0
        
        # Signal handlers for graceful shutdown
        signal.signal(signal.SIGINT, self._signal_handler)
        signal.signal(signal.SIGTERM, self._signal_handler)
        
        logger.info(f"TradingManager initialized in {mode} mode")
    
    def initialize(self) -> bool:
        """
        Initialize all trading components.
        
        Returns:
            True if initialization successful, False otherwise
        """
        try:
            logger.info("Initializing trading components...")
            
            # Initialize API client
            self.api_client = AngelAPIClient(self.config.api)
            if not self.api_client.initialize():
                logger.error("Failed to initialize API client")
                return False
            
            # Initialize logging manager first
            self.logging_manager = LoggingManager(self.config.logging)
            if not self.logging_manager.initialize():
                logger.error("Failed to initialize logging manager")
                return False
            
            # Initialize notification manager
            self.notification_manager = NotificationManager(self.config.notification)
            if not self.notification_manager.initialize():
                logger.warning("Failed to initialize notification manager - continuing without notifications")
            
            # Initialize data manager
            self.data_manager = DataManager(self.api_client)
            
            # Initialize strategy manager
            strategy_config = {
                'max_concurrent_evaluations': 3,
                'evaluation_timeout': 30,
                'enable_concurrent_evaluation': True,
                'max_signals_per_cycle': 2
            }
            self.strategy_manager = StrategyManager(self.data_manager, strategy_config)
            
            # Initialize risk manager
            self.risk_manager = RiskManager(self.config)
            if not self.risk_manager.initialize():
                logger.error("Failed to initialize risk manager")
                return False
            
            # Initialize order manager
            order_config = {
                'monitoring_interval': 30,
                'retry': {
                    'max_attempts': 3,
                    'base_delay': 1.0,
                    'max_delay': 30.0,
                    'backoff_multiplier': 2.0
                }
            }
            self.order_manager = OrderManager(self.api_client, order_config, self.mode)
            
            # Initialize trade reporter
            self.trade_reporter = TradeReporter(self.config.logging)
            if not self.trade_reporter.initialize():
                logger.warning("Failed to initialize trade reporter - continuing without detailed reporting")
            
            # Initialize emergency controller
            emergency_config = {
                'emergency_stop_file': self.emergency_stop_file,
                'daily_loss_limit': self.config.risk.max_daily_loss,
                'check_interval': 5,
                'shutdown_timeout': 300,
                'force_close_after_timeout': True
            }
            self.emergency_controller = EmergencyController(emergency_config)
            
            # Initialize safety monitor
            safety_config = {
                'check_interval': 10,
                'max_concurrent_positions': self.config.risk.max_concurrent_trades,
                'max_position_value': self.config.risk.max_daily_loss * 2,
                'max_single_position_size': self.config.risk.max_daily_loss * 0.5,
                'max_cpu_usage': 80.0,
                'max_memory_usage': 80.0,
                'min_disk_space': 1.0,
                'api_timeout_threshold': 30.0,
                'max_consecutive_api_failures': 5,
                'max_daily_loss_percentage': 0.8,
                'max_drawdown_percentage': 0.15
            }
            self.safety_monitor = SafetyMonitor(safety_config, self.emergency_controller)
            
            # Register emergency callbacks
            self._register_emergency_callbacks()
            
            # Register strategies
            self._register_strategies()
            
            logger.info("All trading components initialized successfully")
            return True
            
        except Exception as e:
            logger.error(f"Failed to initialize trading components: {e}")
            return False
    
    def start_trading_session(self, continuous: bool = False, 
                            polling_interval: int = 30) -> bool:
        """
        Start a trading session.
        
        Args:
            continuous: Whether to run continuously or execute once
            polling_interval: Polling interval in seconds for continuous mode
            
        Returns:
            True if session started successfully
        """
        try:
            if self.session_state != TradingSessionState.STOPPED:
                logger.warning(f"Cannot start session - current state: {self.session_state}")
                return False
            
            self.session_state = TradingSessionState.STARTING
            self.continuous_mode = continuous
            self.polling_interval = polling_interval
            self.session_start_time = datetime.now()
            self.stop_event.clear()
            
            logger.info(f"Starting trading session - Mode: {self.mode}, "
                       f"Continuous: {continuous}, Interval: {polling_interval}s")
            
            # Send session start notification
            if self.notification_manager:
                self.notification_manager.send_notification(
                    "Trading Session Started",
                    f"Session started in {self.mode} mode at {self.session_start_time}",
                    level="info"
                )
            
            # Start order monitoring
            if self.order_manager:
                self.order_manager.start_monitoring()
            
            # Start emergency monitoring
            if self.emergency_controller:
                self.emergency_controller.start_monitoring()
            
            # Start safety monitoring
            if self.safety_monitor:
                self.safety_monitor.start_monitoring()
            
            if continuous:
                # Start continuous trading in separate thread
                self.session_thread = threading.Thread(
                    target=self._continuous_trading_loop,
                    daemon=True
                )
                self.session_thread.start()
                self.session_state = TradingSessionState.RUNNING
                logger.info("Continuous trading session started")
            else:
                # Execute single trading cycle
                success = self._execute_trading_cycle()
                self.session_state = TradingSessionState.STOPPED
                logger.info(f"Single trading cycle completed - Success: {success}")
                return success
            
            return True
            
        except Exception as e:
            logger.error(f"Failed to start trading session: {e}")
            self.session_state = TradingSessionState.ERROR
            return False
    
    def stop_trading_session(self, force: bool = False) -> bool:
        """
        Stop the current trading session.
        
        Args:
            force: Whether to force stop without graceful shutdown
            
        Returns:
            True if session stopped successfully
        """
        try:
            if self.session_state == TradingSessionState.STOPPED:
                logger.info("Trading session already stopped")
                return True
            
            logger.info(f"Stopping trading session - Force: {force}")
            self.session_state = TradingSessionState.STOPPING
            
            # Signal stop to continuous loop
            self.stop_event.set()
            
            if not force:
                # Graceful shutdown - close open positions if configured
                if self.config.risk.close_positions_on_stop:
                    self._close_all_positions("Session stop requested")
            
            # Wait for session thread to complete
            if self.session_thread and self.session_thread.is_alive():
                self.session_thread.join(timeout=30)
                if self.session_thread.is_alive():
                    logger.warning("Session thread did not stop gracefully")
            
            # Stop order monitoring
            if self.order_manager:
                self.order_manager.stop_monitoring()
            
            # Stop emergency monitoring
            if self.emergency_controller:
                self.emergency_controller.stop_monitoring()
            
            # Stop safety monitoring
            if self.safety_monitor:
                self.safety_monitor.stop_monitoring()
            
            # Record session end
            self.session_end_time = datetime.now()
            session_duration = self.session_end_time - self.session_start_time if self.session_start_time else timedelta(0)
            
            # Generate session summary
            summary = self.get_session_summary()
            
            # Send session end notification
            if self.notification_manager:
                self.notification_manager.send_notification(
                    "Trading Session Ended",
                    f"Session ended. Duration: {session_duration}, "
                    f"Trades: {summary.get('total_trades', 0)}, "
                    f"P&L: ₹{summary.get('session_pnl', 0):.2f}",
                    level="info"
                )
            
            # Log session summary
            if self.logging_manager:
                self.logging_manager.log_info("Trading session ended", summary)
            
            self.session_state = TradingSessionState.STOPPED
            logger.info(f"Trading session stopped successfully. Duration: {session_duration}")
            return True
            
        except Exception as e:
            logger.error(f"Error stopping trading session: {e}")
            self.session_state = TradingSessionState.ERROR
            return False
    
    def _continuous_trading_loop(self) -> None:
        """Main continuous trading loop"""
        logger.info("Starting continuous trading loop")
        
        while not self.stop_event.is_set() and self.session_state == TradingSessionState.RUNNING:
            try:
                # Check if we're in trading hours
                if not self._is_trading_hours():
                    logger.debug("Outside trading hours - sleeping")
                    time.sleep(60)  # Check every minute
                    continue
                
                # Execute trading cycle
                self._execute_trading_cycle()
                
                # Wait for next cycle
                self.stop_event.wait(self.polling_interval)
                
            except Exception as e:
                logger.error(f"Error in continuous trading loop: {e}")
                self.error_count += 1
                
                # If too many errors, stop the session
                if self.error_count >= 5:
                    logger.critical("Too many errors in trading loop - stopping session")
                    self.session_state = TradingSessionState.ERROR
                    break
                
                # Sleep before retrying
                time.sleep(30)
        
        logger.info("Continuous trading loop ended")
    
    def _execute_trading_cycle(self) -> bool:
        """
        Execute a single trading cycle.
        
        Returns:
            True if cycle completed successfully
        """
        try:
            cycle_start = datetime.now()
            logger.info("Starting trading cycle")
            
            # Check emergency stop
            if self._check_emergency_stop():
                logger.warning("Emergency stop active - skipping trading cycle")
                return False
            
            # Check daily limits
            if not self.risk_manager.check_daily_limits():
                logger.warning("Daily limits exceeded - skipping trading cycle")
                return False
            
            # Update market data
            market_data = self._get_market_data()
            if not market_data:
                logger.error("Failed to get market data - skipping cycle")
                return False
            
            # Monitor existing positions
            self._monitor_positions()
            
            # Evaluate strategies and generate signals
            signals = self.strategy_manager.evaluate_strategies(market_data)
            
            if signals:
                logger.info(f"Generated {len(signals)} trading signals")
                
                # Process each signal
                for signal in signals:
                    self._process_trading_signal(signal)
            else:
                logger.debug("No trading signals generated")
            
            # Update performance metrics
            self.last_evaluation_time = cycle_start
            self.evaluation_count += 1
            
            cycle_duration = (datetime.now() - cycle_start).total_seconds()
            logger.info(f"Trading cycle completed in {cycle_duration:.2f}s")
            
            return True
            
        except Exception as e:
            logger.error(f"Error in trading cycle: {e}")
            self.error_count += 1
            return False
    
    def _get_market_data(self) -> Optional[Dict[str, Any]]:
        """Get current market data for strategy evaluation"""
        try:
            # Get options chain
            options_chain = self.data_manager.get_options_chain("BANKNIFTY")
            if not options_chain:
                return None
            
            # Get historical data for indicators
            historical_data = self.data_manager.get_historical_data(
                "BANKNIFTY", 
                period="1d",
                count=50
            )
            
            # Calculate indicators
            indicators = {}
            if historical_data:
                indicators = self.data_manager.calculate_indicators(historical_data)
            
            return {
                'options_chain': options_chain,
                'historical_data': historical_data,
                'indicators': indicators,
                'current_time': datetime.now()
            }
            
        except Exception as e:
            logger.error(f"Failed to get market data: {e}")
            return None
    
    def _process_trading_signal(self, signal: TradingSignal) -> bool:
        """
        Process a trading signal through risk management and order placement.
        
        Args:
            signal: Trading signal to process
            
        Returns:
            True if signal processed successfully
        """
        try:
            logger.info(f"Processing signal: {signal.strategy_name} - {signal.signal_type.value}")
            
            # Validate signal through risk management
            validation = self.risk_manager.validate_trade(signal)
            if not validation.is_valid:
                logger.warning(f"Signal rejected by risk manager: {validation.message}")
                return False
            
            # Create trade from signal
            trade = self._create_trade_from_signal(signal, validation)
            if not trade:
                logger.error("Failed to create trade from signal")
                return False
            
            # Place orders for the trade
            success = self._place_trade_orders(trade)
            if success:
                self.active_trades[trade.trade_id] = trade
                self.trade_count += 1
                
                # Log trade creation
                if self.trade_reporter:
                    self.trade_reporter.log_trade_entry(trade)
                
                # Send notification
                if self.notification_manager:
                    self.notification_manager.send_notification(
                        f"Trade Opened: {trade.strategy}",
                        f"Trade ID: {trade.trade_id}, Type: {signal.signal_type.value}, "
                        f"Target: ₹{trade.target_pnl}, Stop: ₹{trade.stop_loss}",
                        level="info"
                    )
                
                logger.info(f"Trade opened successfully: {trade.trade_id}")
                return True
            else:
                logger.error(f"Failed to place orders for trade")
                return False
                
        except Exception as e:
            logger.error(f"Error processing trading signal: {e}")
            return False
    
    def _create_trade_from_signal(self, signal: TradingSignal, 
                                validation: Any) -> Optional[Trade]:
        """Create a Trade object from a TradingSignal"""
        try:
            from ..models.trading_models import Trade, TradeLeg
            import uuid
            
            trade_id = f"TRADE_{int(datetime.now().timestamp())}_{uuid.uuid4().hex[:8]}"
            
            # Create trade legs from signal
            legs = []
            for i, strike in enumerate(signal.strikes):
                leg = TradeLeg(
                    symbol=f"BANKNIFTY{signal.expiry_date}{strike}{signal.option_types[i]}",
                    token="",  # Will be populated by order manager
                    strike=strike,
                    option_type=signal.option_types[i],
                    action=signal.actions[i] if hasattr(signal, 'actions') else 'BUY',
                    quantity=signal.quantities[i] if len(signal.quantities) > i else signal.quantities[0],
                    entry_price=0.0,  # Will be updated after order execution
                    exit_price=None,
                    current_price=0.0
                )
                legs.append(leg)
            
            trade = Trade(
                trade_id=trade_id,
                strategy=signal.strategy_name,
                entry_time=datetime.now(),
                exit_time=None,
                legs=legs,
                target_pnl=signal.target_pnl,
                stop_loss=signal.stop_loss,
                current_pnl=0.0,
                status=TradeStatus.PENDING,
                underlying_symbol="BANKNIFTY",
                expiry_date=signal.expiry_date
            )
            
            return trade
            
        except Exception as e:
            logger.error(f"Error creating trade from signal: {e}")
            return None
    
    def _place_trade_orders(self, trade: Trade) -> bool:
        """Place orders for all legs of a trade"""
        try:
            from ..orders.order_models import OrderRequest, OrderType, OrderAction
            
            success = True
            
            for leg in trade.legs:
                # Create order request
                order = OrderRequest(
                    symbol=leg.symbol,
                    token=leg.token,
                    exchange="NFO",
                    action=OrderAction.BUY if leg.action == 'BUY' else OrderAction.SELL,
                    order_type=OrderType.MARKET,
                    quantity=leg.quantity,
                    price=0.0,  # Market order
                    product="MIS",  # Intraday
                    trade_id=trade.trade_id,
                    strategy_name=trade.strategy
                )
                
                # Place order
                response = self.order_manager.place_order(order)
                if response.is_success:
                    leg.order_id = response.order_id
                    logger.info(f"Order placed for leg {leg.symbol}: {response.order_id}")
                else:
                    logger.error(f"Failed to place order for leg {leg.symbol}: {response.message}")
                    success = False
                    break
            
            if success:
                trade.status = TradeStatus.OPEN
            
            return success
            
        except Exception as e:
            logger.error(f"Error placing trade orders: {e}")
            return False
    
    def _monitor_positions(self) -> None:
        """Monitor existing positions and handle exits"""
        try:
            if not self.active_trades:
                return
            
            # Get position monitoring alerts from order manager
            trades_list = list(self.active_trades.values())
            actions = self.order_manager.monitor_positions(trades_list)
            
            # Process monitoring actions
            for action in actions:
                if action.startswith("CLOSE_TRADE_"):
                    parts = action.split("_")
                    if len(parts) >= 3:
                        trade_id = parts[2]
                        reason = "_".join(parts[3:]) if len(parts) > 3 else "UNKNOWN"
                        self._close_trade(trade_id, reason)
            
            # Check risk alerts from risk manager
            risk_alerts = self.risk_manager.monitor_positions(trades_list)
            for alert in risk_alerts:
                if alert.trade_id and alert.trade_id in self.active_trades:
                    if alert.alert_type.value in ['PROFIT_TARGET_HIT', 'STOP_LOSS_HIT']:
                        self._close_trade(alert.trade_id, alert.message)
            
            # Update emergency controller with current state
            if self.emergency_controller:
                self.emergency_controller.update_daily_loss(abs(self.daily_pnl) if self.daily_pnl < 0 else 0)
                self.emergency_controller.update_active_trades(self.active_trades)
            
            # Update safety monitor with current state
            if self.safety_monitor:
                self.safety_monitor.update_trading_state(self.active_trades, self.daily_pnl)
            
        except Exception as e:
            logger.error(f"Error monitoring positions: {e}")
    
    def _close_trade(self, trade_id: str, reason: str) -> bool:
        """Close a specific trade"""
        try:
            if trade_id not in self.active_trades:
                logger.warning(f"Trade {trade_id} not found in active trades")
                return False
            
            trade = self.active_trades[trade_id]
            logger.info(f"Closing trade {trade_id}: {reason}")
            
            # Place closing orders for all legs
            success = True
            for leg in trade.legs:
                if leg.order_id:
                    # Create closing order (opposite action)
                    from ..orders.order_models import OrderRequest, OrderType, OrderAction
                    
                    closing_action = OrderAction.SELL if leg.action == 'BUY' else OrderAction.BUY
                    
                    close_order = OrderRequest(
                        symbol=leg.symbol,
                        token=leg.token,
                        exchange="NFO",
                        action=closing_action,
                        order_type=OrderType.MARKET,
                        quantity=leg.quantity,
                        price=0.0,
                        product="MIS",
                        trade_id=trade_id,
                        strategy_name=trade.strategy,
                        tag="CLOSE"
                    )
                    
                    response = self.order_manager.place_order(close_order)
                    if not response.is_success:
                        logger.error(f"Failed to close leg {leg.symbol}: {response.message}")
                        success = False
            
            if success:
                trade.status = TradeStatus.CLOSED
                trade.exit_time = datetime.now()
                
                # Update P&L
                self.session_pnl += trade.current_pnl
                self.daily_pnl += trade.current_pnl
                
                # Log trade exit
                if self.trade_reporter:
                    self.trade_reporter.log_trade_exit(trade, reason)
                
                # Send notification
                if self.notification_manager:
                    self.notification_manager.send_notification(
                        f"Trade Closed: {trade.strategy}",
                        f"Trade ID: {trade_id}, Reason: {reason}, "
                        f"P&L: ₹{trade.current_pnl:.2f}",
                        level="info"
                    )
                
                # Remove from active trades
                del self.active_trades[trade_id]
                
                logger.info(f"Trade {trade_id} closed successfully. P&L: ₹{trade.current_pnl:.2f}")
            
            return success
            
        except Exception as e:
            logger.error(f"Error closing trade {trade_id}: {e}")
            return False
    
    def _close_all_positions(self, reason: str) -> None:
        """Close all open positions"""
        try:
            logger.info(f"Closing all positions: {reason}")
            
            active_trade_ids = list(self.active_trades.keys())
            for trade_id in active_trade_ids:
                self._close_trade(trade_id, reason)
            
            logger.info(f"Closed {len(active_trade_ids)} positions")
            
        except Exception as e:
            logger.error(f"Error closing all positions: {e}")
    
    def _check_emergency_stop(self) -> bool:
        """Check if emergency stop is active"""
        try:
            emergency_active = os.path.exists(self.emergency_stop_file)
            
            if emergency_active and not self.emergency_stop_active:
                self.emergency_stop_active = True
                logger.critical("EMERGENCY STOP ACTIVATED")
                
                # Close all positions
                self._close_all_positions("Emergency stop activated")
                
                # Send critical notification
                if self.notification_manager:
                    self.notification_manager.send_notification(
                        "EMERGENCY STOP ACTIVATED",
                        f"Emergency stop file detected: {self.emergency_stop_file}. "
                        "All positions closed.",
                        level="critical"
                    )
            
            elif not emergency_active and self.emergency_stop_active:
                self.emergency_stop_active = False
                logger.info("Emergency stop deactivated")
            
            return emergency_active
            
        except Exception as e:
            logger.error(f"Error checking emergency stop: {e}")
            return False
    
    def _is_trading_hours(self) -> bool:
        """Check if current time is within trading hours"""
        try:
            now = datetime.now()
            
            # Indian market hours: 9:15 AM to 3:30 PM IST
            market_open = now.replace(hour=9, minute=15, second=0, microsecond=0)
            market_close = now.replace(hour=15, minute=30, second=0, microsecond=0)
            
            # Check if it's a weekday (Monday=0, Sunday=6)
            if now.weekday() >= 5:  # Saturday or Sunday
                return False
            
            return market_open <= now <= market_close
            
        except Exception as e:
            logger.error(f"Error checking trading hours: {e}")
            return False
    
    def _register_strategies(self) -> None:
        """Register all available strategies"""
        try:
            from ..strategies.straddle_strategy import StraddleStrategy
            from ..strategies.directional_strategy import DirectionalStrategy
            from ..strategies.iron_condor_strategy import IronCondorStrategy
            from ..strategies.greeks_strategy import GreeksStrategy
            from ..strategies.volatility_strategy import VolatilityStrategy
            
            # Register strategies based on configuration
            if self.config.strategy.straddle.enabled:
                straddle_strategy = StraddleStrategy(self.config.strategy.straddle)
                self.strategy_manager.register_strategy(straddle_strategy)
                logger.info("Registered Straddle Strategy")
            
            if self.config.strategy.directional.enabled:
                directional_strategy = DirectionalStrategy(self.config.strategy.directional)
                self.strategy_manager.register_strategy(directional_strategy)
                logger.info("Registered Directional Strategy")
            
            if self.config.strategy.iron_condor.enabled:
                iron_condor_strategy = IronCondorStrategy(self.config.strategy.iron_condor)
                self.strategy_manager.register_strategy(iron_condor_strategy)
                logger.info("Registered Iron Condor Strategy")
            
            if self.config.strategy.greeks.enabled:
                greeks_strategy = GreeksStrategy(self.config.strategy.greeks)
                self.strategy_manager.register_strategy(greeks_strategy)
                logger.info("Registered Greeks Strategy")
            
            if self.config.strategy.volatility.enabled:
                volatility_strategy = VolatilityStrategy(self.config.strategy.volatility)
                self.strategy_manager.register_strategy(volatility_strategy)
                logger.info("Registered Volatility Strategy")
            
        except Exception as e:
            logger.error(f"Error registering strategies: {e}")
    
    def _register_emergency_callbacks(self) -> None:
        """Register emergency event callbacks"""
        try:
            if not self.emergency_controller:
                return
            
            # Register callback for manual emergency stops
            self.emergency_controller.register_emergency_callback(
                EmergencyType.MANUAL_STOP,
                self._handle_manual_emergency_stop
            )
            
            # Register callback for daily loss limit breaches
            self.emergency_controller.register_emergency_callback(
                EmergencyType.DAILY_LOSS_LIMIT,
                self._handle_daily_loss_limit_breach
            )
            
            # Register callback for system errors
            self.emergency_controller.register_emergency_callback(
                EmergencyType.SYSTEM_ERROR,
                self._handle_system_error
            )
            
            # Register position close callback
            self.emergency_controller.register_position_close_callback(
                self._emergency_close_position
            )
            
            logger.info("Emergency callbacks registered")
            
        except Exception as e:
            logger.error(f"Error registering emergency callbacks: {e}")
    
    def _handle_manual_emergency_stop(self, event) -> None:
        """Handle manual emergency stop event"""
        try:
            logger.critical(f"Manual emergency stop triggered: {event.message}")
            
            # Stop trading session immediately
            self.stop_trading_session(force=True)
            
            # Send critical notification
            if self.notification_manager:
                self.notification_manager.send_notification(
                    "MANUAL EMERGENCY STOP",
                    f"Manual emergency stop activated: {event.message}",
                    level="critical"
                )
            
        except Exception as e:
            logger.error(f"Error handling manual emergency stop: {e}")
    
    def _handle_daily_loss_limit_breach(self, event) -> None:
        """Handle daily loss limit breach"""
        try:
            logger.critical(f"Daily loss limit breached: {event.message}")
            
            # Close all positions
            self._close_all_positions("Daily loss limit breached")
            
            # Stop new trading
            self.session_state = TradingSessionState.ERROR
            
            # Send notification
            if self.notification_manager:
                self.notification_manager.send_notification(
                    "DAILY LOSS LIMIT BREACHED",
                    f"Daily loss limit exceeded: {event.message}",
                    level="critical"
                )
            
        except Exception as e:
            logger.error(f"Error handling daily loss limit breach: {e}")
    
    def _handle_system_error(self, event) -> None:
        """Handle system error event"""
        try:
            logger.error(f"System error detected: {event.message}")
            
            # For critical system errors, initiate emergency shutdown
            if event.level.value == "critical":
                self.emergency_controller.initiate_emergency_shutdown(event.message)
            
            # Send notification
            if self.notification_manager:
                self.notification_manager.send_notification(
                    "SYSTEM ERROR",
                    f"System error detected: {event.message}",
                    level="error"
                )
            
        except Exception as e:
            logger.error(f"Error handling system error: {e}")
    
    def _emergency_close_position(self, trade_id: str, reason: str, emergency: bool = False) -> None:
        """Emergency position closure callback"""
        try:
            logger.warning(f"Emergency close requested for {trade_id}: {reason}")
            
            # Use existing close trade method
            self._close_trade(trade_id, f"Emergency: {reason}")
            
        except Exception as e:
            logger.error(f"Error in emergency position closure: {e}")
    
    def get_session_summary(self) -> Dict[str, Any]:
        """Get summary of current trading session"""
        try:
            duration = timedelta(0)
            if self.session_start_time:
                end_time = self.session_end_time or datetime.now()
                duration = end_time - self.session_start_time
            
            # Get strategy performance
            strategy_performance = {}
            if self.strategy_manager:
                strategy_performance = self.strategy_manager.get_strategy_performance()
            
            # Get risk metrics
            risk_metrics = {}
            if self.risk_manager:
                risk_metrics = self.risk_manager.get_daily_metrics()
            
            return {
                'session_state': self.session_state,
                'mode': self.mode,
                'session_duration': str(duration),
                'session_start_time': self.session_start_time.isoformat() if self.session_start_time else None,
                'session_end_time': self.session_end_time.isoformat() if self.session_end_time else None,
                'total_trades': self.trade_count,
                'active_trades': len(self.active_trades),
                'session_pnl': self.session_pnl,
                'daily_pnl': self.daily_pnl,
                'evaluation_count': self.evaluation_count,
                'error_count': self.error_count,
                'last_evaluation': self.last_evaluation_time.isoformat() if self.last_evaluation_time else None,
                'emergency_stop_active': self.emergency_stop_active,
                'strategy_performance': strategy_performance,
                'risk_metrics': risk_metrics.__dict__ if hasattr(risk_metrics, '__dict__') else risk_metrics
            }
            
        except Exception as e:
            logger.error(f"Error generating session summary: {e}")
            return {'error': str(e)}
    
    def handle_emergency_stop(self) -> None:
        """Handle emergency stop activation"""
        try:
            logger.critical("Handling emergency stop")
            
            # Stop the trading session
            self.stop_trading_session(force=True)
            
            # Close all positions
            self._close_all_positions("Emergency stop - manual activation")
            
            # Set emergency state
            self.session_state = TradingSessionState.ERROR
            self.emergency_stop_active = True
            
        except Exception as e:
            logger.error(f"Error handling emergency stop: {e}")
    
    def _signal_handler(self, signum, frame):
        """Handle system signals for graceful shutdown"""
        logger.info(f"Received signal {signum} - initiating graceful shutdown")
        self.stop_trading_session()
        sys.exit(0)
    
    def cleanup(self) -> None:
        """Cleanup all resources"""
        try:
            logger.info("Cleaning up trading manager resources")
            
            # Stop session if running
            if self.session_state == TradingSessionState.RUNNING:
                self.stop_trading_session()
            
            # Cleanup components
            if self.order_manager:
                self.order_manager.cleanup()
            
            if self.risk_manager:
                self.risk_manager.cleanup()
            
            if self.api_client:
                self.api_client.cleanup()
            
            if self.logging_manager:
                self.logging_manager.cleanup()
            
            if self.notification_manager:
                self.notification_manager.cleanup()
            
            if self.emergency_controller:
                self.emergency_controller.cleanup()
            
            if self.safety_monitor:
                self.safety_monitor.cleanup()
            
            logger.info("Trading manager cleanup completed")
            
        except Exception as e:
            logger.error(f"Error during cleanup: {e}")
    
    def __enter__(self):
        """Context manager entry"""
        return self
    
    def __exit__(self, exc_type, exc_val, exc_tb):
        """Context manager exit"""
        self.cleanup()