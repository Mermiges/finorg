import logging
import shutil
from pathlib import Path

from tqdm import tqdm

from finorg.config import PipelineConfig
from finorg.utils import save_json, sanitize_filename

logger = logging.getLogger("finorg")


def run_organize(config: PipelineConfig, doc_groups: list[dict], log) -> list[dict]:
    # Count docs per (category, institution) to decide on subfolders
    cat_inst_counts = {}
    for g in doc_groups:
        if g.get("is_duplicate"):
            continue
        cat = g.get("category_folder", "Uncategorized")
        inst = sanitize_filename(g.get("institution_name") or "Unknown")
        cat_inst_counts.setdefault((cat, inst), 0)
        cat_inst_counts[(cat, inst)] += 1

    organized = 0
    for g in tqdm([g for g in doc_groups if not g.get("is_duplicate")], desc="Organizing"):
        cat = g.get("category_folder", "Uncategorized")
        inst = sanitize_filename(g.get("institution_name") or "Unknown")
        fname = sanitize_filename(g.get("proposed_filename") or g["doc_id"])
        if not fname:
            fname = g["doc_id"]

        target_dir = config.output_dir / cat
        if cat_inst_counts.get((cat, inst), 0) >= 5:
            target_dir = target_dir / inst
        target_dir.mkdir(parents=True, exist_ok=True)

        target = target_dir / f"{fname}.pdf"
        counter = 2
        while target.exists():
            target = target_dir / f"{fname}_v{counter}.pdf"
            counter += 1
            if counter > 99:
                break

        src = g.get("split_pdf_path")
        if src and Path(src).exists():
            try:
                shutil.copy2(src, target)
                g["organized_path"] = str(target)
                organized += 1
            except Exception as e:
                logger.warning(f"Copy failed for {g['doc_id']}: {e}")
                g["organized_path"] = None
        else:
            g["organized_path"] = None

        conf = g.get("confidence", 0) or 0
        pf = g.get("proposed_filename") or ""
        if (conf < config.confidence_threshold or cat == "Uncategorized"
                or pf.startswith("NODATE") or pf.startswith("Unknown") or "_Unknown_" in pf):
            g["needs_review"] = True

    save_json(config.working_dir / "metadata" / "document_groups.json", doc_groups)
    logger.info(f"Organized: {organized} documents into {config.output_dir}")
    return doc_groups
