# FinOrg

FinOrg is a CLI for organizing messy financial PDFs into labeled folders using OCR, PDF processing, and Ollama-backed LLM classification.

It is designed for mixed document sets such as bank statements, retirement statements, brokerage statements, mortgage statements, and other financial records that need to be split, grouped, classified, deduplicated, and organized.

## Features

- 9-phase document processing pipeline
- OCR support via `pymupdf`, with optional `marker` and `docling`
- Boundary detection and document classification with Ollama models
- Parallel multi-instance Ollama execution across available GPUs
- Resume support and per-phase restart control
- Markdown report output plus structured working metadata

## Pipeline

1. Inventory PDFs
2. Extract page text
3. Detect document boundaries
4. Group pages into documents
5. Split grouped PDFs
6. Classify documents
7. Deduplicate results
8. Organize output folders
9. Generate a final report

## Install

```bash
pip install -e .
```

## Usage

```bash
finorg SOURCE_DIR --output OUTPUT_DIR
```

Check prerequisites without running the pipeline:

```bash
finorg SOURCE_DIR --dry-run
```

Show command help:

```bash
python -m finorg --help
```

## Requirements

- Python environment with the packages in `setup.py`
- Ollama running locally or at a reachable `--ollama-url`
- Optional NVIDIA GPUs for parallel multi-model execution

## License

MIT
