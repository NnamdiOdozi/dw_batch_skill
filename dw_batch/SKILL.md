---
name: dw_batch_request
description: Async batch processing using Doubleword API. Process multiple documents cost-effectively (50-85% cheaper) for analysis, summarization, translation, OCR, and structured data extraction.
---

# Doubleword Batch Request Skill

## Overview

A Claude Code skill for async batch processing using the Doubleword API. Process multiple documents/data files cost-effectively (50-85% cheaper than sync) for non-urgent tasks like analysis, summarization, translation, and evaluation.

**Cost & Speed:** 2 files processed in ~1-2 minutes for ~0.4p (with 1h SLA).

---

## Quick Start (5 Minutes)

### Prerequisites
- Python 3.12+
- `uv` package manager ([install](https://astral.sh/uv/install.sh))
- Doubleword API key from https://app.doubleword.ai

### Setup (One-Time)

```bash
# Navigate to skill directory (works at user or project level)
cd .claude/skills

# Install dependencies using uv (ensures consistent environment in Claude Code shells)
uv sync

# Configure API credentials (ONE-TIME SETUP)
cp .env.dw.sample .env.dw
# Edit .env.dw and add: DOUBLEWORD_AUTH_TOKEN=sk-your-key-here
# SECURITY: .env.dw is gitignored - never commit it
# NOTE: .env.dw should ONLY contain the API token, nothing else

# Configure settings (edit anytime)
# Edit config.toml for: model, max_tokens, summary_word_count, polling_interval, safety thresholds
```

### Run Your First Batch

```bash
# 1. Create your task prompt
echo "Summarize this document in 3 bullet points." > prompt.txt

# 2. Process your files (use --dry-run first to estimate costs)
uv run python create_batch.py --input-dir /path/to/docs --output-dir $PWD/dw_batch_output --dry-run
uv run python create_batch.py --input-dir /path/to/docs --output-dir $PWD/dw_batch_output

# 3. Submit to API
uv run python submit_batch.py --output-dir $PWD/dw_batch_output

# 4. Monitor and download results (~1-2 minutes)
uv run python poll_and_process.py --output-dir $PWD/dw_batch_output
```

**Results:** Check `dw_batch_output/` in your project root

**Why Use `uv run`?** Claude Code spawns multiple shell sessions. `uv run` ensures consistent Python environment across all shells (same dependencies, no version conflicts). See [GUIDE.md](GUIDE.md#why-uv-run) for details.

**Cost Protection:** Built-in safety thresholds (250K input tokens or 100K output tokens) prevent accidentally expensive batches. Override with `--force` if needed (user approval required).

---

## Contract

### Inputs

**Files (via `--input-dir` or `--files`):**
- **Supported formats:** PDF, DOCX, PPTX, ODP, TXT, MD, CSV, TSV, XLS, XLSX, PNG, JPG, JPEG
- **Images:** Requires vision-capable model (Qwen3-VL)
- **Scanned PDFs:** OCR via vision models
- **Path:** Absolute or relative paths accepted

**Required Configuration:**
- `.env` file with `DOUBLEWORD_AUTH_TOKEN` (secret)
- `dw_batch/config.toml` with model settings (non-secret)
- `prompt.txt` with task instructions
- `--output-dir` (REQUIRED - agent must pass absolute path to project root)

### Outputs

**Success:**
- **Files:** `{output-dir}/{filename}_summary_{timestamp}.md`
- **Logs:** `{logs-dir}/batch_requests_*.jsonl`, `batch_id_*.txt`
- **Exit code:** 0
- **Location:** Agent-specified output directory (typically `{project_root}/dw_batch_output`)

**Naming pattern:**
- Original: `2024_Q4_Report.pdf`
- Output: `2024_Q4_Report_summary_20260204_143052.md`

### Failure Behavior

**Individual file failures:**
- Logged to console during `create_batch.py`
- Reasons: Unsupported format, insufficient text (<100 chars), extraction errors
- **Batch continues** - other files still processed

**API errors:**
- Authentication failure → immediate exit with error message
- Batch job fails → reported in `poll_and_process.py`
- Network errors → script exits, can be resumed

**Resumability:**
- `submit_batch.py` can resubmit any `batch_requests_*.jsonl` file
- `poll_and_process.py` monitors most recent batch ID
- Partial results are NOT saved (all-or-nothing per batch)

### Performance Expectations

**Timing (1h SLA):**
- Small batch (2-10 files): 1-2 minutes
- Medium batch (10-50 files): 2-5 minutes
- Large batch (50+ files): 5-15 minutes

**Cost (Feb 2026 Doubleword pricing):**
- Qwen3-VL-30B (simple): ~$0.07 per 1M tokens
- Qwen3-VL-235B (complex): ~$0.125 per 1M tokens
- 50-85% cheaper than sync API calls
- Use `--dry-run` for estimates before processing

**Quality:**
- Model-dependent (configure in `dw_batch/config.toml`)
- Vision models required for images/scanned PDFs
- Output quality checks available (see [GUIDE.md](GUIDE.md#monitoring-results))

---

## When to Use This Skill

### Proactive Triggers

Suggest this skill when the user's request involves:

1. **Bulk processing** - Multiple files need similar LLM treatment
2. **Non-urgent tasks** - Results can wait 1-2 minutes (not critical path)
3. **Cost-sensitive operations** - Budget favors batch pricing (50-85% savings)
4. **Repetitive tasks** - Same operation on many inputs
5. **Background analysis** - "Analyze these files", "process all CSVs", etc.
6. **Image captioning** - "Caption these product images", "Describe visual content in photos"
7. **OCR/Document digitization** - "Extract text from scanned PDFs", "Parse handwritten notes"
8. **Structured data extraction** - "Parse receipts, invoices, and other docs to structured format"

### User Invocation
- `/dw_batch_request` - Direct skill invocation
- "batch this" - Natural language trigger
- "analyze these files" - Implicit batch request

---

## Quick Reference Card

```bash
# SIMPLE WORKFLOW (same prompt/model for all files)
cd .claude/skills
vim prompt.txt                                                  # Edit task prompt
uv run python create_batch.py --input-dir /path/to/files --output-dir $PWD/dw_batch_output --dry-run  # Estimate costs FIRST
uv run python create_batch.py --input-dir /path/to/files --output-dir $PWD/dw_batch_output            # Create requests
uv run python submit_batch.py --output-dir $PWD/dw_batch_output                                       # Submit batch
uv run python poll_and_process.py --output-dir $PWD/dw_batch_output                                   # Monitor & download

# COMPLEX WORKFLOW (different prompts/models per file)
# → Generate custom batch creation code based on patterns in create_batch.py
# → Then run submit_batch.py and poll_and_process.py with --output-dir

# Results location
ls dw_batch_output/

# Log artifacts location
ls dw_batch_output/logs/

# Cost protection (automatic threshold checks)
# If batch exceeds limits: --force to override (use with caution)
uv run python create_batch.py --input-dir /path/to/files --output-dir $PWD/dw_batch_output --force

# Optional: Skip already-processed files
uv run python create_batch.py --skip-existing --output-dir $PWD/dw_batch_output
```

**For detailed guides, see:**
- [GUIDE.md](GUIDE.md) - Complete reference, troubleshooting, optimization
- [examples.md] - Use case-specific examples with prompts

---

## Examples

Ready-to-use examples for common use cases:

### [Receipt/Invoice JSON Extraction](examples.md:receipt_json/)
Extract structured data (vendor, date, amount, items) from scanned receipts and invoices into JSON format. Perfect for accounting automation.

**Use case:** "Parse these 50 receipts into structured data"

### [Multimodal Document Analysis](examples.md:multimodal/)
Process documents with mixed content (text + images) in a single request for cross-referencing and synthesis.

**Use case:** "Create a report using these 3 documents and 2 charts"

### [Scanned PDF OCR](examples.mdscanned_pdfs/)
Extract text from scanned PDFs and images using vision models. Handles handwritten notes and low-quality scans.
:
**Use case:** "Digitize these scanned contracts"
:


---

## Key Concepts

### Tier 1 vs Tier 2 Processing

**Tier 1 (80% of cases):** Use `create_batch.py` when you need the same prompt and model for all files.

**Tier 2 (20% of cases):** Generate custom code when you need different prompts/models per file type or conditional logic.

**Decision rule:** If you can describe the task in one sentence without "if/else", use Tier 1.

See [GUIDE.md - Two-Tier System](GUIDE.md#two-tier-processing-system) for decision table and examples.

### Configuration

**CRITICAL - Two Separate Files:**

1. **`.env.dw`** (gitignored, never commit):
   - **ONLY contains:** `DOUBLEWORD_AUTH_TOKEN=sk-...`
   - **Never edit for:** model, max_tokens, word_count, or ANY other settings

2. **`config.toml`** (committed to repo):
   - **Contains:** model, max_tokens, summary_word_count, polling_interval, safety thresholds
   - **Edit this file** when user wants to change settings

**Agent Rule:** When user requests changes to model, tokens, word count, polling → **edit `config.toml`**, NOT `.env.dw`

**Agent requirement:** Must pass `--output-dir` explicitly (no defaults)

See [GUIDE.md - Configuration](GUIDE.md#configuration) for detailed setup.

### File Formats

Supports: PDF, DOCX, PPTX, CSV, XLSX, TXT, MD, PNG, JPG, JPEG, and more. Vision models for images and scanned PDFs.

See [GUIDE.md - Supported Formats](GUIDE.md#supported-file-formats) for full compatibility table.

---

## Cost Optimization

**Before processing, optimize 3 dimensions:**
1. **File scope** - Only process what's needed (use `--files` or `--extensions`)
2. **Model selection** - Use Qwen3-VL-30B for simple tasks (8x cheaper than 235B)
3. **MAX_TOKENS** - Size to expected output (~1.3 tokens per word)

**Example:** Processing 3 files with wrong model and token settings = **100x more expensive** than optimal.

See [GUIDE.md - Cost Optimization](GUIDE.md#cost-optimization-checkpoint) for detailed analysis.

---

## Troubleshooting

**Common issues:**
- Missing API key → Copy `.env.dw.sample` to `.env.dw` and add token
- Want to change model/tokens → Edit `config.toml` (NOT .env.dw)
- No files found → Check path and extensions
- Module not found → Run `uv sync`
- Quality issues → Check `process_results.py` output summary

See [GUIDE.md - Troubleshooting](GUIDE.md#error-handling-troubleshooting) for complete guide.

---

## Related Resources

- **[GUIDE.md](GUIDE.md)** - Complete reference guide (configuration, optimization, troubleshooting)
- **[examples/](examples/)** - Use case examples with prompts and workflows
- [Doubleword AI Portal](https://doubleword.ai) - API access and billing
- [Doubleword Batch API Docs](https://docs.doubleword.ai/batches/getting-started-with-batched-api) - Official API documentation

---

## Skill Metadata

- **Skill Name:** `dw_batch_request`
- **Invocation:** `/dw_batch_request`, "batch this", "analyze files"
- **Category:** Document Processing, Data Analysis, Batch Operations
- **Dependencies:** Python 3.12+, Doubleword API access, uv package manager
- **Output:** Markdown files in `dw_batch_output/`
- **Latency:** 1-2 minutes (1h SLA) or 10-30 minutes (24h SLA)
