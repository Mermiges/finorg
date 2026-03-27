import json
import logging

import requests

logger = logging.getLogger("finorg")


class OllamaClient:
    def __init__(self, base_url: str = "http://localhost:11434"):
        self.base_url = base_url.rstrip("/")

    def is_available(self) -> bool:
        try:
            r = requests.get(f"{self.base_url}/api/tags", timeout=5)
            return r.status_code == 200
        except Exception:
            return False

    def list_models(self) -> list[str]:
        try:
            r = requests.get(f"{self.base_url}/api/tags", timeout=10)
            return [m["name"] for m in r.json().get("models", [])]
        except Exception:
            return []

    def check_model_loaded(self, model: str) -> bool:
        return any(model in m for m in self.list_models())

    def generate_json(self, model, system, prompt, temperature=0.1, max_retries=2) -> dict:
        return self._do_generate(self.base_url, model, system, prompt, temperature, max_retries)

    def generate_json_at(self, url, model, system, prompt, temperature=0.1, max_retries=2) -> dict:
        return self._do_generate(url.rstrip("/"), model, system, prompt, temperature, max_retries)

    def _do_generate(self, base, model, system, prompt, temperature, max_retries) -> dict:
        raw = ""
        for attempt in range(max_retries + 1):
            try:
                r = requests.post(
                    f"{base}/api/generate",
                    json={
                        "model": model,
                        "system": system,
                        "prompt": prompt,
                        "stream": False,
                        "format": "json",
                        "options": {"temperature": temperature, "num_predict": 2048},
                    },
                    timeout=600,
                )
                raw = r.json().get("response", "")
                return json.loads(raw)
            except json.JSONDecodeError:
                if attempt < max_retries:
                    logger.warning(f"JSON parse fail (attempt {attempt + 1}), retrying")
                    continue
                return {"error": "parse_failed", "raw": raw[:500]}
            except Exception as e:
                if attempt < max_retries:
                    continue
                return {"error": str(e)}
