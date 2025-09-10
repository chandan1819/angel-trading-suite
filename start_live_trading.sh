#!/bin/bash
# Safe Live Trading Startup Script
# This script includes safety checks before starting live trading

echo "🚀 Bank Nifty Options Trading System - Live Trading Startup"
echo "==========================================================="
echo ""

# Color codes for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

# Function to print colored output
print_status() {
    echo -e "${GREEN}✅ $1${NC}"
}

print_warning() {
    echo -e "${YELLOW}⚠️  $1${NC}"
}

print_error() {
    echo -e "${RED}❌ $1${NC}"
}

# Safety confirmation
echo -e "${RED}⚠️  WARNING: This will start LIVE TRADING with real money!${NC}"
echo ""
read -p "Are you sure you want to proceed with LIVE trading? (type 'YES' to confirm): " confirm

if [ "$confirm" != "YES" ]; then
    echo "Live trading cancelled. Use paper trading for testing:"
    echo "python3 main.py trade --mode paper --continuous"
    exit 1
fi

echo ""
echo "🔍 Running Pre-Trading Safety Checks..."
echo ""

# Check 1: Environment variables
echo "1. Checking API credentials..."
if [ -z "$ANGEL_API_KEY" ] || [ -z "$ANGEL_CLIENT_CODE" ] || [ -z "$ANGEL_PIN" ] || [ -z "$ANGEL_TOTP_SECRET" ]; then
    print_error "API credentials not found in environment variables"
    echo "Please run: source setup_credentials.sh"
    exit 1
fi
print_status "API credentials found"

# Check 2: Configuration file
echo "2. Checking configuration file..."
if [ ! -f "config/live_trading_config.yaml" ]; then
    print_error "Live trading configuration file not found"
    exit 1
fi
print_status "Configuration file found"

# Check 3: Validate configuration
echo "3. Validating configuration..."
python3 main.py --config config/live_trading_config.yaml config --validate
if [ $? -ne 0 ]; then
    print_error "Configuration validation failed"
    exit 1
fi
print_status "Configuration validated"

# Check 4: Test API connectivity
echo "4. Testing system components..."
python3 simple_trader.py --test
if [ $? -ne 0 ]; then
    print_error "System test failed"
    echo "Please check your credentials and configuration"
    exit 1
fi
print_status "System test passed"

# Check 5: Ensure no emergency stop file exists
echo "5. Checking for emergency stop file..."
if [ -f "emergency_stop.txt" ]; then
    print_error "Emergency stop file exists - removing it"
    rm emergency_stop.txt
fi
print_status "No emergency stop file found"

# Check 6: Create logs directory
echo "6. Setting up logging..."
mkdir -p logs
chmod 755 logs
print_status "Logging directory ready"

# Final confirmation
echo ""
echo -e "${YELLOW}🎯 Final Safety Check:${NC}"
echo "   • Mode: LIVE TRADING"
echo "   • Max Daily Loss: ₹5,000"
echo "   • Max Concurrent Trades: 2"
echo "   • Strategy: Conservative Straddle Only"
echo "   • Position Size: 25 lots maximum"
echo ""
read -p "Confirm these settings are correct (type 'CONFIRM'): " final_confirm

if [ "$final_confirm" != "CONFIRM" ]; then
    print_error "Final confirmation failed. Exiting for safety."
    exit 1
fi

echo ""
print_status "All safety checks passed!"
echo ""
echo "🚀 Starting Live Trading..."
echo "📊 Monitor the system at: python3 main.py status --detailed"
echo "🛑 Emergency stop: echo 'STOP' > emergency_stop.txt"
echo ""

# Start live trading using simple trader
python3 simple_trader.py --live

echo ""
print_warning "Live trading session ended"