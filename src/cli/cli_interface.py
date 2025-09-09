"""
Command-Line Interface for the Bank Nifty Options Trading System.

This module provides a comprehensive CLI for running the trading system
with various modes and options.
"""

import argparse
import sys
import os
import logging
from pathlib import Path
from typing import Optional, Dict, Any
import signal
import time

# Add src to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent))

from config.config_manager import ConfigManager
from models.config_models import TradingConfig, TradingMode
from trading.trading_manager import TradingManager
from backtesting.backtesting_engine import BacktestingEngine


class CLIInterface:
    """
    Command-line interface for the Bank Nifty Options Trading System.
    
    Provides commands for:
    - Running live/paper trading sessions
    - Backtesting strategies
    - Configuration management
    - System monitoring
    """
    
    def __init__(self):
        self.config_manager = ConfigManager()
        self.trading_manager: Optional[TradingManager] = None
        self.logger = self._setup_logging()
        
    def _setup_logging(self) -> logging.Logger:
        """Setup basic logging for CLI"""
        logging.basicConfig(
            level=logging.INFO,
            format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
            handlers=[
                logging.StreamHandler(sys.stdout)
            ]
        )
        return logging.getLogger(__name__)
    
    def create_parser(self) -> argparse.ArgumentParser:
        """Create and configure argument parser"""
        parser = argparse.ArgumentParser(
            description="Bank Nifty Options Trading System",
            formatter_class=argparse.RawDescriptionHelpFormatter,
            epilog="""
Examples:
  # Run paper trading session continuously
  python -m src.cli.cli_interface trade --mode paper --continuous --interval 30
  
  # Run single evaluation in live mode
  python -m src.cli.cli_interface trade --mode live --once
  
  # Run backtest for straddle strategy
  python -m src.cli.cli_interface backtest --strategy straddle --start 2024-01-01 --end 2024-12-31
  
  # Create default configuration
  python -m src.cli.cli_interface config --create-default
  
  # Validate configuration
  python -m src.cli.cli_interface config --validate
            """
        )
        
        # Global options
        parser.add_argument(
            '--config', '-c',
            type=str,
            default='trading_config.yaml',
            help='Configuration file path (default: trading_config.yaml)'
        )
        
        parser.add_argument(
            '--log-level',
            choices=['DEBUG', 'INFO', 'WARNING', 'ERROR', 'CRITICAL'],
            default='INFO',
            help='Logging level (default: INFO)'
        )
        
        parser.add_argument(
            '--log-file',
            type=str,
            help='Log file path (optional)'
        )
        
        # Subcommands
        subparsers = parser.add_subparsers(dest='command', help='Available commands')
        
        # Trading command
        trade_parser = subparsers.add_parser('trade', help='Run trading session')
        self._add_trade_arguments(trade_parser)
        
        # Backtesting command
        backtest_parser = subparsers.add_parser('backtest', help='Run backtesting')
        self._add_backtest_arguments(backtest_parser)
        
        # Configuration command
        config_parser = subparsers.add_parser('config', help='Configuration management')
        self._add_config_arguments(config_parser)
        
        # Status command
        status_parser = subparsers.add_parser('status', help='Show system status')
        self._add_status_arguments(status_parser)
        
        return parser
    
    def _add_trade_arguments(self, parser: argparse.ArgumentParser) -> None:
        """Add trading-specific arguments"""
        parser.add_argument(
            '--mode', '-m',
            choices=['paper', 'live'],
            default='paper',
            help='Trading mode (default: paper)'
        )
        
        # Execution mode (mutually exclusive)
        exec_group = parser.add_mutually_exclusive_group()
        exec_group.add_argument(
            '--continuous',
            action='store_true',
            help='Run continuously with polling'
        )
        exec_group.add_argument(
            '--once',
            action='store_true',
            help='Execute single evaluation and exit'
        )
        
        parser.add_argument(
            '--interval', '-i',
            type=int,
            default=30,
            help='Polling interval in seconds for continuous mode (default: 30)'
        )
        
        parser.add_argument(
            '--strategies',
            nargs='+',
            choices=['straddle', 'directional', 'iron_condor', 'greeks', 'volatility'],
            help='Specific strategies to enable (overrides config)'
        )
        
        parser.add_argument(
            '--max-trades',
            type=int,
            help='Maximum concurrent trades (overrides config)'
        )
        
        parser.add_argument(
            '--daily-loss-limit',
            type=float,
            help='Daily loss limit in rupees (overrides config)'
        )
        
        parser.add_argument(
            '--emergency-stop-file',
            type=str,
            default='emergency_stop.txt',
            help='Emergency stop file path (default: emergency_stop.txt)'
        )
    
    def _add_backtest_arguments(self, parser: argparse.ArgumentParser) -> None:
        """Add backtesting-specific arguments"""
        parser.add_argument(
            '--strategy',
            choices=['straddle', 'directional', 'iron_condor', 'greeks', 'volatility', 'all'],
            default='all',
            help='Strategy to backtest (default: all)'
        )
        
        parser.add_argument(
            '--start', '-s',
            type=str,
            required=True,
            help='Start date (YYYY-MM-DD)'
        )
        
        parser.add_argument(
            '--end', '-e',
            type=str,
            required=True,
            help='End date (YYYY-MM-DD)'
        )
        
        parser.add_argument(
            '--output-dir',
            type=str,
            default='backtest_results',
            help='Output directory for results (default: backtest_results)'
        )
        
        parser.add_argument(
            '--initial-capital',
            type=float,
            default=100000.0,
            help='Initial capital for backtesting (default: 100000)'
        )
        
        parser.add_argument(
            '--format',
            choices=['csv', 'json', 'both'],
            default='both',
            help='Output format (default: both)'
        )
    
    def _add_config_arguments(self, parser: argparse.ArgumentParser) -> None:
        """Add configuration-specific arguments"""
        config_group = parser.add_mutually_exclusive_group(required=True)
        
        config_group.add_argument(
            '--create-default',
            action='store_true',
            help='Create default configuration file'
        )
        
        config_group.add_argument(
            '--validate',
            action='store_true',
            help='Validate configuration file'
        )
        
        config_group.add_argument(
            '--show',
            action='store_true',
            help='Show current configuration'
        )
        
        parser.add_argument(
            '--output',
            type=str,
            help='Output file for configuration operations'
        )
    
    def _add_status_arguments(self, parser: argparse.ArgumentParser) -> None:
        """Add status-specific arguments"""
        parser.add_argument(
            '--detailed',
            action='store_true',
            help='Show detailed status information'
        )
        
        parser.add_argument(
            '--refresh',
            type=int,
            help='Auto-refresh interval in seconds'
        )
    
    def run(self, args: Optional[list] = None) -> int:
        """
        Run the CLI interface.
        
        Args:
            args: Command line arguments (None to use sys.argv)
            
        Returns:
            Exit code (0 for success, non-zero for error)
        """
        try:
            parser = self.create_parser()
            parsed_args = parser.parse_args(args)
            
            # Setup logging
            self._configure_logging(parsed_args)
            
            # Handle commands
            if parsed_args.command == 'trade':
                return self._handle_trade_command(parsed_args)
            elif parsed_args.command == 'backtest':
                return self._handle_backtest_command(parsed_args)
            elif parsed_args.command == 'config':
                return self._handle_config_command(parsed_args)
            elif parsed_args.command == 'status':
                return self._handle_status_command(parsed_args)
            else:
                parser.print_help()
                return 1
                
        except KeyboardInterrupt:
            self.logger.info("Operation cancelled by user")
            return 130  # Standard exit code for Ctrl+C
        except Exception as e:
            self.logger.error(f"Unexpected error: {e}")
            return 1
    
    def _configure_logging(self, args: argparse.Namespace) -> None:
        """Configure logging based on CLI arguments"""
        level = getattr(logging, args.log_level.upper())
        
        # Configure root logger
        root_logger = logging.getLogger()
        root_logger.setLevel(level)
        
        # Clear existing handlers
        for handler in root_logger.handlers[:]:
            root_logger.removeHandler(handler)
        
        # Console handler
        console_handler = logging.StreamHandler(sys.stdout)
        console_formatter = logging.Formatter(
            '%(asctime)s - %(name)s - %(levelname)s - %(message)s'
        )
        console_handler.setFormatter(console_formatter)
        root_logger.addHandler(console_handler)
        
        # File handler if specified
        if args.log_file:
            file_handler = logging.FileHandler(args.log_file)
            file_formatter = logging.Formatter(
                '%(asctime)s - %(name)s - %(levelname)s - %(message)s'
            )
            file_handler.setFormatter(file_formatter)
            root_logger.addHandler(file_handler)
    
    def _handle_trade_command(self, args: argparse.Namespace) -> int:
        """Handle trade command"""
        try:
            self.logger.info(f"Starting trading session in {args.mode} mode")
            
            # Load configuration
            config = self._load_config(args.config)
            if not config:
                return 1
            
            # Apply CLI overrides
            config = self._apply_trade_overrides(config, args)
            
            # Initialize trading manager
            self.trading_manager = TradingManager(config, args.mode)
            
            if not self.trading_manager.initialize():
                self.logger.error("Failed to initialize trading manager")
                return 1
            
            # Setup signal handlers for graceful shutdown
            def signal_handler(signum, frame):
                self.logger.info("Received shutdown signal")
                if self.trading_manager:
                    self.trading_manager.stop_trading_session()
                sys.exit(0)
            
            signal.signal(signal.SIGINT, signal_handler)
            signal.signal(signal.SIGTERM, signal_handler)
            
            # Determine execution mode
            if args.once:
                # Single execution
                success = self.trading_manager.start_trading_session(
                    continuous=False
                )
                return 0 if success else 1
            else:
                # Continuous mode (default)
                success = self.trading_manager.start_trading_session(
                    continuous=True,
                    polling_interval=args.interval
                )
                
                if success:
                    self.logger.info(f"Trading session started. Polling every {args.interval}s")
                    self.logger.info("Press Ctrl+C to stop gracefully")
                    
                    # Keep main thread alive
                    try:
                        while self.trading_manager.session_state == "running":
                            time.sleep(1)
                    except KeyboardInterrupt:
                        self.logger.info("Stopping trading session...")
                        self.trading_manager.stop_trading_session()
                    
                    return 0
                else:
                    return 1
                    
        except Exception as e:
            self.logger.error(f"Error in trade command: {e}")
            return 1
        finally:
            if self.trading_manager:
                self.trading_manager.cleanup()
    
    def _handle_backtest_command(self, args: argparse.Namespace) -> int:
        """Handle backtest command"""
        try:
            self.logger.info(f"Starting backtest for {args.strategy} strategy")
            
            # Load configuration
            config = self._load_config(args.config)
            if not config:
                return 1
            
            # Create output directory
            output_dir = Path(args.output_dir)
            output_dir.mkdir(exist_ok=True)
            
            # Initialize backtesting engine
            from api.angel_api_client import AngelAPIClient
            from data.data_manager import DataManager
            from strategies.strategy_manager import StrategyManager
            
            api_client = AngelAPIClient(config.api)
            if not api_client.initialize():
                self.logger.error("Failed to initialize API client for backtesting")
                return 1
            
            data_manager = DataManager(api_client)
            strategy_manager = StrategyManager(data_manager, {})
            
            backtest_engine = BacktestingEngine(
                data_manager=data_manager,
                strategy_manager=strategy_manager,
                config=config.backtest
            )
            
            # Run backtest
            result = backtest_engine.run_backtest(
                start_date=args.start,
                end_date=args.end,
                strategy_name=args.strategy,
                initial_capital=args.initial_capital
            )
            
            if result:
                # Generate reports
                backtest_engine.generate_report(result, output_dir, args.format)
                self.logger.info(f"Backtest completed. Results saved to {output_dir}")
                
                # Print summary
                self._print_backtest_summary(result)
                return 0
            else:
                self.logger.error("Backtest failed")
                return 1
                
        except Exception as e:
            self.logger.error(f"Error in backtest command: {e}")
            return 1
    
    def _handle_config_command(self, args: argparse.Namespace) -> int:
        """Handle config command"""
        try:
            if args.create_default:
                output_file = args.output or args.config
                config = self.config_manager.create_default_config(output_file)
                self.logger.info(f"Default configuration created: {output_file}")
                return 0
                
            elif args.validate:
                config = self._load_config(args.config)
                if config and config.validate():
                    self.logger.info("Configuration is valid")
                    return 0
                else:
                    self.logger.error("Configuration validation failed")
                    return 1
                    
            elif args.show:
                config = self._load_config(args.config)
                if config:
                    self._print_config(config)
                    return 0
                else:
                    return 1
                    
        except Exception as e:
            self.logger.error(f"Error in config command: {e}")
            return 1
    
    def _handle_status_command(self, args: argparse.Namespace) -> int:
        """Handle status command"""
        try:
            if args.refresh:
                # Continuous status monitoring
                while True:
                    os.system('clear' if os.name == 'posix' else 'cls')
                    self._print_system_status(args.detailed)
                    time.sleep(args.refresh)
            else:
                # Single status check
                self._print_system_status(args.detailed)
                return 0
                
        except KeyboardInterrupt:
            return 0
        except Exception as e:
            self.logger.error(f"Error in status command: {e}")
            return 1
    
    def _load_config(self, config_file: str) -> Optional[TradingConfig]:
        """Load configuration file"""
        try:
            config = self.config_manager.load_config(config_file)
            self.logger.info(f"Configuration loaded from {config_file}")
            return config
        except Exception as e:
            self.logger.error(f"Failed to load configuration: {e}")
            return None
    
    def _apply_trade_overrides(self, config: TradingConfig, 
                             args: argparse.Namespace) -> TradingConfig:
        """Apply CLI argument overrides to configuration"""
        # Override trading mode
        if args.mode:
            config.mode = TradingMode(args.mode)
        
        # Override strategy selection
        if args.strategies:
            # Disable all strategies first
            config.strategy.straddle.enabled = False
            config.strategy.directional.enabled = False
            config.strategy.iron_condor.enabled = False
            config.strategy.greeks.enabled = False
            config.strategy.volatility.enabled = False
            
            # Enable selected strategies
            for strategy in args.strategies:
                if strategy == 'straddle':
                    config.strategy.straddle.enabled = True
                elif strategy == 'directional':
                    config.strategy.directional.enabled = True
                elif strategy == 'iron_condor':
                    config.strategy.iron_condor.enabled = True
                elif strategy == 'greeks':
                    config.strategy.greeks.enabled = True
                elif strategy == 'volatility':
                    config.strategy.volatility.enabled = True
        
        # Override risk parameters
        if args.max_trades:
            config.risk.max_concurrent_trades = args.max_trades
        
        if args.daily_loss_limit:
            config.risk.max_daily_loss = args.daily_loss_limit
        
        if args.emergency_stop_file:
            config.risk.emergency_stop_file = args.emergency_stop_file
        
        return config
    
    def _print_backtest_summary(self, result: Dict[str, Any]) -> None:
        """Print backtest summary to console"""
        print("\n" + "="*60)
        print("BACKTEST SUMMARY")
        print("="*60)
        
        metrics = result.get('performance_metrics', {})
        
        print(f"Strategy: {result.get('strategy_name', 'Unknown')}")
        print(f"Period: {result.get('start_date')} to {result.get('end_date')}")
        print(f"Total Trades: {metrics.get('total_trades', 0)}")
        print(f"Winning Trades: {metrics.get('winning_trades', 0)}")
        print(f"Losing Trades: {metrics.get('losing_trades', 0)}")
        print(f"Win Rate: {metrics.get('win_rate', 0):.2%}")
        print(f"Total P&L: ₹{metrics.get('total_pnl', 0):,.2f}")
        print(f"Max Drawdown: ₹{metrics.get('max_drawdown', 0):,.2f}")
        print(f"Average Trade: ₹{metrics.get('avg_trade_pnl', 0):,.2f}")
        print(f"Sharpe Ratio: {metrics.get('sharpe_ratio', 0):.2f}")
        print("="*60)
    
    def _print_config(self, config: TradingConfig) -> None:
        """Print configuration to console"""
        print("\n" + "="*60)
        print("CONFIGURATION")
        print("="*60)
        
        print(f"Mode: {config.mode.value}")
        print(f"API Timeout: {config.api.timeout}s")
        print(f"Max Daily Loss: ₹{config.risk.max_daily_loss:,.2f}")
        print(f"Max Concurrent Trades: {config.risk.max_concurrent_trades}")
        print(f"Profit Target: ₹{config.risk.profit_target:,.2f}")
        print(f"Stop Loss: ₹{config.risk.stop_loss:,.2f}")
        
        print("\nEnabled Strategies:")
        if config.strategy.straddle.enabled:
            print("  - Straddle")
        if config.strategy.directional.enabled:
            print("  - Directional")
        if config.strategy.iron_condor.enabled:
            print("  - Iron Condor")
        if config.strategy.greeks.enabled:
            print("  - Greeks")
        if config.strategy.volatility.enabled:
            print("  - Volatility")
        
        print("="*60)
    
    def _print_system_status(self, detailed: bool = False) -> None:
        """Print system status to console"""
        print("\n" + "="*60)
        print("SYSTEM STATUS")
        print("="*60)
        
        # Check if trading manager is running
        if self.trading_manager:
            summary = self.trading_manager.get_session_summary()
            
            print(f"Session State: {summary.get('session_state', 'Unknown')}")
            print(f"Mode: {summary.get('mode', 'Unknown')}")
            print(f"Active Trades: {summary.get('active_trades', 0)}")
            print(f"Total Trades: {summary.get('total_trades', 0)}")
            print(f"Session P&L: ₹{summary.get('session_pnl', 0):,.2f}")
            print(f"Daily P&L: ₹{summary.get('daily_pnl', 0):,.2f}")
            
            if detailed:
                print(f"\nDetailed Information:")
                print(f"Session Duration: {summary.get('session_duration', 'N/A')}")
                print(f"Evaluation Count: {summary.get('evaluation_count', 0)}")
                print(f"Error Count: {summary.get('error_count', 0)}")
                print(f"Emergency Stop: {summary.get('emergency_stop_active', False)}")
                
                # Strategy performance
                strategy_perf = summary.get('strategy_performance', {})
                if strategy_perf:
                    print("\nStrategy Performance:")
                    for strategy, perf in strategy_perf.items():
                        print(f"  {strategy}: {perf.get('total_signals', 0)} signals, "
                              f"{perf.get('success_rate', 0):.2%} success rate")
        else:
            print("Trading Manager: Not Running")
            print("Status: Stopped")
        
        # Check emergency stop file
        emergency_file = "emergency_stop.txt"
        if os.path.exists(emergency_file):
            print(f"\n⚠️  EMERGENCY STOP ACTIVE: {emergency_file}")
        
        print("="*60)


def main():
    """Main entry point for CLI"""
    cli = CLIInterface()
    exit_code = cli.run()
    sys.exit(exit_code)


if __name__ == '__main__':
    main()