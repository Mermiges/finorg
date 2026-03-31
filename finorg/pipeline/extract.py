import hashlib
import logging
from concurrent.futures import ProcessPoolExecutor
from pathlib import Path

from tqdm import tqdm

from finorg.config import PipelineConfig
from finorg.utils import save_json, load_json, sanitize_filename

logger = logging.getLogger("finorg")


def _extract_one_page(args: tuple) -> dict:
    """Extract text from a single PDF page. Top-level for pickling."""
    import pymupdf
    import hashlib
    from pathlib import Path as P

    pdf_path_str, page_0idx, output_path_str = args
    output_path = P(output_path_str)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    text = ""
    try:
        with pymupdf.open(pdf_path_str) as doc:
            if page_0idx < len(doc):
                text = doc[page_0idx].get_text("text")
    except Exception:
        text = ""
    output_path.write_text(text, encoding="utf-8")
    text_h = hashlib.sha256(text.encode("utf-8")).hexdigest()
    char_count = len(text)
    return {
        "source_pdf": pdf_path_str,
        "page_number": page_0idx + 1,
        "text_file": output_path_str,
        "text_hash": text_h,
        "char_count": char_count,
        "has_text": char_count > 50,
        "text_preview": text[:300],
    }


def run_extraction(config: PipelineConfig, inventory: list[dict], log) -> list[dict]:
    meta_path = config.working_dir / "metadata" / "page_index.json"
    if config.resume and meta_path.exists():
        logger.info("Resuming: loading existing page index")
        return load_json(meta_path)

    tasks = []
    for pdf_info in inventory:
        pdf_path = pdf_info["path"]
        stem = sanitize_filename(Path(pdf_path).stem)
        pdf_id = hashlib.sha1(str(Path(pdf_path).resolve()).encode("utf-8")).hexdigest()[:10]
        for page_0idx in range(pdf_info["page_count"]):
            out = str(config.working_dir / "page_text" / f"{stem}_{pdf_id}_p{page_0idx + 1:04d}.txt")
            tasks.append((pdf_path, page_0idx, out))

    if config.parallel and len(tasks) > 10:
        with ProcessPoolExecutor(max_workers=config.pdf_workers) as exe:
            page_index = list(tqdm(exe.map(_extract_one_page, tasks), total=len(tasks), desc="Extracting text"))
    else:
        page_index = [_extract_one_page(t) for t in tqdm(tasks, desc="Extracting text")]

    sparse = [p for p in page_index if not p["has_text"]]
    if sparse and not config.skip_ocr and config.ocr_engine != "pymupdf":
        logger.info(f"{len(sparse)} pages need OCR")
        try:
            from finorg.text_extract import extract_text
            for entry in tqdm(sparse, desc="OCR"):
                new_text = extract_text(
                    Path(entry["source_pdf"]),
                    entry["page_number"],
                    engine=config.ocr_engine,
                    model_id=config.ocr_model,
                    cache_dir=str(config.ocr_cache_dir) if config.ocr_cache_dir else None,
                )
                if new_text and len(new_text) > entry["char_count"]:
                    Path(entry["text_file"]).write_text(new_text, encoding="utf-8")
                    entry["char_count"] = len(new_text)
                    entry["has_text"] = len(new_text) > 50
                    entry["text_preview"] = new_text[:300]
                    entry["text_hash"] = hashlib.sha256(new_text.encode()).hexdigest()
        except ImportError:
            logger.warning(f"OCR engine '{config.ocr_engine}' not available, skipping OCR")

    save_json(meta_path, page_index)
    has_text_count = sum(1 for p in page_index if p["has_text"])
    logger.info(f"Extracted: {len(page_index)} pages, {has_text_count} with text, {len(page_index) - has_text_count} blank")
    return page_index
