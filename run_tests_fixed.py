#!/usr/bin/env python3
"""
Fixed test runner that properly handles Python imports for the trading system.
This script sets up the Python path correctly before running tests.
"""

import sys
import os
import subprocess
from pathlib import Path

def setup_python_path():
    """Setup Python path to handle relative imports correctly"""
    # Get the project root directory
    project_root = Path(__file__).parent
    src_path = project_root / "src"
    
    # Add src to Python path
    if str(src_path) not in sys.path:
        sys.path.insert(0, str(src_path))
    
    # Set PYTHONPATH environment variable
    current_pythonpath = os.environ.get('PYTHONPATH', '')
    if str(src_path) not in current_pythonpath:
        if current_pythonpath:
            os.environ['PYTHONPATH'] = f"{src_path}:{current_pythonpath}"
        else:
            os.environ['PYTHONPATH'] = str(src_path)

def run_tests():
    """Run the test suite with proper Python path setup"""
    setup_python_path()
    
    # Run pytest with the correct configuration
    cmd = [
        sys.executable, "-m", "pytest", 
        "tests/", 
        "-v",
        "--tb=short",  # Shorter traceback format
        "-x",  # Stop on first failure for easier debugging
        "--disable-warnings"  # Disable warnings for cleaner output
    ]
    
    print("🧪 Running Bank Nifty Trading System Tests...")
    print("=" * 60)
    print(f"Python Path: {sys.path[0]}")
    print(f"PYTHONPATH: {os.environ.get('PYTHONPATH', 'Not set')}")
    print("=" * 60)
    
    try:
        result = subprocess.run(cmd, cwd=Path(__file__).parent)
        return result.returncode
    except KeyboardInterrupt:
        print("\n❌ Tests interrupted by user")
        return 1
    except Exception as e:
        print(f"❌ Error running tests: {e}")
        return 1

if __name__ == "__main__":
    exit_code = run_tests()
    
    if exit_code == 0:
        print("\n✅ All tests passed!")
        print("🎉 Lot size update validation successful!")
    else:
        print(f"\n❌ Tests failed with exit code: {exit_code}")
        print("🔧 Check the errors above and fix any issues")
    
    sys.exit(exit_code)