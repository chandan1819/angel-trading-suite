#!/usr/bin/env python3
"""
Direct trading system runner to avoid import issues.
This script runs the trading system directly without complex imports.
"""

import sys
import os
import argparse
import logging
from pathlib import Path

# Add src directory to Python path
current_dir = Path(__file__).parent
src_dir = current_dir / "src"
sys.path.insert(0, str(src_dir))
sys.path.insert(0, str(current_dir))

def setup_logging(level="INFO"):
    """Setup basic logging"""
    logging.basicConfig(
        level=getattr(logging, level.upper()),
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
        handlers=[logging.StreamHandler(sys.stdout)]
    )

def run_paper_trading():
    """Run a simple paper trading test"""
    try:
        print("🧪 Starting Paper Trading Test...")
        print("=" * 50)
        
        # Import required modules
        from config.config_manager import ConfigManager
        from models.config_models import TradingMode
        
        # Load configuration
        config_file = "config/live_trading_config.yaml"
        if not os.path.exists(config_file):
            config_file = "config/trading_config.example.yaml"
        
        print(f"📄 Loading configuration from: {config_file}")
        config_manager = ConfigManager()
        config = config_manager.load_config(config_file)
        
        # Force paper mode for safety
        config.mode = TradingMode.PAPER
        print(f"🔒 Mode set to: {config.mode.value}")
        
        # Test API credentials
        print("🔑 Testing API credentials...")
        api_key = os.getenv('ANGEL_API_KEY')
        client_code = os.getenv('ANGEL_CLIENT_CODE')
        
        if not api_key or not client_code:
            print("❌ API credentials not found in environment variables")
            print("Please set up your credentials first:")
            print("export ANGEL_API_KEY='your_api_key'")
            print("export ANGEL_CLIENT_CODE='your_client_code'")
            print("export ANGEL_PIN='your_pin'")
            print("export ANGEL_TOTP_SECRET='your_totp_secret'")
            return False
        
        print(f"✅ API Key found: {api_key[:10]}...")
        print(f"✅ Client Code found: {client_code}")
        
        # Test basic system components
        print("🔧 Testing system components...")
        
        # Test configuration validation
        if config.validate():
            print("✅ Configuration validation passed")
        else:
            print("❌ Configuration validation failed")
            return False
        
        # Test API client initialization
        try:
            from api.angel_api_client import AngelAPIClient
            api_client = AngelAPIClient(config.api)
            print("✅ API client created successfully")
        except Exception as e:
            print(f"❌ API client creation failed: {e}")
            return False
        
        # Test risk manager
        try:
            from risk.risk_manager import RiskManager
            risk_manager = RiskManager(config.risk)
            print("✅ Risk manager created successfully")
        except Exception as e:
            print(f"❌ Risk manager creation failed: {e}")
            return False
        
        print("=" * 50)
        print("🎉 Paper trading test completed successfully!")
        print("✅ System is ready for trading")
        print("")
        print("Next steps:")
        print("1. Test with: python3 run_trading.py --test")
        print("2. Run paper trading: python3 run_trading.py --paper")
        print("3. For live trading: python3 run_trading.py --live (BE CAREFUL!)")
        
        return True
        
    except Exception as e:
        print(f"❌ Paper trading test failed: {e}")
        import traceback
        traceback.print_exc()
        return False

def run_live_trading():
    """Run live trading with safety checks"""
    print("🚨 WARNING: This will start LIVE TRADING with real money!")
    print("=" * 60)
    
    # Safety confirmation
    confirm = input("Type 'YES' to confirm live trading: ")
    if confirm != 'YES':
        print("Live trading cancelled for safety.")
        return False
    
    try:
        from config.config_manager import ConfigManager
        from trading.trading_manager import TradingManager
        from models.config_models import TradingMode
        
        # Load configuration
        config_file = "config/live_trading_config.yaml"
        config_manager = ConfigManager()
        config = config_manager.load_config(config_file)
        
        # Ensure live mode
        config.mode = TradingMode.LIVE
        
        print("🚀 Starting live trading...")
        trading_manager = TradingManager(config, 'live')
        
        if trading_manager.initialize():
            print("✅ Trading manager initialized")
            success = trading_manager.start_trading_session(continuous=True)
            if success:
                print("✅ Live trading session started")
                return True
            else:
                print("❌ Failed to start trading session")
                return False
        else:
            print("❌ Failed to initialize trading manager")
            return False
            
    except Exception as e:
        print(f"❌ Live trading failed: {e}")
        import traceback
        traceback.print_exc()
        return False

def main():
    """Main function"""
    parser = argparse.ArgumentParser(description="Bank Nifty Options Trading System")
    parser.add_argument('--test', action='store_true', help='Run system test')
    parser.add_argument('--paper', action='store_true', help='Run paper trading')
    parser.add_argument('--live', action='store_true', help='Run live trading (DANGEROUS!)')
    parser.add_argument('--log-level', default='INFO', help='Logging level')
    
    args = parser.parse_args()
    
    # Setup logging
    setup_logging(args.log_level)
    
    if args.test or args.paper:
        success = run_paper_trading()
        sys.exit(0 if success else 1)
    elif args.live:
        success = run_live_trading()
        sys.exit(0 if success else 1)
    else:
        print("Bank Nifty Options Trading System")
        print("=" * 40)
        print("Usage:")
        print("  --test    Run system test")
        print("  --paper   Run paper trading")
        print("  --live    Run live trading (BE CAREFUL!)")
        print("")
        print("Start with: python3 run_trading.py --test")

if __name__ == '__main__':
    main()