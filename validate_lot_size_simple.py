#!/usr/bin/env python3
"""
Simple validation script to check that lot size updates are correct.
"""

import sys
import os
from pathlib import Path

def check_constants_file():
    """Check that constants file has correct values"""
    print("🔍 Checking constants file...")
    
    try:
        constants_file = Path("src/constants.py")
        if not constants_file.exists():
            print("❌ Constants file not found")
            return False
        
        content = constants_file.read_text()
        
        if "BANKNIFTY_LOT_SIZE = 35" in content:
            print("✅ Constants file has correct lot size (35)")
            return True
        else:
            print("❌ Constants file does not have correct lot size")
            return False
            
    except Exception as e:
        print(f"❌ Error checking constants: {e}")
        return False

def check_config_files():
    """Check configuration files"""
    print("\n🔍 Checking configuration files...")
    
    files_to_check = [
        ("config/live_trading_config.yaml", "max_position_size: 35"),
        ("config/trading_config.example.yaml", "max_position_size: 105"),
        ("src/models/trading_models.py", "lot_size: int = 35"),
        ("src/data/data_manager.py", "'default_lot_size': 35"),
        ("src/orders/order_validator.py", "config.get('lot_size', 35)")
    ]
    
    passed = 0
    for file_path, expected_content in files_to_check:
        try:
            if Path(file_path).exists():
                content = Path(file_path).read_text()
                if expected_content in content:
                    print(f"✅ {file_path} - Updated")
                    passed += 1
                else:
                    print(f"❌ {file_path} - Not updated")
            else:
                print(f"❌ {file_path} - File not found")
        except Exception as e:
            print(f"❌ {file_path} - Error: {e}")
    
    return passed == len(files_to_check)

def check_test_files():
    """Check that test files are updated"""
    print("\n🔍 Checking test files...")
    
    test_files = [
        "tests/test_data_manager.py",
        "tests/test_order_integration.py", 
        "tests/mock_angel_api.py"
    ]
    
    passed = 0
    for file_path in test_files:
        try:
            if Path(file_path).exists():
                content = Path(file_path).read_text()
                # Check if old lot size (25) is still present
                if "lot_size': 25" in content or "lotsize=\"25\"" in content or "lot_size == 25" in content:
                    print(f"❌ {file_path} - Still has old lot size (25)")
                else:
                    print(f"✅ {file_path} - Updated")
                    passed += 1
            else:
                print(f"❌ {file_path} - File not found")
        except Exception as e:
            print(f"❌ {file_path} - Error: {e}")
    
    return passed == len(test_files)

def main():
    """Run validation checks"""
    print("🚀 Bank Nifty Lot Size Update Validation")
    print("=" * 50)
    
    checks = [
        check_constants_file,
        check_config_files,
        check_test_files
    ]
    
    passed = 0
    for check in checks:
        if check():
            passed += 1
    
    print("\n" + "=" * 50)
    print(f"📊 Validation Results: {passed}/{len(checks)} checks passed")
    
    if passed == len(checks):
        print("🎉 All validations passed!")
        print("✅ Bank Nifty lot size successfully updated to 35")
        print("\n📋 Summary of changes:")
        print("• Lot size updated from 25 to 35")
        print("• All configuration files updated")
        print("• All test files updated")
        print("• Constants file created")
        print("• Position sizes now use multiples of 35")
        return True
    else:
        print("❌ Some validations failed")
        return False

if __name__ == "__main__":
    success = main()
    sys.exit(0 if success else 1)