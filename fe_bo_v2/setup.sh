#!/bin/bash
echo "Setting up FeBo Ultimate environment..."

# Update system
sudo apt update && sudo apt upgrade -y
sudo apt install -y python3 python3-pip python3-venv git curl wget build-essential
sudo apt install -y docker.io tor espeak   # espeak for TTS

# Setup venv
python3 -m venv febo_env
source febo_env/bin/activate

# Install Python packages
pip install --upgrade pip
pip install -r requirements.txt

# Install Playwright browsers
playwright install chromium

# Pull Docker sandbox image
docker pull python:3.10-slim

# Create directories
mkdir -p memory logs core/reasoning core/memory core/stealth core/self_improvement core/body

# Ensure birth time file exists (will be created on first run)
touch memory/birth_time.txt

echo "Setup complete. Activate environment with: source febo_env/bin/activate"
echo "Then run: python main.py"
