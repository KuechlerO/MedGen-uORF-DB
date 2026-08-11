#!/usr/bin/env python3
"""Run the full MVP ingest pipeline on a 5ULTRA TSV."""

from __future__ import annotations

import argparse
import subprocess
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def run(cmd: list[str]) -> None:
    print("+", " ".join(cmd))
    subprocess.check_call(cmd, cwd=ROOT)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "tsv",
        type=Path,
        nargs="?",
        default=ROOT / "example.tsv",
        help="5ULTRA TSV (default: example.tsv)",
    )
    parser.add_argument(
        "-o",
        "--out-dir",
        type=Path,
        default=ROOT / "data" / "tracks",
    )
    args = parser.parse_args()
    tsv = args.tsv if args.tsv.is_absolute() else ROOT / args.tsv
    out = args.out_dir if args.out_dir.is_absolute() else ROOT / args.out_dir

    py = sys.executable
    run([py, str(ROOT / "ingest" / "parse_5ultra.py"), str(tsv), "-o", str(out)])
    run(
        [
            py,
            str(ROOT / "ingest" / "build_demo_refs.py"),
            str(tsv),
            "-o",
            str(out),
            "--raw-dir",
            str(ROOT / "data" / "raw"),
        ]
    )
    print("Ingest complete →", out)


if __name__ == "__main__":
    main()
