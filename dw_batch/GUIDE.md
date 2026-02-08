# Doubleword Batch Processing - Complete Guide

**Effective Date:** 6 February 2026
**Update Policy:** Documentation is updated monthly to reflect API changes and pricing updates.

Detailed reference for the dw_batch skill. For quick start, see [SKILL.md](SKILL.md).

---

## Table of Contents

- [Why uv run?](#why-uv-run)
- [Two-Tier Processing System](#two-tier-processing-system)
- [Supported File Formats](#supported-file-formats)
- [Handling Long Documents (Chunking)](#handling-long-documents-chunking)
- [Configuration](#configuration)
- [Model Selection Guide](#model-selection-guide)
- [Security & Best Practices](#security--best-practices)
- [SLA / Completion Window](#sla--completion-window)
- [Cost Optimization Checkpoint](#cost-optimization-checkpoint)
- [Step-by-Step Workflow](#step-by-step-workflow)
- [Monitoring, Results & Cleanup](#monitoring-results--cleanup)
- [Cost & Performance Estimates](#cost--performance-estimates)
- [Error Handling & Troubleshooting](#error-handling--troubleshooting)
- [Best Practices](#best-practices)

---

## Why uv run?

Claude Code spawns multiple shell sessions. `uv run` reads `pyproject.toml` / `uv.lock` to give every shell the same resolved dependencies. Just prefix all Python commands with `uv run`.

---

## Two-Tier Processing System

⚠️ **CRITICAL:** Choose the right approach for the task complexity.

**Tier 1 — Simple Uniform Processing (80% of cases):** Use `create_batch.py` when the same prompt and model apply to all files.

**Tier 2 — Complex Custom Processing (20% of cases):** Generate custom code when you need different prompts/models per file type or conditional logic. Use extraction functions from `create_batch.py` as a pattern library, generate a custom script, output `batch_requests_*.jsonl`, then run `submit_batch.py` → `poll_and_process.py` as normal.

**Decision rule:** If you can describe the task in one sentence without "if/else", use Tier 1.

---

## Supported File Formats

**Text documents:** PDF (.pdf), Word (.docx), PowerPoint (.pptx), OpenOffice (.odp), Text (.txt, .md)

**Data files:** Excel (.xls, .xlsx), CSV (.csv), TSV (.tsv) — auto-detects delimiters

**Images:** PNG, JPG, JPEG — requires vision model (Qwen3-VL)

**Scanned PDFs:** Auto-detected (< 100 chars/page extractable text), converted to images for OCR via vision model

**Embeddings:** All above formats via text extraction + embeddings model

Smart imports: only loads required libraries based on detected file types. See scripts for full handler details.

### Performance Optimization for Large PDFs

**Scanned PDF Detection:** Files >50MB are checked for text content during extraction. If a large file extracts <500 chars, it's flagged as likely scanned and the script:
- Skips slow pdfplumber fallback (would take 30-60+ seconds with no benefit)
- Recommends using `create_scanned_pdf_batch.py` with vision model OCR instead

**Why this matters:** A 120MB scanned PDF can take 2-3 minutes with both pypdf and pdfplumber attempts, only to extract almost nothing. This optimization saves significant time during dry-runs.

### Accurate Page Count Estimation (For Scanned PDFs)

**CRITICAL:** Use `pdfinfo` (from poppler-utils) to get exact page counts, then calculate cost as `pages × 3,500 tokens/page`. Do NOT rely on file size estimates.

### Mounted Drive Optimization (WSL2, Network Drives, etc.)

**When files are on mounted/remote filesystems** (e.g., `/mnt/c/` in WSL2, network shares, external drives), **copy to local `/tmp` **. Cross-filesystem I/O adds significant overhead, especially for PDF parsing which requires random access.

**Performance impact:**
- **Small batches (<25MB or < 1 scanned PDF document):** Not worth copying (~5-10 seconds saved)
- **Large batches (>25MB or at least 1 scanned PDF document):** Copy saves **25-40% processing time** (2-5 minutes on typical insurance document batches)

**When to copy:**
- Total file size **>25MB** OR
- **at least 1 scanned PDF document** OR
- Files on **mounted Windows drives** (`/mnt/c/`, `/mnt/d/`) OR
- Files on **network shares** or **cloud-synced folders** OR
- Processing **scanned PDFs** (image-heavy, lots of random seeks)

**Pattern:**
```bash
# Copy files to local temp directory
TEMP_DIR=$(mktemp -d)
cp -r "/mnt/c/path/to/source_directory" "$TEMP_DIR/"

# Process from local filesystem
uv run python create_batch.py --input-dir "$TEMP_DIR/source_directory" \
  --output-dir "$PROJECT_ROOT/dw_batch_output"

# Cleanup after processing
rm -rf "$TEMP_DIR"
```

**Why it helps:** PDFs are parsed with random access patterns (jumping through file structure), which is 5-10x slower on mounted filesystems. Large scanned PDFs (100MB+) see the biggest improvement. The 9P protocol (WSL2) and network protocols add latency to every seek operation.

---

## Handling Long Documents (Chunking)

The Qwen3-VL models have a **128K token context window** (~90K words). When a single text document exceeds this after extraction (e.g., a 300-page report), use a **map-reduce** approach:

### CRITICAL - Two-Step Map-Reduce Process

**⚠️ AGENTS: You MUST complete BOTH steps. Completing only the map step is incomplete processing.**

1. **MAP STEP:** Chunk the text into ~80K-token segments at natural boundaries (paragraphs, headings) with slight overlap → batch-process each chunk with the same prompt → get per-chunk summaries

2. **REDUCE STEP (MANDATORY):** Collect all per-chunk summaries → submit to a SECOND batch with a synthesis prompt → produce final coherent output

**Example synthesis prompt:**
```
"You have been provided with N separate summaries covering different sections of [document name].
Synthesize these summaries into ONE comprehensive, coherent [length]-token summary that covers
the entire document without duplication or redundancy."
```

This is a **Tier 2 task** — the agent generates custom code for chunking and synthesis. Scanned PDFs already have built-in page-based chunking in `create_scanned_pdf_batch.py`; this workflow applies to both scanned PDFs and text-heavy documents.

---

## Configuration

**CRITICAL - What Goes Where:**

| Setting | File | Purpose |
|---------|------|---------|
| `DOUBLEWORD_AUTH_TOKEN` | `.env.dw` | Secret API key (gitignored, never commit) |
| model, max_tokens, word_count, polling, thresholds | `config.toml` | All other settings (committed to repo) |

**Agent Rule:** When user says "change the model" or "use 1000 tokens" → **edit `config.toml`**, NOT `.env.dw`. Only edit `.env.dw` for first-time setup or API key changes.

### config.toml Reference

```toml
[api]
base_url = "https://api.doubleword.ai/v1"
chat_completions_endpoint = "/v1/chat/completions"

[models]
default_model = "Qwen/Qwen3-VL-30B-A3B-Instruct-FP8"   # Simple tasks (DEFAULT)
# default_model = "Qwen/Qwen3-VL-235B-A22B-Instruct-FP8"  # Complex tasks
embedding_model = "Qwen/Qwen3-Embedding-8B"

[batch]
completion_window = "1h"   # "1h" (recommended) or "24h"
polling_interval = 30

[output]
max_tokens = 750
summary_word_count = 500

[safety]
max_input_tokens = 250000
max_output_tokens = 100000
dry_run_threshold = 25000   # Only suggest dry-run when estimated input tokens exceed this
# Use --force flag to override (requires user approval)
# Rule of thumb: 1 token ≈ 0.75 words, or ~4 characters
```

### Prompt Template (prompt.txt)

Use `{WORD_COUNT}` as an optional placeholder substituted from config.toml.

---

## Model Selection Guide

| Task Complexity | Model | Cost | Use When |
|----------------|-------|------|----------|
| **Simple (DEFAULT)** | Qwen3-VL-30B | Cheaper | Summaries, basic extraction, sentiment, Q&A |
| **Complex** | Qwen3-VL-235B | ~8x more | Deep reasoning, technical analysis, structured extraction |

**Rule:** Start with 30B. Only upgrade to 235B if output quality is insufficient.

---

## Security & Best Practices

- `.env.dw` contains your API token — **never commit to git** (already in `.gitignore`)
- Scripts never log full API tokens (only last 4 chars shown)
- Batch request files in `dw_batch_output/logs/` may contain document text — clean up after use
- If you accidentally commit `.env.dw`: rotate your key immediately at https://app.doubleword.ai

**Other providers:** The scripts use OpenAI SDK, so any OpenAI-compatible API works. Change `base_url` and model in `config.toml`, update token in `.env.dw`.

### Prompt Injection Warning

**Documents can contain prompt injection attacks.** Malicious or compromised documents may include text like "IGNORE ALL PREVIOUS INSTRUCTIONS..." designed to hijack the LLM's output. Many LLMs are susceptible to these attacks — structural defences (system messages, `<document>` tags, guardrail text) do not reliably prevent injection.

**Recommendations:**
1. **Review outputs** when processing documents from untrusted sources
2. **Don't use batch results directly** in automated pipelines without human review for sensitive use cases
3. The scripts use `<document>` tags to separate prompt from content — this provides structural clarity but is not a security boundary

---

## SLA / Completion Window

Use **1h** (recommended) for most tasks — results in 1-5 minutes. Use **24h** only for very large batches where cost matters more than speed.

---

## Cost Optimization Checkpoint

**Before creating batch requests, optimize 3 dimensions:**

1. **File scope** — Only process what's needed. Use `--files` for specific files or `--extensions` to filter by type.
2. **Model selection** — Use 30B for simple tasks (8x cheaper than 235B).
3. **MAX_TOKENS** — Size to expected output length (~1.3 tokens per word). Don't set 5000 tokens for a 50-word summary.

**Rule of thumb:** Getting all 3 wrong can compound to **100-400x** overspend. Test with 2-3 files first.

---

## Interpreting Dry-Run Results (For Agents)

When presenting dry-run results to users, provide a comprehensive breakdown WITHOUT being prompted:

### Required Information
1. **Total token counts:**
   - Input tokens for all files (processable + skipped)
   - Output tokens (use user assumptions if provided, otherwise use MAX_TOKENS from config)
   - Total cost at current model pricing

2. **Category breakdown:**
   - Small files (ready to process): count, tokens, cost
   - Large files (need Tier 2 chunking): count, tokens, cost
   - Scanned PDFs (need OCR): count, estimated tokens (**use 3,500 tokens/page** per examples.md), cost
   - Failed files (missing libraries, etc.): count and fix required

3. **Top N largest files:**
   - Show top 10 files by token count with individual costs
   - Helps users decide on selective processing

4. **Tier 2 handling plan** (if applicable):
   - Brief description of chunking approach
   - Expected workflow: chunk → process → combine
   - Note: No user approval needed for technical implementation unless strategy is ambiguous

### Example Output Format
```
Dry-run complete for 48 files:

✅ PROCESSABLE NOW (19 files): $0.06
   - 709K input + 28.5K output tokens

📦 NEED TIER 2 CHUNKING (23 files): $0.27
   - 3.7M input + 34.5K output tokens
   - Plan: Read GUIDE.md, implement overlapping chunk strategy
   - Will proceed automatically if scope confirmed, otherwise will ask

🖼️ SCANNED PDFs (5 files): $0.13
   - ~515 pages × 3,500 tokens/page = 1.8M input + 6K output
   - (Token estimate per examples.md)
   - Process via create_scanned_pdf_batch.py

💰 TOTAL (47 files): $0.46
   - 6.2M input + 66.5K output = 6.3M total tokens

📊 Top 10 Largest Files:
   1. Continental Reinsurance: 366K tokens ($0.026)
   2. Cornerstone Insurance: 224K tokens ($0.016)
   ...

⚠️ EXCLUDED:
   - 1 Excel file (needs: uv pip install openpyxl)
```

### Tier 2 Handling Workflow
When files need chunking:
1. **Read** GUIDE.md 'Handling Long Documents' section
2. **Choose** chunking strategy based on file type:
   - PDFs: Page-based chunks (e.g., 20-30 pages per chunk with 5-page overlap)
   - Financial statements: Section-based (Income Statement, Balance Sheet, Notes)
   - Reports: Chapter/section-based
3. **Implement** custom chunking code (see GUIDE.md examples)
4. **Process** chunks via batch API
5. **Combine** results into coherent output

### Why This Matters
- Users want to understand the full scope before committing
- Prevents "what about the skipped files?" follow-up questions
- Shows clear path forward for all files (no dead ends)
- Demonstrates proactive problem-solving

---

## Step-by-Step Workflow

### Setup (One-time)

```bash
cd .claude/skills
cp .env.dw.sample .env.dw    # Add your DOUBLEWORD_AUTH_TOKEN
uv sync                       # Install dependencies
```

### Simple Workflow

```bash
# 1. Edit prompt.txt with your task

# 2. Create batch requests
uv run python create_batch.py --input-dir /path/to/files --output-dir $PWD/dw_batch_output

# Optional: filter by type
uv run python create_batch.py --input-dir /path/to/files --extensions csv xlsx --output-dir $PWD/dw_batch_output

# 3. Submit batch
uv run python submit_batch.py --output-dir $PWD/dw_batch_output

# 4. Monitor and retrieve results
uv run python poll_and_process.py --output-dir $PWD/dw_batch_output
```

### Specialized Scripts

- **Scanned PDFs:** `create_scanned_pdf_batch.py` with optional `--chunk-size` and `--force-scan`
- **Images:** `create_image_batch.py` for captioning, OCR, visual analysis
- **Embeddings:** `create_embeddings_batch.py` with optional `--chunk-size` for long documents
- **Structured extraction (receipts/invoices):** Use `create_image_batch.py` with a JSON-schema prompt in `prompt.txt`
- **Multi-modal (text + images in one request):** Tier 2 — generate custom code using mixed-content message format

All specialized scripts feed into the same `submit_batch.py` → `poll_and_process.py` pipeline.

---

## Monitoring, Results & Cleanup

- `poll_and_process.py` prints status updates every 30s; results saved to `dw_batch_output/`
- Press `Ctrl+C` to stop polling; resume with the same command (batch continues on server)
- Results named: `{original_filename}_{task}_{timestamp}.md`
- Outputs go to `dw_batch_output/` and logs to `dw_batch_output/logs/`
- After completion, optionally delete `dw_batch_output/logs/` (batch artifacts). Keep final outputs.

---

## Cost & Performance Estimates

Based on real-world usage (Feb 2026). Costs depend heavily on output length — use `--dry-run` for accurate per-job estimates.

| Files | Model | SLA | Time | Notes |
|-------|-------|-----|------|-------|
| 2 files | 235B | 1h | ~1 min | Fast turnaround |
| 50 CSVs | 30B | 1h | ~5 min | Simple analysis |
| 100 docs | 235B | 24h | ~30 min | Cost-optimized |

**Doubleword Pricing (Feb 2026, per 1M tokens):**

| Model | 1h Input | 1h Output | 24h Input | 24h Output |
|-------|----------|-----------|-----------|------------|
| Qwen3-VL-30B | $0.07 | $0.30 | $0.05 | $0.20 |
| Qwen3-VL-235B | $0.15 | $0.55 | $0.10 | $0.40 |
| Qwen3-Embedding-8B | $0.03 | — | $0.02 | — |

Use `--dry-run` for cost estimates before processing.

---

## Error Handling & Troubleshooting

### Cost Threshold Protection

Automatic safety checks prevent accidentally expensive batches. When estimated input tokens exceed `dry_run_threshold` (25K tokens) in config.toml, the agent should offer a dry-run first. If the user declines, proceed with the task.

Override safety thresholds with `--force` (requires explicit user approval). **Agents must NEVER use --force without user consent.**

### Error Logging

Failed files are logged to `{output-dir}/logs/batch_errors_TIMESTAMP.log` with file path and error reason. Batch continues despite individual file failures.

**Error categories:**
- **Minor** (logged, batch continues): Individual file extraction failures, unsupported formats, empty files
- **Significant** (pause execution): Cost threshold exceeded, missing API key, invalid configuration

### Common Issues

| Problem | Solution |
|---------|----------|
| Missing API key | Copy `.env.dw.sample` to `.env.dw`, add token |
| No files found | Check path and file extensions |
| Insufficient text extracted | File may be corrupted or scanned (use OCR script) |
| Module not found | Run `uv sync` |
| Missing --output-dir | Always pass `--output-dir $PWD/dw_batch_output` |
| Batch stuck in progress | Normal for large batches. Ctrl+C and resume later. |

---

## Best Practices

1. **SLA:** Use 1h for most tasks. Only 24h for massive jobs where cost > time.
2. **Model:** Start with 30B. Upgrade to 235B only if quality insufficient.
3. **Prompt:** Clear, specific, include output format requirements.
4. **Tokens:** Set MAX_TOKENS to ~1.5x expected output length.
5. **Validation:** Test with 2-3 files first before batching 100s.
6. **Always use --output-dir** and **uv run** for all commands.
7. **Cleanup:** Delete `dw_batch_output/logs/` periodically.

### Always Use Existing Scripts

**CRITICAL RULE:** The `dw_batch` folder is the **canonical version** — always use its scripts (`create_batch.py`, `create_image_batch.py`, `create_scanned_pdf_batch.py`, `create_embeddings_batch.py`, `submit_batch.py`, `poll_and_process.py`, `process_results.py`) for batch operations. **Never write inline Python** to replicate what these scripts already do.

For Tier 2 edge cases where the existing scripts genuinely don't cover the use case (e.g., different prompts per file, conditional logic), write **one-off inline scripts** — do not persist them to the dw_batch folder unless the user explicitly requests it. This keeps the canonical folder clean and easy to understand.

### Multiple Batches

When submitting multiple batches, poll them in submission order (first submitted = first polled). Use `--batch-id` to specify which batch to poll:

```bash
# Submit two batches
uv run python submit_batch.py batch_a.jsonl --output-dir ...   # Batch ID: aaa-111
uv run python submit_batch.py batch_b.jsonl --output-dir ...   # Batch ID: bbb-222

# Poll in submission order
uv run python poll_and_process.py --output-dir ... --batch-id aaa-111
uv run python poll_and_process.py --output-dir ... --batch-id bbb-222
```

Without `--batch-id`, `poll_and_process.py` defaults to the most recent `batch_id_*.txt` file in the logs directory.

---

## Related Resources

- **[SKILL.md](SKILL.md)** - Quick reference and getting started guide
- **[examples.md](examples.md)** - Use case examples with prompts and workflows
- [Doubleword AI Portal](https://doubleword.ai) - API access and billing
- [Doubleword Batch API Docs](https://docs.doubleword.ai/batches/getting-started-with-batched-api) - Official API documentation
