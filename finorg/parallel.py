import logging
import os
import signal
import socket
import subprocess
import sys
import time
from concurrent.futures import ProcessPoolExecutor, ThreadPoolExecutor, as_completed
from dataclasses import dataclass, field
from subprocess import DEVNULL
from typing import Callable, Optional

import requests
from tqdm import tqdm

logger = logging.getLogger("finorg")

# VRAM requirements (MB) for common models — used in planning
MODEL_VRAM_ESTIMATES = {
    "72b": 50000,   # ~50GB for q4_K_M + KV cache at moderate context
    "14b": 12000,   # ~12GB for q4_K_M + KV cache
}

# Reserved VRAM per GPU for OS/display/other processes (bytes)
DEFAULT_GPU_OVERHEAD_BYTES = 500 * 1024 * 1024  # 500 MiB


def detect_gpus() -> list[dict]:
    """Detect NVIDIA GPUs via nvidia-smi. Returns list of GPU info dicts."""
    try:
        result = subprocess.run(
            ["nvidia-smi", "--query-gpu=index,name,memory.total,memory.free",
             "--format=csv,noheader,nounits"],
            capture_output=True,
            text=True,
            timeout=10,
        )
        gpus = []
        for line in result.stdout.strip().split("\n"):
            if not line.strip():
                continue
            parts = [p.strip() for p in line.split(",")]
            if len(parts) >= 4:
                gpus.append({
                    "index": int(parts[0]),
                    "name": parts[1],
                    "total_mb": int(parts[2]),
                    "free_mb": int(parts[3]),
                })
        return gpus
    except Exception:
        return []


@dataclass
class OllamaInstance:
    port: int
    gpu_ids: list[int]
    model: str
    url: str = ""
    process: Optional[subprocess.Popen] = field(default=None, repr=False)

    def __post_init__(self):
        if not self.url:
            self.url = f"http://localhost:{self.port}"


def _estimate_model_vram(model_name: str) -> int:
    """Estimate VRAM needed (MB) based on model name heuristics."""
    name_lower = model_name.lower()
    for key, vram in MODEL_VRAM_ESTIMATES.items():
        if key in name_lower:
            return vram
    # Default conservative estimate
    return 16000


def plan_instances(gpus: list[dict], fast_model: str, deep_model: str) -> list[OllamaInstance]:
    """Plan Ollama instances based on available GPUs and model VRAM requirements.

    Strategy:
    - Assign smallest sufficient GPU(s) to 14B fast model
    - Assign remaining GPUs to 72B deep model
    - If enough remaining VRAM for two deep instances, split for parallelism
    """
    if not gpus:
        return [
            OllamaInstance(port=11434, gpu_ids=[], model=fast_model),
            OllamaInstance(port=11435, gpu_ids=[], model=deep_model),
        ]

    # Sort GPUs by free VRAM descending for better allocation
    sorted_gpus = sorted(gpus, key=lambda g: g["free_mb"], reverse=True)
    fast_vram_needed = _estimate_model_vram(fast_model)
    deep_vram_needed = _estimate_model_vram(deep_model)

    instances = []

    # Find smallest GPU that fits the fast model
    fast_gpu = None
    for g in reversed(sorted_gpus):  # Start from smallest
        if g["free_mb"] >= fast_vram_needed:
            fast_gpu = g
            break
    if fast_gpu is None:
        fast_gpu = sorted_gpus[-1]  # Use smallest GPU anyway

    instances.append(OllamaInstance(
        port=11434, gpu_ids=[fast_gpu["index"]], model=fast_model))

    remaining = [g for g in sorted_gpus if g["index"] != fast_gpu["index"]]
    remaining_ids = [g["index"] for g in remaining]
    total_remaining_vram = sum(g["free_mb"] for g in remaining)

    if not remaining:
        # All GPUs used for fast model; deep model shares or uses CPU
        instances.append(OllamaInstance(
            port=11435, gpu_ids=[], model=deep_model))
    elif total_remaining_vram >= deep_vram_needed * 2:
        # Enough VRAM for two deep instances — split for parallelism
        mid = len(remaining_ids) // 2
        group1 = remaining_ids[:mid]
        group2 = remaining_ids[mid:]
        instances.append(OllamaInstance(
            port=11435, gpu_ids=group1, model=deep_model))
        instances.append(OllamaInstance(
            port=11436, gpu_ids=group2, model=deep_model))
    else:
        # Single deep instance across all remaining GPUs
        instances.append(OllamaInstance(
            port=11435, gpu_ids=remaining_ids, model=deep_model))

    return instances


def is_port_in_use(port: int) -> bool:
    """Check if a TCP port is already in use."""
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        return s.connect_ex(("localhost", port)) == 0


def _check_instance_alive(url: str, timeout: int = 5) -> bool:
    """Quick liveness check via /api/version (lightest endpoint)."""
    try:
        r = requests.get(f"{url}/api/version", timeout=timeout)
        return r.status_code == 200
    except Exception:
        return False


