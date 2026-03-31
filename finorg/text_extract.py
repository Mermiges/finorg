import logging
from pathlib import Path

from finorg.pdf_ops import extract_page_text

logger = logging.getLogger("finorg")

_marker_models = None
_marker_converter = None
_marker_cache: dict[str, dict[int, str]] = {}
_docling_cache: dict[str, dict[int, str]] = {}


def _get_marker_converter():
    """Lazy-load marker models once and reuse across calls."""
    global _marker_models, _marker_converter
    if _marker_converter is not None:
        return _marker_converter
    from marker.converters.pdf import PdfConverter
    from marker.models import create_model_dict
    from marker.config.parser import ConfigParser
    _marker_models = create_model_dict()
    # Enable paginate_output so marker inserts page separators we can split on
    config_parser = ConfigParser({"paginate_output": True, "disable_image_extraction": True})
    _marker_converter = PdfConverter(
        artifact_dict=_marker_models,
        config=config_parser.generate_config_dict(),
        processor_list=config_parser.get_processors(),
        renderer=config_parser.get_renderer(),
    )
    return _marker_converter


def extract_text_pymupdf(pdf_path: Path, page_num: int) -> str:
    """Extract text via PyMuPDF. page_num is 0-indexed."""
    return extract_page_text(pdf_path, page_num)


def extract_text_marker(pdf_path: Path) -> dict[int, str]:
    """Convert entire PDF via marker. Returns {1: text, 2: text, ...} (1-indexed).

    Marker processes the whole document at once — there is no per-page API.
    The result is a MarkdownOutput pydantic model with a .markdown attribute
    containing the full converted text. We split on page breaks if present,
    otherwise return the whole text under page 1.
    """
    key = str(pdf_path.resolve())
    if key in _marker_cache:
        return _marker_cache[key]

    try:
        converter = _get_marker_converter()
        rendered = converter(str(pdf_path))

        # rendered is a MarkdownOutput pydantic model
        # Primary attribute: rendered.markdown (str)
        full_text = ""
        if hasattr(rendered, "markdown"):
            full_text = rendered.markdown
        elif hasattr(rendered, "html"):
            full_text = rendered.html
        elif hasattr(rendered, "text"):
            full_text = rendered.text
        else:
            # Fallback: try text_from_rendered helper
            try:
                from marker.output import text_from_rendered
                text, _, _ = text_from_rendered(rendered)
                full_text = text
            except (ImportError, Exception):
                full_text = str(rendered)

        if not full_text:
            _marker_cache[key] = {}
            return _marker_cache[key]

        # With paginate_output=True, marker inserts page separators:
        # "\n\n{PAGE_NUMBER}\n" followed by 48 dashes "------------------------------------------------"
        # Split on this pattern to get per-page text.
        import re
        pages = {}
        page_sep_pattern = re.compile(r'\n\n(\d+)\n-{48}\n')
        parts = page_sep_pattern.split(full_text)

        if len(parts) >= 3:
            # parts = [text_before_first_sep, page_num, text, page_num, text, ...]
            # First chunk (before any separator) belongs to page 1
            if parts[0].strip():
                pages[1] = parts[0].strip()
            for i in range(1, len(parts) - 1, 2):
                try:
                    page_no = int(parts[i])
                except (ValueError, IndexError):
                    continue
                text_chunk = parts[i + 1].strip() if i + 1 < len(parts) else ""
                if text_chunk:
                    pages[page_no] = text_chunk
        else:
            # No page separators found — return all text as page 1
            pages[1] = full_text

        _marker_cache[key] = pages
        return _marker_cache[key]
    except ImportError:
        raise
    except Exception as e:
        logger.warning(f"Marker failed on {pdf_path}: {e}")
        return {}


