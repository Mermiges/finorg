from pydantic import BaseModel, model_validator
from pathlib import Path
from typing import Optional

from finorg.routing import CASE_FOLDER_TEMPLATE


class PipelineConfig(BaseModel):
    source_dir: Path
    output_dir: Path
    working_dir: Optional[Path] = None
    fast_model: str = "qwen3.5:35b"
    deep_model: str = "qwen3.5:122b"
    ollama_url: str = "http://localhost:11434"
    skip_ocr: bool = False
    ocr_engine: str = "lightonocr"
    ocr_model: str = "lightonai/LightOnOCR-2-1B"
    ocr_cache_dir: Optional[Path] = None
    confidence_threshold: float = 0.75
    dpi: int = 300
    max_text_chars: int = 10000
    resume: bool = False
    verbose: bool = False
    parallel: bool = True
    llm_workers_per_instance: int = 2
    pdf_workers: int = 4
    gpu_ids_fast: Optional[list[int]] = None
    gpu_ids_deep: Optional[list[int]] = None

    model_config = {"arbitrary_types_allowed": True}

    @model_validator(mode="after")
    def set_working_dir(self):
        if self.working_dir is None:
            self.working_dir = self.output_dir / "!lf" / "work"
        return self

    @property
    def lf_dir(self) -> Path:
        return self.output_dir / "!lf"

    @property
    def reports_dir(self) -> Path:
        return self.lf_dir / "reports"

    @property
    def logs_dir(self) -> Path:
        return self.lf_dir / "logs"

    @property
    def duplicates_dir(self) -> Path:
        return self.lf_dir / "duplicates"

    def ensure_dirs(self):
        for sub in ["page_text", "page_images", "split_pdfs", "metadata"]:
            (self.working_dir / sub).mkdir(parents=True, exist_ok=True)
        for relative in CASE_FOLDER_TEMPLATE:
            (self.output_dir / Path(relative)).mkdir(parents=True, exist_ok=True)
