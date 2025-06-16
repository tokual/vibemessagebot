#!/bin/bash

# Quick update script for VibeMessageBot
# This script pulls the latest changes and restarts the service

set -e

# Colors for output
GREEN='\033[0;32m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

print_status() {
    echo -e "${GREEN}[INFO]${NC} $1"
}

print_info() {
    echo -e "${BLUE}[UPDATE]${NC} $1"
}

print_info "Updating VibeMessageBot..."

# Pull latest changes
print_info "Pulling latest changes from git..."
git pull

# Update Python dependencies
print_info "Updating Python dependencies..."
source .venv/bin/activate
pip install -r requirements.txt --upgrade

# Determine systemctl command
if [ -f ".systemctl_cmd" ]; then
    SYSTEMCTL_CMD=$(cat .systemctl_cmd)
else
    if [[ $EUID -eq 0 ]]; then
        SYSTEMCTL_CMD="systemctl"
    else
        SYSTEMCTL_CMD="systemctl --user"
    fi
fi

# Restart the service
print_info "Restarting VibeMessageBot service..."
$SYSTEMCTL_CMD restart vibemessagebot.service

# Check if service restarted successfully
sleep 2
if $SYSTEMCTL_CMD is-active --quiet vibemessagebot.service; then
    print_status "VibeMessageBot updated and restarted successfully!"
    $SYSTEMCTL_CMD status vibemessagebot.service --no-pager
else
    echo "Failed to restart service. Check logs with: $SYSTEMCTL_CMD logs vibemessagebot.service"
    exit 1
fi
