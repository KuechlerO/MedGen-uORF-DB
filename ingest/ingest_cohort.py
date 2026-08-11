#!/usr/bin/env python3
"""Ingest 5ULTRA cohort TSVs (splice + nosplice) into SQLite + per-sample tracks."""

from __future__ import annotations

import argparse
import json
import sqlite3
import sys
from collections import defaultdict
from pathlib import Path

from parse_5ultra import (
    locus_window,
    parse_rows,
    write_context_beds,
    write_perturbed_bed,
    write_vcf,
)
from sample_utils import full_sample_name_from_path, sample_id_from_full

ROOT = Path(__file__).resolve().parents[1]
DEFAULT_DATA = ROOT / "data" / "5ULTRA"
DEFAULT_DB = ROOT / "data" / "catalog" / "uorf.db"
DEFAULT_TRACKS = ROOT / "data" / "tracks" / "by_sample"
DEFAULT_SUMMARY = ROOT / "data" / "catalog" / "samples.json"

SCHEMA = """
CREATE TABLE IF NOT EXISTS samples (
    sample_id TEXT NOT NULL,
    full_sample_name TEXT NOT NULL,
    dataset TEXT NOT NULL DEFAULT '5ultra',
    mode TEXT NOT NULL,
    hit_count INTEGER NOT NULL DEFAULT 0,
    source_path TEXT,
    PRIMARY KEY (sample_id, mode, dataset)
);

CREATE TABLE IF NOT EXISTS hits (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    sample_id TEXT NOT NULL,
    mode TEXT NOT NULL,
    dataset TEXT NOT NULL DEFAULT '5ultra',
    hit_id TEXT NOT NULL,
    gene TEXT,
    chrom TEXT,
    pos INTEGER,
    score REAL,
    csq_class TEXT,
    payload TEXT NOT NULL,
    UNIQUE(sample_id, mode, dataset, hit_id)
);

CREATE INDEX IF NOT EXISTS idx_hits_sample_mode ON hits(sample_id, mode, dataset);
CREATE INDEX IF NOT EXISTS idx_hits_gene ON hits(gene);
CREATE INDEX IF NOT EXISTS idx_hits_score ON hits(score DESC);
CREATE INDEX IF NOT EXISTS idx_hits_chrom_pos ON hits(chrom, pos);
"""


def init_db(db_path: Path) -> sqlite3.Connection:
    db_path.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(db_path)
    conn.executescript(SCHEMA)
    return conn


def clear_dataset(conn: sqlite3.Connection, dataset: str = "5ultra") -> None:
    conn.execute("DELETE FROM hits WHERE dataset = ?", (dataset,))
    conn.execute("DELETE FROM samples WHERE dataset = ?", (dataset,))
    conn.commit()


def enrich_hit(hit: dict, *, sample_id: str, mode: str, full_name: str) -> dict:
    out = dict(hit)
    out["sample_id"] = sample_id
    out["mode"] = mode
    out["full_sample_name"] = full_name
    out["window"] = locus_window(hit)
    # stable id includes sample + mode for multi-sample UI
    base = hit["id"]
    out["id"] = f"{sample_id}:{mode}:{base}"
    return out


