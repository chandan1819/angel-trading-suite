#!/usr/bin/env python3
"""
Main entry point for the Bank Nifty Options Trading System.

This script provides the primary interface for running the trading system
with various modes and configurations.
"""

import sys
import os
from pathlib import Path

# Add src directory to Python path
src_path = Path(__file__).parent / "src"
sys.path.insert(0, str(src_path))

from cli.cli_interface import main

if __name__ == '__main__':
    main()