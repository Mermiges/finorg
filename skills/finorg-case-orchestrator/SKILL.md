---
name: finorg-case-orchestrator
description: Use when organizing family-law client PDFs with FinOrg, especially when OCRing scanned financial records, renaming chronological root copies, routing files into the LegalFlow/CaseFlow case-folder structure, and reviewing missing financial-statement months.
---

# FinOrg Case Orchestrator

Use this skill when the task is to run or supervise the FinOrg pipeline on a client file.

## Defaults

- Repo: `E:\finorg`
- Virtualenv: `E:\finorg\.venv`
- OCR cache: `E:\huggingface`
- OCR engine: `lightonocr`
- Deep model: `qwen3.5:122b`
- Fast model: `qwen3.5:35b`

## Workflow

1. Read `E:\finorg\README.md` only if you need command details.
2. Confirm the source directory and the output case root.
3. Run a dry check first:
   `E:\finorg\.venv\Scripts\python -m finorg SOURCE --output CASE_ROOT --dry-run`
4. Run the full organizer with LightOnOCR:
   `E:\finorg\.venv\Scripts\python -m finorg SOURCE --output CASE_ROOT --ocr-engine lightonocr --ocr-cache-dir E:\huggingface --model qwen3.5:122b --fast-model qwen3.5:35b`
5. Review:
   `CASE_ROOT\!lf\reports\PIPELINE_REPORT.md`
   `CASE_ROOT\!lf\reports\REVIEW_NEEDED.csv`
   `CASE_ROOT\!lf\reports\MISSING_STATEMENT_MONTHS.csv`
6. If OCR was good but routing/classification needs work, rerun from phase 6 or later instead of rerunning OCR:
   `--start-phase 6`
7. If only copy placement/reporting needs to be rerun, use:
   `--start-phase 8`

## Guardrails

- Do not rename or overwrite the original source PDFs unless the user explicitly asks for in-place changes.
- FinOrg writes renamed copies at the case-root level and foldered copies inside the numbered structure.
- Missing-month review is highest priority for financial accounts; surface that report first.
- Documents routed into `13 - Additional Categories` should be reviewed and either accepted or folded into a better category on the next pass.
