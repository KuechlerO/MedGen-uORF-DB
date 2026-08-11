#!/usr/bin/env python3
"""Convert uORFdb TSV dumps (or curated demo subsets) into BED tracks.

Streams rows to disk (suitable for ~2.4M human intervals). Sorting / bgzip /
tabix are handled by scripts/prepare_uorfdb.sh for genome-wide dumps.
"""

from __future__ import annotations

import argparse
import csv
import sys
from pathlib import Path


def _clean(name: str) -> str:
    return name.strip().lstrip("#")


def bed_interval(start: int, end: int) -> tuple[int, int]:
    a, b = sorted((start, end))
    return a - 1, b


def convert_uorfdb_tsv(
    tsv_path: Path,
    out_bed: Path,
    *,
    assembly: str | None = "hg38",
    taxon: str | None = "Homo sapiens",
    genes: set[str] | None = None,
    progress_every: int = 250_000,
) -> int:
    """Stream-write BED6 from uORFdb dump. Returns number of intervals written."""
    count = 0
    scanned = 0
    out_bed.parent.mkdir(parents=True, exist_ok=True)

    with tsv_path.open(newline="", encoding="utf-8", errors="replace") as fh, out_bed.open(
        "w", encoding="utf-8"
    ) as out:
        reader = csv.DictReader(fh, delimiter="\t")
        if not reader.fieldnames:
            raise SystemExit(f"No header in {tsv_path}")

        field_map = {_clean(f): f for f in reader.fieldnames}

        def get(row: dict, key: str) -> str:
            raw_key = field_map.get(key) or field_map.get(key.strip())
            if raw_key is None:
                for k, v in field_map.items():
                    if k.replace(" ", "") == key.replace(" ", ""):
                        return (row.get(v) or "").strip()
                return ""
            return (row.get(raw_key) or "").strip()

        for row in reader:
            scanned += 1
            if taxon:
                tax = get(row, "Taxon")
                if tax and tax != taxon:
                    continue
            if assembly:
                asm = get(row, "Assembly")
                if asm and asm != assembly:
                    continue
            symbol = get(row, "Symbol")
            if genes and symbol not in genes:
                continue
            chrom = get(row, "Chr")
            u_start = get(row, "uORFstart")
            u_end = get(row, "uORFend")
            if not chrom or not u_start or not u_end:
                continue
            try:
                start0, end = bed_interval(int(u_start), int(u_end))
            except ValueError:
                continue
            strand = get(row, "Strand") or "."
            if strand not in ("+", "-"):
                strand = "."
            uorf_id = get(row, "uORF_ID") or f"{symbol}_uORF"
            u_type = get(row, "uORFtype") or "uORF"
            start_codon = get(row, "uORFstartCodon") or "?"
            name = f"{symbol}|{u_type}|{start_codon}|{uorf_id}"
            out.write(
                "\t".join([chrom, str(start0), str(end), name, "0", strand]) + "\n"
            )
            count += 1
            if progress_every and count % progress_every == 0:
                print(
                    f"  … {count:,} intervals kept ({scanned:,} rows scanned)",
                    file=sys.stderr,
                    flush=True,
                )

    return count


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("tsv", type=Path, help="uORFdb uORF dump TSV")
    parser.add_argument("-o", "--out", type=Path, required=True, help="Output BED path")
    parser.add_argument(
        "--assembly",
        default="hg38",
        help="Keep only this assembly (default: hg38). Use '' for all.",
    )
    parser.add_argument(
        "--taxon",
        default="Homo sapiens",
        help="Keep only this taxon (default: Homo sapiens). Use '' for all.",
    )
    parser.add_argument(
        "--genes",
        default="",
        help="Comma-separated gene symbols to keep (default: all)",
    )
    args = parser.parse_args()
    genes = {g.strip() for g in args.genes.split(",") if g.strip()} or None
    assembly = args.assembly or None
    taxon = args.taxon or None
    n = convert_uorfdb_tsv(
        args.tsv,
        args.out,
        assembly=assembly,
        taxon=taxon,
        genes=genes,
    )
    print(f"Wrote {n} uORF intervals → {args.out}")


if __name__ == "__main__":
    main()
