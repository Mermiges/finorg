import logging
from pathlib import Path

import pymupdf
from PIL import Image

from finorg.utils import file_hash

logger = logging.getLogger("finorg")


def get_pdf_info(path: Path) -> dict:
    try:
        with pymupdf.open(str(path)) as doc:
            page_count = len(doc)
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
    """Extract text from a single page. page_num is 0-indexed."""
    try:
        with pymupdf.open(str(pdf_path)) as doc:
            if page_num < len(doc):
                return doc[page_num].get_text("text")
            return ""
    except Exception as e:
        logger.warning(f"Error extracting text from {pdf_path} page {page_num}: {e}")
        return ""


def render_page_image(pdf_path: Path, page_num: int, dpi: int, output_path: Path) -> Path:
    """Render a page to an image. page_num is 0-indexed."""
    output_path.parent.mkdir(parents=True, exist_ok=True)
    with pymupdf.open(str(pdf_path)) as doc:
        page = doc[page_num]
        mat = pymupdf.Matrix(dpi / 72, dpi / 72)
        pixmap = page.get_pixmap(matrix=mat, alpha=False)
        pixmap.save(str(output_path))
    return output_path


def render_page_pil(pdf_path: Path, page_num: int, dpi: int = 200, longest_dimension: int = 1540) -> Image.Image:
    """Render a PDF page to a PIL image following LightOnOCR guidance."""
    with pymupdf.open(str(pdf_path)) as doc:
        page = doc[page_num]
        mat = pymupdf.Matrix(dpi / 72, dpi / 72)
        pixmap = page.get_pixmap(matrix=mat, alpha=False)
        image = Image.frombytes("RGB", [pixmap.width, pixmap.height], pixmap.samples)
    if max(image.size) > longest_dimension:
        image.thumbnail((longest_dimension, longest_dimension))
    return image


def split_pdf(source_path: Path, start_page: int, end_page: int, output_path: Path) -> Path:
    """Split PDF. start_page and end_page are 1-indexed inclusive."""
    output_path.parent.mkdir(parents=True, exist_ok=True)
    with pymupdf.open(str(source_path)) as src:
        with pymupdf.open() as dst:
            dst.insert_pdf(src, from_page=start_page - 1, to_page=end_page - 1)
            dst.save(str(output_path))
    return output_path
