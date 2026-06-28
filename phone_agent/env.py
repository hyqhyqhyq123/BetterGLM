"""Environment file loading helpers."""

from __future__ import annotations

import os
from pathlib import Path


def load_env_file(path: str | os.PathLike[str] = ".env") -> None:
    """Load simple KEY=VALUE pairs from a .env file without overriding env vars."""

    env_path = Path(path)
    if not env_path.exists():
        return

    for line in env_path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue

        key, value = line.split("=", 1)
        key = key.strip()
        value = value.strip().strip('"').strip("'")

        if key:
            os.environ.setdefault(key, value)
