import logging
from pathlib import Path

from finorg.config import PipelineConfig
from finorg.utils import save_json, load_json

logger = logging.getLogger("finorg")


def run_grouping(config: PipelineConfig, classifications: list[dict], log) -> list[dict]:
    meta_path = config.working_dir / "metadata" / "document_groups.json"
    if config.resume and meta_path.exists():
        return load_json(meta_path)

    sorted_cls = sorted(classifications, key=lambda x: (x["source_pdf"], x["page_number"]))

    groups = []
    current = None
    doc_counter = 0

    for entry in sorted_cls:
        starts_new_group = (
            current is None
            or entry["source_pdf"] != current["source_pdf"]
            or entry["page_number"] == 1
            or entry.get("is_first_page", False)
        )
        if starts_new_group:
            if current is not None:
                groups.append(current)
            doc_counter += 1
            current = {
                "doc_id": f"DOC_{doc_counter:04d}",
                "source_pdf": entry["source_pdf"],
                "start_page": entry["page_number"],
                "end_page": entry["page_number"],
                "page_count": 1,
                "document_type": entry.get("document_type", "unknown"),
                "institution_name": entry.get("institution_name"),
                "statement_period": entry.get("statement_period"),
                "account_last4": entry.get("account_last4"),
                "confidences": [entry.get("confidence", 0.0)],
                "needs_review": entry.get("confidence", 0) < 0.6,
                "pages": [{"page_number": entry["page_number"], "text_file": entry["text_file"]}],
            }
        else:
            current["end_page"] = entry["page_number"]
            current["page_count"] += 1
            current["confidences"].append(entry.get("confidence", 0.0))
            if entry.get("confidence", 0) < 0.6:
                current["needs_review"] = True
            current["pages"].append({"page_number": entry["page_number"], "text_file": entry["text_file"]})

    if current is not None:
        groups.append(current)

    for g in groups:
        confs = g.pop("confidences")
        g["confidence_avg"] = sum(confs) / len(confs) if confs else 0.0
        try:
            g["text_preview"] = Path(g["pages"][0]["text_file"]).read_text(encoding="utf-8", errors="replace")[:500]
        except Exception:
            g["text_preview"] = ""

    save_json(meta_path, groups)
    type_dist = {}
    for g in groups:
        t = g.get("document_type", "unknown")
        type_dist[t] = type_dist.get(t, 0) + 1
    logger.info(f"Grouping: {len(groups)} documents. Types: {type_dist}")
    return groups
