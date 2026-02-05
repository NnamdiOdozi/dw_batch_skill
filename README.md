
# dw_batch (Doubleword AI Batch Skill)

Get your coding agent to batch-process lots of files (documents, spreadsheets, images, scanned PDFs) through the Doubleword API, cheaply and asynchronously with 50-85% savings compared to real-time LLMs. You give your agent what files you want processed plus a prompt, it creates a batch, submits it, then polls and saves results back to disk.

I built this for **Claude Code** and it works very well there when Claude is the model. I also tested it with **GLM-4.7 running on Ollama** as the driving model; it worked, but the overall experience was slower.

All you need to know to get started in in this README and the SKILLS.md and GUIDE.md is really for agents to read

---

## What you get

- **Bulk summarization and analysis** across many files in one go.
- **Image captioning** and **OCR** (including receipts/invoices) when using a vision-capable model.
- **Structured extraction** (for example “return JSON with these fields”).
- **Asynchronous batching** that is usually much cheaper than doing the same work via synchronous calls.

Typical “yes use this” jobs:
- “Summarize these 50 PDFs.”
- “Extract vendor, date, total, and line items from these 200 receipt images.”
- “Caption these product photos.”
- “Pull key metrics out of these CSV files.”

---

## Install (GitHub → your skills folder)

### 1) Clone the repo
```bash
git clone https://github.com/NnamdiOdozi/dw_batch_skill
cd dw_batch_skill
````

### 2) Copy the skill folder into your agent harness

You are copying the folder named `dw_batch` (or `dw_batch`, into the “skills” directory, either at project or user level .

Pick **one** of these patterns:

#### Option A: User-level (recommended)

This makes the skill available to all Claude Code sessions.

```bash
mkdir -p ~/.claude/skills
cp -R dw_batch ~/.claude/skills/
```

#### Option B: Project-level

This makes the skill available only inside one repo/project.

```bash
mkdir -p .claude/skills
cp -r dw_batch .claude/skills/
```

If you are using a different harness (not Claude Code), put the folder wherever that harness expects “skills”. The important thing is that the folder contains `SKILL.md` plus the scripts.

---

## Configure your API key (required)

1. Create your local secrets file from the sample:

```bash
cp .env.dw.sample .env.dw
```

2. Edit `.env.dw` and set:

```bash
DOUBLEWORD_AUTH_TOKEN=sk-your-doubleword-key
```

Get a Doubleword key from the Doubleword portal. https://www.doubleword.ai/

Security note: `.env.dw` should never be committed to Git. Keep it local.

## Configure your config.toml (required)
Check that you are happy with the defaults in the config.toml file eg LLM model, SLA, Polling Interval etc


## Add this comment to your CLAUDE.md files at project and user level (required)

```## Available Skills
**dw_batch:** Async batch processing using Doubleword API. Process multiple PDFs/DOCXs cost-effectively (50-85% cheaper) for non-urgent summarization, analysis, OCR, and extraction tasks. **Suggest for any token-heavy non-urgent work (10K+ tokens).**
```

## Operation of Skill ie batching of jobs

You just need to say "dw_batch" this task,together with a prompt that includes how long in words or tokens the output should be etc and the agent will load the skill and then take care of the rest, set config etc. Sometimes the agent will detect a suitable set of tasks for batching and prompt you about it.

Results will be written under:

* `dw_batch_output/` for final outputs
* `dw_batch_output/logs/` for batch request artifacts and batch IDs

---

## Using OpenAI or other OpenAI-compatible providers

Doubleword API is OpenAI-compatible. If you want to point this skill at **OpenAI** (or another compatible gateway), change the base URL and model in the config file (typically `config.toml` or `dw_batch/config.toml`):

* Set `base_url` to your provider’s API base.
* Set `model` to a model name your provider supports.
* Put that provider’s key in `.env.dw` (same variable name, this skill just needs a token).

That is it. The request format remains the same.

---

## Safety

There are quite a few built-in safety featues eg:

* Cost guardrails: the skill enforces input and output token thresholds (default examples are 250K input tokens or 100K output tokens) and will stop and warn before an expensive batch runs.

 * Dry-run mode: lets the agent estimate scope and cost before submitting anything to the provider. 

 * Safe failure mode: if one file fails extraction (unsupported, too short, corrupted), the batch creation logs it and continues with the remaining files rather than silently failing everything

 * Resumable polling: stopping polling (Ctrl+C) does not cancel the remote batch; you can restart polling later to fetch results, which avoids “panic re-submit” double-spend. 


## Other Agent Harnesses

I only tried the Skill with Claude Code. If you want to try it with other or even multiple agent harnesses then my advice would be to use symlinks so that they all point to the same skills folder

---

## Where to look next

* `SKILL.md` for how the agent should invoke this skill.
* `GUIDE.md` for deeper usage patterns and troubleshooting.
* `examples.md` for ready-to-run prompts (receipts, multimodal, OCR).

---

## License and support

This is provided as-is. If you hit issues, open a GitHub issue with:

* your command, your OS, and the error text
* a description of the file types you processed (no sensitive content)
