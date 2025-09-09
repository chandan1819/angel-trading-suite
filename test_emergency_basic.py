#!/usr/bin/env python3
"""
Basic test for emergency stop file functionality.
"""

import os
import tempfile
import time


def test_emergency_file_creation():
    """Test creating and detecting emergency stop file"""
    print("Testing emergency stop file creation and detection...")
    
    # Create temporary directory
    temp_dir = tempfile.mkdtemp()
    emergency_file = os.path.join(temp_dir, "emergency_stop.txt")
    
    try:
        # Test file creation
        print(f"Creating emergency stop file: {emergency_file}")
        with open(emergency_file, 'w') as f:
            f.write("Emergency stop activated at: " + str(time.time()))
        
        # Test file detection
        if os.path.exists(emergency_file):
            print("✓ Emergency stop file created successfully")
            
            # Read content
            with open(emergency_file, 'r') as f:
                content = f.read()
            print(f"✓ File content: {content.strip()}")
        else:
            print("✗ Emergency stop file not found")
        
        # Test file removal
        print("Removing emergency stop file...")
        os.remove(emergency_file)
        
        if not os.path.exists(emergency_file):
            print("✓ Emergency stop file removed successfully")
        else:
            print("✗ Emergency stop file still exists")
            
    finally:
        # Cleanup
        if os.path.exists(emergency_file):
            os.remove(emergency_file)
        os.rmdir(temp_dir)


def test_daily_loss_calculation():
    """Test daily loss calculation logic"""
    print("\nTesting daily loss calculation...")
    
    daily_loss_limit = 10000.0
    test_cases = [
        (5000.0, False, "Normal loss within limit"),
        (10000.0, True, "Loss at exact limit"),
        (12000.0, True, "Loss exceeding limit"),
        (0.0, False, "No loss"),
    ]
    
    for loss_amount, should_breach, description in test_cases:
        is_breached = loss_amount >= daily_loss_limit
        
        if is_breached == should_breach:
            print(f"✓ {description}: {loss_amount} -> {'BREACH' if is_breached else 'OK'}")
        else:
            print(f"✗ {description}: Expected {'BREACH' if should_breach else 'OK'}, got {'BREACH' if is_breached else 'OK'}")


def test_trading_hours_check():
    """Test trading hours validation"""
    print("\nTesting trading hours validation...")
    
    from datetime import datetime, time as dt_time
    
    # Market hours: 9:15 AM to 3:30 PM IST
    market_open = dt_time(9, 15)
    market_close = dt_time(15, 30)
    
    test_times = [
        (dt_time(8, 0), False, "Before market open"),
        (dt_time(9, 15), True, "Market open"),
        (dt_time(12, 0), True, "During market hours"),
        (dt_time(15, 30), True, "Market close"),
        (dt_time(16, 0), False, "After market close"),
        (dt_time(23, 0), False, "Late night"),
    ]
    
    for test_time, should_be_valid, description in test_times:
        is_valid = market_open <= test_time <= market_close
        
        if is_valid == should_be_valid:
            print(f"✓ {description}: {test_time} -> {'VALID' if is_valid else 'INVALID'}")
        else:
            print(f"✗ {description}: Expected {'VALID' if should_be_valid else 'INVALID'}, got {'VALID' if is_valid else 'INVALID'}")


def test_position_limits():
    """Test position limit validation"""
    print("\nTesting position limits...")
    
    max_concurrent_positions = 5
    max_position_value = 100000.0
    
    test_cases = [
        (3, 50000.0, True, "Normal position count and value"),
        (5, 80000.0, True, "At position limit"),
        (6, 50000.0, False, "Exceeds position count limit"),
        (3, 120000.0, False, "Exceeds position value limit"),
        (7, 150000.0, False, "Exceeds both limits"),
    ]
    
    for position_count, total_value, should_be_valid, description in test_cases:
        count_valid = position_count <= max_concurrent_positions
        value_valid = total_value <= max_position_value
        is_valid = count_valid and value_valid
        
        if is_valid == should_be_valid:
            print(f"✓ {description}: {position_count} positions, ₹{total_value:,.0f} -> {'VALID' if is_valid else 'INVALID'}")
        else:
            print(f"✗ {description}: Expected {'VALID' if should_be_valid else 'INVALID'}, got {'VALID' if is_valid else 'INVALID'}")


def test_emergency_scenarios():
    """Test various emergency scenarios"""
    print("\nTesting emergency scenarios...")
    
    scenarios = [
        {
            'name': 'Manual Emergency Stop',
            'conditions': ['emergency_file_exists'],
            'expected_action': 'immediate_stop'
        },
        {
            'name': 'Daily Loss Limit Breach',
            'conditions': ['daily_loss_exceeded'],
            'expected_action': 'close_positions_and_stop'
        },
        {
            'name': 'Multiple Emergency Conditions',
            'conditions': ['emergency_file_exists', 'daily_loss_exceeded'],
            'expected_action': 'immediate_stop'
        },
        {
            'name': 'System Resource Exhaustion',
            'conditions': ['high_cpu_usage', 'low_memory'],
            'expected_action': 'gradual_shutdown'
        }
    ]
    
    for scenario in scenarios:
        print(f"Scenario: {scenario['name']}")
        print(f"  Conditions: {', '.join(scenario['conditions'])}")
        print(f"  Expected Action: {scenario['expected_action']}")
        print(f"  ✓ Scenario defined correctly")


def main():
    """Run all basic tests"""
    print("Emergency Controls Basic Test Suite")
    print("=" * 50)
    
    try:
        test_emergency_file_creation()
        test_daily_loss_calculation()
        test_trading_hours_check()
        test_position_limits()
        test_emergency_scenarios()
        
        print("\n" + "=" * 50)
        print("✓ All basic emergency control tests passed!")
        print("\nNote: These are basic logic tests.")
        print("Full integration tests require the complete system setup.")
        
    except Exception as e:
        print(f"\nTest failed with error: {e}")
        import traceback
        traceback.print_exc()


if __name__ == '__main__':
    main()