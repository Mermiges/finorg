import logging
from pathlib import Path

import fitz

from finorg.utils import file_hash

logger = logging.getLogger("finorg")


def get_pdf_info(path: Path) -> dict:
    try:
        doc = fitz.open(str(path))
        page_count = len(doc)
        doc.close()
        return {
            "path": str(path),
            "page_count": page_count,
            "file_size": path.stat().st_size,
            "file_hash": file_hash(path),
        }
    except Exception as e:
        logger.warning(f"Error reading {path}: {e}")
        return {
            "path": str(path),
            "page_count": 0,
            "file_size": path.stat().st_size if path.exists() else 0,
            "file_hash": "",
        }


def extract_page_text(pdf_path: Path, page_num: int) -> str:
    try:
        doc = fitz.open(str(pdf_path))
        if page_num < len(doc):
            text = doc[page_num].get_text("text")
        else:
            text = ""
        doc.close()
        return text
    except Exception as e:
        logger.warning(f"Error extracting text from {pdf_path} page {page_num}: {e}")
        return ""


def render_page_image(pdf_path: Path, page_num: int, dpi: int, output_path: Path) -> Path:
    output_path.parent.mkdir(parents=True, exist_ok=True)
    doc = fitz.open(str(pdf_path))
    page = doc[page_num]
    mat = fitz.Matrix(dpi / 72, dpi / 72)
    pixmap = page.get_pixmap(matrix=mat)
    pixmap.save(str(output_path))
    doc.close()
    return output_path


def split_pdf(source_path: Path, start_page: int, end_page: int, output_path: Path) -> Path:
    """Split PDF. start_page and end_page are 1-indexed inclusive."""
    output_path.parent.mkdir(parents=True, exist_ok=True)
    src = fitz.open(str(source_path))
    dst = fitz.open()
    dst.insert_pdf(src, from_page=start_page - 1, to_page=end_page - 1)
    dst.save(str(output_path))
    dst.close()
    src.close()
    return output_path
