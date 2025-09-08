#!/usr/bin/env python3
"""
Quick launcher for Angel Broking Trading Suite
"""

import subprocess
import sys
import os

def main():
    """Launch the main application"""
    print("🚀 Launching Angel Broking Trading Suite...")
    
    # Check if main.py exists
    if not os.path.exists('main.py'):
        print("❌ main.py not found. Make sure you're in the project directory.")
        return
    
    try:
        subprocess.run([sys.executable, 'main.py'])
    except KeyboardInterrupt:
        print("\n👋 Goodbye!")
    except Exception as e:
        print(f"❌ Error launching application: {e}")

if __name__ == "__main__":
    main()