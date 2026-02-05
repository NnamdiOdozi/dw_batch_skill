#!/usr/bin/env python3
"""Create batch requests for image analysis using vision models.

This is a custom script for processing images with the Doubleword vision API.
Images are base64-encoded and sent to the Qwen3-VL model.

USAGE:
  # Process all images in default directory
  python create_image_batch.py

  # Process specific image files
  python create_image_batch.py --files image1.jpg image2.png

  # Process images from custom directory
  python create_image_batch.py --input-dir /path/to/images/
"""

import json
import os
import base64
import argparse
from pathlib import Path
from datetime import datetime
from dotenv import load_dotenv

# Parse arguments
parser = argparse.ArgumentParser(description='Create image batch requests')
parser.add_argument('--files', nargs='+', metavar='FILE', help='Specific image files to process')
parser.add_argument('--input-dir', metavar='DIR', help='Directory to scan for images (default: ../../data/)')
args = parser.parse_args()

# Load environment variables
load_dotenv()

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

print("="*60)
print("IMAGE BATCH REQUEST CONFIGURATION")
print("="*60)
print(f"Model: {os.getenv('DOUBLEWORD_MODEL', 'Qwen/Qwen3-VL-235B-A22B-Instruct-FP8')}")
print(f"Max tokens: {os.getenv('MAX_TOKENS', '5000')}")
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
            "url": os.getenv('CHAT_COMPLETIONS_ENDPOINT', '/v1/chat/completions'),
            "body": {
                "model": os.getenv('DOUBLEWORD_MODEL', 'Qwen/Qwen3-VL-235B-A22B-Instruct-FP8'),
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
                "max_tokens": int(os.getenv('MAX_TOKENS', '100'))
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
logs_dir = Path('../../dw_batch_output/logs')
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
