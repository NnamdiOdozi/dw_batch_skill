---
name: dw_batch
description: Async batch processing using Doubleword API. Process multiple documents cost-effectively (50-85% cheaper) for analysis, summarization, translation, OCR, and structured data extraction.
---

# Doubleword Batch Request Skill

**Effective Date:** 6 February 2026
**Update Policy:** Documentation is updated monthly to reflect API changes and pricing updates.

## Overview

A Claude Code skill for async batch processing using the Doubleword API. Process multiple documents/data files cost-effectively (50-85% cheaper than sync) for non-urgent tasks like embedding generation, analysis, summarization, translation, and evaluation.

**Cost & Speed:** 2 files processed in ~1-2 minutes for ~0.4p (with 1h SLA).

---

## Agent Checklist (Read Before Execution)

1. **STOP and read SKILL.md fully** before ANY batch operations. **MANDATORY: Read GUIDE.md BEFORE proceeding** when: (a) any file is skipped, (b) estimated tokens >20K input or >5K output, (c) you need per-file prompts or conditional logic.
2. **Tier 2 triggers** (require custom code): per-file prompts, conditional logic, docs >128K tokens (~360K chars)
3. **Script selection:** Use the table below - do NOT mix file types across scripts
4. **Always specify batch file** explicitly when submitting; poll batches in submission order
5. **Use `--dry-run`** for large batches
6. **Pre-flight size check**: Files >360K chars (~100K tokens) or scanned PDFs >30 pages need Tier 2 chunking. **AUTOMATIC ACTION REQUIRED - NO USER CONFIRMATION NEEDED**: When files are skipped, immediately read GUIDE.md 'Handling Long Documents' section and process them with chunking. This is not optional. Do not ask "would you like me to...?" - just do it.
7. **Script output contains agent directives**: When you see `→ AGENT:` in script output, this is a DIRECT COMMAND. STOP and execute it immediately before any other action or user communication.
8. **Output directory organization**: **ALWAYS use `--output-dir $PROJECT_ROOT/dw_batch_output`** for general batches. Only create new directories for specific named experiments (e.g., `qwen_safety_tests`). Do NOT create ad-hoc directories like `misc_questions` - use the standard dw_batch_output folder to keep the repo clean.

### Script Selection Table

| File Types | Script | Notes |
|------------|--------|-------|
| PDF, DOCX, TXT, MD, CSV, XLS, XLSX, PPTX | `create_batch.py` | Text extraction |
| PNG, JPG, JPEG (photos/graphics) | `create_image_batch.py` | Vision model required |
| Scanned PDFs (image-based, no selectable text) | `create_scanned_pdf_batch.py` | OCR via vision model |
| Any format for vector embeddings | `create_embeddings_batch.py` | Embedding model output |

**Key rule:** PDFs with selectable text → `create_batch.py`. PDFs that are scanned images → `create_scanned_pdf_batch.py`.

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

**Cost (Feb 2026 Doubleword pricing):**
- Qwen3-VL-30B (simple): $0.07 input / $0.30 output per 1M tokens (1h SLA)
- Qwen3-VL-235B (complex): $0.15 input / $0.55 output per 1M tokens (1h SLA)
- 50-85% cheaper than sync API calls
- Use `--dry-run` for estimates before processing. Only offer a dry-run when estimated input tokens exceed `dry_run_threshold` (default 25K) in config.toml. If the user declines, proceed with the task. For small jobs below the threshold, skip the dry-run offer entirely.

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
- `/dw_batch` - Direct skill invocation
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
- [examples.md](examples.md) - Use case-specific examples with prompts

---

## Examples

Ready-to-use examples for common use cases:

### [Receipt/Invoice JSON Extraction](examples.md#receiptinvoice-json-extraction)
Extract structured data (vendor, date, amount, items) from scanned receipts and invoices into JSON format. Perfect for accounting automation.

**Use case:** "Parse these 50 receipts into structured data"

### [Multimodal Document Analysis](examples.md#multimodal-document-analysis)
Process documents with mixed content (text + images) in a single request for cross-referencing and synthesis.

**Use case:** "Create a report using these 3 documents and 2 charts"

### [Scanned PDF OCR](examples.md#scanned-pdf-ocr)
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

**Agent requirement:** The `dw_batch` folder is the **canonical version** — always use its scripts for batch operations. Never write inline Python to replicate what the scripts already do. For Tier 2 edge cases, write **one-off inline scripts** but do not persist them to the dw_batch folder unless the user explicitly requests it.

**Agent requirement:** When polling multiple batches, poll in submission order (first submitted = first polled). Use `--batch-id <id>` to specify which batch. Without it, `poll_and_process.py` defaults to the most recent batch_id file.

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

## Security Note

**Prompt injection:** Documents can contain text designed to hijack LLM output. Many LLMs are susceptible. Review outputs when processing untrusted documents. See [GUIDE.md - Prompt Injection Warning](GUIDE.md#prompt-injection-warning) for details.

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
- **[examples/](examples.md)** - Use case examples with prompts and workflows
- [Doubleword AI Portal](https://doubleword.ai) - API access and billing
- [Doubleword Batch API Docs](https://docs.doubleword.ai/batches/getting-started-with-batched-api) - Official API documentation

---

## Skill Metadata

- **Skill Name:** `dw_batch`
- **Invocation:** `/dw_batch`, "batch this", "analyze files", "batch process", "not urgent"
- **Category:** Document Processing, Data Analysis, Batch Operations
- **Dependencies:** Python 3.12+, Doubleword API access, uv package manager
- **Output:** Markdown files in `dw_batch_output/`
- **Latency:** typically < 5 minutes (1h SLA) or 10-30 minutes (24h SLA)
