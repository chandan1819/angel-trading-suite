#!/usr/bin/env python3
"""
Angel Broking Trading Suite - Main Menu
Professional trading application with organized modules
"""

import os
import sys
import subprocess

class TradingSuite:
    def __init__(self):
        self.base_path = os.path.dirname(os.path.abspath(__file__))
        
    def show_banner(self):
        """Show application banner"""
        print("=" * 60)
        print("🚀 ANGEL BROKING TRADING SUITE")
        print("=" * 60)
        print("Professional Trading Application")
        print("Organized • Secure • Easy to Use")
        print("=" * 60)
    
    def show_main_menu(self):
        """Show main menu"""
        print("\n📋 MAIN MENU")
        print("=" * 30)
        print("1. 🔐 Authentication & Login")
        print("2. 📊 Market Data & Analysis") 
        print("3. 💼 Trading & Orders")
        print("4. 🔧 Utilities & Tools")
        print("5. 📞 Support & Help")
        print("6. 📚 Documentation")
        print("7. 🚪 Exit")
        
    def show_auth_menu(self):
        """Show authentication menu"""
        print("\n🔐 AUTHENTICATION MENU")
        print("=" * 25)
        print("1. Simple Login Test")
        print("2. Detailed Login Demo")
        print("3. API Key Monitor")
        print("4. Back to Main Menu")
        
        choice = input("\nEnter choice (1-4): ").strip()
        
        if choice == '1':
            self.run_script('auth/simple_login.py')
        elif choice == '2':
            self.run_script('auth/login_example.py')
        elif choice == '3':
            self.run_script('auth/api_monitor.py')
        elif choice == '4':
            return
        else:
            print("❌ Invalid choice")
    
    def show_market_menu(self):
        """Show market data menu"""
        print("\n📊 MARKET DATA MENU")
        print("=" * 22)
        print("1. Simple Market Data")
        print("2. Advanced Market Data")
        print("3. Back to Main Menu")
        
        choice = input("\nEnter choice (1-3): ").strip()
        
        if choice == '1':
            self.run_script('market_data/simple_market.py')
        elif choice == '2':
            self.run_script('market_data/market_data.py')
        elif choice == '3':
            return
        else:
            print("❌ Invalid choice")
    
    def show_trading_menu(self):
        """Show trading menu"""
        print("\n💼 TRADING MENU")
        print("=" * 17)
        print("1. Trading Demo (Safe)")
        print("2. Order Management (Live)")
        print("3. Back to Main Menu")
        
        choice = input("\nEnter choice (1-3): ").strip()
        
        if choice == '1':
            self.run_script('trading/trading_demo.py')
        elif choice == '2':
            print("⚠️  WARNING: This will allow REAL order placement!")
            confirm = input("Continue? (yes/no): ").lower()
            if confirm == 'yes':
                self.run_script('trading/order_management.py')
        elif choice == '3':
            return
        else:
            print("❌ Invalid choice")
    
    def show_utils_menu(self):
        """Show utilities menu"""
        print("\n🔧 UTILITIES MENU")
        print("=" * 18)
        print("1. Diagnose API Issues")
        print("2. Troubleshoot Problems")
        print("3. Update API Key")
        print("4. Test New API Key")
        print("5. Back to Main Menu")
        
        choice = input("\nEnter choice (1-5): ").strip()
        
        if choice == '1':
            self.run_script('utils/diagnose_api.py')
        elif choice == '2':
            self.run_script('utils/troubleshoot_angel.py')
        elif choice == '3':
            self.run_script('utils/update_api_key.py')
        elif choice == '4':
            self.run_script('utils/test_new_api.py')
        elif choice == '5':
            return
        else:
            print("❌ Invalid choice")
    
    def show_support_menu(self):
        """Show support menu"""
        print("\n📞 SUPPORT MENU")
        print("=" * 16)
        print("1. View Support Email Template")
        print("2. View Clean Email Template")
        print("3. Angel Broking Contact Info")
        print("4. Back to Main Menu")
        
        choice = input("\nEnter choice (1-4): ").strip()
        
        if choice == '1':
            self.show_file('support/support_email.txt')
        elif choice == '2':
            self.show_file('support/support_email_clean.txt')
        elif choice == '3':
            self.show_contact_info()
        elif choice == '4':
            return
        else:
            print("❌ Invalid choice")
    
    def show_docs_menu(self):
        """Show documentation menu"""
        print("\n📚 DOCUMENTATION")
        print("=" * 18)
        print("1. Project Structure")
        print("2. Setup Instructions")
        print("3. API Reference")
        print("4. Back to Main Menu")
        
        choice = input("\nEnter choice (1-4): ").strip()
        
        if choice == '1':
            self.show_project_structure()
        elif choice == '2':
            self.show_setup_instructions()
        elif choice == '3':
            self.show_api_reference()
        elif choice == '4':
            return
        else:
            print("❌ Invalid choice")
    
    def run_script(self, script_path):
        """Run a Python script"""
        full_path = os.path.join(self.base_path, script_path)
        if os.path.exists(full_path):
            print(f"\n🚀 Running {script_path}...")
            print("-" * 40)
            try:
                subprocess.run([sys.executable, full_path], cwd=self.base_path)
            except KeyboardInterrupt:
                print("\n⏸️  Script interrupted by user")
            except Exception as e:
                print(f"❌ Error running script: {e}")
        else:
            print(f"❌ Script not found: {script_path}")
        
        input("\n⏸️  Press Enter to continue...")
    
    def show_file(self, file_path):
        """Show contents of a file"""
        full_path = os.path.join(self.base_path, file_path)
        if os.path.exists(full_path):
            print(f"\n📄 {file_path}")
            print("=" * 40)
            try:
                with open(full_path, 'r') as f:
                    content = f.read()
                    print(content)
            except Exception as e:
                print(f"❌ Error reading file: {e}")
        else:
            print(f"❌ File not found: {file_path}")
        
        input("\n⏸️  Press Enter to continue...")
    
    def show_contact_info(self):
        """Show Angel Broking contact information"""
        print("\n📞 ANGEL BROKING CONTACT INFO")
        print("=" * 35)
        print("📧 Email: smartapi.sdk@gmail.com")
        print("🌐 Developer Portal: https://smartapi.angelone.in/")
        print("📱 Trading App: Angel One")
        print("🏢 Website: https://www.angelone.in/")
        print("\n💡 For API issues, email with:")
        print("  • Your client code")
        print("  • Error codes (like AB1053)")
        print("  • Detailed description")
        
        input("\n⏸️  Press Enter to continue...")
    
    def show_project_structure(self):
        """Show project structure"""
        print("\n📁 PROJECT STRUCTURE")
        print("=" * 22)
        print("smartapi-python/")
        print("├── auth/           # Authentication scripts")
        print("├── trading/        # Trading & order management")
        print("├── market_data/    # Market data & analysis")
        print("├── utils/          # Utilities & troubleshooting")
        print("├── support/        # Support templates")
        print("├── config/         # Configuration files")
        print("├── docs/           # Documentation")
        print("├── SmartApi/       # Angel Broking SDK")
        print("├── logs/           # Application logs")
        print("└── main.py         # This main menu")
        
        input("\n⏸️  Press Enter to continue...")
    
    def show_setup_instructions(self):
        """Show setup instructions"""
        print("\n⚙️  SETUP INSTRUCTIONS")
        print("=" * 23)
        print("1. 🔑 Get API Key from Angel Broking")
        print("   • Visit https://smartapi.angelone.in/")
        print("   • Register and get API key")
        print("   • Enable 2FA and get TOTP secret")
        print()
        print("2. 📝 Update config/config.json:")
        print("   • api_key: Your API key")
        print("   • client_code: Your client ID")
        print("   • pin: Your login PIN")
        print("   • totp_secret: Your 2FA secret")
        print()
        print("3. 🚀 Run the application:")
        print("   • python3 main.py")
        print("   • Start with Authentication menu")
        print("   • Test login before trading")
        
        input("\n⏸️  Press Enter to continue...")
    
    def show_api_reference(self):
        """Show API reference"""
        print("\n📖 API REFERENCE")
        print("=" * 18)
        print("🔐 Authentication:")
        print("  • generateSession() - Login")
        print("  • terminateSession() - Logout")
        print()
        print("📊 Market Data:")
        print("  • ltpData() - Live prices")
        print("  • searchScrip() - Search stocks")
        print("  • getCandleData() - Historical data")
        print()
        print("💼 Trading:")
        print("  • placeOrder() - Place orders")
        print("  • cancelOrder() - Cancel orders")
        print("  • orderBook() - View orders")
        print("  • position() - View positions")
        print("  • holding() - View holdings")
        print()
        print("🔧 Account:")
        print("  • rmsLimit() - Account limits")
        print("  • getProfile() - User profile")
        
        input("\n⏸️  Press Enter to continue...")
    
    def run(self):
        """Main application loop"""
        while True:
            self.show_banner()
            self.show_main_menu()
            
            choice = input("\nEnter your choice (1-7): ").strip()
            
            if choice == '1':
                self.show_auth_menu()
            elif choice == '2':
                self.show_market_menu()
            elif choice == '3':
                self.show_trading_menu()
            elif choice == '4':
                self.show_utils_menu()
            elif choice == '5':
                self.show_support_menu()
            elif choice == '6':
                self.show_docs_menu()
            elif choice == '7':
                print("\n👋 Thank you for using Angel Broking Trading Suite!")
                print("Happy Trading! 📈")
                break
            else:
                print("❌ Invalid choice. Please select 1-7.")
                input("\n⏸️  Press Enter to continue...")

if __name__ == "__main__":
    app = TradingSuite()
    try:
        app.run()
    except KeyboardInterrupt:
        print("\n\n👋 Goodbye!")
    except Exception as e:
        print(f"\n❌ Application error: {e}")
        print("Please report this issue.")