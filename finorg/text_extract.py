import logging
from pathlib import Path

from finorg.pdf_ops import extract_page_text

logger = logging.getLogger("finorg")

_marker_cache = {}


def extract_text_pymupdf(pdf_path: Path, page_num: int) -> str:
    return extract_page_text(pdf_path, page_num)


def extract_text_marker(pdf_path: Path) -> dict[int, str]:
    key = str(pdf_path)
    if key in _marker_cache:
        return _marker_cache[key]
    try:
        from marker.converters.pdf import PdfConverter
        from marker.models import create_model_dict

        models = create_model_dict()
        converter = PdfConverter(artifact_dict=models)
        result = converter(str(pdf_path))
        pages = {}
        if hasattr(result, "pages"):
            for i, page in enumerate(result.pages):
                text = page.text if hasattr(page, "text") else str(page)
                pages[i + 1] = text
        elif isinstance(result, dict) and "pages" in result:
            for i, page in enumerate(result["pages"]):
                text = page.get("text", str(page)) if isinstance(page, dict) else str(page)
                pages[i + 1] = text
        elif isinstance(result, tuple) and len(result) >= 1:
            text = result[0] if isinstance(result[0], str) else str(result[0])
            pages[1] = text
        _marker_cache[key] = pages
        return pages
    except ImportError:
        raise
    except Exception as e:
        logger.warning(f"Marker failed on {pdf_path}: {e}")
        return {}


def extract_text_docling(pdf_path: Path) -> dict[int, str]:
    try:
        from docling.document_converter import DocumentConverter

        converter = DocumentConverter()
        result = converter.convert(str(pdf_path))
        pages = {}
        if hasattr(result, "document") and hasattr(result.document, "pages"):
            for i, page in enumerate(result.document.pages):
                text = page.text if hasattr(page, "text") else str(page)
                pages[i + 1] = text
        elif hasattr(result, "pages"):
            for i, page in enumerate(result.pages):
                text = page.text if hasattr(page, "text") else str(page)
                pages[i + 1] = text
        else:
            text = result.document.export_to_markdown() if hasattr(result, "document") else str(result)
            pages[1] = text
        return pages
    except ImportError:
        raise
    except Exception as e:
        logger.warning(f"Docling failed on {pdf_path}: {e}")
        return {}


def extract_text(pdf_path: Path, page_num: int, engine: str = "pymupdf") -> str:
    """Extract text from a page. page_num is 1-indexed."""
    if engine == "pymupdf":
        return extract_text_pymupdf(pdf_path, page_num - 1)
    elif engine == "marker":
        try:
            pages = extract_text_marker(pdf_path)
            return pages.get(page_num, extract_text_pymupdf(pdf_path, page_num - 1))
        except ImportError:
            logger.warning("Marker not available, falling back to pymupdf")
            return extract_text_pymupdf(pdf_path, page_num - 1)
    elif engine == "docling":
        try:
            pages = extract_text_docling(pdf_path)
            return pages.get(page_num, extract_text_pymupdf(pdf_path, page_num - 1))
        except ImportError:
            logger.warning("Docling not available, falling back to pymupdf")
            return extract_text_pymupdf(pdf_path, page_num - 1)
    else:
        return extract_text_pymupdf(pdf_path, page_num - 1)
