#!/usr/bin/env python3
"""Poll batch job status and automatically download results when complete."""

import os
import sys
import time
import subprocess
import argparse
from pathlib import Path
import tomllib
from openai import OpenAI
from dotenv import load_dotenv

# Load configuration from config.toml and .env.dw
def load_config():
    """Load config from dw_batch/config.toml and merge with .env.dw secrets."""
    # Load TOML config (non-secrets)
    config_path = Path(__file__).parent / 'config.toml'
    if not config_path.exists():
        print(f"Error: Configuration file not found: {config_path}")
        print("Please ensure config.toml exists")
        sys.exit(1)

    with open(config_path, 'rb') as f:
        config = tomllib.load(f)

    # Load .env.dw for secrets
    env_path = Path(__file__).parent / ".env.dw"
    load_dotenv(dotenv_path=env_path)

    # Check for required secret
    auth_token = os.getenv('DOUBLEWORD_AUTH_TOKEN')
    if not auth_token:
        print("="*60)
        print("ERROR: DOUBLEWORD_AUTH_TOKEN not found")
        print("="*60)
        print("Please ensure you have:")
        print("1. Created .env.dw file from .env.dw.sample")
        print("2. Added your DOUBLEWORD_AUTH_TOKEN to .env.dw")
        print("="*60)
        sys.exit(1)

    return config, auth_token

config, auth_token = load_config()

# Parse command line arguments
parser = argparse.ArgumentParser(
    description='Poll batch job and download results when complete'
)
parser.add_argument(
    '--output-dir',
    metavar='DIR',
    required=True,
    help='Output directory (REQUIRED - agent must pass absolute path to project root)'
)
parser.add_argument(
    '--logs-dir',
    metavar='DIR',
    help='Logs directory (default: {output-dir}/logs)'
)
parser.add_argument(
    '--batch-id',
    metavar='ID',
    help='Specific batch ID to poll (default: most recent batch_id file in logs/)'
)

args = parser.parse_args()

# Get config values
base_url = config['api']['base_url']
polling_interval = config['batch']['polling_interval']

# Initialize client
client = OpenAI(
    api_key=auth_token,
    base_url=base_url
)

# Determine output and logs directories
output_dir = Path(args.output_dir)
logs_dir = Path(args.logs_dir) if args.logs_dir else (output_dir / 'logs')

# Determine batch ID
if args.batch_id:
    batch_id = args.batch_id
else:
    if not logs_dir.exists():
        print(f"Error: {logs_dir} directory not found.")
        print("Run submit_batch.py first to create a batch job.")
        exit(1)

    batch_id_files = list(logs_dir.glob('batch_id_*.txt'))
    if not batch_id_files:
        print("Error: No batch_id_*.txt files found in logs/.")
        print("Run submit_batch.py first to create a batch job.")
        exit(1)

    # Get most recent batch ID file
    latest_batch_id_file = max(batch_id_files, key=lambda p: p.stat().st_mtime)
    with open(latest_batch_id_file, 'r') as f:
        batch_id = f.read().strip()

print("="*60)
print("BATCH MONITORING")
print("="*60)
print(f"Output directory: {output_dir.resolve()}")
print(f"Logs directory: {logs_dir.resolve()}")
if not args.batch_id:
    print(f"Batch ID file: {latest_batch_id_file}")
print(f"Batch ID: {batch_id}")
print(f"Polling interval: {polling_interval}s")
print("="*60)
print("\nPress Ctrl+C to stop polling\n")

try:
    while True:
        batch = client.batches.retrieve(batch_id)
        status = batch.status
        completed = batch.request_counts.completed
        total = batch.request_counts.total

        timestamp = time.strftime('%Y-%m-%d %H:%M:%S')
        print(f"[{timestamp}] Status: {status} | Progress: {completed}/{total}")

        if status == 'completed':
            print("\n✓ Batch completed successfully!")
            print("Downloading and processing results...\n")

            # Run process_results.py with the same output/logs directories and batch ID
            cmd = [sys.executable, 'process_results.py', '--output-dir', str(output_dir), '--batch-id', batch_id]
            if args.logs_dir:
                cmd.extend(['--logs-dir', str(logs_dir)])
            result = subprocess.run(cmd)

            if result.returncode == 0:
                print(f"\n✓ All results saved to {output_dir.resolve()}")
            else:
                print("\n✗ Error processing results")
            break

        elif status == 'failed':
            print(f"\n✗ Batch failed!")
            if hasattr(batch, 'errors') and batch.errors:
                print(f"Errors: {batch.errors}")
            break

        elif status == 'expired':
            print(f"\n✗ Batch expired!")
            break

        elif status == 'cancelled':
            print(f"\n✗ Batch was cancelled!")
            break

        # Wait before next check
        time.sleep(polling_interval)

except KeyboardInterrupt:
    print("\n\nPolling stopped by user")
    print(f"Current status: {status}")
    print("Run this script again to resume polling")
