"""Compatibility wrapper that forwards to the package CLI module."""
from __future__ import annotations

from set_weaver.cli import main


if __name__ == "__main__":
    raise SystemExit(main())
