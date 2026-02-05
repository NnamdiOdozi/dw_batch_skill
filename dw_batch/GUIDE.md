# Doubleword Batch Processing - Complete Guide

Detailed reference for the dw_batch_request skill. For quick start, see [SKILL.md](SKILL.md).

---

## Table of Contents

- [Why uv run?](#why-uv-run)
- [Two-Tier Processing System](#two-tier-processing-system)
- [Supported File Formats](#supported-file-formats)
- [Configuration](#configuration)
- [Model Selection Guide](#model-selection-guide)
- [Security & Best Practices](#security-best-practices)
- [SLA / Completion Window](#sla-completion-window-recommendation)
- [Cost Optimization Checkpoint](#cost-optimization-checkpoint)
- [Step-by-Step Workflow](#step-by-step-workflow)
- [Streaming API (Non-Batch)](#streaming-api-non-batch)
- [File Organization](#file-organization)
- [Monitoring & Results](#monitoring-results)
- [Artifact Cleanup](#artifact-cleanup-post-batch)
- [Cost & Performance Estimates](#cost-performance-estimates)
- [Error Handling & Troubleshooting](#error-handling-troubleshooting)
- [Integration Tips for Claude](#integration-tips-for-claude)
- [Best Practices](#best-practices)

---

## Why uv run?

Claude Code spawns multiple shell sessions for different tasks. Without `uv run`, each shell may use a different Python environment, causing:
- "Module not found" errors even after installation
- Version conflicts between shells
- Inconsistent behavior

**How `uv run` solves this:**
- Reads `pyproject.toml` / `uv.lock` to create consistent environment
- Every `uv run python script.py` uses the SAME resolved dependencies
- Works across all Claude Code shells automatically

**Alternative approaches:**
- `uv sync` once, then activate venv in each shell (manual, error-prone)
- Use system Python (dependency conflicts, version issues)
- ✅ **Recommended:** Just prefix all commands with `uv run`

**Platform notes:**
- **Linux/macOS:** Commands above work directly
- **Windows:** Use PowerShell, replace `echo "text" >` with `Set-Content`, paths use `\`

---

## Two-Tier Processing System

⚠️ **CRITICAL:** Choose the right approach for the task complexity.

### **Tier 1: Simple Uniform Processing (80% of cases)**

**Use `create_batch.py` when:**
- ✅ Same prompt for ALL files
- ✅ Same model for ALL files
- ✅ No conditional logic needed
- ✅ Standard extraction (PDF, Excel, CSV, etc.)

**Example:** "Analyze these 50 CSV files for statistical patterns" (one prompt, one model, uniform treatment)

**Workflow:**
```bash
cd .claude/skills
# 1. Edit prompt.txt with your analysis instructions
# 2. Configure config.toml (model, tokens, SLA)
# 3. Run simple workflow
uv run python create_batch.py --input-dir /path/to/files --output-dir $PWD/dw_batch_output
uv run python submit_batch.py --output-dir $PWD/dw_batch_output
uv run python poll_and_process.py --output-dir $PWD/dw_batch_output
```

---

### **Tier 2: Complex Custom Processing (20% of cases)**

**Generate custom code when:**
- ❌ Different prompts per file/group
- ❌ Different models per request (30B for simple, 235B for complex)
- ❌ Conditional logic (if file > 100KB, use model X)
- ❌ Per-file routing or customization

**Example:** "Summarize PDFs with 235B, but analyze CSVs with 30B using different prompts"

**Workflow:**
1. Use extraction functions from `create_batch.py` as a **pattern library**
2. Generate custom Python script for this specific task
3. Create batch_requests_*.jsonl with per-request customization
4. Run submit_batch.py → poll_and_process.py with --output-dir

**Pattern Library (Reference):**
See `create_batch.py` for extraction functions:
- `extract_from_excel()` - Read XLS/XLSX (all sheets)
- `extract_from_csv_tsv()` - Auto-detect delimiter
- `extract_text_pypdf()` / `extract_text_pdfplumber()` - PDF extraction
- `extract_from_docx()`, `extract_from_pptx()`, etc.

---

## Supported File Formats

| Format | Extensions | Handler | Notes |
|--------|------------|---------|-------|
| **PDFs (text-based)** | .pdf | pypdf → pdfplumber (fallback) | Auto-fallback on errors, text extraction |
| **PDFs (scanned)** | .pdf | pdf2image + Vision API | Converts pages to images, OCR via vision model |
| **Excel** | .xls, .xlsx | pandas | Reads all sheets, tab-separated output |
| **CSV/TSV** | .csv, .tsv | pandas | Auto-detects delimiter (`,` `\t` `;` `\|`) |
| **Word** | .docx | python-docx | Extracts paragraphs |
| **PowerPoint** | .pptx | python-pptx | Extracts slide text |
| **OpenOffice** | .odp | odfpy | Presentation text |
| **Text** | .txt, .md | Native | Direct read |
| **Images** | .png, .jpg, .jpeg | Vision API | Direct model processing (captioning, OCR) |
| **Embeddings** | All above formats | Text extraction + embeddings model | Generates vector embeddings for semantic search |

**Smart Imports:** Only loads required libraries based on detected file types (faster startup).

**Vision Capabilities:** Qwen3-VL models have native vision support for image captioning and OCR. Images can be passed directly to the model without text extraction - useful for:
- Product image captioning
- Scanned document OCR
- Handwritten note digitization
- Visual content description

---

## Configuration

**CRITICAL - What Goes Where:**

| Setting | File | Purpose |
|---------|------|---------|
| `DOUBLEWORD_AUTH_TOKEN` | `.env.dw` | Secret API key (gitignored, never commit) |
| model, max_tokens, word_count, polling, thresholds | `config.toml` | All other settings (committed to repo) |

**Agent Rule:** When user says "change the model" or "use 1000 tokens" → **edit `config.toml`**, NOT `.env.dw`

**Only edit `.env.dw`** if user is setting up for the first time or changing their API key.

---

### 1. Configuration Files (config.toml)

```toml
# REQUIRED
[api]
base_url = "https://api.doubleword.ai/v1"
chat_completions_endpoint = "/v1/chat/completions"

# Model Selection
[models]
default_model = "Qwen/Qwen3-VL-30B-A3B-Instruct-FP8"   # Simple tasks (faster, cheaper) - DEFAULT
# default_model = "Qwen/Qwen3-VL-235B-A22B-Instruct-FP8"  # Complex tasks (upgrade for reasoning/analysis)
embedding_model = "BAAI/bge-en-icl"  # Embeddings for semantic search

# SLA / Completion Window
[batch]
completion_window = "1h"  # RECOMMENDED: Fast turnaround (1-2 min results)
# completion_window = "24h"  # Only for massive jobs where cost > speed
polling_interval = 30  # Seconds between status checks

# Output Settings
[output]
max_tokens = 750          # Adjust based on expected output length
summary_word_count = 500  # Used in prompt template (optional placeholder)

# Cost Protection (NEW)
[safety]
max_input_tokens = 250000   # Pause if input tokens exceed this (default: 250K)
max_output_tokens = 100000  # Pause if output tokens exceed this (default: 100K)
# Script will pause for confirmation if EITHER threshold is exceeded
# Use --force flag to override (requires user approval)
# Rule of thumb: 1 token ≈ 0.75 words, or ~4 characters
```

**API token:** Stored in `.env.dw` file (gitignored):
```bash
DOUBLEWORD_AUTH_TOKEN=sk-your-key-here
```

**Cost Protection:** The `[safety]` section prevents accidentally expensive batches. If your estimated costs exceed these thresholds, the script will:
1. Display a detailed warning with actual vs. limit values
2. Suggest cost reduction strategies
3. Exit with error (exit code 1)
4. Allow override with `--force` flag if you're certain

### 2. Prompt Template (prompt.txt)

**Simple example:**
```
Analyze the provided data and identify key patterns, trends, and anomalies.

Structure your analysis in markdown with:
- **Data Overview** (rows, columns, time period)
- **Key Findings** (bullet points)
- **Statistical Summary** (mean, median, outliers)
- **Recommendations**

Be concise and data-driven.
```

**Variables:** Use `{WORD_COUNT}` if you want it substituted from config.toml (optional).

---

## Model Selection Guide

| Task Complexity | Model | Speed | Cost | Use When |
|----------------|-------|-------|------|----------|
| **Simple (DEFAULT)** | Qwen3-VL-30B | Faster | Cheaper | Sentiment analysis, basic Q&A, simple extraction, summaries |
| **Complex** | Qwen3-VL-235B | Slower | ~8x cost | Technical analysis, deep reasoning, structured extraction, code generation |

**Default:** 30B (faster, cheaper) - sufficient for most document summarization tasks

**Upgrade to 235B when:**
- Complex technical analysis required
- Deep reasoning or nuanced understanding needed
- Structured data extraction from complex formats
- 30B output quality is insufficient

---

## Security & Best Practices

### API Key Protection

**Critical rules:**
- `.env` file contains your `DOUBLEWORD_AUTH_TOKEN` - **NEVER commit to git**
- `.env` is already in `.gitignore` - verify it's listed
- `dw_batch_output/logs/` may contain batch artifacts - also in `.gitignore`
- Scripts perform preflight checks - will error if token missing (but won't print it)

### Safe Key Handling

```bash
# ✅ GOOD: Token in .env (gitignored)
DOUBLEWORD_AUTH_TOKEN=sk-your-key-here

# ❌ BAD: Token in shell history or scripts
export DOUBLEWORD_AUTH_TOKEN=sk-your-key-here  # Logged in shell history
```

**If you accidentally commit `.env`:**
1. Immediately rotate (delete and regenerate) your API key at https://app.doubleword.ai
2. Use `git filter-branch` or BFG Repo-Cleaner to remove from git history
3. Push cleaned history (force push if necessary)

### What Gets Logged

**Scripts never log:**
- Full API tokens (only last 4 chars shown: `****...ab12`)
- File contents in plaintext (embedded in batch requests)

**Scripts do log:**
- Batch request files (`batch_requests_*.jsonl`) in `dw_batch_output/logs/`
- Batch IDs (`batch_id_*.txt`) for status tracking
- Final outputs in `dw_batch_output/` (your results)

**Cleanup recommendation:** After batch completes, keep final outputs but optionally delete `dw_batch_output/logs/` if not needed for debugging.

### Using Other Providers (3-Line Change)

To use a different API provider (OpenAI, Azure, etc.), change 3 settings in `config.toml`:

```toml
[api]
base_url = "https://api.your-provider.com/v1"

[model]
chat = "your-provider-model-name"
```

And update `.env`:
```bash
DOUBLEWORD_AUTH_TOKEN=your-provider-key
```

The scripts use OpenAI SDK under the hood, so any OpenAI-compatible API works.

---

## SLA / Completion Window Recommendation

### **Default: 1h (Recommended)**
- **Turnaround:** 1-2 minutes for small-medium batches
- **Use for:** Most tasks where you're waiting for results
- **Why:** Fast enough for interactive workflows

### **Alternative: 24h (Cost Savings)**
- **Turnaround:** Could be hours
- **Use for:** Very large batches (100s of files, gigabytes of data)
- **Why:** 50-85% cheaper, but only worth it if time isn't critical

**Our recommendation:** Use 1h unless you're processing massive datasets overnight.

---

## Cost Optimization Checkpoint

**BEFORE creating batch requests, optimize these 3 dimensions:**

### 1. File Scope - Only Process What's Needed

**Check:** How many files does the user actually need processed?

**Use selective arguments:**
- `--files file1.pdf file2.csv` - Process specific files only
- `--extensions pdf docx` - Filter by type
- `--input-dir` with narrow scope - Don't process entire data/ if only subset needed

**Example wasteful patterns to AVOID:**
```bash
# ❌ User asked for 1 file, but processing all 100 images in folder
uv run python create_batch.py --input-dir /path/to/all_images --output-dir $PWD/dw_batch_output

# ✅ Process only what's requested
uv run python create_batch.py --files "/path/to/invoice_2024.pdf" --output-dir $PWD/dw_batch_output
```

### 2. Model Selection - Use Cheapest Model That Works

| Task Complexity | Use Model | Cost Multiplier |
|----------------|-----------|-----------------|
| **Simple** - OCR, basic extraction, simple captions | Qwen3-VL-30B | 1x (baseline) |
| **Complex** - Detailed analysis, reasoning, nuanced understanding | Qwen3-VL-235B | ~8x more expensive |

**Decision framework:**
```toml
# ❌ Using 235B for simple OCR text extraction
[model]
chat = "Qwen/Qwen3-VL-235B-A22B-Instruct-FP8"

# ✅ Using 30B for simple tasks
[model]
chat = "Qwen/Qwen3-VL-30B-A3B-Instruct-FP8"

# ✅ Only use 235B when you need complex reasoning
# Example: "Analyze sentiment and provide strategic recommendations"
```

**Rule of thumb:** Start with 30B. Only upgrade to 235B if output quality is insufficient.

### 3. MAX_TOKENS - Size to Expected Output

**Check:** How much output does the task actually need?

| User Request | Expected Output | Right MAX_TOKENS | Wrong MAX_TOKENS |
|--------------|----------------|------------------|------------------|
| "50 words" | ~50 words | 100 | 5000 (50x waste) |
| "Extract text from handwritten notes" | ~200 words | 300 | 5000 (17x waste) |
| "Detailed analysis report" | ~1500 words | 2000 | 5000 (2.5x waste) |
| "Comprehensive summary" | ~3000 words | 4000 | 5000 (1.25x waste) |

**Conversion:** 1 word ≈ 1.3 tokens (English average)

**Example:**
```toml
# ❌ User asked for "extract text" but using massive token limit
[output]
max_tokens = 5000

# ✅ Size appropriately
[output]
max_tokens = 300  # For OCR extraction (~200 words)
```

### Combined Cost Impact

**Example waste from all 3 dimensions:**
- Processing 3 images instead of 1: **3x waste**
- Using 235B instead of 30B: **8x waste**
- Using 5000 tokens instead of 300: **17x waste**

**Total:** 3 × 8 × 17 = **408x more expensive than necessary**

**With 1000s of files, these mistakes compound catastrophically.**

---

## Step-by-Step Workflow

### Setup (One-time)

```bash
cd .claude/skills
cp .env.sample .env
# Edit .env - add DOUBLEWORD_AUTH_TOKEN

# Install dependencies using uv
uv sync
```

### Execution (Per Batch)

#### **Simple Workflow:**
```bash
# 1. Edit prompt.txt with your task
vim prompt.txt

# 2. Create batch requests (with --output-dir)
uv run python create_batch.py --input-dir /path/to/files --output-dir $PWD/dw_batch_output

# Optional: Filter file types
uv run python create_batch.py --input-dir /path/to/files --extensions csv xlsx --output-dir $PWD/dw_batch_output

# 3. Submit batch
uv run python submit_batch.py --output-dir $PWD/dw_batch_output

# 4. Monitor and retrieve results (runs until complete)
uv run python poll_and_process.py --output-dir $PWD/dw_batch_output

# Results saved to: dw_batch_output/
```

#### **Complex Workflow (Custom Code):**
```python
# Generate custom batch creation script based on patterns in create_batch.py
# Example: Different prompts per file type

import json
from pathlib import Path
from datetime import datetime

# Use extraction functions from create_batch.py as needed
# Build custom request logic here
requests = []

for pdf_file in pdf_files:
    requests.append({
        "custom_id": f"summary-{pdf_file.stem}",
        "method": "POST",
        "url": "/v1/chat/completions",
        "body": {
            "model": "Qwen/Qwen3-VL-235B-A22B-Instruct-FP8",  # Complex model for PDFs
            "messages": [{"role": "user", "content": f"{summarize_prompt}\n\n{pdf_text}"}],
            "max_tokens": 5000
        }
    })

for csv_file in csv_files:
    requests.append({
        "custom_id": f"analysis-{csv_file.stem}",
        "method": "POST",
        "url": "/v1/chat/completions",
        "body": {
            "model": "Qwen/Qwen3-VL-30B-A3B-Instruct-FP8",  # Simple model for CSVs
            "messages": [{"role": "user", "content": f"{analyze_prompt}\n\n{csv_data}"}],
            "max_tokens": 2000
        }
    })

# Save to output-dir/logs/
output_file = Path('dw_batch_output/logs') / f'batch_requests_{datetime.now().strftime("%Y%m%d_%H%M%S")}.jsonl'
output_file.parent.mkdir(parents=True, exist_ok=True)
with open(output_file, 'w') as f:
    for req in requests:
        f.write(json.dumps(req) + '\n')

# Then run submit_batch.py and poll_and_process.py with --output-dir as normal
```

#### **Structured Data Extraction Example (Receipts/Invoices):**

For extracting structured data from scanned receipts, invoices, or forms, use a prompt that specifies the exact fields and output format:

**Example prompt.txt for receipt parsing:**
```
Extract the following fields from this receipt/invoice and return as JSON:

{
  "vendor_name": "string",
  "date": "YYYY-MM-DD",
  "total_amount": "number",
  "tax_amount": "number",
  "currency": "string (USD, EUR, etc.)",
  "items": [
    {"description": "string", "quantity": number, "price": number}
  ],
  "payment_method": "string (if visible)"
}

Important:
- Extract exact values as they appear
- Use null for missing fields
- Parse dates to YYYY-MM-DD format
- Return only valid JSON, no additional text
```

**Usage:**
```bash
# 1. Create prompt.txt with structured extraction instructions
# 2. Process receipt images
uv run python create_image_batch.py --files /path/to/receipts/*.jpg --output-dir $PWD/dw_batch_output

# 3. Set appropriate MAX_TOKENS (structured output ≈ 500 tokens)
# In config.toml: max_tokens = 800

# 4. Submit and process
uv run python submit_batch.py --output-dir $PWD/dw_batch_output
uv run python poll_and_process.py --output-dir $PWD/dw_batch_output
```

**Result:** Each receipt processed to clean JSON with extracted fields, ready for import into accounting systems.

#### **Multi-Modal Multi-Document Request:**

For tasks requiring **multiple documents AND images in a SINGLE request**, use the mixed-content message format. This is useful for cross-referencing, synthesis, or when context from multiple sources is needed for one analysis.

**Use case example:** "Create a report using these 3 documents and 2 images" or "Tell a story that incorporates all these inputs"

**Example batch request structure:**
```json
{
  "custom_id": "multi-modal-001",
  "method": "POST",
  "url": "/v1/chat/completions",
  "body": {
    "model": "Qwen/Qwen3-VL-30B-A3B-Instruct-FP8",
    "messages": [
      {
        "role": "system",
        "content": "You are a helpful assistant. Use all provided text and images as context."
      },
      {
        "role": "user",
        "content": [
          {"type": "text", "text": "Task: Synthesize insights from ALL the provided documents and images."},
          {"type": "text", "text": "Document 1:\n<TEXT CONTENT HERE>"},
          {"type": "text", "text": "Document 2:\n<TEXT CONTENT HERE>"},
          {"type": "text", "text": "Document 3:\n<TEXT CONTENT HERE>"},
          {"type": "image_url", "image_url": {"url": "data:image/jpeg;base64,<BASE64_IMAGE_1>"}},
          {"type": "image_url", "image_url": {"url": "data:image/jpeg;base64,<BASE64_IMAGE_2>"}},
          {"type": "text", "text": "Question: Based on everything above, what are the key insights and how do they relate?"}
        ]
      }
    ],
    "max_tokens": 1000
  }
}
```

**Key points:**
- Mix text and images in the `content` array
- Order matters: present context before the question
- Model processes ALL inputs together for holistic understanding
- Use base64-encoded images: `data:image/jpeg;base64,<encoded_data>`
- Tested with Qwen3-VL-30B (235B compatibility not yet verified)

**Tested successfully:** Story generation using 2 text documents + 2 images with Qwen3-VL-30B produced coherent narrative incorporating all inputs.

#### **Embeddings Generation:**

Generate embeddings for documents to enable semantic search, similarity matching, and vector database population.

**Use case:** "Create embeddings for all product descriptions", "Generate vectors for semantic search"

**Model:** Doubleword supports embeddings models (e.g., `BAAI/bge-en-icl`)

**Usage:**
```bash
# 1. Set embedding model in config.toml
[model]
embedding = "BAAI/bge-en-icl"

# 2. Create embeddings batch
uv run python create_embeddings_batch.py --input-dir /path/to/documents --output-dir $PWD/dw_batch_output

# Optional: Chunk long documents
uv run python create_embeddings_batch.py --chunk-size 2000 --output-dir $PWD/dw_batch_output

# 3. Submit and process
uv run python submit_batch.py --output-dir $PWD/dw_batch_output
uv run python poll_and_process.py --output-dir $PWD/dw_batch_output
```

**Key features:**
- Automatic chunking for long documents (respects token limits)
- Same extraction support as create_batch.py (PDF, Excel, CSV, etc.)
- Outputs embedding vectors for downstream use (similarity search, clustering, RAG)
- Custom ID includes chunk number if chunked: `embed-filename-chunk1`, `embed-filename-chunk2`

**Endpoint:** `/v1/embeddings` (not `/v1/chat/completions`)

#### **Scanned PDF Processing:**

Handle scanned PDFs (images of documents) by converting pages to images and processing with vision models.

**Use case:** "Process scanned contracts", "Extract text from scanned invoices with handwriting"

**Context limits:**
- Model context: 128K tokens
- Each page image: ~3-4K tokens
- Max ~30 pages per request
- Longer PDFs automatically chunked

**Usage:**
```bash
# 1. Process scanned PDFs (auto-detects minimal text)
uv run python create_scanned_pdf_batch.py --input-dir /path/to/scans --output-dir $PWD/dw_batch_output

# 2. Force all PDFs to be treated as scanned (skip detection)
uv run python create_scanned_pdf_batch.py --force-scan --files document.pdf --output-dir $PWD/dw_batch_output

# 3. Custom chunk size (pages per request)
uv run python create_scanned_pdf_batch.py --chunk-size 20 --output-dir $PWD/dw_batch_output

# 4. Submit and process
uv run python submit_batch.py --output-dir $PWD/dw_batch_output
uv run python poll_and_process.py --output-dir $PWD/dw_batch_output
```

**How it works:**
1. Detects if PDF is scanned (< 100 chars/page extractable text)
2. Converts each page to JPEG image (150 DPI)
3. Base64-encodes images
4. Sends to vision model (Qwen3-VL)
5. Auto-chunks if pages exceed context limit

**Dependencies:**
```bash
pip install pdf2image Pillow
# System: apt-get install poppler-utils (Ubuntu) or brew install poppler (macOS)
```

**Cost consideration:** Scanned PDF processing uses vision models and is more token-intensive (~3-4K tokens per page vs text PDFs).

---

## Streaming API (Non-Batch)

For **real-time interactive use cases** (not batch), Doubleword supports streaming chat completions.

**When to use streaming vs batch:**
- **Streaming:** Interactive chat, live UI updates, immediate token-by-token response
- **Batch:** Bulk processing, non-urgent tasks, cost savings (50-85% cheaper)

**Key parameter:** `stream=True`

**Example:** See [streaming_example.py](../streaming_example.py) for reference implementation

**Differences from batch:**
- Response arrives incrementally (chunks with `delta` field)
- Same cost per token, just different delivery mechanism
- No cost savings vs non-streaming (both are sync API calls)
- Batch API does NOT support streaming (batch returns complete results)

---

## File Organization

```
.claude/skills/
├── create_batch.py               # Tier 1: Text documents (PDF, Excel, CSV, etc.)
├── create_image_batch.py         # Image processing (captions, OCR)
├── create_embeddings_batch.py    # Embeddings generation
├── create_scanned_pdf_batch.py   # Scanned PDFs (converts to images)
├── streaming_example.py          # Streaming API reference (non-batch)
├── submit_batch.py               # Upload and submit (deterministic)
├── poll_and_process.py           # Monitor and download (deterministic)
├── process_results.py            # Result extraction (called by poll)
├── prompt.txt                    # User's task prompt template
├── .env                          # API token (gitignored)
├── dw_batch/
│   ├── config.toml               # Configuration (model, tokens, SLA)
│   ├── SKILL.md                  # Quick reference
│   └── GUIDE.md                  # This file
└── dw_batch_output/              # Final results (project root)
    ├── logs/                     # Batch artifacts (auto-created)
    │   ├── batch_requests_*.jsonl
    │   └── batch_id_*.txt
    ├── filename1_summary_timestamp.md
    └── filename2_analysis_timestamp.md
```

---

## Monitoring & Results

### Real-Time Progress
```
============================================================
BATCH MONITORING
============================================================
Batch ID: 7836efbd-0e01-4528-8cee-32340ea1ac3f
Polling interval: 60s
============================================================

[2026-02-04 14:32:15] Status: in_progress | Progress: 12/35
[2026-02-04 14:32:45] Status: in_progress | Progress: 24/35
[2026-02-04 14:33:15] Status: completed | Progress: 35/35

✓ Batch completed successfully!
✓ All results saved to dw_batch_output/
```

### Output Files
Results saved to `dw_batch_output/` with format:
```
{original_filename}_{task}_timestamp.md
```

Example: `sales_data_analysis_20260204_143315.md`

### Interruption & Resume
- Press `Ctrl+C` to stop polling
- Run `uv run python poll_and_process.py --output-dir $PWD/dw_batch_output` to resume
- Batch continues processing on server even when polling stops

---

## Artifact Cleanup (Post-Batch)

After batch completes, **ask the user** if they want to keep artifacts:

**Artifacts in `dw_batch_output/logs/` folder:**
- `batch_requests_*.jsonl` - Request file (useful for debugging/rerun)
- `batch_id_*.txt` - Tracking ID (useful for manual status checks)

**Final outputs in `dw_batch_output/`:**
- `*_summary_*.md` / `*_analysis_*.md` - **Keep these** (the actual results)

**Recommendation:** Keep final outputs, optionally delete `dw_batch_output/logs/` if not needed for debugging.

---

## Cost & Performance Estimates

Based on real-world usage (Feb 2026):

| Files | Model | SLA | Time | Cost | Notes |
|-------|-------|-----|------|------|-------|
| 2 files | 235B | 1h | ~1 min | ~0.4p | Fast turnaround |
| 50 CSVs | 30B | 1h | ~5 min | ~8p | Simple analysis |
| 100 docs | 235B | 24h | ~30 min | ~15p | Cost-optimized |

**Doubleword Pricing (Feb 2026):**

| Model | 1h SLA | 24h SLA | Best For |
|-------|--------|---------|----------|
| Qwen3-VL-30B | $0.07 / 1M tokens | $0.05 / 1M tokens | Simple tasks, fast |
| Qwen3-VL-235B | $0.125 / 1M tokens | $0.40 / 1M tokens | Complex reasoning |

**Cost factors:**
- Input token count (document length)
- Output token count (MAX_TOKENS setting)
- Model size (30B is ~2x cheaper than 235B for 1h SLA)
- SLA (1h vs 24h - savings vary by model)

**Example calculation:**
- 10 files × 2K tokens input + 1K tokens output = 30K tokens
- Qwen3-VL-30B (1h): 30K × $0.07/1M = **$0.0021** (~0.2p)
- Qwen3-VL-235B (1h): 30K × $0.125/1M = **$0.00375** (~0.4p)

---

## Error Handling & Troubleshooting

### Cost Threshold Protection

**Automatic safety checks** prevent accidentally expensive batches:

```bash
# Run dry-run to check costs
uv run python create_batch.py --input-dir /path/to/files --output-dir $PWD/dw_batch_output --dry-run

# If thresholds exceeded, you'll see:
⚠️  COST THRESHOLD EXCEEDED - REVIEW REQUIRED
Safety thresholds from config.toml:
  Max input tokens: 250,000
  Max output tokens: 100,000

Your batch exceeds these limits:
  ✗ Input tokens: 352,340 (exceeds 250,000)
  ✓ Output tokens: 75,000 (within limit)

⚠️  RECOMMENDED ACTIONS:
  1. Reduce file count (use --files to select subset)
  2. Lower MAX_TOKENS in config.toml
  3. Use smaller model (Qwen3-VL-30B instead of 235B)
  4. Split into multiple smaller batches

To proceed anyway, add --force flag (use with caution)
```

**Override safety check:**
```bash
# Only if you've reviewed costs and want to proceed
uv run python create_batch.py --input-dir /path/to/files --output-dir $PWD/dw_batch_output --force
```

**IMPORTANT FOR AGENTS:**
- **NEVER use --force without explicit user approval**
- When threshold is exceeded, present the cost estimate and ask the user whether to:
  1. Reduce file count or MAX_TOKENS
  2. Use smaller model
  3. Proceed with --force
- The user pays for API costs - they must make the final decision

**Adjust thresholds:** Edit `config.toml` `[safety]` section to match your budget.

### Error Logging

**Failed files are logged automatically:**

When files fail during batch creation (extraction errors, unsupported formats, insufficient text), errors are:
1. **Displayed in console** during processing
2. **Logged to file** in `{output-dir}/logs/batch_errors_TIMESTAMP.log`

Example error log:
```
Batch Creation Error Log
Generated: 2026-02-04 14:30:52
Total files failed: 3
============================================================

File: /path/to/corrupted.pdf
Reason: PdfReadError: Invalid PDF file
------------------------------------------------------------
File: /path/to/empty.docx
Reason: insufficient text
------------------------------------------------------------
File: /path/to/image.png
Reason: requires vision model (not enabled)
------------------------------------------------------------
```

**Error categories:**
- **Minor errors** (logged, batch continues): Individual file extraction failures, unsupported formats, empty files
- **Significant errors** (pause execution): Cost threshold exceeded, missing API key, invalid configuration

### Common Issues

**1. Missing API Key**
```
Error: Missing required environment variables: DOUBLEWORD_AUTH_TOKEN
```
**Solution:** Copy `.env.dw.sample` to `.env.dw` and add your API key (one-time setup)

**2. No Files Found**
```
Found 0 files in /path/to/directory
```
**Solution:** Check path, ensure files have supported extensions

**3. Insufficient Text Extracted**
```
⚠ Skipped (insufficient text: 45 chars)
```
**Solution:** File may be corrupted, empty, or scanned image (OCR needed)

**4. Import Error (Missing Library)**
```
ModuleNotFoundError: No module named 'pandas'
```
**Solution:** `uv sync` or `pip install pandas xlrd`

**5. Batch Stuck in Progress**
```
Status: in_progress | Progress: 12/35 (30 minutes)
```
**Solution:** Normal for large batches. Check Doubleword portal or wait. Can Ctrl+C and resume later.

**6. Missing --output-dir**
```
Error: --output-dir is required
```
**Solution:** Always pass `--output-dir $PWD/dw_batch_output` to scripts

---

## Integration Tips for Claude

### When to Proactively Suggest

```
User: "I need to analyze these 50 customer feedback documents"
Claude: "This is perfect for batch processing! I can use the
         dw_batch_request skill to process these async at 50-85% cost savings.
         Results in 1-2 minutes. Want me to set that up?"

User: "Caption these 200 product images for our website"
Claude: "Batch processing is ideal for this! The Qwen3-VL model has native
         vision capabilities for image captioning. I can process all 200
         images async with 50-85% cost savings. Results in 2-3 minutes."

User: "Extract text from these scanned invoices"
Claude: "This is a great use case for batch OCR! The vision model can
         process scanned documents directly. Want me to set up batch
         processing for cost-effective OCR?"

User: "Parse these 100 receipts and extract vendor, date, total, and items to JSON"
Claude: "Perfect for structured batch extraction! I'll set up a prompt
         requesting JSON output with those specific fields (vendor, date,
         total, items). The vision model can read receipts and output
         structured data. Results in 2-3 minutes."
```

### Dynamic Decision Making

**Simple case (use create_batch.py):**
```
User: "Analyze all CSVs in data/ for patterns"
→ One prompt, one model, uniform treatment
→ Edit prompt.txt, run create_batch.py with --output-dir
```

**Complex case (generate custom code):**
```
User: "Summarize PDFs with detailed analysis, but just extract key metrics from CSVs"
→ Different prompts per file type
→ Generate custom batch request code
```

### ⚠️ Warning in Complex Cases

If the task requires per-file customization, **DO NOT** run `create_batch.py` verbatim. Instead:
1. Use extraction functions from `create_batch.py` as a reference library
2. Generate custom code with conditional logic
3. Create batch_requests_*.jsonl with per-request customization

---

## Best Practices

1. **SLA Selection:** Use 1h for most tasks (fast). Only use 24h for massive batch jobs where cost > time.
2. **Model Selection:** Start with 30B (cheaper, faster). Upgrade to 235B if quality insufficient.
3. **Prompt Design:** Clear, specific, include output format requirements.
4. **Token Limits:** Set MAX_TOKENS to ~1.5x expected output length.
5. **File Organization:** Use descriptive filenames for easy result identification.
6. **Validation:** Test with 2-3 files first before batching 100s.
7. **Cleanup:** Archive or delete `dw_batch_output/logs/` periodically. Always keep final outputs.
8. **Always use --output-dir:** Pass explicit `--output-dir $PWD/dw_batch_output` to all scripts.
9. **Use uv run:** Prefix all Python commands with `uv run` for consistent environments.

---

## Related Resources

- **[SKILL.md](SKILL.md)** - Quick reference and getting started guide
- **[examples/](../examples/)** - Use case examples with prompts and workflows
- [Doubleword AI Portal](https://doubleword.ai) - API access and billing
- [Doubleword Batch API Docs](https://docs.doubleword.ai/batches/getting-started-with-batched-api) - Official API documentation
