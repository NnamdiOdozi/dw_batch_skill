#!/usr/bin/env python3
"""Download batch results and save summaries to data/summaries/."""

import os
import sys
import glob
import json
import argparse
from pathlib import Path
from datetime import datetime
import tomllib
from openai import OpenAI
from dotenv import load_dotenv

# Load configuration from config.toml and .env.dw
def load_config():
    """Load config from config.toml and merge with .env.dw secrets."""
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
    description='Download batch results and save to output directory'
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
    help='Specific batch ID to process (default: most recent batch_id file in logs/)'
)

args = parser.parse_args()

# Get config values
base_url = config['api']['base_url']

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
    # Find most recent batch_id file in logs/
    if not logs_dir.exists():
        print(f"Error: {logs_dir} directory not found.")
        exit(1)

    batch_id_files = list(logs_dir.glob('batch_id_*.txt'))
    if not batch_id_files:
        print("Error: No batch_id_*.txt files found in logs/.")
        exit(1)

    latest_batch_id_file = max(batch_id_files, key=lambda p: p.stat().st_mtime)
    with open(latest_batch_id_file, 'r') as f:
        batch_id = f.read().strip()

print(f"Retrieving batch results: {batch_id}\n")

# Get batch status
batch = client.batches.retrieve(batch_id)

if batch.status != 'completed':
    print(f"✗ Batch not completed yet. Status: {batch.status}")
    exit(1)

print(f"✓ Batch completed successfully")
print(f"Output file ID: {batch.output_file_id}\n")

# Download results file
print("Downloading results...")
file_response = client.files.content(batch.output_file_id)

# Create output directory
output_dir.mkdir(parents=True, exist_ok=True)
print(f"Output directory: {output_dir.resolve()}")
print(f"Summaries will be saved to: {output_dir}/\n")

# Detect if prompt expects JSON output
prompt_expects_json = False
try:
    prompt_path = Path(__file__).parent / 'prompt.txt'
    with open(prompt_path, 'r') as f:
        prompt_content = f.read().lower()
        json_keywords = ['json', 'structured', 'parse', 'return as', 'output format']
        prompt_expects_json = any(keyword in prompt_content for keyword in json_keywords)
        if prompt_expects_json:
            print("JSON output detected in prompt - will validate JSON structure\n")
except FileNotFoundError:
    pass  # prompt.txt not found, skip JSON validation

# Detect response type from first result line
first_line = next((l for l in file_response.text.split('\n') if l.strip()), None)
if first_line:
    first_result = json.loads(first_line)
    is_embeddings = 'data' in first_result.get('response', {}).get('body', {})
else:
    is_embeddings = False

# Handle embeddings separately
if is_embeddings:
    timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
    embeddings_dir = output_dir / 'embeddings' / f'batch_{timestamp}'
    embeddings_dir.mkdir(parents=True, exist_ok=True)
    print(f"Embeddings batch detected - saving to: {embeddings_dir}/\n")

    results_count = 0
    for line in file_response.text.split('\n'):
        if not line.strip():
            continue

        result = json.loads(line)
        custom_id = result['custom_id']
        body = result['response']['body']

        # Extract embedding data
        embedding_data = body['data'][0]
        model = body.get('model', 'unknown')
        dimensions = len(embedding_data['embedding'])

        # Save embedding as JSON
        output_file = embeddings_dir / f'{custom_id}.json'
        with open(output_file, 'w') as f:
            json.dump({
                'custom_id': custom_id,
                'model': model,
                'dimensions': dimensions,
                'embedding': embedding_data['embedding']
            }, f, indent=2)

        print(f"✓ Saved: {output_file.name} ({dimensions} dimensions)")
        results_count += 1

    print("\n" + "="*60)
    print("EMBEDDINGS SUMMARY")
    print("="*60)
    print(f"Total embeddings saved: {results_count}")
    print(f"Output folder: {embeddings_dir}")
    print("="*60)
    sys.exit(0)

