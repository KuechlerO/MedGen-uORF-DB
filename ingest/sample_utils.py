"""Sample ID helpers for 5ULTRA cohort files."""

from __future__ import annotations

import re
from pathlib import Path

SAMPLE_RE = re.compile(r"\.([^.]+)\.hg38\.5ULTRA\.(tsv|done)$")


def full_sample_name_from_path(path: Path) -> str | None:
    m = SAMPLE_RE.search(path.name)
    if m:
        return m.group(1)
    # fallback: token before first __
    if "__" in path.name:
        return path.name.split("__")[0]
    return None


def sample_id_from_full(full_name: str) -> str:
    """Prefix before -N1 (e.g. 10_0463-N1-DNA1-WGS1 → 10_0463)."""
    if "-N1" in full_name:
        return full_name.split("-N1")[0]
    return full_name
