#!/usr/bin/env python3
"""Upload batch requests and submit batch job to Doubleword API."""

import os
import sys
import glob
import argparse
from pathlib import Path
from datetime import datetime
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
    description='Upload and submit batch requests to Doubleword API'
)
parser.add_argument(
    'batch_file',
    nargs='?',
    help='Path to batch_requests_*.jsonl file (default: most recent in logs/)'
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

args = parser.parse_args()

# Get config values
base_url = config['api']['base_url']
completion_window = config['batch']['completion_window']
chat_endpoint = config['api']['chat_completions_endpoint']

# Initialize client with Doubleword credentials
client = OpenAI(
    api_key=auth_token,
    base_url=base_url
)

# Print configuration being used
print("="*60)
print("BATCH SUBMISSION")
print("="*60)
print(f"Doubleword API: {base_url}")
print(f"Auth Token: {'*' * 20}...{auth_token[-4:]}")
print(f"Completion Window: {completion_window}")
print(f"Endpoint: {chat_endpoint}")
print("="*60)
print()

# Determine output and logs directories
output_dir = Path(args.output_dir)
logs_dir = Path(args.logs_dir) if args.logs_dir else (output_dir / 'logs')

# Print absolute paths for clarity
print(f"Output directory: {output_dir.resolve()}")
print(f"Logs directory: {logs_dir.resolve()}")
print()

# Determine which batch file to upload
if args.batch_file:
    # User specified a file path
    batch_file_path = args.batch_file
    if not os.path.exists(batch_file_path):
        print(f"Error: File '{batch_file_path}' not found.")
        exit(1)
else:
    # Look for most recent batch file in logs/ folder
    if not logs_dir.exists():
        print(f"Error: {logs_dir} directory not found. Run create_batch.py first.")
        exit(1)

    batch_files = list(logs_dir.glob('batch_requests_*.jsonl'))
    if not batch_files:
        print(f"Error: No batch_requests_*.jsonl files found in {logs_dir}.")
        print("Run create_batch.py first to create a batch file.")
        exit(1)

    # Get most recent batch file
    batch_file_path = max(batch_files, key=lambda p: p.stat().st_mtime)

print(f"Uploading: {batch_file_path}")
print()

# Upload batch file
with open(batch_file_path, "rb") as file:
    batch_file = client.files.create(
        file=file,
        purpose="batch"
    )

print(f"✓ File uploaded successfully!")
print(f"  File ID: {batch_file.id}")

# Create batch job
print(f"\nCreating batch job (completion window: {completion_window})...")
batch = client.batches.create(
    input_file_id=batch_file.id,
    endpoint=chat_endpoint,
    completion_window=completion_window
)

print(f"✓ Batch job created successfully!")
print(f"  Batch ID: {batch.id}")
print(f"  Status: {batch.status}")

# Save batch ID to logs/ folder with timestamp
logs_dir.mkdir(parents=True, exist_ok=True)

timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
batch_id_file = logs_dir / f'batch_id_{timestamp}.txt'
with open(batch_id_file, 'w') as f:
    f.write(batch.id)

print(f"\n✓ Batch ID saved to {batch_id_file}")
print()
print("="*60)
print("NEXT STEP:")
print("  python poll_and_process.py")
print("="*60)
