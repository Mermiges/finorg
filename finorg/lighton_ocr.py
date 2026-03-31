from __future__ import annotations

import logging
from pathlib import Path

from finorg.pdf_ops import render_page_pil

logger = logging.getLogger("finorg")

_MODEL = None
_PROCESSOR = None
_MODEL_KEY = None


def _resolve_device_dtype(torch):
    if torch.cuda.is_available():
        supports_bf16 = getattr(torch.cuda, "is_bf16_supported", lambda: False)()
        return "cuda", torch.bfloat16 if supports_bf16 else torch.float16
    if getattr(torch.backends, "mps", None) and torch.backends.mps.is_available():
        return "mps", torch.float32
    return "cpu", torch.float32


def _get_model(model_id: str, cache_dir: str | None = None):
    global _MODEL, _PROCESSOR, _MODEL_KEY
    key = (model_id, cache_dir or "")
    if _MODEL is not None and _PROCESSOR is not None and _MODEL_KEY == key:
        return _MODEL, _PROCESSOR

    import torch
    from transformers import LightOnOcrForConditionalGeneration, LightOnOcrProcessor

    device, dtype = _resolve_device_dtype(torch)
    model = LightOnOcrForConditionalGeneration.from_pretrained(
        model_id,
        torch_dtype=dtype,
        cache_dir=cache_dir,
    ).to(device)
    processor = LightOnOcrProcessor.from_pretrained(model_id, cache_dir=cache_dir)

    _MODEL = model
    _PROCESSOR = processor
    _MODEL_KEY = key
    logger.info(f"Loaded {model_id} for OCR on {device} ({dtype})")
    return _MODEL, _PROCESSOR


def extract_pdf_page_text(
    pdf_path: Path,
    page_num: int,
    model_id: str = "lightonai/LightOnOCR-2-1B",
    cache_dir: str | None = None,
) -> str:
    import torch

    model, processor = _get_model(model_id=model_id, cache_dir=cache_dir)
    image = render_page_pil(pdf_path, page_num - 1, dpi=200, longest_dimension=1540)
    messages = [
        {
            "role": "user",
            "content": [
                {"type": "image", "image": image},
                {
                    "type": "text",
                    "text": "Perform OCR on this document page and return only the document text in natural reading order.",
                },
            ],
        }
    ]
    inputs = processor.apply_chat_template(
        messages,
        add_generation_prompt=True,
        tokenize=True,
        return_dict=True,
        return_tensors="pt",
    )

    target_device = getattr(model, "device", None)
    prepared = {}
    for key, value in inputs.items():
        if hasattr(value, "is_floating_point") and value.is_floating_point():
            prepared[key] = value.to(device=target_device, dtype=model.dtype)
        else:
            prepared[key] = value.to(device=target_device)

    input_len = prepared["input_ids"].shape[1]
    with torch.no_grad():
        generated_ids = model.generate(**prepared, max_new_tokens=4096, do_sample=False)
    text = processor.decode(generated_ids[0, input_len:], skip_special_tokens=True)
    return text.strip()
