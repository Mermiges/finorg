import hashlib
import logging
from concurrent.futures import ProcessPoolExecutor
from pathlib import Path

from tqdm import tqdm

from finorg.config import PipelineConfig
from finorg.utils import save_json

logger = logging.getLogger("finorg")


def _split_one(args: tuple) -> dict:
    """Split one document out of a source PDF. Top-level for pickling."""
    import pymupdf
    import hashlib
    from pathlib import Path as P

    source_str, start_pg, end_pg, output_str = args
    output_path = P(output_str)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    try:
        with pymupdf.open(source_str) as src:
            with pymupdf.open() as dst:
                dst.insert_pdf(src, from_page=start_pg - 1, to_page=end_pg - 1)
                dst.save(str(output_path))
                page_count = len(dst)
        h = hashlib.sha256()
        with open(str(output_path), "rb") as f:
            while True:
                chunk = f.read(65536)
                if not chunk:
                    break
                h.update(chunk)
        return {
            "split_pdf_path": str(output_path),
            "split_file_hash": h.hexdigest(),
            "verified_pages": page_count,
            "error": None,
        }
    except Exception as e:
        return {
            "split_pdf_path": str(output_path),
            "split_file_hash": "",
            "verified_pages": 0,
            "error": str(e),
        }


def run_split(config: PipelineConfig, doc_groups: list[dict], log) -> list[dict]:
    meta_path = config.working_dir / "metadata" / "document_groups.json"

    tasks = []
    for g in doc_groups:
        out = str(config.working_dir / "split_pdfs" / f"{g['doc_id']}.pdf")
        tasks.append((g["source_pdf"], g["start_page"], g["end_page"], out))

    if config.parallel and len(tasks) > 5:
        with ProcessPoolExecutor(max_workers=config.pdf_workers) as exe:
            results = list(tqdm(exe.map(_split_one, tasks), total=len(tasks), desc="Splitting PDFs"))
    else:
        results = [_split_one(t) for t in tqdm(tasks, desc="Splitting PDFs")]

    errors = 0
    for g, r in zip(doc_groups, results):
        g["split_pdf_path"] = r["split_pdf_path"]
        g["split_file_hash"] = r["split_file_hash"]
        if r["error"]:
            errors += 1
            logger.warning(f"Split error for {g['doc_id']}: {r['error']}")

    save_json(meta_path, doc_groups)
    logger.info(f"Split: {len(doc_groups)} PDFs created, {errors} errors")
    return doc_groups
