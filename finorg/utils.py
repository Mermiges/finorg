import hashlib
import logging
from datetime import datetime
from pathlib import Path
from typing import Any

import orjson
import xxhash
from pathvalidate import sanitize_filename as _sanitize
from rich.logging import RichHandler


def file_hash(path: Path) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as f:
        while True:
            chunk = f.read(65536)
            if not chunk:
                break
            h.update(chunk)
    return h.hexdigest()


def text_hash(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def fast_hash(path: Path) -> str:
    h = xxhash.xxh64()
    with open(path, "rb") as f:
        while True:
            chunk = f.read(65536)
            if not chunk:
                break
            h.update(chunk)
    return h.hexdigest()


def sanitize_filename(name: str, max_length: int = 100) -> str:
    result = _sanitize(name, replacement_text="_")
    result = result.replace(" ", "_")
    result = result.strip(". ")
    return result[:max_length]


def setup_logging(log_dir: Path, verbose: bool) -> logging.Logger:
    logger = logging.getLogger("finorg")
    logger.setLevel(logging.DEBUG)
    logger.handlers.clear()

    console_handler = RichHandler(rich_tracebacks=True)
    console_handler.setLevel(logging.DEBUG if verbose else logging.INFO)
    logger.addHandler(console_handler)

    log_dir.mkdir(parents=True, exist_ok=True)
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    file_handler = logging.FileHandler(log_dir / f"finorg_{timestamp}.log", encoding="utf-8")
    file_handler.setLevel(logging.DEBUG)
    file_handler.setFormatter(logging.Formatter("%(asctime)s %(levelname)s %(name)s: %(message)s"))
    logger.addHandler(file_handler)

    return logger


def load_json(path: Path) -> Any:
    return orjson.loads(path.read_bytes())


def save_json(path: Path, data: Any):
    path.write_bytes(orjson.dumps(data, option=orjson.OPT_INDENT_2))


def load_metadata(working_dir: Path, name: str):
    try:
        return load_json(working_dir / "metadata" / f"{name}.json")
    except FileNotFoundError:
        return None
