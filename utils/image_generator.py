"""Image generation support for article typesetting."""

from __future__ import annotations

import base64
import io
import json
import logging
import os
import re
from datetime import datetime
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import requests

import config

logger = logging.getLogger("service.image_generator")

_IMAGE_SIZES = [
    "1024x1024",
    "1536x1024",
    "1024x1536",
    "2048x2048",
    "2048x1152",
    "1152x2048",
    "3072x1024",
    "1024x3072",
]


@dataclass
class GeneratedImage:
    local_path: str
    public_url: str
    prompt: str
    alt_text: str


def _build_images_url(base_url: str) -> str:
    base = (base_url or "").rstrip("/")
    for suffix in ("/chat/completions", "/responses", "/images/generations"):
        if base.endswith(suffix):
            base = base[: -len(suffix)]
    if base.endswith("/v1") or base.endswith("/api/v1"):
        return f"{base}/images/generations"
    return f"{base}/v1/images/generations"


def _extract_b64(response_data: dict[str, Any]) -> str:
    data = response_data.get("data")
    if not isinstance(data, list) or not data:
        raise RuntimeError(f"Unexpected image response: {response_data}")

    first = data[0]
    if isinstance(first, dict):
        b64_json = first.get("b64_json")
        if isinstance(b64_json, str) and b64_json:
            return b64_json

        url = first.get("url")
        if isinstance(url, str) and url.startswith("data:image") and "," in url:
            return url.split(",", 1)[1]

    raise RuntimeError(f"Image response missing data[0].b64_json: {response_data}")


def _safe_slug(text: str, fallback: str = "image") -> str:
    slug = re.sub(r"[^0-9A-Za-z_-]+", "-", text).strip("-")
    return (slug or fallback)[:48]


def _image_bytes_from_b64(encoded: str) -> bytes:
    return base64.b64decode(encoded)


def _extension_from_format(output_format: str) -> str:
    value = output_format.lower().strip().lstrip(".")
    return value if value in {"png", "jpg", "jpeg", "webp"} else "png"


def _sanitize_log(obj: Any) -> Any:
    if isinstance(obj, dict):
        return {key: _sanitize_log(value) for key, value in obj.items()}
    if isinstance(obj, list):
        return [_sanitize_log(item) for item in obj]
    if isinstance(obj, str) and len(obj) > 500 and " " not in obj and "\n" not in obj:
        return f"[base64,{len(obj)}chars]"
    return obj


def generate_image_file(
    *,
    prompt: str,
    draft_id: int,
    image_index: int,
    alt_text: str,
    size: str | None = None,
    run_id: str | None = None,
) -> GeneratedImage:
    if not config.IMAGE_GEN_API_KEY:
        raise RuntimeError("IMAGE_GEN_API_KEY 未配置，无法生成图片")

    chosen_size = size or config.IMAGE_GEN_DEFAULT_SIZE
    if chosen_size not in _IMAGE_SIZES:
        chosen_size = config.IMAGE_GEN_DEFAULT_SIZE if config.IMAGE_GEN_DEFAULT_SIZE in _IMAGE_SIZES else "1536x1024"

    payload: dict[str, Any] = {
        "model": config.IMAGE_GEN_MODEL.strip() or "gpt-image-2-client",
        "prompt": prompt,
        "size": chosen_size,
        "quality": config.IMAGE_GEN_QUALITY,
        "moderation": config.IMAGE_GEN_MODERATION,
        "output_format": config.IMAGE_GEN_OUTPUT_FORMAT,
    }
    headers = {
        "Authorization": f"Bearer {config.IMAGE_GEN_API_KEY}",
        "Content-Type": "application/json",
    }
    proxy = os.getenv("IMAGE_GEN_PROXY") or os.getenv("HTTPS_PROXY") or None
    proxies = {"http": proxy, "https": proxy} if proxy else None
    url = _build_images_url(config.IMAGE_GEN_BASE_URL)

    logger.info("[image-gen] POST %s model=%s size=%s", url, payload["model"], chosen_size)
    logger.debug("[image-gen] request: %s", json.dumps(_sanitize_log(payload), ensure_ascii=False))
    response = requests.post(url, json=payload, headers=headers, timeout=600, proxies=proxies)
    response.raise_for_status()

    response_data = response.json()
    logger.debug("[image-gen] response: %s", json.dumps(_sanitize_log(response_data), ensure_ascii=False))
    image_bytes = _image_bytes_from_b64(_extract_b64(response_data))

    output_dir = Path(config.IMAGE_GEN_OUTPUT_DIR) / f"draft_{draft_id}"
    output_dir.mkdir(parents=True, exist_ok=True)
    extension = _extension_from_format(config.IMAGE_GEN_OUTPUT_FORMAT)
    run_suffix = _safe_slug(run_id or datetime.now().strftime("%Y%m%d_%H%M%S_%f"), "run")
    filename = f"{run_suffix}_{image_index:02d}_{_safe_slug(alt_text)}.{extension}"
    file_path = output_dir / filename
    file_path.write_bytes(image_bytes)

    public_url = f"/static/generated_images/draft_{draft_id}/{filename}"
    return GeneratedImage(
        local_path=str(file_path).replace("\\", "/"),
        public_url=public_url,
        prompt=prompt,
        alt_text=alt_text,
    )
