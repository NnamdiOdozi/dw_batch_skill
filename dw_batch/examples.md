# Batch Processing Examples

Quick examples for common use cases. For detailed guides, see [GUIDE.md](GUIDE.md).

---

## Receipt/Invoice JSON Extraction

Extract structured data from scanned receipts for accounting automation.

**Use case:** "Parse these 50 receipts into structured data"

**Prompt (prompt.txt):**
```
Extract the following fields from this receipt/invoice and return as JSON:

{
  "vendor_name": "string",
  "date": "YYYY-MM-DD",
  "total_amount": number,
  "tax_amount": number,
  "currency": "string (USD, EUR, etc.)",
  "items": [{"description": "string", "quantity": number, "price": number}],
  "payment_method": "string (if visible)"
}

Important: Extract exact values, use null for missing fields, return ONLY valid JSON.
```

**Workflow:**
```bash
# 1. Copy prompt above to prompt.txt
# 2. Process receipt images/PDFs
uv run python create_batch.py --input-dir /path/to/receipts --output-dir $PWD/../../dw_batch_output
uv run python submit_batch.py --output-dir $PWD/../../dw_batch_output
uv run python poll_and_process.py --output-dir $PWD/../../dw_batch_output

# Results: JSON files in dw_batch_output/ with vendor, date, amount, items extracted
```

**JSON validation:** Automatically detects JSON prompt and validates outputs. Invalid JSON flagged in quality summary.

---

## Scanned PDF OCR

Extract text from scanned documents using vision models.

**Use case:** "Digitize these scanned contracts"

**Workflow:**
```bash
# Process scanned PDFs (auto-detects minimal text)
uv run python create_scanned_pdf_batch.py --input-dir /path/to/scans --output-dir $PWD/../../dw_batch_output

# Force treat as scanned (if needed)
uv run python create_scanned_pdf_batch.py --force-scan --files contract.pdf --output-dir $PWD/../../dw_batch_output

# Submit and process
uv run python submit_batch.py --output-dir $PWD/../../dw_batch_output
uv run python poll_and_process.py --output-dir $PWD/../../dw_batch_output
```

**How it works:** Converts PDF pages to images (150 DPI), sends to vision model for OCR. Auto-chunks long PDFs (max ~30 pages/request).

**Cost:** ~7x more expensive than text PDFs (~3.5K tokens/page vs ~500 tokens/page), but still cost-effective.

---

## Multimodal Document Analysis

Process multiple documents + images in a single request for synthesis.

**Use case:** "Create Q4 report using these 3 docs and 2 charts"

**Custom batch code (Tier 2):**
```python
import json, base64
from pathlib import Path

# Read documents
doc1 = Path('q4_financials.txt').read_text()
doc2 = Path('q4_metrics.csv').read_text()
doc3 = Path('q4_notes.md').read_text()

# Encode images
def encode_image(path):
    with open(path, 'rb') as f:
        return base64.b64encode(f.read()).decode('utf-8')

chart1 = encode_image('revenue_chart.png')
chart2 = encode_image('customer_growth.png')

# Create multimodal request
request = {
    "custom_id": "q4-report-2024",
    "method": "POST",
    "url": "/v1/chat/completions",
    "body": {
        "model": "Qwen/Qwen3-VL-30B-A3B-Instruct-FP8",
        "messages": [{
            "role": "user",
            "content": [
                {"type": "text", "text": "Create Q4 2024 report using ALL provided documents and charts."},
                {"type": "text", "text": f"Financials:\\n{doc1}"},
                {"type": "text", "text": f"Metrics:\\n{doc2}"},
                {"type": "text", "text": f"Notes:\\n{doc3}"},
                {"type": "image_url", "image_url": {"url": f"data:image/png;base64,{chart1}"}},
                {"type": "image_url", "image_url": {"url": f"data:image/png;base64,{chart2}"}},
                {"type": "text", "text": "Provide: 1) Executive summary, 2) Key insights, 3) Recommendations"}
            ]
        }],
        "max_tokens": 2000
    }
}

# Save to batch file
with open('batch_requests_multimodal.jsonl', 'w') as f:
    f.write(json.dumps(request) + '\\n')

# Then run: submit_batch.py and poll_and_process.py
```

**Key points:**
- Content array combines text + images
- Order matters: context before question
- Model processes ALL inputs together for holistic analysis
- Use base64-encoded images: `data:image/png;base64,...`
- ~3-4K tokens per image + text content

**When to use:** Cross-referencing multiple sources, synthesis tasks, connecting text and visuals. For independent summaries, use individual processing instead.

---

## More Examples

See [GUIDE.md](GUIDE.md#step-by-step-workflow) for:
- Embeddings generation
- Streaming API (non-batch)
- Custom Tier 2 workflows
- Cost optimization strategies
