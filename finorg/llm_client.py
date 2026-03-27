import json
import logging
import time

import requests
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry

logger = logging.getLogger("finorg")

# Connection pool settings — reuse TCP connections across requests
_SESSION_POOL_SIZE = 10
_SESSION_RETRIES = Retry(
    total=0,  # We handle retries ourselves at the application level
    backoff_factor=0,
)


def _make_session(pool_size: int = _SESSION_POOL_SIZE) -> requests.Session:
    """Create a requests session with connection pooling."""
    session = requests.Session()
    adapter = HTTPAdapter(
        pool_connections=pool_size,
        pool_maxsize=pool_size,
        max_retries=_SESSION_RETRIES,
    )
    session.mount("http://", adapter)
    session.mount("https://", adapter)
    return session


class OllamaClient:
    def __init__(self, base_url: str = "http://localhost:11434"):
        self.base_url = base_url.rstrip("/")
        self._session = _make_session()

    def is_available(self) -> bool:
        """Check if Ollama server is responding."""
        try:
            r = self._session.get(f"{self.base_url}/api/version", timeout=5)
            return r.status_code == 200
        except Exception:
            return False

    def list_models(self) -> list[str]:
        """List all locally available model names."""
        try:
            r = self._session.get(f"{self.base_url}/api/tags", timeout=10)
            return [m["name"] for m in r.json().get("models", [])]
        except Exception:
            return []

    def list_running_models(self) -> list[dict]:
        """List currently loaded/running models via /api/ps."""
        try:
            r = self._session.get(f"{self.base_url}/api/ps", timeout=10)
            return r.json().get("models", [])
        except Exception:
            return []

    def check_model_loaded(self, model: str) -> bool:
        """Check if a specific model is currently loaded in memory."""
        running = self.list_running_models()
        return any(model in m.get("name", "") for m in running)

    def generate_json(self, model, system, prompt, temperature=0.1,
                      num_predict=2048, json_schema=None, max_retries=2) -> dict:
        return self._do_generate(self.base_url, model, system, prompt,
                                 temperature, num_predict, json_schema, max_retries)

    def generate_json_at(self, url, model, system, prompt, temperature=0.1,
                         num_predict=2048, json_schema=None, max_retries=2) -> dict:
        return self._do_generate(url.rstrip("/"), model, system, prompt,
                                 temperature, num_predict, json_schema, max_retries)

    def _do_generate(self, base, model, system, prompt, temperature,
                     num_predict, json_schema, max_retries) -> dict:
        """Execute a generate request with structured JSON output.

        Uses schema-based constrained decoding (Ollama v0.5+) when json_schema
        is provided, otherwise falls back to plain JSON mode.

        Retries with exponential backoff on transient failures.
        """
        # Use schema-based format if provided (Ollama v0.5+), else plain "json"
        fmt = json_schema if json_schema else "json"

        raw = ""
        for attempt in range(max_retries + 1):
            try:
                r = self._session.post(
                    f"{base}/api/generate",
                    json={
                        "model": model,
                        "system": system,
                        "prompt": prompt,
                        "stream": False,
                        "format": fmt,
                        "keep_alive": "-1",  # Keep model loaded for batch processing
                        "options": {
                            "temperature": temperature,
                            "num_predict": num_predict,
                            "top_p": 0.8,
                            "top_k": 20,
                            "repeat_penalty": 1.05,
                            # Explicit stop tokens for Qwen 2.5 — guards against
                            # known infinite generation bug (ollama/ollama#7166)
                            "stop": [
                                "<|im_end|>",
                                "<|endoftext|>",
                            ],
                        },
                    },
                    timeout=600,
                )

                if r.status_code == 503:
                    # Server busy / max queue exceeded — back off and retry
                    if attempt < max_retries:
                        wait = 2 ** (attempt + 1)
                        logger.warning(f"Ollama busy (503), retrying in {wait}s")
                        time.sleep(wait)
                        continue
                    return {"error": "server_busy"}

                if r.status_code != 200:
                    if attempt < max_retries:
                        wait = 2 ** attempt
                        logger.warning(f"Ollama returned {r.status_code}, "
                                       f"retrying in {wait}s")
                        time.sleep(wait)
                        continue
                    return {"error": f"http_{r.status_code}",
                            "raw": r.text[:500]}

                raw = r.json().get("response", "")
                return json.loads(raw)

            except json.JSONDecodeError:
                if attempt < max_retries:
                    logger.warning(f"JSON parse fail (attempt {attempt + 1}), retrying")
                    continue
                return {"error": "parse_failed", "raw": raw[:500]}

            except requests.ConnectionError:
                if attempt < max_retries:
                    wait = 2 ** (attempt + 1)
                    logger.warning(f"Connection error to {base}, retrying in {wait}s")
                    time.sleep(wait)
                    continue
                return {"error": "connection_failed", "url": base}

            except requests.Timeout:
                if attempt < max_retries:
                    logger.warning(f"Request timed out (attempt {attempt + 1}), retrying")
                    continue
                return {"error": "timeout", "url": base}

            except Exception as e:
                if attempt < max_retries:
                    wait = 2 ** attempt
                    time.sleep(wait)
                    continue
                return {"error": str(e)}
