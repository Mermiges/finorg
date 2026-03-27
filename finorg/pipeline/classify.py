import logging
import time as _time
from pathlib import Path

from tqdm import tqdm

from finorg.config import PipelineConfig
from finorg.utils import save_json, load_json

logger = logging.getLogger("finorg")


def _classify_document_item(doc_group: dict, ollama_url: str) -> dict:
    """Classify one document via LLM. Called from thread pool."""
    from pathlib import Path as P

    from finorg.llm_client import OllamaClient
    from finorg.prompts.classify_prompt import CLASSIFY_SYSTEM_PROMPT, make_classify_user_prompt

    full_text = ""
    for pg in doc_group.get("pages", []):
        try:
            full_text += P(pg["text_file"]).read_text(encoding="utf-8", errors="replace") + "\n"
        except Exception:
            pass

    model = doc_group.get("_model", "qwen2.5:72b-instruct-q4_K_M")
    max_chars = doc_group.get("_max_chars", 10000)
    client = OllamaClient(ollama_url)
    result = client.generate_json_at(
        url=ollama_url,
        model=model,
        system=CLASSIFY_SYSTEM_PROMPT,
        prompt=make_classify_user_prompt(full_text, max_chars),
    )

    entry = {k: v for k, v in doc_group.items() if not k.startswith("_")}
    fields = [
        "document_type", "category_folder", "institution_name", "account_type",
        "account_number_last4", "account_holder_name", "statement_start_date",
        "statement_end_date", "statement_period_label", "opening_balance",
        "closing_balance", "confidence", "proposed_filename", "notes",
    ]
    for f in fields:
        entry[f] = result.get(f)

    if not entry.get("category_folder"):
        entry["category_folder"] = "Uncategorized"
    if entry.get("confidence") is None:
        entry["confidence"] = 0.0
        entry["needs_review"] = True
    if "error" in result:
        entry["needs_review"] = True
        entry["notes"] = (entry.get("notes") or "") + f" [LLM error: {result['error']}]"
    return entry


def run_classification(config: PipelineConfig, doc_groups: list[dict], log, parallel_pool=None) -> list[dict]:
    meta_path = config.working_dir / "metadata" / "deep_classifications.json"
    if config.resume and meta_path.exists():
        return load_json(meta_path)

    enriched = [{**g, "_model": config.deep_model, "_max_chars": config.max_text_chars} for g in doc_groups]

    if parallel_pool:
        results = parallel_pool.map(_classify_document_item, enriched, desc="Classifying documents")
    else:
        results = []
        for g in tqdm(enriched, desc="Classifying documents"):
            results.append(_classify_document_item(g, config.ollama_url))
            _time.sleep(1.0)

    save_json(meta_path, results)
    cat_dist = {}
    for r in results:
        c = r.get("category_folder", "Uncategorized")
        cat_dist[c] = cat_dist.get(c, 0) + 1
    logger.info(f"Classification: {len(results)} docs. Categories: {cat_dist}")
    return results