def _check_model_loaded(url: str, model: str, timeout: int = 5) -> bool:
    """Check if a specific model is currently loaded via /api/ps."""
    try:
        r = requests.get(f"{url}/api/ps", timeout=timeout)
        if r.status_code == 200:
            data = r.json()
            models = data.get("models", [])
            return any(model in m.get("name", "") for m in models)
    except Exception:
        pass
    return False


def start_ollama_instance(instance: OllamaInstance, timeout: int = 120,
                          num_parallel: int = 1, keep_alive: str = "-1") -> bool:
    """Start an Ollama serve process for the given instance.

    Args:
        instance: OllamaInstance to start
        timeout: Max seconds to wait for server readiness
        num_parallel: Concurrent requests per loaded model (OLLAMA_NUM_PARALLEL)
        keep_alive: How long models stay loaded after last request (OLLAMA_KEEP_ALIVE)
                    Use "-1" for indefinite (best for batch processing)
    """
    # Check if already running on this port
    if _check_instance_alive(instance.url):
        logger.info(f"Ollama already running on port {instance.port}")
        return True

    env = os.environ.copy()

    # GPU assignment — CUDA_VISIBLE_DEVICES makes GPUs appear as 0,1,2... internally
    if instance.gpu_ids:
        env["CUDA_VISIBLE_DEVICES"] = ",".join(str(g) for g in instance.gpu_ids)

    # Core instance settings
    env["OLLAMA_HOST"] = f"0.0.0.0:{instance.port}"
    env["OLLAMA_FLASH_ATTENTION"] = "1"

    # Force all layers to GPU(s) — Ollama auto-offloads to CPU if VRAM insufficient
    env["OLLAMA_NUM_GPU"] = "999"

    # Concurrent request handling — share KV cache across parallel requests
    env["OLLAMA_NUM_PARALLEL"] = str(num_parallel)

    # Keep models loaded indefinitely during batch processing
    env["OLLAMA_KEEP_ALIVE"] = keep_alive

    # Only load one model per instance (we dedicate instances to specific models)
    env["OLLAMA_MAX_LOADED_MODELS"] = "1"

    # Reserve VRAM for OS/display overhead to prevent OOM
    env["OLLAMA_GPU_OVERHEAD"] = str(DEFAULT_GPU_OVERHEAD_BYTES)

    # For multi-GPU: spread layers across all GPUs evenly (better than packing
    # when all GPUs are dedicated to this instance)
    if instance.gpu_ids and len(instance.gpu_ids) > 1:
        env["OLLAMA_SCHED_SPREAD"] = "true"

    # Use quantized KV cache to reduce VRAM usage (requires flash attention)
    env["OLLAMA_KV_CACHE_TYPE"] = "q8_0"

    # Platform-specific subprocess flags
    kwargs = {}
    if sys.platform == "win32":
        kwargs["creationflags"] = subprocess.CREATE_NO_WINDOW
    else:
        # Prevent child from receiving parent's signals (SIGINT etc.)
        kwargs["start_new_session"] = True

    try:
        instance.process = subprocess.Popen(
            ["ollama", "serve"],
            env=env,
            stdout=DEVNULL,
            stderr=DEVNULL,
            **kwargs,
        )
    except FileNotFoundError:
        logger.error("ollama not found in PATH")
        return False

    # Poll for readiness with increasing intervals
    elapsed = 0
    poll_interval = 1
    while elapsed < timeout:
        time.sleep(poll_interval)
        elapsed += poll_interval
        # Check if process died
        if instance.process.poll() is not None:
            logger.error(f"Ollama process exited with code {instance.process.returncode} "
                         f"on port {instance.port}")
            return False
        if _check_instance_alive(instance.url):
            logger.info(f"Ollama started on port {instance.port} "
                        f"(GPUs: {instance.gpu_ids}, {elapsed}s)")
            return True
        # Increase poll interval up to 5s
        poll_interval = min(poll_interval + 1, 5)

    logger.error(f"Ollama failed to start on port {instance.port} within {timeout}s")
    stop_ollama_instance(instance)
    return False


def preload_model(instance: OllamaInstance, timeout: int = 600) -> bool:
    """Preload model into GPU memory. Uses empty prompt to trigger load only.

    The timeout is generous (10 min default) because loading a 72B model
    from disk to multiple GPUs can take 1-3 minutes.
    """
    try:
        # Send empty prompt — Ollama loads the model without generating
        r = requests.post(
            f"{instance.url}/api/generate",
            json={
                "model": instance.model,
                "prompt": "",
                "stream": False,
                "keep_alive": "-1",  # Keep loaded indefinitely
            },
            timeout=timeout,
        )
        if r.status_code != 200:
            logger.error(f"Preload returned {r.status_code} for {instance.model} "
                         f"on :{instance.port}")
            return False

        # Verify model is actually loaded via /api/ps
        time.sleep(1)
        if _check_model_loaded(instance.url, instance.model):
            logger.info(f"Model {instance.model} loaded on :{instance.port}")
            return True

        # Model may still be loading; the generate call succeeded so trust it
        logger.info(f"Model {instance.model} preload completed on :{instance.port}")
        return True
    except requests.Timeout:
        logger.error(f"Preload timed out ({timeout}s) for {instance.model} "
                     f"on :{instance.port}")
        return False
    except Exception as e:
        logger.error(f"Failed to preload {instance.model} on :{instance.port}: {e}")
        return False


