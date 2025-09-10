#!/bin/bash
# Setup script for Angel Broking API credentials
# DO NOT commit this file to git - it contains sensitive information

echo "🔐 Setting up Angel Broking API Credentials"
echo "============================================="
echo ""
echo "⚠️  IMPORTANT: Keep these credentials secure and never share them!"
echo ""

# Prompt for credentials
read -p "Enter your Angel API Key: " ANGEL_API_KEY
read -p "Enter your Angel Client Code: " ANGEL_CLIENT_CODE
read -s -p "Enter your Angel PIN: " ANGEL_PIN
echo ""
read -p "Enter your Angel TOTP Secret: " ANGEL_TOTP_SECRET

# Export environment variables
export ANGEL_API_KEY="$ANGEL_API_KEY"
export ANGEL_CLIENT_CODE="$ANGEL_CLIENT_CODE"
export ANGEL_PIN="$ANGEL_PIN"
export ANGEL_TOTP_SECRET="$ANGEL_TOTP_SECRET"

# Add to current session
echo "export ANGEL_API_KEY=\"$ANGEL_API_KEY\"" >> ~/.bashrc
echo "export ANGEL_CLIENT_CODE=\"$ANGEL_CLIENT_CODE\"" >> ~/.bashrc
echo "export ANGEL_PIN=\"$ANGEL_PIN\"" >> ~/.bashrc
echo "export ANGEL_TOTP_SECRET=\"$ANGEL_TOTP_SECRET\"" >> ~/.bashrc

echo ""
echo "✅ Credentials have been set up!"
echo "🔄 Please restart your terminal or run: source ~/.bashrc"
echo ""
echo "🧪 Next step: Test with paper trading first!"