#!/usr/bin/env python3
"""Validate consolidated project documentation completeness and minimum quality."""

from __future__ import annotations

import sys
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[1]
DOCS_FILE = REPO_ROOT / "DOCS.md"

REQUIRED_TOP_LEVEL_HEADINGS = [
    "# Consolidated Project Documentation",
    "## Source Sets",
    "## docs",
    "## Logistics Tracking System",
]

REQUIRED_SOURCE_MARKERS = [
    "#### `docs/requirements/requirements.md`",
    "#### `docs/onboarding/project-orientation.md`",
    "#### `docs/infrastructure/production-hardening-checklist.md`",
    "#### `Logistics Tracking System/requirements/requirements-document.md`",
    "#### `Logistics Tracking System/high-level-design/architecture-diagram.md`",
    "#### `Logistics Tracking System/implementation/implementation-playbook.md`",
]

REQUIRED_CONTENT_HEADINGS = [
    "### Documentation Structure",
    "### Key Features",
    "### Getting Started",
    "### Documentation Status",
    "## What This Template Is",
    "## Bootstrap Workflow",
    "## Before You Rename Anything",
    "## Secrets",
]


def is_empty(path: Path) -> bool:
    return not path.exists() or not path.read_text(encoding="utf-8").strip()


def main() -> int:
    errors: list[str] = []

    if is_empty(DOCS_FILE):
        errors.append("Missing or empty DOCS.md")
    else:
        text = DOCS_FILE.read_text(encoding="utf-8")
        for heading in REQUIRED_TOP_LEVEL_HEADINGS:
            if heading not in text:
                errors.append(f"DOCS.md missing heading: {heading}")
        for marker in REQUIRED_SOURCE_MARKERS:
            if marker not in text:
                errors.append(f"DOCS.md missing source marker: {marker}")
        for heading in REQUIRED_CONTENT_HEADINGS:
            if heading not in text:
                errors.append(f"DOCS.md missing content heading: {heading}")
        if "```mermaid" not in text:
            errors.append("DOCS.md missing Mermaid diagrams")

    if errors:
        print("Documentation validation failed:")
        for error in errors:
            print(f"- {error}")
        return 1

    print("Documentation validation passed.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
