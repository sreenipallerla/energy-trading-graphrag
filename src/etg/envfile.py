"""Tiny .env loader (no extra dependency). Existing environment variables win over the file."""
from __future__ import annotations

import os
from pathlib import Path


def load_env(path: Path | None = None) -> list[str]:
    """Read KEY=VALUE lines from .env (project root by default). Returns the names it set."""
    path = path or Path(__file__).resolve().parents[2] / ".env"
    if not path.is_file():
        return []
    set_names = []
    for raw in path.read_text(encoding="utf-8").splitlines():
        line = raw.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        if line.startswith("export "):
            line = line[len("export "):].lstrip()
        key, _, value = line.partition("=")
        key, value = key.strip(), value.strip()
        if len(value) >= 2 and value[0] == value[-1] and value[0] in "\"'":
            value = value[1:-1]
        if key and key not in os.environ:
            os.environ[key] = value
            set_names.append(key)
    return set_names