def stop_ollama_instance(instance: OllamaInstance):
    """Gracefully stop an Ollama instance. SIGTERM first, SIGKILL as fallback."""
    if instance.process is None:
        return
    try:
        instance.process.terminate()  # SIGTERM on Linux, TerminateProcess on Windows
        instance.process.wait(timeout=15)
        logger.info(f"Ollama on :{instance.port} stopped gracefully")
    except subprocess.TimeoutExpired:
        logger.warning(f"Ollama on :{instance.port} didn't stop gracefully, killing")
        instance.process.kill()  # SIGKILL
        try:
            instance.process.wait(timeout=5)
        except subprocess.TimeoutExpired:
            pass
    except Exception:
        pass
    finally:
        instance.process = None


def cleanup_orphan_ollama(ports: list[int] = None):
    """Kill any orphaned ollama processes on specified ports.

    Useful for cleanup after crashes where stop_ollama_instance wasn't called.
    """
    if sys.platform == "win32":
        return  # Not implemented for Windows

    for port in (ports or []):
        try:
            result = subprocess.run(
                ["lsof", "-ti", f":{port}"],
                capture_output=True, text=True, timeout=5,
            )
            pids = result.stdout.strip().split()
            for pid in pids:
                if pid.isdigit():
                    try:
                        os.kill(int(pid), signal.SIGTERM)
                        logger.info(f"Killed orphan process {pid} on port {port}")
                    except ProcessLookupError:
                        pass
        except Exception:
            pass


def health_check_all(instances: list[OllamaInstance]) -> dict:
    """Check health of all instances. Returns {port: {"alive": bool, "model_loaded": bool}}."""
    status = {}
    for inst in instances:
        alive = _check_instance_alive(inst.url)
        loaded = _check_model_loaded(inst.url, inst.model) if alive else False
        status[inst.port] = {"alive": alive, "model_loaded": loaded}
    return status


class ParallelLLMPool:
    """Thread pool for distributing LLM requests across multiple Ollama instances.

    Uses round-robin distribution with retry logic for failed requests.
    """

    def __init__(self, instances: list[OllamaInstance], workers_per_instance: int = 2):
        self.instances = instances
        self.total_workers = len(instances) * workers_per_instance
        self._urls = []
        for inst in instances:
            for _ in range(workers_per_instance):
                self._urls.append(inst.url)

    def map(self, func: Callable, items: list, desc: str = "Processing",
            max_retries: int = 1) -> list:
        """Map func(item, url) across items using round-robin URL assignment.

        Args:
            func: Callable(item, url) -> result
            items: List of items to process
            desc: Progress bar description
            max_retries: Number of retries on failure (with different URL)
        """
        results = [None] * len(items)
        errors = 0

        def _worker(idx_item):
            idx, item = idx_item
            url = self._urls[idx % len(self._urls)]
            last_error = None
            for attempt in range(max_retries + 1):
                try:
                    return idx, func(item, url)
                except Exception as e:
                    last_error = e
                    # On retry, try a different URL
                    if attempt < max_retries and len(self._urls) > 1:
                        url = self._urls[(idx + attempt + 1) % len(self._urls)]
                        time.sleep(1)
            return idx, {"error": str(last_error)}

        indexed = list(enumerate(items))
        with ThreadPoolExecutor(max_workers=self.total_workers) as exe:
            futures = {exe.submit(_worker, item): item for item in indexed}
            for future in tqdm(as_completed(futures), total=len(items), desc=desc):
                idx, result = future.result()
                if isinstance(result, dict) and "error" in result:
                    errors += 1
                results[idx] = result

        if errors:
            logger.warning(f"{desc}: {errors} errors out of {len(items)}")
        return results

    def check_health(self) -> bool:
        """Check if all backing instances are alive and have models loaded."""
        for inst in self.instances:
            if not _check_instance_alive(inst.url):
                return False
            if not _check_model_loaded(inst.url, inst.model):
                return False
        return True


class ParallelPDFPool:
    def __init__(self, max_workers: int = 4):
        self.max_workers = max_workers

    def map(self, func: Callable, items: list, desc: str = "Processing") -> list:
        results = [None] * len(items)

        with ProcessPoolExecutor(max_workers=self.max_workers) as exe:
            futures = {}
            for idx, item in enumerate(items):
                fut = exe.submit(func, item)
                futures[fut] = idx

            for fut in tqdm(as_completed(futures), total=len(items), desc=desc):
                idx = futures[fut]
                try:
                    results[idx] = fut.result()
                except Exception as e:
                    results[idx] = {"error": str(e)}

        return results
