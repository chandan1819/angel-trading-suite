#!/usr/bin/env python3
"""
Backtesting Engine Demo

This script demonstrates how to use the backtesting engine
to analyze strategy performance on historical data.
"""

import sys
import os
from datetime import datetime, timedelta
from unittest.mock import Mock

# Add src to path for imports
sys.path.append(os.path.join(os.path.dirname(__file__), '..'))

from src.backtesting import BacktestingEngine, BacktestResult, PerformanceMetrics
from src.models.trading_models import TradingSignal, SignalType, OptionType
from src.strategies.base_strategy import BaseStrategy


class SimpleStraddleStrategy(BaseStrategy):
    """Simple straddle strategy for demo purposes"""
    
    def __init__(self):
        super().__init__("SimpleStraddle", {
            'enabled': True,
            'min_confidence': 0.6,
            'target_profit_per_trade': 2000.0,
            'max_loss_per_trade': 1000.0
        })
    
    def evaluate(self, market_data):
        """Generate straddle signal based on simple conditions"""
        try:
            options_chain = market_data.get('options_chain', {})
            underlying_price = market_data.get('underlying_price', 0)
            
            if not options_chain or underlying_price <= 0:
                return None
            
            # Simple condition: create straddle if underlying is near round number
            atm_strike = options_chain.get('atm_strike', 0)
            
            # Generate signal with 70% confidence
            if atm_strike > 0:
                signal = TradingSignal(
                    strategy_name=self.name,
                    signal_type=SignalType.STRADDLE,
                    underlying="BANKNIFTY",
                    strikes=[atm_strike, atm_strike],
                    option_types=[OptionType.CE, OptionType.PE],
                    quantities=[25, 25],
                    confidence=0.7,
                    expiry_date="2024-01-04",
                    target_pnl=2000.0,
                    stop_loss=-1000.0
                )
                
                return signal
            
            return None
            
        except Exception as e:
            print(f"Error in strategy evaluation: {e}")
            return None


def create_mock_data_manager():
    """Create a mock data manager for demo"""
    mock_dm = Mock()
    
    # Mock historical data
    historical_data = []
    start_date = datetime(2024, 1, 1)
    
    for i in range(10):  # 10 days of data
        date = start_date + timedelta(days=i)
        price = 45000 + (i * 100)  # Trending upward
        
        data_point = {
            'date': date.strftime('%Y-%m-%d'),
            'open': price - 50,
            'high': price + 100,
            'low': price - 100,
            'close': price,
            'volume': 1000000 + (i * 10000),
            'volatility': 0.2 + (i * 0.01)
        }
        historical_data.append(data_point)
    
    mock_dm.get_historical_data.return_value = historical_data
    
    return mock_dm


def main():
    """Run backtesting demo"""
    print("=" * 60)
    print("BANK NIFTY OPTIONS BACKTESTING ENGINE DEMO")
    print("=" * 60)
    
    try:
        # Create mock data manager
        print("\n1. Setting up mock data manager...")
        data_manager = create_mock_data_manager()
        
        # Create backtesting engine
        print("2. Initializing backtesting engine...")
        config = {
            'initial_capital': 100000.0,
            'commission_per_trade': 20.0,
            'slippage_pct': 0.1,
            'fill_probability': 1.0,
            'max_trades_per_day': 3,
            'risk_free_rate': 0.06,
            'trading_hours': {'start': '09:15', 'end': '15:30'},
            'early_exit_time': '15:00'
        }
        
        engine = BacktestingEngine(data_manager, config)
        
        # Create strategy
        print("3. Creating simple straddle strategy...")
        strategy = SimpleStraddleStrategy()
        
        # Run backtest
        print("4. Running backtest...")
        print("   Start Date: 2024-01-01")
        print("   End Date: 2024-01-10")
        print("   Strategy: Simple Straddle")
        print("   Initial Capital: ₹1,00,000")
        
        result = engine.run_backtest(
            strategy=strategy,
            start_date="2024-01-01",
            end_date="2024-01-10",
            underlying_symbol="BANKNIFTY"
        )
        
        # Display results
        print("\n5. Backtest Results:")
        print("-" * 40)
        print(f"Strategy: {result.strategy_name}")
        print(f"Period: {result.start_date} to {result.end_date}")
        print(f"Initial Capital: ₹{result.initial_capital:,.2f}")
        print(f"Final Capital: ₹{result.final_capital:,.2f}")
        print(f"Total P&L: ₹{result.performance_metrics.total_pnl:,.2f}")
        print(f"Total Return: {result.performance_metrics.total_return_pct:.2f}%")
        print(f"Total Trades: {result.performance_metrics.total_trades}")
        print(f"Win Rate: {result.performance_metrics.win_rate:.2f}%")
        
        if result.performance_metrics.total_trades > 0:
            print(f"Average Trade Return: ₹{result.performance_metrics.avg_trade_return:.2f}")
            print(f"Max Drawdown: ₹{result.performance_metrics.max_drawdown:.2f}")
            print(f"Sharpe Ratio: {result.performance_metrics.sharpe_ratio:.2f}")
        
        # Generate reports
        print("\n6. Generating reports...")
        try:
            engine.generate_report(result, "demo_reports")
            print("   Reports generated in 'demo_reports' directory")
            print("   Files created:")
            print("   - CSV trade details")
            print("   - JSON performance summary")
            print("   - Trade analysis")
            print("   - Daily P&L")
            print("   - Equity curve")
        except Exception as e:
            print(f"   Report generation failed: {e}")
        
        # Display performance summary
        print("\n7. Performance Summary:")
        print("-" * 40)
        summary = engine.reporter.generate_performance_summary(result)
        print(summary)
        
        print("\n" + "=" * 60)
        print("DEMO COMPLETED SUCCESSFULLY!")
        print("=" * 60)
        
    except Exception as e:
        print(f"\nDemo failed with error: {e}")
        import traceback
        traceback.print_exc()
        return 1
    
    return 0


if __name__ == "__main__":
    exit_code = main()
    sys.exit(exit_code)