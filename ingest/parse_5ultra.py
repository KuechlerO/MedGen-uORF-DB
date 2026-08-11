#!/usr/bin/env python3
"""Parse 5ULTRA TSV into gene-indexed JSON, VCF, and BED tracks."""

from __future__ import annotations

import argparse
import ast
import csv
import json
import re
from collections import defaultdict
from pathlib import Path
from typing import Any


def _clean_header(name: str) -> str:
    return name.lstrip("#").strip()


def _parse_listish(value: str) -> list[str]:
    value = (value or "").strip()
    if not value or value == ".":
        return []
    if value.startswith("["):
        try:
            parsed = ast.literal_eval(value)
            if isinstance(parsed, list):
                return [str(x) for x in parsed]
        except (SyntaxError, ValueError):
            pass
    return [value]


def _parse_mstart(value: str) -> list[dict[str, int]]:
    value = (value or "").strip()
    if not value or value == ".":
        return []
    try:
        parsed = ast.literal_eval(value)
    except (SyntaxError, ValueError):
        return []
    out: list[dict[str, int]] = []
    if isinstance(parsed, list):
        for item in parsed:
            if isinstance(item, (list, tuple)) and len(item) == 2:
                out.append({"start": int(item[0]), "end": int(item[1])})
    return out


def _safe_float(value: str | None) -> float | None:
    if value is None or value == "" or value == ".":
        return None
    try:
        return float(value)
    except ValueError:
        return None


def _safe_int(value: str | None) -> int | None:
    if value is None or value == "" or value == ".":
        return None
    try:
        return int(float(value))
    except ValueError:
        return None


def _csq_class(csq: str) -> str:
    csq = csq or ""
    for key in (
        "uStart_loss",
        "uStart_gain",
        "uStop_loss",
        "uStop_gain",
        "uORF_missense",
        "uORF_synonymous",
    ):
        if key in csq:
            return key
    return csq.split()[0] if csq else "unknown"


def bed_interval(start: int, end: int) -> tuple[int, int]:
    """Return 0-based half-open BED coords from inclusive genomic positions."""
    a, b = sorted((start, end))
    return a - 1, b


