#!/bin/bash

# Quick test setup for VibeMessageBot (macOS/Development)
# This script sets up the bot for manual testing without systemd

set -e

# Colors for output
GREEN='\033[0;32m'
BLUE='\033[0;34m'
RED='\033[0;31m'
NC='\033[0m' # No Color

print_status() {
    echo -e "${GREEN}[INFO]${NC} $1"
}

print_info() {
    echo -e "${BLUE}[SETUP]${NC} $1"
}

print_error() {
    echo -e "${RED}[ERROR]${NC} $1"
}

print_info "Setting up VibeMessageBot for manual testing..."

# Check if .env exists
if [ ! -f ".env" ]; then
    print_error ".env file not found!"
    print_info "Please copy .env.example to .env and configure it:"
    print_info "cp .env.example .env"
    exit 1
fi

# Create virtual environment
print_info "Creating virtual environment..."
python3 -m venv .venv
source .venv/bin/activate
print_status "Virtual environment created and activated"

# Install dependencies
print_info "Installing dependencies..."
pip install -r requirements.txt
print_status "Dependencies installed"

# Create directories
print_info "Creating directories..."
mkdir -p data logs src
print_status "Directories created"

# Create initial whitelist if it doesn't exist
if [ ! -f "data/whitelist.json" ]; then
    print_info "Creating initial whitelist..."
    cat > data/whitelist.json << 'EOF'
{
  "users": [],
  "user_info": {},
  "last_updated": "2025-06-16T00:00:00.000000",
  "description": "Whitelist for VibeMessageBot - Add user IDs to allow access"
}
EOF
    print_status "Initial whitelist created"
    print_info "Add your user ID using whitelist-manager.html or manually edit data/whitelist.json"
fi

# Test configuration
print_info "Testing configuration..."
source .env

if [ -z "$TELEGRAM_BOT_TOKEN" ] || [ "$TELEGRAM_BOT_TOKEN" = "your_bot_token_here" ]; then
    print_error "TELEGRAM_BOT_TOKEN not configured in .env"
    exit 1
fi

if [ -z "$GOOGLE_AI_API_KEY" ] || [ "$GOOGLE_AI_API_KEY" = "your_google_ai_api_key_here" ]; then
    print_error "GOOGLE_AI_API_KEY not configured in .env"
    exit 1
fi

print_status "Configuration looks good!"
print_info ""
print_info "Setup complete! To start the bot:"
print_info "1. Make sure you've added your user ID to the whitelist"
print_info "2. Run: source .venv/bin/activate && python3 bot.py"
print_info ""
print_info "To get your Telegram user ID, forward a message to @userinfobot"
print_info "Then add it to data/whitelist.json or use whitelist-manager.html"
