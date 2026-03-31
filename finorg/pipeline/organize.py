import logging
import shutil
from pathlib import Path

from tqdm import tqdm

from finorg.config import PipelineConfig
from finorg.routing import apply_routing
from finorg.utils import save_json

logger = logging.getLogger("finorg")


def _ensure_unique_pdf(path: Path) -> Path:
    target = path
    counter = 2
    while target.exists():
        target = path.with_name(f"{path.stem}_v{counter}{path.suffix}")
        counter += 1
        if counter > 99:
            break
    return target


def run_organize(config: PipelineConfig, doc_groups: list[dict], log) -> list[dict]:
    organized = 0
    active_docs = [apply_routing(g) for g in doc_groups if not g.get("is_duplicate")]

    for g in tqdm(active_docs, desc="Organizing"):
        file_stem = g.get("proposed_filename") or g["doc_id"]
        root_target = _ensure_unique_pdf(config.output_dir / f"{file_stem}.pdf")

        src = g.get("split_pdf_path")
        if src and Path(src).exists():
            try:
                shutil.copy2(src, root_target)
                g["root_copy_path"] = str(root_target)
            except Exception as e:
                logger.warning(f"Root copy failed for {g['doc_id']}: {e}")
                g["root_copy_path"] = None
        else:
            g["root_copy_path"] = None

        folder_parts = g.get("folder_parts") or ["13 - Additional Categories"]
        target_dir = config.output_dir
        for part in folder_parts:
            target_dir = target_dir / part
        target_dir.mkdir(parents=True, exist_ok=True)

        source_for_folder = Path(g["root_copy_path"]) if g.get("root_copy_path") else (Path(src) if src else None)
        if source_for_folder and source_for_folder.exists():
            target = _ensure_unique_pdf(target_dir / root_target.name)
            try:
                shutil.copy2(source_for_folder, target)
                g["organized_path"] = str(target)
                g["relative_folder"] = str(Path(*folder_parts))
                organized += 1
            except Exception as e:
                logger.warning(f"Folder copy failed for {g['doc_id']}: {e}")
                g["organized_path"] = None
        else:
            g["organized_path"] = None

        conf = g.get("confidence", 0) or 0
        filename = g.get("proposed_filename") or ""
        if (
            conf < config.confidence_threshold
            or folder_parts[0] == "13 - Additional Categories"
            or filename.startswith("NODATE")
            or "Unknown" in filename
        ):
            g["needs_review"] = True

    by_id = {g["doc_id"]: g for g in doc_groups}
    for g in active_docs:
        by_id[g["doc_id"]] = g
    updated = list(by_id.values())

    save_json(config.working_dir / "metadata" / "document_groups.json", updated)
    logger.info(f"Organized: {organized} documents into {config.output_dir}")
    return updated
