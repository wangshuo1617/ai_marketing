"""Load editable prompt templates from the prompts directory."""

from __future__ import annotations

from pathlib import Path
from typing import Any

PROMPTS_DIR = Path(__file__).resolve().parent.parent / "prompts"


def load_prompt(relative_path: str, **variables: Any) -> str:
    template_path = PROMPTS_DIR / relative_path
    template = template_path.read_text(encoding="utf-8")
    safe_variables = {key: str(value) for key, value in variables.items()}
    return template.format(**safe_variables)
