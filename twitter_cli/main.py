"""Process entrypoint with a dependency-free version fast path."""

from __future__ import annotations

import sys

from . import __version__


def main() -> None:
    if sys.argv[1:] in (["--version"], ["-V"]):
        print(f"twitter, version {__version__}")
        return

    from .cli import cli

    cli()
