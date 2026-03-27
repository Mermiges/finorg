from pydantic import BaseModel, model_validator
from pathlib import Path
from typing import Optional


class PipelineConfig(BaseModel):
    source_dir: Path
    output_dir: Path
    working_dir: Optional[Path] = None
    fast_model: str = "qwen2.5:14b-instruct-q4_K_M"
    deep_model: str = "qwen2.5:72b-instruct-q4_K_M"
    ollama_url: str = "http://localhost:11434"
    skip_ocr: bool = False
    ocr_engine: str = "pymupdf"
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
            self.working_dir = self.output_dir / ".finorg_work"
        return self

    def ensure_dirs(self):
        for sub in ["page_text", "page_images", "split_pdfs", "metadata"]:
            (self.working_dir / sub).mkdir(parents=True, exist_ok=True)
        for folder in [
            "Bank_Statements",
            "Retirement_Accounts",
            "Brokerage_Statements",
            "TSP_Statements",
            "Credit_Card_Statements",
            "Mortgage_Statements",
            "Uncategorized",
        ]:
            (self.output_dir / folder).mkdir(parents=True, exist_ok=True)
        (self.output_dir / "duplicates").mkdir(parents=True, exist_ok=True)
        (self.output_dir / "logs").mkdir(parents=True, exist_ok=True)
