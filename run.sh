#!/bin/bash

# VibeMessageBot Setup and Start Script
# This script handles the complete setup and start process for the bot

set -e  # Exit on any error

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Function to print colored output
print_status() {
    echo -e "${GREEN}[INFO]${NC} $1"
}

print_warning() {
    echo -e "${YELLOW}[WARNING]${NC} $1"
}

print_error() {
    echo -e "${RED}[ERROR]${NC} $1"
}

print_info() {
    echo -e "${BLUE}[SETUP]${NC} $1"
}

# Check if we're running as root (needed for systemd service)
check_root() {
    if [[ $EUID -eq 0 ]]; then
        print_warning "Running as root. This is needed for systemd service installation."
        return 0
    else
        print_info "Not running as root. Will use --user flag for systemd service."
        return 1
    fi
}

# Function to check if .env file exists and is configured
check_env_file() {
    if [ ! -f ".env" ]; then
        print_error ".env file not found!"
        print_info "Please copy .env.example to .env and configure it:"
        print_info "cp .env.example .env"
        print_info "Then edit .env with your API keys and configuration."
        exit 1
    fi
    
    # Check if required variables are set
    if ! grep -q "TELEGRAM_BOT_TOKEN=your_bot_token_here" .env; then
        print_status ".env file appears to be configured"
    else
        print_error "Please configure your .env file with actual values!"
        print_info "Edit .env and replace placeholder values with actual API keys."
        exit 1
    fi
}

# Function to setup Python virtual environment
setup_venv() {
    print_info "Setting up Python virtual environment..."
    
    if [ ! -d ".venv" ]; then
        python3 -m venv .venv
        print_status "Virtual environment created"
    else
        print_status "Virtual environment already exists"
    fi
    
    # Activate virtual environment
    source .venv/bin/activate
    
    # Upgrade pip
    pip install --upgrade pip
    
    # Install requirements
    print_info "Installing Python dependencies..."
    pip install -r requirements.txt
    
    # Freeze current versions back to requirements.txt
    print_info "Freezing dependency versions..."
    pip freeze > requirements.txt
    
    print_status "Dependencies installed and frozen successfully"
}

# Function to create necessary directories
setup_directories() {
    print_info "Creating necessary directories..."
    mkdir -p data
    mkdir -p logs
    mkdir -p src
    
    # Create initial whitelist if it doesn't exist
    if [ ! -f "data/whitelist.json" ]; then
        print_info "Creating initial whitelist file..."
        cat > data/whitelist.json << 'EOF'
{
  "users": [],
  "user_info": {},
  "last_updated": "2025-06-16T00:00:00.000000",
  "description": "Whitelist for VibeMessageBot - Add user IDs to allow access"
}
EOF
        print_status "Initial whitelist created at data/whitelist.json"
        print_warning "Remember to add authorized user IDs using whitelist-manager.html"
    fi
    
    print_status "Directories created"
}

# Function to test bot configuration
test_bot() {
    print_info "Testing bot configuration..."
    source .venv/bin/activate
    
    # Simple import test
    python3 -c "
import sys
import os
sys.path.append('./src')

try:
    from dotenv import load_dotenv
    load_dotenv()
    
    # Check required environment variables
    token = os.getenv('TELEGRAM_BOT_TOKEN')
    ai_key = os.getenv('GOOGLE_AI_API_KEY')
    
    if not token or token == 'your_bot_token_here':
        print('ERROR: TELEGRAM_BOT_TOKEN not configured')
        sys.exit(1)
    
    if not ai_key or ai_key == 'your_google_ai_api_key_here':
        print('ERROR: GOOGLE_AI_API_KEY not configured')
        sys.exit(1)
    
    print('Configuration test passed!')
    
except ImportError as e:
    print(f'Import error: {e}')
    sys.exit(1)
except Exception as e:
    print(f'Configuration error: {e}')
    sys.exit(1)
"
    
    if [ $? -eq 0 ]; then
        print_status "Bot configuration test passed"
    else
        print_error "Bot configuration test failed"
        exit 1
    fi
}

