#!/usr/bin/env python3
"""
Simple test to validate that the lot size updates are working correctly.
This test can be run independently to verify the changes.
"""

import sys
import os
from pathlib import Path

# Add src to path
sys.path.insert(0, str(Path(__file__).parent / "src"))

def test_constants():
    """Test that constants are correctly defined"""
    print("🔍 Testing Constants...")
    
    try:
        from constants import BANKNIFTY_LOT_SIZE, validate_quantity, round_to_lot_size
        
        # Test lot size value
        assert BANKNIFTY_LOT_SIZE == 35, f"Expected lot size 35, got {BANKNIFTY_LOT_SIZE}"
        print(f"✅ Lot size constant: {BANKNIFTY_LOT_SIZE}")
        
        # Test validation function
        assert validate_quantity(35) == True, "35 should be valid"
        assert validate_quantity(70) == True, "70 should be valid"
        assert validate_quantity(25) == False, "25 should be invalid"
        assert validate_quantity(50) == False, "50 should be invalid"
        print("✅ Quantity validation working")
        
        # Test rounding function
        assert round_to_lot_size(30) == 35, "30 should round to 35"
        assert round_to_lot_size(60) == 70, "60 should round to 70"
        assert round_to_lot_size(100) == 105, "100 should round to 105"
        print("✅ Quantity rounding working")
        
    except Exception as e:
        print(f"❌ Constants test failed: {e}")
        return False
    
    return True

def test_data_models():
    """Test that data models use correct lot size"""
    print("\n🔍 Testing Data Models...")
    
    try:
        from models.trading_models import Option
        
        # Test default lot size in Option model
        option = Option(
            symbol="BANKNIFTY25DEC2450000CE",
            token="12345",
            ltp=100.0,
            bid=99.5,
            ask=100.5,
            volume=1000,
            oi=5000
        )
        
        assert option.lot_size == 35, f"Expected lot size 35, got {option.lot_size}"
        print(f"✅ Option model lot size: {option.lot_size}")
        
    except Exception as e:
        print(f"❌ Data models test failed: {e}")
        return False
    
    return True

def test_configuration():
    """Test that configuration files have correct values"""
    print("\n🔍 Testing Configuration...")
    
    try:
        import yaml
        
        # Test live trading config
        with open("config/live_trading_config.yaml", 'r') as f:
            live_config = yaml.safe_load(f)
        
        max_pos = live_config['risk']['max_position_size']
        assert max_pos % 35 == 0, f"max_position_size {max_pos} should be multiple of 35"
        print(f"✅ Live config max_position_size: {max_pos}")
        
        # Test example config
        with open("config/trading_config.example.yaml", 'r') as f:
            example_config = yaml.safe_load(f)
        
        max_pos_ex = example_config['risk']['max_position_size']
        assert max_pos_ex % 35 == 0, f"max_position_size {max_pos_ex} should be multiple of 35"
        print(f"✅ Example config max_position_size: {max_pos_ex}")
        
    except Exception as e:
        print(f"❌ Configuration test failed: {e}")
        return False
    
    return True

def test_data_manager():
    """Test that data manager uses correct lot size"""
    print("\n🔍 Testing Data Manager...")
    
    try:
        from data.data_manager import DataManager
        from config.config_manager import ConfigManager
        from api.angel_api_client import AngelAPIClient
        
        # Create mock config manager
        class MockConfigManager:
            def get_config(self):
                return {
                    'cache_ttl_seconds': 300,
                    'max_strike_distance': 0.05,
                    'default_lot_size': 35,
                    'default_strike_spacing': 100.0,
                    'enable_caching': True,
                }
        
        # Create mock API client
        class MockAPIClient:
            pass
        
        config_manager = MockConfigManager()
        api_client = MockAPIClient()
        
        data_manager = DataManager(api_client, config_manager)
        
        # Check that default lot size is correct
        assert data_manager.config['default_lot_size'] == 35, \
            f"Expected default_lot_size 35, got {data_manager.config['default_lot_size']}"
        print(f"✅ Data manager default lot size: {data_manager.config['default_lot_size']}")
        
    except Exception as e:
        print(f"❌ Data manager test failed: {e}")
        return False
    
    return True

def main():
    """Run all validation tests"""
    print("🚀 Bank Nifty Lot Size Validation Tests")
    print("=" * 50)
    
    tests = [
        test_constants,
        test_data_models,
        test_configuration,
        test_data_manager
    ]
    
    passed = 0
    failed = 0
    
    for test in tests:
        try:
            if test():
                passed += 1
            else:
                failed += 1
        except Exception as e:
            print(f"❌ Test {test.__name__} crashed: {e}")
            failed += 1
    
    print("\n" + "=" * 50)
    print(f"📊 Test Results: {passed} passed, {failed} failed")
    
    if failed == 0:
        print("🎉 All lot size validations passed!")
        print("✅ Bank Nifty lot size successfully updated to 35")
        return True
    else:
        print("❌ Some validations failed - check the errors above")
        return False

if __name__ == "__main__":
    success = main()
    sys.exit(0 if success else 1)