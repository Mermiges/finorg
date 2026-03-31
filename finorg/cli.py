import click
from pathlib import Path

from finorg.config import PipelineConfig


@click.command()
@click.argument("source_dir", type=click.Path(exists=True, file_okay=False, path_type=Path))
@click.option("-o", "--output", "output_dir", type=click.Path(path_type=Path), default=None,
              help="Output case root. Default: SOURCE_DIR/organized")
@click.option("--model", "deep_model", default="qwen3.5:122b",
              help="Ollama model for classification")
@click.option("--fast-model", default="qwen3.5:35b",
              help="Ollama model for boundary detection")
@click.option("--ollama-url", default="http://localhost:11434")
@click.option("--skip-ocr", is_flag=True, help="Skip OCR on scanned pages")
@click.option("--ocr-engine", type=click.Choice(["lightonocr", "marker", "docling", "pymupdf"]), default="lightonocr")
@click.option("--ocr-model", default="lightonai/LightOnOCR-2-1B", help="OCR model ID for LightOnOCR runs")
@click.option("--ocr-cache-dir", type=click.Path(path_type=Path), default=None,
              help="Optional Hugging Face cache dir for OCR weights")
@click.option("--confidence", default=0.75, help="Auto-organize confidence threshold")
@click.option("--resume", is_flag=True, help="Resume from last completed phase")
@click.option("-v", "--verbose", is_flag=True)
@click.option("--dry-run", is_flag=True, help="Check prerequisites only")
@click.option("--start-phase", type=int, default=1, help="Start from phase N (1-9)")
@click.option("--no-parallel", is_flag=True, help="Single Ollama instance mode")
@click.option("--llm-workers", default=2, type=int, help="Concurrent LLM requests per Ollama instance")
@click.option("--pdf-workers", default=4, type=int, help="CPU workers for PDF operations")
@click.option("--gpu-fast", default=None, type=str,
              help="Comma-sep GPU IDs for fast model, e.g. '0'")
@click.option("--gpu-deep", default=None, type=str,
              help="Comma-sep GPU IDs for deep model, e.g. '1,2,3,4'")
def main(source_dir, output_dir, deep_model, fast_model, ollama_url, skip_ocr, ocr_engine,
         ocr_model, ocr_cache_dir, confidence, resume, verbose, dry_run, start_phase, no_parallel,
         llm_workers, pdf_workers, gpu_fast, gpu_deep):
    """Organize messy financial PDFs into clean labeled folders.

    SOURCE_DIR is the folder containing disorganized PDFs.
    """
    if output_dir is None:
        output_dir = source_dir / "organized"

    config = PipelineConfig(
        source_dir=source_dir,
        output_dir=output_dir,
        fast_model=fast_model,
        deep_model=deep_model,
        ollama_url=ollama_url,
        skip_ocr=skip_ocr,
        ocr_engine=ocr_engine,
        ocr_model=ocr_model,
        ocr_cache_dir=ocr_cache_dir,
        confidence_threshold=confidence,
        resume=resume,
        verbose=verbose,
        parallel=not no_parallel,
        llm_workers_per_instance=llm_workers,
        pdf_workers=pdf_workers,
        gpu_ids_fast=[int(x) for x in gpu_fast.split(",")] if gpu_fast else None,
        gpu_ids_deep=[int(x) for x in gpu_deep.split(",")] if gpu_deep else None,
    )

    if dry_run:
        from finorg.pipeline.runner import check_prerequisites
        check_prerequisites(config)
        return

    from finorg.pipeline.runner import run_pipeline
    run_pipeline(config, start_phase=start_phase)
