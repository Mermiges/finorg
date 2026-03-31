# FinOrg

FinOrg organizes mixed legal and financial PDFs for family-law case files.

It is built around:

- `lightonai/LightOnOCR-2-1B` for high-quality OCR on scanned pages
- `qwen3.5:122b` for deep document classification and metadata extraction
- a deterministic case-folder router for the client structure described in the planning chat

## What it does

FinOrg scans a source directory of PDFs and produces a case root with:

- root-level chronological renamed PDF copies
- copies routed into the numbered client-file folders
- `!lf/` reports, logs, working metadata, and duplicate tracking
- per-account statement timelines with missing-month detection

The highest-priority workflow is financial statement handling:

- identify bank, credit-card, brokerage, retirement, TSP, mortgage, loan, payment-provider, and crypto statements
- extract institution, period, account clues, balances, and filenames
- sort statement copies chronologically
- detect missing months across each account timeline

## Output shape

The output directory is the case root. FinOrg creates:

- `!lf/reports/`
- `!lf/logs/`
- `!lf/work/`
- `01 - Pleadings/`
- `02 - Discovery/`
- `03 - Financial Accounts/`
- `04 - Real Estate & Property/`
- `05 - Income & Taxes/`
- `06 - Affidavits/`
- `07 - Communications/`
- `08 - Medical/`
- `09 - Children & Custody/`
- `10 - Photos & Media/`
- `11 - Trial Prep/`
- `12 - Admin/`
- `13 - Additional Categories/`
- `_archive/`

## Install

Base install:

```bash
pip install -e .
```

Install LightOnOCR support:

```bash
pip install -e .[lightonocr]
```

Set the Hugging Face cache to `E:` if you want model weights off `C:`:

```powershell
$env:HF_HOME = 'E:\huggingface'
```

## Usage

Prerequisite check:

```bash
finorg SOURCE_DIR --output CASE_ROOT --dry-run
```

Default run with LightOnOCR and Qwen 3.5 122B:

```bash
finorg SOURCE_DIR --output CASE_ROOT
```

Explicit OCR cache/model settings:

```bash
finorg SOURCE_DIR --output CASE_ROOT `
  --ocr-engine lightonocr `
  --ocr-model lightonai/LightOnOCR-2-1B `
  --ocr-cache-dir E:\huggingface
```

Example with explicit GPU pinning:

```bash
finorg SOURCE_DIR --output CASE_ROOT `
  --gpu-fast 4 `
  --gpu-deep 0,1,2,3,5,6
```

## Reports

FinOrg writes:

- `!lf/reports/MASTER_INDEX.csv`
- `!lf/reports/REVIEW_NEEDED.csv`
- `!lf/reports/STATEMENT_TIMELINES.csv`
- `!lf/reports/MISSING_STATEMENT_MONTHS.csv`
- `!lf/reports/PIPELINE_REPORT.md`

## OCR notes

LightOnOCR-2 is the default OCR engine. Per the official model card, FinOrg renders PDF pages at 200 DPI and caps the longest dimension at roughly 1540px before inference.

If LightOnOCR is not installed, FinOrg falls back to the other configured engines.

## License

MIT