def parse_rows(tsv_path: Path) -> tuple[list[dict[str, Any]], str | None]:
    rows: list[dict[str, Any]] = []
    sample_name: str | None = None

    with tsv_path.open(newline="") as fh:
        reader = csv.DictReader(fh, delimiter="\t")
        if not reader.fieldnames:
            raise SystemExit(f"No header in {tsv_path}")
        fieldnames = [_clean_header(f) for f in reader.fieldnames]
        # Remap cleaned names
        rename = {
            raw: _clean_header(raw) for raw in reader.fieldnames if raw != _clean_header(raw)
        }

        known = {
            "CHROM",
            "POS",
            "ID",
            "REF",
            "ALT",
            "CSQ",
            "Translation",
            "5ULTRA_Score",
            "GENE",
            "TRANSCRIPT",
            "QUAL",
            "FILTER",
            "INFO",
            "FORMAT",
            "SpliceAI",
            "Splicing_CSQ",
            "5UTR_START",
            "5UTR_END",
            "STRAND",
            "5UTR_LENGTH",
            "mSTART",
            "mSTART_CODON",
            "START_EXON",
            "mKOZAK",
            "mKOZAK_STRENGTH",
            "uORF_count",
            "Overlapping_count",
            "Nterminal_count",
            "NonOverlapping_count",
            "minimum_uORF_mSTART_DIST",
            "MANE",
            "uORF_START",
            "uORF_END",
            "Ribo_seq",
            "uSTART_mSTART_DIST",
            "uSTART_CODON",
            "uSTOP_CODON",
            "uORF_TYPE",
            "uKOZAK",
            "uKOZAK_STRENGTH",
            "uORF_LENGTH",
            "uORF_AA_LENGTH",
            "uORF_SEQ",
            "uORF_rank",
            "uSTART_PHYLOP",
            "uSTART_PHASTCONS",
            "uSTART_CAP_DIST",
            "LOEUF",
            "pLI",
        }
        for raw in reader.fieldnames:
            cleaned = _clean_header(raw)
            if cleaned not in known and cleaned not in {
                "FORMAT",
            }:
                # Sample genotype column is typically the first unknown after FORMAT
                if sample_name is None and cleaned not in known:
                    sample_name = cleaned

        for i, raw_row in enumerate(reader):
            row = {_clean_header(k): (v if v is not None else "") for k, v in raw_row.items()}
            chrom = row.get("CHROM", "")
            pos = _safe_int(row.get("POS"))
            gene = row.get("GENE", "")
            if not chrom or pos is None or not gene:
                continue

            transcripts = _parse_listish(row.get("TRANSCRIPT", ""))
            mane = _parse_listish(row.get("MANE", ""))
            mstarts = _parse_mstart(row.get("mSTART", ""))
            uorf_start = _safe_int(row.get("uORF_START"))
            uorf_end = _safe_int(row.get("uORF_END"))
            utr_start = _safe_int(row.get("5UTR_START"))
            utr_end = _safe_int(row.get("5UTR_END"))
            strand = row.get("STRAND", "")
            csq = row.get("CSQ", "")
            score = _safe_float(row.get("5ULTRA_Score"))
            hit_id = f"{gene}:{chrom}:{pos}:{row.get('REF', '')}>{row.get('ALT', '')}"

            genotype = ""
            if sample_name:
                genotype = row.get(sample_name, "")

            record: dict[str, Any] = {
                "id": hit_id,
                "index": i,
                "chrom": chrom,
                "pos": pos,
                "ref": row.get("REF", ""),
                "alt": row.get("ALT", ""),
                "qual": _safe_float(row.get("QUAL")),
                "filter": row.get("FILTER", ""),
                "csq": csq,
                "csq_class": _csq_class(csq),
                "translation": row.get("Translation", ""),
                "score": score,
                "gene": gene,
                "transcripts": transcripts,
                "mane": mane,
                "strand": strand,
                "utr5": {
                    "start": utr_start,
                    "end": utr_end,
                    "length": _safe_int(row.get("5UTR_LENGTH")),
                },
                "mstart": mstarts,
                "mstart_codon": row.get("mSTART_CODON", ""),
                "mkozak": row.get("mKOZAK", ""),
                "mkozak_strength": row.get("mKOZAK_STRENGTH", ""),
                "uorf_counts": {
                    "total": _safe_float(row.get("uORF_count")),
                    "overlapping": _safe_float(row.get("Overlapping_count")),
                    "nterminal": _safe_float(row.get("Nterminal_count")),
                    "non_overlapping": _safe_float(row.get("NonOverlapping_count")),
                    "min_mstart_dist": _safe_float(row.get("minimum_uORF_mSTART_DIST")),
                },
                "uorf": {
                    "start": uorf_start,
                    "end": uorf_end,
                    "type": row.get("uORF_TYPE", ""),
                    "start_codon": row.get("uSTART_CODON", ""),
                    "stop_codon": row.get("uSTOP_CODON", ""),
                    "kozak": row.get("uKOZAK", ""),
                    "kozak_strength": row.get("uKOZAK_STRENGTH", ""),
                    "length": _safe_int(row.get("uORF_LENGTH")),
                    "aa_length": _safe_float(row.get("uORF_AA_LENGTH")),
                    "seq": row.get("uORF_SEQ", ""),
                    "rank": row.get("uORF_rank", ""),
                    "ribo_seq": _safe_int(row.get("Ribo_seq")),
                    "ustart_mstart_dist": _safe_int(row.get("uSTART_mSTART_DIST")),
                    "ustart_cap_dist": _safe_int(row.get("uSTART_CAP_DIST")),
                    "phylop": _safe_float(row.get("uSTART_PHYLOP")),
                    "phastcons": _safe_float(row.get("uSTART_PHASTCONS")),
                },
                "spliceai": row.get("SpliceAI", ""),
                "splicing_csq": row.get("Splicing_CSQ", ""),
                "loeuf": _safe_float(row.get("LOEUF")),
                "pli": _safe_float(row.get("pLI")),
                "sample": sample_name,
                "genotype": genotype,
                "info": row.get("INFO", ""),
            }
            rows.append(record)

    return rows, sample_name