def ingest_file(
    conn: sqlite3.Connection,
    tsv_path: Path,
    mode: str,
    tracks_root: Path,
    *,
    dataset: str = "5ultra",
) -> tuple[str, int]:
    full_name = full_sample_name_from_path(tsv_path)
    if not full_name:
        raise ValueError(f"Cannot parse sample from {tsv_path.name}")
    sid = sample_id_from_full(full_name)

    rows, _ = parse_rows(tsv_path)
    enriched = [enrich_hit(h, sample_id=sid, mode=mode, full_name=full_name) for h in rows]
    # TSV rows can repeat the same variant/uORF; keep one row per hit_id for DB + tracks.
    seen: set[str] = set()
    unique: list[dict] = []
    for hit in enriched:
        hid = hit["id"]
        if hid in seen:
            continue
        seen.add(hid)
        unique.append(hit)
    enriched = unique

    conn.execute(
        """
        INSERT OR REPLACE INTO samples
        (sample_id, full_sample_name, dataset, mode, hit_count, source_path)
        VALUES (?, ?, ?, ?, ?, ?)
        """,
        (sid, full_name, dataset, mode, len(enriched), str(tsv_path)),
    )

    for hit in enriched:
        conn.execute(
            """
            INSERT OR REPLACE INTO hits
            (sample_id, mode, dataset, hit_id, gene, chrom, pos, score, csq_class, payload)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                sid,
                mode,
                dataset,
                hit["id"],
                hit["gene"],
                hit["chrom"],
                hit["pos"],
                hit["score"],
                hit["csq_class"],
                json.dumps(hit),
            ),
        )

    track_dir = tracks_root / sid / mode
    track_dir.mkdir(parents=True, exist_ok=True)
    write_vcf(enriched, track_dir / "variants.vcf", full_name)
    write_perturbed_bed(enriched, track_dir / "perturbed_uorfs.bed")
    write_context_beds(enriched, track_dir)

    return sid, len(enriched)


def write_samples_summary(conn: sqlite3.Connection, out_path: Path) -> None:
    cur = conn.execute(
        """
        SELECT sample_id, full_sample_name,
               SUM(CASE WHEN mode='nosplice' THEN hit_count ELSE 0 END) AS nosplice_hits,
               SUM(CASE WHEN mode='splice' THEN hit_count ELSE 0 END) AS splice_hits,
               GROUP_CONCAT(DISTINCT mode) AS modes
        FROM samples
        WHERE dataset = '5ultra'
        GROUP BY sample_id, full_sample_name
        ORDER BY sample_id
        """
    )
    samples = []
    for row in cur.fetchall():
        sid, full, ns, sp, modes = row
        mode_list = sorted(modes.split(",")) if modes else []
        samples.append(
            {
                "sample_id": sid,
                "full_sample_name": full,
                "nosplice_hits": ns or 0,
                "splice_hits": sp or 0,
                "total_hits": (ns or 0) + (sp or 0),
                "modes": mode_list,
            }
        )
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(
        json.dumps({"sample_count": len(samples), "samples": samples}, indent=2)
    )


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--data-dir",
        type=Path,
        default=DEFAULT_DATA,
        help="Root with splice/ and nosplice/ subdirs",
    )
    parser.add_argument("--db", type=Path, default=DEFAULT_DB)
    parser.add_argument("--tracks", type=Path, default=DEFAULT_TRACKS)
    parser.add_argument("--summary", type=Path, default=DEFAULT_SUMMARY)
    parser.add_argument("--dataset", default="5ultra")
    args = parser.parse_args()

    conn = init_db(args.db)
    clear_dataset(conn, args.dataset)

    totals: dict[str, int] = defaultdict(int)
    files_processed = 0

    for mode in ("nosplice", "splice"):
        mode_dir = args.data_dir / mode
        if not mode_dir.is_dir():
            print(f"Skip missing {mode_dir}", file=sys.stderr)
            continue
        tsvs = sorted(mode_dir.glob("*.tsv"))
        print(f"==> {mode}: {len(tsvs)} TSV files")
        for tsv in tsvs:
            full_name = full_sample_name_from_path(tsv)
            if not full_name or "-N1" not in full_name:
                print(f"  skip {tsv.name} (not a sample TSV)", file=sys.stderr)
                continue
            sid, n = ingest_file(conn, tsv, mode, args.tracks, dataset=args.dataset)
            totals[mode] += n
            files_processed += 1
            if files_processed % 25 == 0:
                conn.commit()
                print(f"  … {files_processed} files, {totals[mode]:,} {mode} hits", file=sys.stderr)

    conn.commit()
    write_samples_summary(conn, args.summary)
    conn.close()

    print(f"Processed {files_processed} files")
    print(f"  nosplice hits: {totals['nosplice']:,}")
    print(f"  splice hits:   {totals['splice']:,}")
    print(f"DB → {args.db}")
    print(f"Tracks → {args.tracks}")
    print(f"Summary → {args.summary}")


if __name__ == "__main__":
    main()
