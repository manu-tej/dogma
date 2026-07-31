"""Compatibility entry point for python -m dogma_service."""

from .cli import main

if __name__ == "__main__":
    raise SystemExit(main())