def locus_window(hit: dict[str, Any], pad: int = 250) -> dict[str, Any]:
    """Choose a browser window that stays in the TLS neighborhood.

    5ULTRA may report genomic 5UTR/uORF spans that cross large introns while
    5UTR_LENGTH is only a few hundred nt. Prefer a compact view around the
    variant (and nearby mSTART / compact UTR) so IGV is usable.
    """
    chrom = hit["chrom"]
    pos = hit["pos"]
    coords: list[int] = [pos]

    utr = hit["utr5"]
    utr_len = utr.get("length")
    if (
        utr.get("start") is not None
        and utr.get("end") is not None
        and utr_len is not None
        and abs(utr["end"] - utr["start"]) <= max(2000, utr_len * 3)
    ):
        coords.extend([utr["start"], utr["end"]])

    for m in hit.get("mstart") or []:
        if abs(m["start"] - pos) <= 5000 and abs(m["end"] - pos) <= 5000:
            coords.extend([m["start"], m["end"]])

    u = hit["uorf"]
    if u.get("start") is not None and u.get("end") is not None:
        if abs(u["end"] - u["start"]) <= 5000:
            coords.extend([u["start"], u["end"]])

    lo, hi = min(coords), max(coords)
    # Always keep at least ±pad around the variant
    start = max(1, min(lo, pos) - pad)
    end = max(hi, pos) + pad
    # Hard cap so intron-spanning annotations cannot explode the view
    if end - start > 8000:
        start = max(1, pos - 3000)
        end = pos + 3000
    return {
        "chrom": chrom,
        "start": start,
        "end": end,
        "locus": f"{chrom}:{start}-{end}",
    }


def write_json_index(rows: list[dict[str, Any]], out_path: Path) -> None:
    by_gene: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for hit in rows:
        enriched = dict(hit)
        enriched["window"] = locus_window(hit)
        by_gene[hit["gene"]].append(enriched)

    genes = []
    for gene, hits in sorted(by_gene.items()):
        windows = [h["window"] for h in hits]
        g_start = min(w["start"] for w in windows)
        g_end = max(w["end"] for w in windows)
        chrom = windows[0]["chrom"]
        genes.append(
            {
                "gene": gene,
                "chrom": chrom,
                "start": g_start,
                "end": g_end,
                "locus": f"{chrom}:{g_start}-{g_end}",
                "hit_count": len(hits),
                "max_score": max((h["score"] or 0.0) for h in hits),
                "hits": hits,
            }
        )

    payload = {
        "genome": "hg38",
        "source": "5ULTRA",
        "hit_count": len(rows),
        "gene_count": len(genes),
        "genes": genes,
        "hits": [dict(h, window=locus_window(h)) for h in rows],
    }
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(json.dumps(payload, indent=2))


def write_vcf(rows: list[dict[str, Any]], out_path: Path, sample_name: str | None) -> None:
    sample = sample_name or "SAMPLE"
    lines = [
        "##fileformat=VCFv4.2",
        "##reference=hg38",
        '##INFO=<ID=GENE,Number=1,Type=String,Description="Gene symbol">',
        '##INFO=<ID=CSQ,Number=1,Type=String,Description="5ULTRA consequence">',
        '##INFO=<ID=SCORE,Number=1,Type=Float,Description="5ULTRA score">',
        '##INFO=<ID=TRANSLATION,Number=1,Type=String,Description="Predicted translation effect">',
        '##FORMAT=<ID=GT,Number=1,Type=String,Description="Genotype">',
        f"#CHROM\tPOS\tID\tREF\tALT\tQUAL\tFILTER\tINFO\tFORMAT\t{sample}",
    ]
    for hit in sorted(rows, key=lambda r: (r["chrom"], r["pos"])):
        csq = re.sub(r"[^A-Za-z0-9_.]", "_", hit["csq"])[:80]
        info = (
            f"GENE={hit['gene']};"
            f"CSQ={csq};"
            f"SCORE={hit['score'] if hit['score'] is not None else '.'};"
            f"TRANSLATION={hit['translation'] or '.'}"
        )
        gt = "."
        if hit.get("genotype"):
            gt = hit["genotype"].split(":")[0]
        qual = hit["qual"] if hit["qual"] is not None else "."
        filt = hit["filter"] if hit["filter"] not in ("", None) else "."
        lines.append(
            "\t".join(
                [
                    hit["chrom"],
                    str(hit["pos"]),
                    ".",
                    hit["ref"],
                    hit["alt"],
                    str(qual),
                    filt,
                    info,
                    "GT",
                    gt,
                ]
            )
        )
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text("\n".join(lines) + "\n")


