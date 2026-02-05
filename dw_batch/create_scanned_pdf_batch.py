#!/usr/bin/env python3
"""Create batch requests for scanned PDFs by converting pages to images.

For PDFs that are scanned (no extractable text), this script:
1. Detects scanned PDFs (minimal text content)
2. Converts each page to an image
3. Sends images to vision model with base64 encoding

CONTEXT LIMITS:
- Model context: 128K tokens
- Each image page: ~3-4K tokens
- Max pages per request: ~30 pages
- For longer PDFs, creates multiple requests (chunked)

USAGE:
  # Process scanned PDFs in directory
  python create_scanned_pdf_batch.py --input-dir /path/to/scans/

  # Process specific file
  python create_scanned_pdf_batch.py --files document.pdf

  # Custom chunk size (pages per request)
  python create_scanned_pdf_batch.py --chunk-size 20
"""

import json
import os
import base64
import argparse
from pathlib import Path
from datetime import datetime
from dotenv import load_dotenv
import glob

# Parse arguments
parser = argparse.ArgumentParser(
    description='Create batch requests for scanned PDFs (converts to images)',
    formatter_class=argparse.RawDescriptionHelpFormatter
)
parser.add_argument('--files', nargs='+', metavar='FILE', help='Specific PDF files to process')
parser.add_argument('--input-dir', metavar='DIR', help='Directory to scan for PDFs (default: ../../data/)')
parser.add_argument('--chunk-size', type=int, default=30, metavar='PAGES',
                    help='Max pages per request (default: 30, considers context limit)')
parser.add_argument('--force-scan', action='store_true',
                    help='Treat all PDFs as scanned (skip text extraction check)')
args = parser.parse_args()

# Load environment variables
load_dotenv()

# Import PDF processing libraries
try:
    from pypdf import PdfReader
    from pdf2image import convert_from_path
    import tempfile
except ImportError as e:
    print(f"ERROR: Missing required library: {e}")
    print("\nInstall dependencies:")
    print("  pip install pypdf pdf2image")
    print("  # Also need poppler-utils on system: apt-get install poppler-utils")
    exit(1)

# Read prompt template
with open('prompt.txt', 'r') as f:
    prompt_template = f.read()

# Configuration
INPUT_DIR = Path(args.input_dir) if args.input_dir else Path('../../data')
CHUNK_SIZE = args.chunk_size
TOKENS_PER_PAGE = 3500  # Conservative estimate: 3-4K tokens per image page
MAX_CONTEXT = 128000  # 128K tokens context limit

# Validate chunk size
max_safe_pages = MAX_CONTEXT // TOKENS_PER_PAGE
if CHUNK_SIZE > max_safe_pages:
    print(f"⚠ WARNING: Chunk size {CHUNK_SIZE} may exceed context limit")
    print(f"  Recommended max: {max_safe_pages} pages ({MAX_CONTEXT} tokens / {TOKENS_PER_PAGE} tokens/page)")
    print(f"  Continuing with {CHUNK_SIZE} pages per request...\n")

print("="*70)
print("SCANNED PDF BATCH REQUEST CONFIGURATION")
print("="*70)
print(f"Model: {os.getenv('DOUBLEWORD_MODEL', 'Qwen/Qwen3-VL-235B-A22B-Instruct-FP8')}")
print(f"Max tokens: {os.getenv('MAX_TOKENS', '5000')}")
print(f"Pages per request: {CHUNK_SIZE}")
print(f"Estimated tokens per page: {TOKENS_PER_PAGE}")
print(f"Force scan mode: {args.force_scan}")
print("="*70)
print()

# Collect PDF files
pdf_files = []

if args.files:
    pdf_files = [Path(f).resolve() for f in args.files]
    print(f"Processing {len(pdf_files)} specified PDF(s)\n")
else:
    for pdf_pattern in ['**/*.pdf', '**/*.PDF']:
        pdf_files.extend(glob.glob(str(INPUT_DIR / pdf_pattern), recursive=True))
    pdf_files = sorted(set(pdf_files))
    print(f"Found {len(pdf_files)} PDFs in {INPUT_DIR}\n")

if not pdf_files:
    print("No PDF files found. Exiting.")
    exit(0)


def is_scanned_pdf(pdf_path, threshold=100):
    """Detect if a PDF is scanned (has minimal extractable text).

    Args:
        pdf_path: Path to PDF file
        threshold: Min characters per page to consider "text-based" (default: 100)

    Returns:
        bool: True if scanned (minimal text), False if text-based PDF
    """
    try:
        reader = PdfReader(pdf_path)
        total_chars = 0
        for page in reader.pages[:5]:  # Check first 5 pages only
            text = page.extract_text() or ""
            total_chars += len(text.strip())

        avg_chars_per_page = total_chars / min(5, len(reader.pages))
        return avg_chars_per_page < threshold

    except Exception as e:
        print(f"  ⚠ Warning: Could not analyze PDF ({e}), assuming scanned")
        return True


def pdf_to_images(pdf_path, dpi=150):
    """Convert PDF pages to images.

    Args:
        pdf_path: Path to PDF file
        dpi: Resolution for conversion (default: 150, good balance of quality/size)

    Returns:
        list: PIL Image objects, one per page
    """
    # Convert PDF to images using pdf2image
    # This uses poppler under the hood
    images = convert_from_path(pdf_path, dpi=dpi)
    return images