# Function to create systemd service
create_systemd_service() {
    local IS_ROOT=$1
    local SERVICE_FILE
    local SYSTEMCTL_CMD
    
    if [ "$IS_ROOT" = true ]; then
        SERVICE_FILE="/etc/systemd/system/vibemessagebot.service"
        SYSTEMCTL_CMD="systemctl"
    else
        mkdir -p ~/.config/systemd/user
        SERVICE_FILE="$HOME/.config/systemd/user/vibemessagebot.service"
        SYSTEMCTL_CMD="systemctl --user"
    fi
    
    print_info "Creating systemd service file at $SERVICE_FILE"
    
    cat > "$SERVICE_FILE" << EOF
[Unit]
Description=VibeMessageBot - Telegram Inline Bot
After=network.target

[Service]
Type=simple
User=$USER
WorkingDirectory=$(pwd)
Environment=PATH=$(pwd)/.venv/bin
ExecStart=$(pwd)/.venv/bin/python $(pwd)/bot.py
Restart=always
RestartSec=10
StandardOutput=journal
StandardError=journal

[Install]
WantedBy=default.target
EOF

    # Reload systemd and enable service
    $SYSTEMCTL_CMD daemon-reload
    $SYSTEMCTL_CMD enable vibemessagebot.service
    
    print_status "Systemd service created and enabled"
    
    # Store the systemctl command for later use
    echo "$SYSTEMCTL_CMD" > .systemctl_cmd
}

# Function to start the service
start_service() {
    local SYSTEMCTL_CMD
    
    if [ -f ".systemctl_cmd" ]; then
        SYSTEMCTL_CMD=$(cat .systemctl_cmd)
    else
        if check_root; then
            SYSTEMCTL_CMD="systemctl"
        else
            SYSTEMCTL_CMD="systemctl --user"
        fi
    fi
    
    print_info "Starting VibeMessageBot service..."
    $SYSTEMCTL_CMD start vibemessagebot.service
    
    # Check if service started successfully
    sleep 2
    if $SYSTEMCTL_CMD is-active --quiet vibemessagebot.service; then
        print_status "VibeMessageBot service started successfully!"
        print_info "Service status:"
        $SYSTEMCTL_CMD status vibemessagebot.service --no-pager
    else
        print_error "Failed to start VibeMessageBot service"
        print_info "Check logs with: $SYSTEMCTL_CMD logs vibemessagebot.service"
        exit 1
    fi
}

# Function to show service status
show_status() {
    local SYSTEMCTL_CMD
    
    if [ -f ".systemctl_cmd" ]; then
        SYSTEMCTL_CMD=$(cat .systemctl_cmd)
    else
        if check_root; then
            SYSTEMCTL_CMD="systemctl"
        else
            SYSTEMCTL_CMD="systemctl --user"
        fi
    fi
    
    print_info "VibeMessageBot Service Status:"
    $SYSTEMCTL_CMD status vibemessagebot.service --no-pager
    
    print_info ""
    print_info "Useful commands:"
    print_info "  View logs: $SYSTEMCTL_CMD logs -f vibemessagebot.service"
    print_info "  Restart:   $SYSTEMCTL_CMD restart vibemessagebot.service"
    print_info "  Stop:      $SYSTEMCTL_CMD stop vibemessagebot.service"
    print_info "  Update:    git pull && $SYSTEMCTL_CMD restart vibemessagebot.service"
}

# Main execution
main() {
    print_status "Starting VibeMessageBot setup..."
    
    # Check if this is an update (service already exists)
    local IS_ROOT
    if check_root; then
        IS_ROOT=true
        SERVICE_EXISTS=$(systemctl list-unit-files | grep vibemessagebot.service || true)
    else
        IS_ROOT=false
        SERVICE_EXISTS=$(systemctl --user list-unit-files | grep vibemessagebot.service || true)
    fi
    
    if [ -n "$SERVICE_EXISTS" ]; then
        print_info "Existing service detected. This appears to be an update."
        print_info "Stopping existing service..."
        
        if [ "$IS_ROOT" = true ]; then
            systemctl stop vibemessagebot.service || true
        else
            systemctl --user stop vibemessagebot.service || true
        fi
    fi
    
    # Run setup steps
    check_env_file
    setup_directories
    setup_venv
    test_bot
    
    # Create or update systemd service
    create_systemd_service "$IS_ROOT"
    
    # Start the service
    start_service
    
    print_status "Setup completed successfully!"
    print_info ""
    print_info "Your VibeMessageBot is now running!"
    print_info "You can use it in any Telegram chat by typing: @vibemessagebot <your topic>"
    print_info ""
    
    # Show status
    show_status
}

# Handle command line arguments
case "${1:-}" in
    "status"|"--status")
        show_status
        ;;
    "setup"|"--setup"|"")
        main
        ;;
    *)
        echo "Usage: $0 [setup|status]"
        echo "  setup  - Run full setup (default)"
        echo "  status - Show service status"
        exit 1
        ;;
esac
