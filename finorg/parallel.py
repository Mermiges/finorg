import logging
import os
import socket
import subprocess
import time
from concurrent.futures import ProcessPoolExecutor, ThreadPoolExecutor
from dataclasses import dataclass, field
from subprocess import DEVNULL
from typing import Callable, Optional

import requests
from tqdm import tqdm

logger = logging.getLogger("finorg")


def detect_gpus() -> list[dict]:
    try:
        result = subprocess.run(
            ["nvidia-smi", "--query-gpu=index,name,memory.total,memory.free", "--format=csv,noheader,nounits"],
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


def plan_instances(gpus: list[dict], fast_model: str, deep_model: str) -> list[OllamaInstance]:
    if not gpus:
        return [
            OllamaInstance(port=11434, gpu_ids=[], model=fast_model),
            OllamaInstance(port=11435, gpu_ids=[], model=deep_model),
        ]

    big = [g for g in gpus if g["total_mb"] >= 20000]
    small = [g for g in gpus if g["total_mb"] < 20000]

    instances = []

    if big:
        fast_gpu = big[0]
        instances.append(OllamaInstance(port=11434, gpu_ids=[fast_gpu["index"]], model=fast_model))
        remaining = [g for g in gpus if g["index"] != fast_gpu["index"]]
    else:
        fast_gpu = small[0] if small else gpus[0]
        instances.append(OllamaInstance(port=11434, gpu_ids=[fast_gpu["index"]], model=fast_model))
        remaining = [g for g in gpus if g["index"] != fast_gpu["index"]]

    remaining_ids = [g["index"] for g in remaining]
    total_vram = sum(g["total_mb"] for g in remaining)

    if total_vram >= 94000:
        mid = len(remaining_ids) // 2
        group1 = remaining_ids[:mid]
        group2 = remaining_ids[mid:]
        instances.append(OllamaInstance(port=11435, gpu_ids=group1, model=deep_model))
        instances.append(OllamaInstance(port=11436, gpu_ids=group2, model=deep_model))
    elif total_vram >= 47000:
        instances.append(OllamaInstance(port=11435, gpu_ids=remaining_ids, model=deep_model))
    else:
        instances.append(OllamaInstance(port=11435, gpu_ids=remaining_ids, model=deep_model))

    return instances


def is_port_in_use(port: int) -> bool:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        return s.connect_ex(("localhost", port)) == 0


def start_ollama_instance(instance: OllamaInstance, timeout: int = 120) -> bool:
    try:
        r = requests.get(f"{instance.url}/api/tags", timeout=5)
        if r.status_code == 200:
            logger.info(f"Ollama already running on port {instance.port}")
            return True
    except Exception:
        pass

    env = os.environ.copy()
    if instance.gpu_ids:
        env["CUDA_VISIBLE_DEVICES"] = ",".join(str(g) for g in instance.gpu_ids)
    env["OLLAMA_HOST"] = f"0.0.0.0:{instance.port}"
    env["OLLAMA_FLASH_ATTENTION"] = "1"
    env["OLLAMA_NUM_GPU"] = "999"

    kwargs = {}
    if os.name == "nt":
        kwargs["creationflags"] = subprocess.CREATE_NO_WINDOW

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

    elapsed = 0
    while elapsed < timeout:
        time.sleep(2)
        elapsed += 2
        try:
            r = requests.get(f"{instance.url}/api/tags", timeout=5)
            if r.status_code == 200:
                logger.info(f"Ollama started on port {instance.port}")
                return True
        except Exception:
            pass

    logger.error(f"Ollama failed to start on port {instance.port} within {timeout}s")
    return False


def preload_model(instance: OllamaInstance) -> bool:
    try:
        r = requests.post(
            f"{instance.url}/api/generate",
            json={"model": instance.model, "prompt": "hi", "stream": False, "options": {"num_predict": 1}},
            timeout=300,
        )
        return r.status_code == 200
    except Exception as e:
        logger.error(f"Failed to preload {instance.model} on :{instance.port}: {e}")
        return False


def stop_ollama_instance(instance: OllamaInstance):
    if instance.process is None:
        return
    try:
        instance.process.terminate()
        instance.process.wait(timeout=10)
    except subprocess.TimeoutExpired:
        instance.process.kill()
        instance.process.wait(timeout=5)
    except Exception:
        pass


class ParallelLLMPool:
    def __init__(self, instances: list[OllamaInstance], workers_per_instance: int = 2):
        self.total_workers = len(instances) * workers_per_instance
        self._urls = []
        for inst in instances:
            for _ in range(workers_per_instance):
                self._urls.append(inst.url)

    def map(self, func: Callable, items: list, desc: str = "Processing") -> list:
        results = [None] * len(items)
        errors = 0

        def _worker(idx_item):
            idx, item = idx_item
            url = self._urls[idx % len(self._urls)]
            try:
                return idx, func(item, url)
            except Exception as e:
                return idx, {"error": str(e)}

        indexed = list(enumerate(items))
        with ThreadPoolExecutor(max_workers=self.total_workers) as exe:
            for idx, result in tqdm(exe.map(_worker, indexed), total=len(items), desc=desc):
                if isinstance(result, dict) and "error" in result:
                    errors += 1
                results[idx] = result

        if errors:
            logger.warning(f"{desc}: {errors} errors out of {len(items)}")
        return results


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

            for fut in tqdm(futures, total=len(items), desc=desc):
                idx = futures[fut]
                try:
                    results[idx] = fut.result()
                except Exception as e:
                    results[idx] = {"error": str(e)}

        return results