def write_perturbed_bed(rows: list[dict[str, Any]], out_path: Path) -> None:
    lines: list[str] = []
    for hit in rows:
        u = hit["uorf"]
        if u.get("start") is None or u.get("end") is None:
            continue
        start0, end = bed_interval(u["start"], u["end"])
        name = f"{hit['gene']}|{hit['csq_class']}|score={hit['score']}"
        score = int(min(1000, max(0, round((hit["score"] or 0) * 1000))))
        strand = hit["strand"] if hit["strand"] in ("+", "-") else "."
        lines.append(
            "\t".join(
                [
                    hit["chrom"],
                    str(start0),
                    str(end),
                    name,
                    str(score),
                    strand,
                ]
            )
        )
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text("\n".join(lines) + ("\n" if lines else ""))


def write_context_beds(rows: list[dict[str, Any]], out_dir: Path) -> None:
    utr_lines: list[str] = []
    mstart_lines: list[str] = []
    seen_utr: set[tuple] = set()
    seen_m: set[tuple] = set()

    for hit in rows:
        utr = hit["utr5"]
        if utr.get("start") is not None and utr.get("end") is not None:
            start0, end = bed_interval(utr["start"], utr["end"])
            key = (hit["chrom"], start0, end, hit["gene"])
            if key not in seen_utr:
                seen_utr.add(key)
                strand = hit["strand"] if hit["strand"] in ("+", "-") else "."
                utr_lines.append(
                    "\t".join(
                        [hit["chrom"], str(start0), str(end), f"{hit['gene']}_5UTR", "0", strand]
                    )
                )
        for m in hit.get("mstart") or []:
            start0, end = bed_interval(m["start"], m["end"])
            key = (hit["chrom"], start0, end, hit["gene"])
            if key not in seen_m:
                seen_m.add(key)
                strand = hit["strand"] if hit["strand"] in ("+", "-") else "."
                mstart_lines.append(
                    "\t".join(
                        [
                            hit["chrom"],
                            str(start0),
                            str(end),
                            f"{hit['gene']}_mSTART",
                            "0",
                            strand,
                        ]
                    )
                )

    out_dir.mkdir(parents=True, exist_ok=True)
    (out_dir / "utr5.bed").write_text("\n".join(utr_lines) + ("\n" if utr_lines else ""))
    (out_dir / "mstart.bed").write_text("\n".join(mstart_lines) + ("\n" if mstart_lines else ""))


def write_predicted_from_hits(rows: list[dict[str, Any]], out_path: Path) -> None:
    """5ULTRA-consistent predicted uORFs = unique affected intervals from the TSV."""
    lines: list[str] = []
    seen: set[tuple] = set()
    for hit in rows:
        u = hit["uorf"]
        if u.get("start") is None or u.get("end") is None:
            continue
        start0, end = bed_interval(u["start"], u["end"])
        key = (hit["chrom"], start0, end)
        if key in seen:
            continue
        seen.add(key)
        strand = hit["strand"] if hit["strand"] in ("+", "-") else "."
        name = f"{hit['gene']}|{u.get('type') or 'uORF'}|{u.get('start_codon') or '?'}"
        lines.append("\t".join([hit["chrom"], str(start0), str(end), name, "0", strand]))
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text("\n".join(lines) + ("\n" if lines else ""))


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("tsv", type=Path, help="5ULTRA TSV path")
    parser.add_argument(
        "-o",
        "--out-dir",
        type=Path,
        default=Path("data/tracks"),
        help="Output directory for tracks",
    )
    args = parser.parse_args()

    rows, sample = parse_rows(args.tsv)
    if not rows:
        raise SystemExit("No parseable rows found")

    out = args.out_dir
    out.mkdir(parents=True, exist_ok=True)
    write_json_index(rows, out / "hits.json")
    write_vcf(rows, out / "variants.vcf", sample)
    write_perturbed_bed(rows, out / "perturbed_uorfs.bed")
    write_context_beds(rows, out)
    write_predicted_from_hits(rows, out / "predicted_uorfs_from_5ultra.bed")
    print(f"Wrote {len(rows)} hits → {out}")


if __name__ == "__main__":
    main()
