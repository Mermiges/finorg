# financial-ocr

Extract structured financial data from pay stubs, tax returns, and bank statements using vision LLMs and OCR. Outputs JSON suitable for auto-populating SC Form 430 (Financial Declaration).

## Pipeline

```
Document (PDF/image) → Vision LLM (qwen3-vl:8b) or OCR (glm-ocr) → Structured JSON → Form 430 fields
```

## Extracted Fields

- Gross monthly income, net monthly income
- Federal/state tax withholding, FICA, Medicare
- Health insurance, retirement contributions
- YTD totals with monthly average calculation
- Employer name and pay period

## Status

**Scaffolded** — architecture defined, implementation in progress.

## License

MIT
