#!/bin/bash

# GridPulse One-Command Setup Script
# This script installs Docker, Docker Compose, and starts the project.

set -e

echo "Starting GridPulse Auto-Setup..."

# 1. Check for Docker
if ! [ -x "$(command -v docker)" ]; then
    echo "Docker not found. Installing Docker..."
    curl -fsSL https://get.docker.com -o get-docker.sh
    sudo sh get-docker.sh
    sudo usermod -aG docker $USER
    rm get-docker.sh
    echo "Docker installed successfully."
else
    echo "Docker is already installed."
fi

# 2. Check for Docker Compose
if ! docker compose version >/dev/null 2>&1; then
    echo "Docker Compose plugin not found. Installing..."
    sudo apt-get update
    sudo apt-get install -y docker-compose-plugin
    echo "Docker Compose installed."
else
    echo "Docker Compose is already available."
fi

# 3. Handle .env file
if [ ! -f .env ]; then
    echo ".env file missing. Creating from example..."
    cp .env.example .env
    echo "Created .env. Please ensure you edit it with your API keys later."
fi

# Core directory provisioning (V6 Hardening)
# Pre-creating these prevents Docker from creating them as root.
mkdir -p data logs

# Capture and append host identification metadata for dynamic permission mapping
# Using grep to avoid duplicate entries if the script is run multiple times
if ! grep -q "HOST_UID" .env; then
    echo "HOST_UID=$(id -u)" >> .env
    echo "HOST_GID=$(id -g)" >> .env
fi

# 4. Build and Run
echo "Building and starting GridPulse..."
sudo docker compose up -d --build

echo "-------------------------------------------------------"
echo "SUCCESS! GridPulse is running in the background."
echo "   - Logs: sudo docker compose logs -f"
echo "   - Stop: sudo docker compose down"
echo "-------------------------------------------------------"
