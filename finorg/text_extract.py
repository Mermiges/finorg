import logging
from pathlib import Path

from finorg.pdf_ops import extract_page_text

logger = logging.getLogger("finorg")

_marker_models = None
_marker_converter = None


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
            return {}

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

        return pages
    except ImportError:
        raise
    except Exception as e:
        logger.warning(f"Marker failed on {pdf_path}: {e}")
        return {}


def extract_text_docling(pdf_path: Path) -> dict[int, str]:
    """Convert PDF via docling. Returns {1: text, 2: text, ...} (1-indexed).

    Docling's ConversionResult has a .document (DoclingDocument) with:
    - .pages: dict mapping page numbers to PageItem
    - .iterate_items(page_no=N): yields items for a specific page
    - .export_to_markdown(): full document as markdown string
    """
    try:
        from docling.document_converter import DocumentConverter

        converter = DocumentConverter()
        conv_result = converter.convert(str(pdf_path))
        doc = conv_result.document

        pages = {}

        # Method 1: Use iterate_items with page_no filtering (most reliable)
        if hasattr(doc, "pages") and doc.pages:
            page_numbers = sorted(doc.pages.keys()) if isinstance(doc.pages, dict) else range(1, len(doc.pages) + 1)
            for page_no in page_numbers:
                page_texts = []
                try:
                    for item, _level in doc.iterate_items(page_no=page_no):
                        if hasattr(item, "text") and item.text:
                            page_texts.append(item.text)
                        elif hasattr(item, "export_to_markdown"):
                            md = item.export_to_markdown()
                            if md:
                                page_texts.append(md)
                except (TypeError, AttributeError):
                    # iterate_items may not support page_no in older versions
                    pass
                if page_texts:
                    pages[int(page_no)] = "\n".join(page_texts)

        # Method 2: Fallback — iterate all items and filter by provenance
        if not pages:
            try:
                for item, _level in doc.iterate_items():
                    if hasattr(item, "prov") and item.prov:
                        for prov in item.prov:
                            if hasattr(prov, "page_no") and prov.page_no:
                                pg = int(prov.page_no)
                                text = ""
                                if hasattr(item, "text") and item.text:
                                    text = item.text
                                elif hasattr(item, "export_to_markdown"):
                                    text = item.export_to_markdown() or ""
                                if text:
                                    pages.setdefault(pg, [])
                                    if isinstance(pages[pg], list):
                                        pages[pg].append(text)
                # Join lists into strings
                for pg in pages:
                    if isinstance(pages[pg], list):
                        pages[pg] = "\n".join(pages[pg])
            except (TypeError, AttributeError):
                pass

        # Method 3: Last resort — full document export
        if not pages:
            full_text = ""
            if hasattr(doc, "export_to_markdown"):
                full_text = doc.export_to_markdown()
            elif hasattr(doc, "export_to_text"):
                full_text = doc.export_to_text()
            else:
                full_text = str(doc)
            if full_text:
                pages[1] = full_text

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
