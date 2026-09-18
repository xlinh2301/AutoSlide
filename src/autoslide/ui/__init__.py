"""UI assets and template serving package for AutoSlide Local Workbench."""

from __future__ import annotations

from pathlib import Path

PACKAGE_DIR = Path(__file__).parent.resolve()
STATIC_DIR = PACKAGE_DIR / "static"
TEMPLATES_DIR = PACKAGE_DIR / "templates"
