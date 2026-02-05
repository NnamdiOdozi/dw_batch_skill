#!/usr/bin/env python3
"""Create batch requests for image analysis using vision models.

This is a custom script for processing images with the Doubleword vision API.
Images are base64-encoded and sent to the Qwen3-VL model.

CONFIGURATION:
- Edit prompt.txt for your task instructions
- Edit config.toml for model, max_tokens, and other settings

USAGE:
  # Process all images in default directory
  python create_image_batch.py --output-dir /path/to/output/

  # Process specific image files
  python create_image_batch.py --output-dir /path/to/output/ --files image1.jpg image2.png

  # Process images from custom directory
  python create_image_batch.py --output-dir /path/to/output/ --input-dir /path/to/images/
"""

import json
import os
import base64
import argparse
from pathlib import Path
from datetime import datetime
from dotenv import load_dotenv
import tomllib
import sys

# Load configuration from config.toml and .env.dw
def load_config():
    """Load config from dw_batch/config.toml and merge with .env.dw secrets."""
    config_path = Path(__file__).parent / 'config.toml'
    if not config_path.exists():
        print(f"Error: Configuration file not found: {config_path}")
        print("Please ensure config.toml exists")
        sys.exit(1)

    with open(config_path, 'rb') as f:
        config = tomllib.load(f)

    env_path = Path(__file__).parent / '.env.dw'
    load_dotenv(dotenv_path=env_path)

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

# Parse arguments
parser = argparse.ArgumentParser(description='Create image batch requests')
parser.add_argument('--files', nargs='+', metavar='FILE', help='Specific image files to process')
parser.add_argument('--input-dir', metavar='DIR', help='Directory to scan for images (default: ../../data/)')
parser.add_argument(
    '--output-dir',
    metavar='DIR',
    required=True,
    help='Output directory for results (REQUIRED - agent must pass absolute path to project root)'
)
parser.add_argument(
    '--logs-dir',
    metavar='DIR',
    help='Directory for logs and batch files (default: {output-dir}/logs)'
)
args = parser.parse_args()

# Read prompt template
with open('prompt.txt', 'r') as f:
    prompt_template = f.read()

# Configuration
IMAGE_EXTENSIONS = ['.jpg', '.jpeg', '.png']
INPUT_DIR = Path(args.input_dir) if args.input_dir else Path('../../data')

# Collect image files
image_files = []

if args.files:
    # Use specific files provided
    image_files = [Path(f).resolve() for f in args.files]
    print(f"Processing {len(image_files)} specified image(s)\n")
else:
    # Find all images in directory
    for ext in IMAGE_EXTENSIONS:
        image_files.extend(INPUT_DIR.glob(f'*{ext}'))
        image_files.extend(INPUT_DIR.glob(f'*{ext.upper()}'))
    image_files = sorted(image_files)
    print(f"Found {len(image_files)} images in {INPUT_DIR}\n")

# Get config values
model = config['models']['default_model']
max_tokens = config['output']['max_tokens']
chat_endpoint = config['api']['chat_completions_endpoint']

print("="*60)
print("IMAGE BATCH REQUEST CONFIGURATION")
print("="*60)
print(f"Model: {model}")
print(f"Max tokens: {max_tokens}")
print(f"Auth token: ...{auth_token[-4:]}")
if args.files:
    print(f"Mode: Specific files ({len(image_files)} images)")
else:
    print(f"Mode: Directory scan ({INPUT_DIR})")
    print(f"Found: {len(image_files)} images")
print("="*60)
print()

if not image_files:
    print("No image files found. Exiting.")
    exit(0)

# Create batch requests
requests = []
failed_files = []

for idx, image_path in enumerate(image_files, 1):
    print(f"[{idx}/{len(image_files)}] Processing {image_path.name}...")

    try:
        # Read and base64 encode image
        with open(image_path, 'rb') as f:
            image_data = base64.b64encode(f.read()).decode('utf-8')

        # Determine mime type
        ext = image_path.suffix.lower()
        mime_type = f"image/{'jpeg' if ext in ['.jpg', '.jpeg'] else 'png'}"

        # Create safe custom_id
        safe_filename = image_path.stem.replace('%', '_').replace(' ', '_').replace('&', 'and')[:55]

        # Create batch request with vision model
        request = {
            "custom_id": f"image-{safe_filename}",
            "method": "POST",
            "url": chat_endpoint,
            "body": {
                "model": model,
                "messages": [
                    {
                        "role": "user",
                        "content": [
                            {
                                "type": "text",
                                "text": prompt_template
                            },
                            {
                                "type": "image_url",
                                "image_url": {
                                    "url": f"data:{mime_type};base64,{image_data}"
                                }
                            }
                        ]
                    }
                ],
                "max_tokens": max_tokens
            }
        }
        requests.append(request)
        print(f"  ✓ Encoded {len(image_data)} bytes [{mime_type}]")

    except Exception as e:
        print(f"\n{'!'*60}")
        print(f"ERROR DURING IMAGE PROCESSING: {image_path.name}")
        print(f"{'!'*60}")
        print(f"File: {image_path}")
        print(f"Error type: {type(e).__name__}")
        print(f"Error message: {str(e)}")
        print(f"{'!'*60}\n")
        failed_files.append((str(image_path), f"{type(e).__name__}: {str(e)}"))
        continue

# Save to logs folder
logs_dir = Path(args.logs_dir) if args.logs_dir else Path(args.output_dir) / 'logs'
logs_dir.mkdir(parents=True, exist_ok=True)

timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
output_file = logs_dir / f'batch_requests_{timestamp}.jsonl'

with open(output_file, 'w') as f:
    for req in requests:
        f.write(json.dumps(req) + '\n')

print(f"\n{'='*60}")
print(f"✓ Created {output_file} with {len(requests)} image requests")

if failed_files:
    print(f"\n⚠ Failed to process {len(failed_files)} files:")
    for path, reason in failed_files:
        print(f"  - {Path(path).name}: {reason}")

print(f"\n{'='*60}")
print("NEXT STEPS:")
print(f"1. Review the batch file: {output_file}")
print(f"2. Submit the batch: python submit_batch.py")
print("3. Monitor progress: python poll_and_process.py")
print("="*60)
