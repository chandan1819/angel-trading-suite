#!/usr/bin/env python3
"""
Demonstration script for the Bank Nifty Options Trading System setup.

This script demonstrates that the project structure and core interfaces
are properly set up and can be imported and used.
"""

import sys
import os
from pathlib import Path

# Add src to path for imports
sys.path.insert(0, str(Path(__file__).parent / "src"))

def main():
    """Demonstrate the trading system setup"""
    
    print("=== Bank Nifty Options Trading System Setup Demo ===\n")
    
    # Test imports
    print("1. Testing core imports...")
    try:
        from src.models import (
            TradingConfig, TradingSignal, Trade, Option, OptionsChain,
            TradingMode, SignalType, OptionType
        )
        print("   ✓ Models imported successfully")
    except ImportError as e:
        print(f"   ✗ Failed to import models: {e}")
        return False
    
    try:
        from src.config import ConfigManager, ConfigurationError
        print("   ✓ Configuration manager imported successfully")
    except ImportError as e:
        print(f"   ✗ Failed to import config manager: {e}")
        return False
    
    try:
        from src.interfaces import (
            IDataProvider, IStrategy, IRiskManager, BaseStrategy,
            TradingSystemError
        )
        print("   ✓ Interfaces imported successfully")
    except ImportError as e:
        print(f"   ✗ Failed to import interfaces: {e}")
        return False
    
    # Test configuration management
    print("\n2. Testing configuration management...")
    try:
        config_manager = ConfigManager("config")
        default_config = config_manager.create_default_config("demo_config.yaml")
        print(f"   ✓ Created default configuration in {default_config.mode.value} mode")
        print(f"   ✓ Underlying symbol: {default_config.underlying_symbol}")
        print(f"   ✓ Profit target: ₹{default_config.risk.profit_target}")
        print(f"   ✓ Stop loss: ₹{default_config.risk.stop_loss}")
    except Exception as e:
        print(f"   ✗ Configuration management failed: {e}")
        return False
    
    # Test data models
    print("\n3. Testing data models...")
    try:
        # Create a sample option
        option = Option(
            symbol="BANKNIFTY2409050000CE",
            token="12345",
            strike_price=50000.0,
            option_type=OptionType.CE,
            expiry_date="2024-09-05",
            ltp=150.0,
            bid=148.0,
            ask=152.0,
            volume=1000,
            oi=5000
        )
        
        if option.validate():
            print(f"   ✓ Created valid option: {option.symbol}")
            print(f"   ✓ Bid-ask spread: ₹{option.bid_ask_spread}")
            print(f"   ✓ Mid price: ₹{option.mid_price}")
        else:
            print("   ✗ Option validation failed")
            return False
        
        # Create a sample trading signal
        signal = TradingSignal(
            strategy_name="demo_strategy",
            signal_type=SignalType.BUY,
            underlying="BANKNIFTY",
            strikes=[50000.0],
            option_types=[OptionType.CE],
            quantities=[25],
            confidence=0.8,
            expiry_date="2024-09-05"
        )
        
        if signal.validate():
            print(f"   ✓ Created valid trading signal: {signal.signal_type.value}")
            print(f"   ✓ Confidence: {signal.confidence}")
            print(f"   ✓ Total quantity: {signal.total_quantity}")
        else:
            print("   ✗ Trading signal validation failed")
            return False
        
    except Exception as e:
        print(f"   ✗ Data model testing failed: {e}")
        return False
    
    # Test base strategy interface
    print("\n4. Testing strategy interface...")
    try:
        class DemoStrategy(BaseStrategy):
            def evaluate(self, market_data):
                # Simple demo implementation
                return TradingSignal(
                    strategy_name=self.name,
                    signal_type=SignalType.BUY,
                    underlying="BANKNIFTY",
                    strikes=[50000.0],
                    option_types=[OptionType.CE],
                    quantities=[25],
                    confidence=0.7
                )
        
        demo_strategy = DemoStrategy("demo", {"enabled": True, "weight": 1.0})
        print(f"   ✓ Created strategy: {demo_strategy.get_name()}")
        
        # Test signal generation
        test_signal = demo_strategy.evaluate({})
        if demo_strategy.validate_signal(test_signal):
            print("   ✓ Strategy signal validation passed")
        else:
            print("   ✗ Strategy signal validation failed")
            return False
        
    except Exception as e:
        print(f"   ✗ Strategy interface testing failed: {e}")
        return False
    
    print("\n=== Setup Demo Completed Successfully! ===")
    print("\nNext steps:")
    print("1. Set up environment variables for API credentials")
    print("2. Customize configuration in config/trading_config.yaml")
    print("3. Implement specific trading strategies")
    print("4. Run the trading system in paper mode for testing")
    
    return True


if __name__ == "__main__":
    success = main()
    sys.exit(0 if success else 1)