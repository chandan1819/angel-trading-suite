#!/usr/bin/env python3
"""
Angel Broking API Key Monitor
This script continuously monitors your API key status and alerts you when it becomes active
"""

import json
import time
import datetime
from SmartApi import SmartConnect
import pyotp
import os
import sys

class APIMonitor:
    def __init__(self, config_file='config.json'):
        self.config_file = config_file
        self.config = self.load_config()
        self.test_count = 0
        self.start_time = datetime.datetime.now()
        
    def load_config(self):
        """Load configuration from JSON file"""
        try:
            with open(self.config_file, 'r') as f:
                return json.load(f)
        except Exception as e:
            print(f"❌ Error loading config: {e}")
            sys.exit(1)
    
    def clear_screen(self):
        """Clear terminal screen"""
        os.system('clear' if os.name == 'posix' else 'cls')
    
    def print_header(self):
        """Print monitoring header"""
        print("🔍 Angel Broking API Key Monitor")
        print("=" * 50)
        print(f"📱 Client Code: {self.config['client_code']}")
        print(f"🔑 API Key: {self.config['api_key'][:8]}...{self.config['api_key'][-8:]}")
        print(f"⏰ Started: {self.start_time.strftime('%Y-%m-%d %H:%M:%S')}")
        print(f"🔄 Tests Run: {self.test_count}")
        print("-" * 50)
    
    def test_api_key(self):
        """Test API key authentication"""
        try:
            # Initialize SmartConnect
            smartApi = SmartConnect(api_key=self.config['api_key'])
            
            # Generate TOTP
            totp = pyotp.TOTP(self.config['totp_secret']).now()
            
            # Attempt login
            response = smartApi.generateSession(
                self.config['client_code'], 
                self.config['pin'], 
                totp
            )
            
            return response.get('status', False), response.get('message', 'Unknown error'), totp
            
        except Exception as e:
            return False, str(e), None
    
    def send_success_notification(self, response_data):
        """Send success notification (you can customize this)"""
        print("\n" + "🎉" * 20)
        print("🎉 SUCCESS! API KEY IS NOW WORKING! 🎉")
        print("🎉" * 20)
        print(f"\n✅ Login successful at: {datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
        print(f"🎫 Auth Token: {response_data.get('data', {}).get('jwtToken', 'N/A')[:20]}...")
        print(f"🔄 Refresh Token: {response_data.get('data', {}).get('refreshToken', 'N/A')[:20]}...")
        
        # You can add more notifications here:
        # - Send email
        # - Play sound
        # - Send push notification
        # - Write to log file
        
        # Create success log
        with open('api_success.log', 'w') as f:
            f.write(f"API Key activated at: {datetime.datetime.now()}\n")
            f.write(f"Response: {json.dumps(response_data, indent=2)}\n")
    
    def monitor(self, interval_minutes=5, max_tests=None):
        """Main monitoring loop"""
        interval_seconds = interval_minutes * 60
        
        print(f"🚀 Starting API key monitoring...")
        print(f"⏱️  Testing every {interval_minutes} minutes")
        print(f"🛑 Press Ctrl+C to stop monitoring")
        print("\n" + "=" * 50)
        
        try:
            while True:
                self.test_count += 1
                current_time = datetime.datetime.now()
                
                # Clear screen and show header
                self.clear_screen()
                self.print_header()
                
                print(f"🔄 Test #{self.test_count} - {current_time.strftime('%H:%M:%S')}")
                
                # Test API key
                success, message, totp = self.test_api_key()
                
                if success:
                    # SUCCESS! API key is working
                    self.send_success_notification({'status': True, 'data': {'jwtToken': 'token_here', 'refreshToken': 'refresh_here'}})
                    print(f"\n🎯 You can now run: python3 simple_login.py")
                    print(f"🎯 Or run: python3 login_example.py")
                    break
                else:
                    # Still failing
                    print(f"❌ Status: Still failing")
                    print(f"🔢 TOTP Used: {totp}")
                    print(f"📝 Error: {message}")
                    
                    # Show countdown
                    print(f"\n⏳ Next test in {interval_minutes} minutes...")
                    
                    # Countdown timer
                    for remaining in range(interval_seconds, 0, -1):
                        mins, secs = divmod(remaining, 60)
                        timer = f"{mins:02d}:{secs:02d}"
                        print(f"\r⏰ Next test in: {timer}", end="", flush=True)
                        time.sleep(1)
                    
                    print()  # New line after countdown
                
                # Check if we've reached max tests
                if max_tests and self.test_count >= max_tests:
                    print(f"\n🛑 Reached maximum tests ({max_tests}). Stopping monitor.")
                    break
                    
        except KeyboardInterrupt:
            print(f"\n\n🛑 Monitoring stopped by user")
            print(f"📊 Total tests run: {self.test_count}")
            print(f"⏱️  Total time: {datetime.datetime.now() - self.start_time}")
        except Exception as e:
            print(f"\n❌ Monitor error: {e}")

def main():
    """Main function with command line options"""
    print("🔍 Angel Broking API Key Monitor")
    print("=" * 40)
    
    # Get monitoring preferences
    try:
        interval = input("⏱️  Test interval in minutes (default 5): ").strip()
        interval = int(interval) if interval else 5
        
        max_tests_input = input("🔢 Maximum tests (press Enter for unlimited): ").strip()
        max_tests = int(max_tests_input) if max_tests_input else None
        
        print(f"\n✅ Will test every {interval} minutes")
        if max_tests:
            print(f"✅ Will stop after {max_tests} tests")
        else:
            print("✅ Will run until API key works or you stop it")
        
        input("\n🚀 Press Enter to start monitoring...")
        
    except KeyboardInterrupt:
        print("\n👋 Goodbye!")
        return
    except ValueError:
        print("❌ Invalid input. Using defaults: 5 minutes, unlimited tests")
        interval = 5
        max_tests = None
    
    # Start monitoring
    monitor = APIMonitor()
    monitor.monitor(interval_minutes=interval, max_tests=max_tests)

if __name__ == "__main__":
    main()