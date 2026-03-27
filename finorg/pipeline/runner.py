import logging
import shutil
import time
from pathlib import Path

from rich.console import Console
from rich.panel import Panel

from finorg.config import PipelineConfig
from finorg.utils import setup_logging, load_metadata

console = Console()
logger = logging.getLogger("finorg")


def check_prerequisites(config: PipelineConfig):
    console.print(Panel("[bold]FinOrg \u2014 Prerequisite Check[/bold]", style="blue"))

    pdfs = list(config.source_dir.rglob("*.pdf")) + list(config.source_dir.rglob("*.PDF"))
    mark = "\u2713" if pdfs else "\u2717"
    console.print(f"  {mark} Source PDFs: {len(pdfs)} in {config.source_dir}")

    try:
        config.output_dir.mkdir(parents=True, exist_ok=True)
        console.print(f"  \u2713 Output: {config.output_dir}")
    except Exception as e:
        console.print(f"  \u2717 Output: {e}")

    from finorg.llm_client import OllamaClient
    client = OllamaClient(config.ollama_url)
    if client.is_available():
        models = client.list_models()
        console.print(f"  \u2713 Ollama at {config.ollama_url}")
        for m, label in [(config.fast_model, "Fast"), (config.deep_model, "Deep")]:
            found = any(m in x for x in models)
            mark = "\u2713" if found else "\u2717"
            console.print(f"    {mark} {label}: {m}")
    else:
        console.print(f"  \u2717 Ollama not responding at {config.ollama_url}")

    for pkg, name in [("fitz", "PyMuPDF"), ("PIL", "Pillow"), ("tqdm", "tqdm"),
                      ("rich", "rich"), ("pydantic", "pydantic"), ("orjson", "orjson"),
                      ("click", "click"), ("pathvalidate", "pathvalidate"), ("xxhash", "xxhash")]:
        try:
            __import__(pkg)
            console.print(f"  \u2713 {name}")
        except ImportError:
            console.print(f"  \u2717 {name}")

    for eng, pkg in [("marker", "marker"), ("docling", "docling.document_converter")]:
        try:
            __import__(pkg)
            console.print(f"  \u2713 OCR: {eng}")
        except Exception:
            console.print(f"  \u25cb OCR: {eng} (optional, not installed)")

    if config.parallel:
        from finorg.parallel import detect_gpus, plan_instances
        gpus = detect_gpus()
        if gpus:
            console.print(f"  \u2713 GPUs: {len(gpus)}")
            for g in gpus:
                console.print(f"    GPU {g['index']}: {g['name']} \u2014 {g['total_mb']}MB total, {g['free_mb']}MB free")
            planned = plan_instances(gpus, config.fast_model, config.deep_model)
            for inst in planned:
                console.print(f"    :{inst.port} \u2192 {inst.model} on GPUs {inst.gpu_ids}")
        else:
            console.print("  \u26a0 No GPUs detected via nvidia-smi")

    try:
        total, used, free = shutil.disk_usage(config.output_dir.anchor or "/")
        mark = "\u2713" if free / 1e9 > 10 else "\u26a0"
        console.print(f"  {mark} Disk: {free / 1e9:.1f} GB free")
    except Exception:
        pass


