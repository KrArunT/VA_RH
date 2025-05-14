#!/bin/bash

# Load environment variables from .env file
set -o allexport
source .env
set +o allexport

# Define the path to the virtual environment and the script
VENV_PATH="/home/amd/workspace/va_deployment/env/bin/activate"
SCRIPT_DIR="/home/amd/workspace/va_deployment"
SCRIPT_AMD="src_amd/pub_va.py"

# Function to run the script on a remote host using sshpass
run_remote_script_amd() {
    local HOST=$1
    local PASS=$2
    echo "Connecting to $HOST..."
    sshpass -p "$PASS" ssh -o StrictHostKeyChecking=no "$HOST" "cd $SCRIPT_DIR && source $VENV_PATH && python3 $SCRIPT_AMD"
}

SCRIPT_INTEL="src_intel/pub_va.py"

# Function to run the script on a remote host using sshpass
run_remote_script_intel() {
    local HOST=$1
    local PASS=$2
    echo "Connecting to $HOST..."
    sshpass -p "$PASS" ssh -o StrictHostKeyChecking=no "$HOST" "cd $SCRIPT_DIR && source $VENV_PATH && python3 $SCRIPT_INTEL"
}

# Run the script on AMD machine
run_remote_script_amd "$AMD_HOST" "$AMD_PASS"

# Run the script on Intel machine
run_remote_script_intel "$INTEL_HOST" "$INTEL_PASS"
