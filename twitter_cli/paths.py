"""User-scoped filesystem locations."""

from __future__ import annotations

import os
from pathlib import Path


def config_file() -> Path:
    root = Path(os.environ.get("XDG_CONFIG_HOME", Path.home() / ".config"))
    return root / "twitter-cli" / "config.yaml"


def cache_dir() -> Path:
    root = Path(os.environ.get("XDG_CACHE_HOME", Path.home() / ".cache"))
    return root / "twitter-cli"
