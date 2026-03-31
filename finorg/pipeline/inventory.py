import logging
from pathlib import Path

from tqdm import tqdm

from finorg.config import PipelineConfig
from finorg.pdf_ops import get_pdf_info, extract_page_text
from finorg.utils import save_json, load_json

logger = logging.getLogger("finorg")


def _should_skip_pdf(config: PipelineConfig, pdf_path: Path) -> bool:
    resolved = pdf_path.resolve()
    skip_roots = [config.output_dir.resolve(), config.working_dir.resolve()]
    for root in skip_roots:
        try:
            resolved.relative_to(root)
            return True
        except ValueError:
            continue
    return False


def run_inventory(config: PipelineConfig, log) -> list[dict]:
    meta_path = config.working_dir / "metadata" / "pdf_inventory.json"
    if config.resume and meta_path.exists():
        logger.info("Resuming: loading existing inventory")
        return load_json(meta_path)

    candidates = sorted(set(list(config.source_dir.rglob("*.pdf")) + list(config.source_dir.rglob("*.PDF"))))
    pdfs = [pdf for pdf in candidates if not _should_skip_pdf(config, pdf)]
    logger.info(f"Found {len(pdfs)} PDFs in {config.source_dir}")

    inventory = []
    total_pages = 0
    corrupt = 0
    for pdf_path in tqdm(pdfs, desc="Scanning PDFs"):
        info = get_pdf_info(pdf_path)
        preview = ""
        if info["page_count"] > 0:
            preview = extract_page_text(pdf_path, 0)[:200]
        info["text_preview"] = preview
        info["path"] = str(pdf_path)
        inventory.append(info)
        total_pages += info["page_count"]
        if info["page_count"] == 0:
            corrupt += 1

    save_json(meta_path, inventory)
    logger.info(f"Inventory: {len(inventory)} PDFs, {total_pages} total pages, {corrupt} corrupt")
    return inventory