def image_to_base64(pil_image, format='JPEG', quality=85):
    """Convert PIL Image to base64 string.

    Args:
        pil_image: PIL Image object
        format: Image format (JPEG or PNG)
        quality: JPEG quality (1-100, higher = better quality/larger size)

    Returns:
        tuple: (base64_string, mime_type)
    """
    import io

    buffer = io.BytesIO()
    pil_image.save(buffer, format=format, quality=quality)
    buffer.seek(0)

    b64_data = base64.b64encode(buffer.read()).decode('utf-8')
    mime_type = f"image/{format.lower()}"

    return b64_data, mime_type


# Process PDFs
requests = []
failed_files = []

for idx, pdf_path in enumerate(pdf_files, 1):
    pdf_path = Path(pdf_path)
    print(f"[{idx}/{len(pdf_files)}] Processing {pdf_path.name}...")

    try:
        # Check if PDF is scanned
        if args.force_scan:
            is_scanned = True
            print(f"  → Force scan mode: treating as scanned PDF")
        else:
            is_scanned = is_scanned_pdf(pdf_path)
            if is_scanned:
                print(f"  → Detected as scanned PDF (minimal text)")
            else:
                print(f"  ⚠ Skipping: appears to be text-based PDF")
                print(f"    Use create_batch.py for text extraction, or --force-scan to override")
                continue

        # Convert PDF to images
        print(f"  → Converting pages to images...")
        images = pdf_to_images(pdf_path)
        total_pages = len(images)
        print(f"  ✓ Converted {total_pages} pages to images")

        # Chunk pages if necessary
        num_chunks = (total_pages + CHUNK_SIZE - 1) // CHUNK_SIZE  # Ceiling division
        if num_chunks > 1:
            print(f"  → Splitting into {num_chunks} requests ({CHUNK_SIZE} pages each)")

        # Create batch requests for each chunk
        for chunk_idx in range(num_chunks):
            start_page = chunk_idx * CHUNK_SIZE
            end_page = min(start_page + CHUNK_SIZE, total_pages)
            chunk_images = images[start_page:end_page]

            # Convert each page to base64
            content_parts = [
                {"type": "text", "text": prompt_template}
            ]

            for page_idx, img in enumerate(chunk_images, start=start_page + 1):
                # Convert image to base64
                b64_data, mime_type = image_to_base64(img)

                # Add to content
                content_parts.append({
                    "type": "image_url",
                    "image_url": {
                        "url": f"data:{mime_type};base64,{b64_data}"
                    }
                })

            # Create custom_id
            safe_filename = pdf_path.stem.replace('%', '_').replace(' ', '_').replace('&', 'and')[:40]
            if num_chunks > 1:
                custom_id = f"scan-{safe_filename}-chunk{chunk_idx+1}of{num_chunks}"
            else:
                custom_id = f"scan-{safe_filename}"

            # Create batch request
            request = {
                "custom_id": custom_id,
                "method": "POST",
                "url": os.getenv('CHAT_COMPLETIONS_ENDPOINT', '/v1/chat/completions'),
                "body": {
                    "model": os.getenv('DOUBLEWORD_MODEL', 'Qwen/Qwen3-VL-235B-A22B-Instruct-FP8'),
                    "messages": [
                        {
                            "role": "user",
                            "content": content_parts
                        }
                    ],
                    "max_tokens": int(os.getenv('MAX_TOKENS', '5000'))
                }
            }
            requests.append(request)

            print(f"    Chunk {chunk_idx+1}/{num_chunks}: pages {start_page+1}-{end_page} ({len(chunk_images)} pages)")

    except Exception as e:
        print(f"\n{'!'*60}")
        print(f"ERROR DURING PDF PROCESSING: {pdf_path.name}")
        print(f"{'!'*60}")
        print(f"File: {pdf_path}")
        print(f"Error type: {type(e).__name__}")
        print(f"Error message: {str(e)}")
        print(f"{'!'*60}\n")
        failed_files.append((str(pdf_path), f"{type(e).__name__}: {str(e)}"))
        continue

# Save to logs folder
logs_dir = Path('../../dw_batch_output/logs')
logs_dir.mkdir(parents=True, exist_ok=True)

timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
output_file = logs_dir / f'batch_requests_scanned_pdf_{timestamp}.jsonl'

with open(output_file, 'w') as f:
    for req in requests:
        f.write(json.dumps(req) + '\n')

print(f"\n{'='*70}")
print(f"✓ Created {output_file} with {len(requests)} scanned PDF requests")

if failed_files:
    print(f"\n⚠ Failed to process {len(failed_files)} files:")
    for path, reason in failed_files:
        print(f"  - {Path(path).name}: {reason}")

print(f"\n{'='*70}")
print("NEXT STEPS:")
print(f"1. Review the batch file: {output_file}")
print(f"2. Submit the batch: python submit_batch.py")
print("3. Monitor progress: python poll_and_process.py")
print("="*70)
print("\nNOTE: Scanned PDF processing uses vision models and is more token-intensive")
print(f"      Each page ≈ {TOKENS_PER_PAGE} tokens, chunked at {CHUNK_SIZE} pages/request")
print("="*70)