def run_pipeline(config: PipelineConfig, start_phase: int = 1):
    config.ensure_dirs()
    log = setup_logging(config.output_dir / "logs", config.verbose)
    t0 = time.time()

    console.print(Panel(
        f"[bold]FinOrg \u2014 Financial Document Organizer[/bold]\n"
        f"Source: {config.source_dir}\nOutput: {config.output_dir}\n"
        f"Models: {config.fast_model} / {config.deep_model}\n"
        f"Parallel: {config.parallel}", style="green"))

    ollama_instances = []
    fast_pool = None
    deep_pool = None

    if config.parallel:
        from finorg.parallel import (
            detect_gpus, plan_instances, start_ollama_instance,
            preload_model, stop_ollama_instance, ParallelLLMPool, OllamaInstance,
        )
        try:
            console.print(Panel("Setting up GPU instances...", style="yellow"))
            gpus = detect_gpus()
            if gpus:
                for g in gpus:
                    console.print(f"  GPU {g['index']}: {g['name']} ({g['free_mb']}MB free)")
                if config.gpu_ids_fast or config.gpu_ids_deep:
                    planned = []
                    if config.gpu_ids_fast:
                        planned.append(OllamaInstance(port=11434, gpu_ids=config.gpu_ids_fast, model=config.fast_model))
                    if config.gpu_ids_deep:
                        planned.append(OllamaInstance(port=11435, gpu_ids=config.gpu_ids_deep, model=config.deep_model))
                else:
                    planned = plan_instances(gpus, config.fast_model, config.deep_model)
                for inst in planned:
                    console.print(f"  Starting :{inst.port} ({inst.model} on GPUs {inst.gpu_ids})...")
                    if start_ollama_instance(inst):
                        console.print(f"    Loading {inst.model}...")
                        if preload_model(inst):
                            ollama_instances.append(inst)
                            console.print("    [green]Ready[/green]")
                        else:
                            console.print("    [red]Model load failed[/red]")
                    else:
                        console.print("    [red]Instance failed[/red]")
                fast_insts = [i for i in ollama_instances if i.model == config.fast_model]
                deep_insts = [i for i in ollama_instances if i.model == config.deep_model]
                if fast_insts:
                    fast_pool = ParallelLLMPool(fast_insts, config.llm_workers_per_instance)
                if deep_insts:
                    deep_pool = ParallelLLMPool(deep_insts, config.llm_workers_per_instance)
                console.print(f"  [green]{len(fast_insts)} fast + {len(deep_insts)} deep instances[/green]")
            else:
                console.print("  [yellow]No GPUs detected[/yellow]")
        except Exception as e:
            console.print(f"  [red]Parallel setup failed: {e}[/red]")
            log.exception("Parallel setup failed")

    try:
        if start_phase <= 1:
            console.print(Panel("Phase 1/9: Inventory", style="cyan"))
            t = time.time()
            from finorg.pipeline.inventory import run_inventory
            inventory = run_inventory(config, log)
            console.print(f"  {len(inventory)} PDFs \u2014 {time.time() - t:.1f}s")
        else:
            inventory = load_metadata(config.working_dir, "pdf_inventory") or []

        if start_phase <= 2:
            console.print(Panel("Phase 2/9: Text Extraction", style="cyan"))
            t = time.time()
            from finorg.pipeline.extract import run_extraction
            page_index = run_extraction(config, inventory, log)
            console.print(f"  {len(page_index)} pages \u2014 {time.time() - t:.1f}s")
        else:
            page_index = load_metadata(config.working_dir, "page_index") or []

        if start_phase <= 3:
            console.print(Panel("Phase 3/9: Boundary Detection", style="cyan"))
            t = time.time()
            from finorg.pipeline.boundaries import run_boundary_detection
            classifications = run_boundary_detection(config, page_index, log, parallel_pool=fast_pool)
            console.print(f"  {len(classifications)} pages \u2014 {time.time() - t:.1f}s")
        else:
            classifications = load_metadata(config.working_dir, "page_classifications") or []

        if start_phase <= 4:
            console.print(Panel("Phase 4/9: Grouping", style="cyan"))
            t = time.time()
            from finorg.pipeline.grouping import run_grouping
            doc_groups = run_grouping(config, classifications, log)
            console.print(f"  {len(doc_groups)} documents \u2014 {time.time() - t:.1f}s")
        else:
            doc_groups = load_metadata(config.working_dir, "document_groups") or []

        if start_phase <= 5:
            console.print(Panel("Phase 5/9: Splitting", style="cyan"))
            t = time.time()
            from finorg.pipeline.split import run_split
            doc_groups = run_split(config, doc_groups, log)
            console.print(f"  {len(doc_groups)} PDFs \u2014 {time.time() - t:.1f}s")

        if start_phase <= 6:
            console.print(Panel("Phase 6/9: Classification", style="yellow"))
            t = time.time()
            from finorg.pipeline.classify import run_classification
            doc_groups = run_classification(config, doc_groups, log, parallel_pool=deep_pool)
            console.print(f"  Done \u2014 {time.time() - t:.1f}s")

        if start_phase <= 7:
            console.print(Panel("Phase 7/9: Dedup", style="cyan"))
            t = time.time()
            from finorg.pipeline.dedup import run_dedup
            doc_groups = run_dedup(config, doc_groups, log)
            console.print(f"  Done \u2014 {time.time() - t:.1f}s")

        if start_phase <= 8:
            console.print(Panel("Phase 8/9: Organizing", style="cyan"))
            t = time.time()
            from finorg.pipeline.organize import run_organize
            doc_groups = run_organize(config, doc_groups, log)
            console.print(f"  Done \u2014 {time.time() - t:.1f}s")

        if start_phase <= 9:
            console.print(Panel("Phase 9/9: Report", style="cyan"))
            t = time.time()
            from finorg.pipeline.report import run_report
            report_path = run_report(config, doc_groups, log)
            console.print(f"  {report_path} \u2014 {time.time() - t:.1f}s")

        console.print(Panel(
            f"[bold green]\u2713 Complete[/bold green] in {(time.time() - t0) / 60:.1f} min\n"
            f"Output: {config.output_dir}\nReport: {config.output_dir / 'PIPELINE_REPORT.md'}",
            style="bold green"))

    except Exception as e:
        console.print(f"[bold red]Failed: {e}[/bold red]")
        log.exception("Pipeline failed")
        raise
    finally:
        for inst in ollama_instances:
            try:
                from finorg.parallel import stop_ollama_instance
                stop_ollama_instance(inst)
            except Exception:
                pass
