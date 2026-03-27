import logging
import time as _time
from pathlib import Path

from tqdm import tqdm

from finorg.config import PipelineConfig
from finorg.utils import save_json, load_json

logger = logging.getLogger("finorg")


def _classify_boundary_item(page_entry: dict, ollama_url: str) -> dict:
    """Classify one page for boundary detection. Called from thread pool."""
    from pathlib import Path as P

    from finorg.llm_client import OllamaClient
    from finorg.prompts.boundary_prompt import BOUNDARY_SYSTEM_PROMPT, make_boundary_user_prompt

    try:
        page_text = P(page_entry["text_file"]).read_text(encoding="utf-8", errors="replace")
    except Exception:
        page_text = ""

    model = page_entry.get("_model", "qwen2.5:14b-instruct-q4_K_M")
    client = OllamaClient(ollama_url)
    result = client.generate_json_at(
        url=ollama_url,
        model=model,
        system=BOUNDARY_SYSTEM_PROMPT,
        prompt=make_boundary_user_prompt(page_text),
    )

    entry = {k: v for k, v in page_entry.items() if not k.startswith("_")}
    defaults = {
        "is_first_page": False,
        "confidence": 0.0,
        "document_type": "unknown",
        "institution_name": None,
        "statement_period": None,
        "account_last4": None,
        "reasoning": "error",
    }
    for k, v in defaults.items():
        entry[k] = result.get(k, v)
    return entry


def run_boundary_detection(config: PipelineConfig, page_index: list[dict], log, parallel_pool=None) -> list[dict]:
    meta_path = config.working_dir / "metadata" / "page_classifications.json"
    if config.resume and meta_path.exists():
        return load_json(meta_path)

    enriched = [{**p, "_model": config.fast_model} for p in page_index]

    if parallel_pool:
        results = parallel_pool.map(_classify_boundary_item, enriched, desc="Detecting boundaries")
    else:
        results = []
        for entry in tqdm(enriched, desc="Detecting boundaries"):
            r = _classify_boundary_item(entry, config.ollama_url)
            results.append(r)
            _time.sleep(0.3)

    # Force page 1 of each PDF to be a first page unless model is very confident it's not
    by_pdf = {}
    for r in results:
        by_pdf.setdefault(r["source_pdf"], []).append(r)
    for pdf_pages in by_pdf.values():
        pdf_pages.sort(key=lambda x: x["page_number"])
        first = pdf_pages[0]
        if not first.get("is_first_page", False) and first.get("confidence", 0) < 0.8:
            first["is_first_page"] = True
            first["reasoning"] = (first.get("reasoning", "") + " [forced: page 1 of PDF]").strip()

    boundaries = sum(1 for r in results if r.get("is_first_page"))
    save_json(meta_path, results)
    logger.info(f"Boundaries: {boundaries} document starts detected in {len(results)} pages")
    return results
