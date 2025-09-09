#!/usr/bin/env python3
"""
Simple test script for emergency controls functionality.
"""

import os
import sys
import tempfile
import time
import logging
from pathlib import Path
from datetime import datetime
from typing import Dict, Any, List, Optional
from dataclasses import dataclass
from enum import Enum

# Add src to path
sys.path.insert(0, str(Path(__file__).parent / "src"))

# Import the emergency controller directly with minimal dependencies
from emergency.emergency_controller import EmergencyLevel, EmergencyType, EmergencyEvent


def test_emergency_stop_file():
    """Test emergency stop file detection"""
    print("Testing emergency stop file detection...")
    
    # Create temporary emergency stop file
    temp_dir = tempfile.mkdtemp()
    emergency_file = os.path.join(temp_dir, "emergency_stop.txt")
    
    try:
        # Create emergency controller
        config = {
            'emergency_stop_file': emergency_file,
            'daily_loss_limit': 10000.0,
            'check_interval': 0.5
        }
        
        controller = EmergencyController(config)
        
        # Track events
        events = []
        def capture_event(event):
            events.append(event)
            print(f"Emergency event captured: {event.event_type.value} - {event.message}")
        
        controller.register_emergency_callback(EmergencyType.MANUAL_STOP, capture_event)
        
        # Start monitoring
        controller.start_monitoring()
        
        print("Creating emergency stop file...")
        with open(emergency_file, 'w') as f:
            f.write("Test emergency stop")
        
        # Wait for detection
        time.sleep(1)
        
        # Check results
        if controller.emergency_stop_active:
            print("✓ Emergency stop detected successfully")
        else:
            print("✗ Emergency stop not detected")
        
        if len(events) > 0:
            print(f"✓ Emergency event triggered: {events[0].message}")
        else:
            print("✗ No emergency events triggered")
        
        # Remove file and test deactivation
        print("Removing emergency stop file...")
        os.remove(emergency_file)
        time.sleep(1)
        
        if not controller.emergency_stop_active:
            print("✓ Emergency stop deactivated successfully")
        else:
            print("✗ Emergency stop still active")
        
        controller.stop_monitoring()
        
    finally:
        # Cleanup
        if os.path.exists(emergency_file):
            os.remove(emergency_file)
        os.rmdir(temp_dir)


def test_daily_loss_limit():
    """Test daily loss limit enforcement"""
    print("\nTesting daily loss limit enforcement...")
    
    config = {
        'emergency_stop_file': 'test_emergency.txt',
        'daily_loss_limit': 5000.0,
        'check_interval': 0.5
    }
    
    controller = EmergencyController(config)
    
    # Track events
    events = []
    def capture_event(event):
        events.append(event)
        print(f"Daily loss event: {event.message}")
    
    controller.register_emergency_callback(EmergencyType.DAILY_LOSS_LIMIT, capture_event)
    
    controller.start_monitoring()
    
    print("Setting daily loss to 6000 (exceeds 5000 limit)...")
    controller.update_daily_loss(6000.0)
    
    time.sleep(1)
    
    if controller.daily_loss_limit_breached:
        print("✓ Daily loss limit breach detected")
    else:
        print("✗ Daily loss limit breach not detected")
    
    if len(events) > 0:
        print(f"✓ Daily loss event triggered: {events[0].message}")
    else:
        print("✗ No daily loss events triggered")
    
    controller.stop_monitoring()


def test_emergency_status():
    """Test emergency status reporting"""
    print("\nTesting emergency status reporting...")
    
    config = {
        'emergency_stop_file': 'test_emergency.txt',
        'daily_loss_limit': 10000.0
    }
    
    controller = EmergencyController(config)
    
    status = controller.get_emergency_status()
    
    print("Emergency status fields:")
    for key, value in status.items():
        print(f"  {key}: {value}")
    
    # Check required fields
    required_fields = [
        'emergency_stop_active',
        'daily_loss_limit_breached',
        'monitoring_active',
        'current_daily_loss',
        'daily_loss_limit'
    ]
    
    missing_fields = [field for field in required_fields if field not in status]
    
    if not missing_fields:
        print("✓ All required status fields present")
    else:
        print(f"✗ Missing status fields: {missing_fields}")


def main():
    """Run all tests"""
    print("Emergency Controls Test Suite")
    print("=" * 40)
    
    try:
        test_emergency_stop_file()
        test_daily_loss_limit()
        test_emergency_status()
        
        print("\n" + "=" * 40)
        print("Emergency controls tests completed!")
        
    except Exception as e:
        print(f"\nTest failed with error: {e}")
        import traceback
        traceback.print_exc()


if __name__ == '__main__':
    main()