def extract_text_docling(pdf_path: Path) -> dict[int, str]:
    """Convert PDF via docling. Returns {1: text, 2: text, ...} (1-indexed).

    Docling's ConversionResult.document is a DoclingDocument with:
    - .pages: dict[int, PageItem] mapping page numbers to page metadata
    - .iterate_items(page_no=N): yields (item, level) for a specific page
    - .export_to_markdown(): full document as markdown string
    Each TextItem has .text (str) and .prov (list of ProvenanceItem with .page_no).
    """
    key = str(pdf_path.resolve())
    if key in _docling_cache:
        return _docling_cache[key]

    try:
        from docling.document_converter import DocumentConverter

        converter = DocumentConverter()
        conv_result = converter.convert(str(pdf_path))
        doc = conv_result.document

        # Import TextItem for proper type checking (preferred over hasattr)
        try:
            from docling_core.types.doc import TextItem
            has_text_item_type = True
        except ImportError:
            has_text_item_type = False

        pages = {}

        # Method 1: Use iterate_items with page_no filtering (recommended by docs)
        if hasattr(doc, "pages") and doc.pages:
            page_numbers = sorted(doc.pages.keys()) if isinstance(doc.pages, dict) else list(range(1, len(doc.pages) + 1))
            for page_no in page_numbers:
                page_texts = []
                try:
                    for item, _level in doc.iterate_items(page_no=page_no):
                        if has_text_item_type and isinstance(item, TextItem):
                            if item.text:
                                page_texts.append(item.text)
                        elif hasattr(item, "text") and item.text:
                            page_texts.append(item.text)
                except (TypeError, AttributeError):
                    # iterate_items may not support page_no kwarg in older versions
                    pass
                if page_texts:
                    pages[int(page_no)] = "\n".join(page_texts)

        # Method 2: Fallback — iterate all items and filter by provenance page_no
        if not pages:
            try:
                page_parts = {}
                for item, _level in doc.iterate_items():
                    text = ""
                    if has_text_item_type and isinstance(item, TextItem):
                        text = item.text or ""
                    elif hasattr(item, "text") and item.text:
                        text = item.text
                    if not text:
                        continue
                    if hasattr(item, "prov") and item.prov:
                        for prov in item.prov:
                            if hasattr(prov, "page_no") and prov.page_no is not None:
                                pg = int(prov.page_no)
                                page_parts.setdefault(pg, []).append(text)
                                break  # only assign to first provenance page
                pages = {pg: "\n".join(parts) for pg, parts in page_parts.items() if parts}
            except (TypeError, AttributeError):
                pass

        # Method 3: Last resort — full document export as markdown
        if not pages:
            full_text = ""
            if hasattr(doc, "export_to_markdown"):
                full_text = doc.export_to_markdown()
            elif hasattr(doc, "export_to_text"):
                full_text = doc.export_to_text()
            if full_text:
                pages[1] = full_text

        _docling_cache[key] = pages
        return _docling_cache[key]
    except ImportError:
        raise
    except Exception as e:
        logger.warning(f"Docling failed on {pdf_path}: {e}")
        return {}


def extract_text_lightonocr(pdf_path: Path, page_num: int, model_id: str, cache_dir: str | None = None) -> str:
    try:
        from finorg.lighton_ocr import extract_pdf_page_text
    except ImportError:
        raise
    return extract_pdf_page_text(pdf_path, page_num, model_id=model_id, cache_dir=cache_dir)


def extract_text(
    pdf_path: Path,
    page_num: int,
    engine: str = "pymupdf",
    model_id: str = "lightonai/LightOnOCR-2-1B",
    cache_dir: str | None = None,
) -> str:
    """Extract text from a page. page_num is 1-indexed."""
    if engine == "pymupdf":
        return extract_text_pymupdf(pdf_path, page_num - 1)
    elif engine == "lightonocr":
        try:
            return extract_text_lightonocr(pdf_path, page_num, model_id=model_id, cache_dir=cache_dir)
        except ImportError:
            logger.warning("LightOnOCR not available, falling back to pymupdf")
            return extract_text_pymupdf(pdf_path, page_num - 1)
    elif engine == "marker":
        try:
            pages = extract_text_marker(pdf_path)
            if page_num in pages:
                return pages[page_num]
            # Fallback to pymupdf for this page
            return extract_text_pymupdf(pdf_path, page_num - 1)
        except ImportError:
            logger.warning("Marker not available, falling back to pymupdf")
            return extract_text_pymupdf(pdf_path, page_num - 1)
    elif engine == "docling":
        try:
            pages = extract_text_docling(pdf_path)
            if page_num in pages:
                return pages[page_num]
            return extract_text_pymupdf(pdf_path, page_num - 1)
        except ImportError:
            logger.warning("Docling not available, falling back to pymupdf")
            return extract_text_pymupdf(pdf_path, page_num - 1)
    else:
        return extract_text_pymupdf(pdf_path, page_num - 1)
