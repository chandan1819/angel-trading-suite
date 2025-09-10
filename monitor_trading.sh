#!/bin/bash
# Trading System Monitor Script
# Use this to monitor the live trading system

echo "📊 Bank Nifty Trading System Monitor"
echo "===================================="

while true; do
    clear
    echo "📊 Bank Nifty Trading System Monitor - $(date)"
    echo "=============================================="
    echo ""
    
    # Check if emergency stop is active
    if [ -f "emergency_stop.txt" ]; then
        echo -e "\033[0;31m🚨 EMERGENCY STOP ACTIVE\033[0m"
        echo ""
    fi
    
    # Show system status
    python3 main.py --config config/live_trading_config.yaml status --detailed
    
    echo ""
    echo "Press Ctrl+C to exit monitor"
    echo "Refreshing in 30 seconds..."
    
    sleep 30
done