# Process each result with quality checks (chat completions)
# Create timestamped summaries folder
batch_timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
summaries_dir = output_dir / 'summaries' / f'batch_{batch_timestamp}'
summaries_dir.mkdir(parents=True, exist_ok=True)
print(f"Summaries batch - saving to: {summaries_dir}/\n")

results_count = 0
quality_issues = []
empty_outputs = []
too_short_outputs = []
invalid_json_outputs = []

MIN_LENGTH_THRESHOLD = 50  # Characters
SHORT_LENGTH_THRESHOLD = 200  # Warn if output is suspiciously short

for line in file_response.text.split('\n'):
    if not line.strip():
        continue

    result = json.loads(line)
    custom_id = result['custom_id']

    # Extract summary from response
    summary = result['response']['body']['choices'][0]['message']['content']

    # Extract filename from custom_id (e.g., "summary-DGM" -> "DGM")
    filename = custom_id.replace('summary-', '')

    # Quality checks
    summary_length = len(summary)

    # Check for empty/short outputs
    if summary_length < MIN_LENGTH_THRESHOLD:
        empty_outputs.append((filename, summary_length))
        print(f"⚠️  {filename}: Empty or very short output ({summary_length} chars)")
    elif summary_length < SHORT_LENGTH_THRESHOLD:
        too_short_outputs.append((filename, summary_length))
        print(f"⚠️  {filename}: Suspiciously short output ({summary_length} chars)")

    # JSON validation (if prompt expects JSON)
    json_valid = None
    if prompt_expects_json:
        try:
            json.loads(summary)
            json_valid = True
        except json.JSONDecodeError as e:
            json_valid = False
            invalid_json_outputs.append((filename, str(e)))
            print(f"⚠️  {filename}: Invalid JSON - {e}")

    # Save summary to timestamped batch folder
    output_path = summaries_dir / f'{filename}_summary.md'
    with open(output_path, 'w', encoding='utf-8') as f:
        f.write(summary)

    # Print save status with quality indicators
    status_parts = [f"{summary_length} chars"]
    if json_valid is True:
        status_parts.append("valid JSON")
    elif json_valid is False:
        status_parts.append("INVALID JSON")

    status_str = ", ".join(status_parts)

    if summary_length >= MIN_LENGTH_THRESHOLD and (json_valid is None or json_valid):
        print(f"✓ Saved: {output_path} ({status_str})")
    else:
        print(f"✗ Saved (with issues): {output_path} ({status_str})")

    results_count += 1

# Print quality summary
print("\n" + "="*60)
print("QUALITY SUMMARY")
print("="*60)
print(f"Total outputs processed: {results_count}")

# Calculate success count
issues_count = len(empty_outputs) + len(invalid_json_outputs)
success_count = results_count - issues_count
print(f"Successfully processed: {success_count}")

if empty_outputs:
    print(f"\n⚠️  Empty outputs ({len(empty_outputs)}):")
    for fname, length in empty_outputs:
        print(f"  - {fname} ({length} chars)")

if too_short_outputs:
    print(f"\n⚠️  Suspiciously short outputs ({len(too_short_outputs)}):")
    for fname, length in too_short_outputs:
        print(f"  - {fname} ({length} chars)")

if prompt_expects_json:
    valid_json_count = results_count - len(invalid_json_outputs) - len(empty_outputs)
    print(f"\nJSON Validation (prompt expects JSON):")
    print(f"  ✓ Valid JSON: {valid_json_count}")
    if invalid_json_outputs:
        print(f"  ✗ Invalid JSON: {len(invalid_json_outputs)}")
        for fname, error in invalid_json_outputs:
            print(f"    - {fname}: {error}")

if not empty_outputs and not too_short_outputs and not invalid_json_outputs:
    print("\n✓ All outputs look good!")

print(f"\nOutput folder: {summaries_dir}")
print("="*60)
