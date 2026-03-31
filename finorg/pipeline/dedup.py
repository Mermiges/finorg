import logging
import shutil
from pathlib import Path

from finorg.config import PipelineConfig
from finorg.utils import save_json, text_hash

logger = logging.getLogger("finorg")


def run_dedup(config: PipelineConfig, doc_groups: list[dict], log) -> list[dict]:
    duplicates_dir = config.duplicates_dir
    duplicates_dir.mkdir(parents=True, exist_ok=True)
    dedup_log = []

    by_id = {g["doc_id"]: g for g in doc_groups}

    # LAYER 1: Exact file hash
    hash_groups = {}
    for g in doc_groups:
        h = g.get("split_file_hash", "")
        if h:
            hash_groups.setdefault(h, []).append(g["doc_id"])
    for h, ids in hash_groups.items():
        if len(ids) > 1:
            keeper = ids[0]
            for dup_id in ids[1:]:
                by_id[dup_id]["is_duplicate"] = True
                by_id[dup_id]["duplicate_of"] = keeper
                by_id[dup_id]["dedup_layer"] = 1
                dedup_log.append({"doc_id": dup_id, "duplicate_of": keeper, "layer": 1})

    # LAYER 2: Text content hash
    text_hashes = {}
    for g in doc_groups:
        if g.get("is_duplicate"):
            continue
        full_text = ""
        for pg in g.get("pages", []):
            try:
                full_text += Path(pg["text_file"]).read_text(encoding="utf-8", errors="replace")
            except Exception:
                pass
        th = text_hash(full_text) if full_text else ""
        if th:
            text_hashes.setdefault(th, []).append(g["doc_id"])
    for th, ids in text_hashes.items():
        if len(ids) > 1:
            sizes = []
            for did in ids:
                try:
                    sizes.append((did, Path(by_id[did].get("split_pdf_path", "")).stat().st_size))
                except Exception:
                    sizes.append((did, 0))
            sizes.sort(key=lambda x: -x[1])
            keeper = sizes[0][0]
            for did, _ in sizes[1:]:
                by_id[did]["is_duplicate"] = True
                by_id[did]["duplicate_of"] = keeper
                by_id[did]["dedup_layer"] = 2
                dedup_log.append({"doc_id": did, "duplicate_of": keeper, "layer": 2})

    # LAYER 3: Metadata match
    meta_groups = {}
    for g in doc_groups:
        if g.get("is_duplicate"):
            continue
        inst = (g.get("institution_name") or "").lower().strip()
        last4 = g.get("account_number_last4") or g.get("account_last4")
        end_date = g.get("statement_end_date")
        doc_type = g.get("document_type")
        if inst and last4 and end_date and doc_type:
            key = (inst, str(last4), str(end_date), doc_type)
            meta_groups.setdefault(key, []).append(g["doc_id"])
    for key, ids in meta_groups.items():
        if len(ids) > 1:
            best = max(ids, key=lambda did: by_id[did].get("confidence", 0))
            for did in ids:
                if did != best:
                    by_id[did]["is_duplicate"] = True
                    by_id[did]["duplicate_of"] = best
                    by_id[did]["dedup_layer"] = 3
                    dedup_log.append({"doc_id": did, "duplicate_of": best, "layer": 3})

    # Move duplicate files
    for entry in dedup_log:
        g = by_id[entry["doc_id"]]
        src = g.get("split_pdf_path")
        if src and Path(src).exists():
            dst = duplicates_dir / f"DUP_{g['doc_id']}.pdf"
            try:
                shutil.copy2(src, dst)
            except Exception:
                pass

    save_json(config.working_dir / "metadata" / "dedup_results.json", {
        "kept": [g["doc_id"] for g in doc_groups if not g.get("is_duplicate")],
        "duplicates": dedup_log,
    })
    updated = list(by_id.values())
    save_json(config.working_dir / "metadata" / "document_groups.json", updated)

    layer_counts = {1: 0, 2: 0, 3: 0}
    for d in dedup_log:
        layer_counts[d["layer"]] = layer_counts.get(d["layer"], 0) + 1
    non_dup = sum(1 for g in updated if not g.get("is_duplicate"))
    logger.info(f"Dedup: {len(dedup_log)} duplicates (L1:{layer_counts[1]}, L2:{layer_counts[2]}, L3:{layer_counts[3]}), {non_dup} unique")
    return updated
