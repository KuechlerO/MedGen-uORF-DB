#!/usr/bin/env python3
"""Build demo reference tracks for genes present in a 5ULTRA TSV.

Creates:
  - predicted_uorfs.bed  — 5ULTRA-hit uORFs plus additional intervals inside the 5'UTR
    (placeholders for a full predicted catalog until a genome-wide dump is ingested)
  - uorfdb_uorfs.bed     — curated "established" annotations in the same loci
    (demo stand-in for a filtered human uORFdb dump; converter-compatible TSV also written)

When a real human uORFdb dump is available, prefer:
  python ingest/convert_uorfdb.py data/raw/uORF_dump_uORFdb.tsv \\
    -o data/tracks/uorfdb_uorfs.bed --assembly hg38 --genes GPR55,CUL1,...
"""

from __future__ import annotations

import argparse
import csv
from pathlib import Path

from parse_5ultra import bed_interval, parse_rows, write_predicted_from_hits


def _extra_predicted(hit: dict, existing: set[tuple]) -> list[str]:
    """Place short additional predicted uORFs inside the 5'UTR for demo context."""
    utr = hit["utr5"]
    if utr.get("start") is None or utr.get("end") is None:
        return []
    strand = hit["strand"] if hit["strand"] in ("+", "-") else "."
    u_start, u_end = utr["start"], utr["end"]
    lo, hi = sorted((u_start, u_end))
    span = hi - lo
    if span < 60:
        return []

    # Distribute up to 3 additional short ORFs (~21–45 nt) along the UTR,
    # skipping overlaps with the affected uORF when possible.
    extras: list[str] = []
    lengths = [21, 33, 45]
    count_hint = int(hit.get("uorf_counts", {}).get("total") or 1)
    n_extra = max(0, min(3, count_hint - 1))
    if n_extra == 0:
        n_extra = 1  # always show at least one contextual predicted ORF for dual-track demo

    affected = hit["uorf"]
    aff_lo = aff_hi = None
    if affected.get("start") is not None and affected.get("end") is not None:
        aff_lo, aff_hi = sorted((affected["start"], affected["end"]))

    for i in range(n_extra):
        length = lengths[i % len(lengths)]
        # Position fractions along UTR (cap-proximal → CDS-proximal)
        frac = (i + 1) / (n_extra + 2)
        if strand == "-":
            # on minus strand, "cap" is at the high genomic coordinate
            center = hi - int(span * frac)
        else:
            center = lo + int(span * frac)
        start = max(lo, center - length // 2)
        end = min(hi, start + length - 1)
        if end - start + 1 < 15:
            continue
        if aff_lo is not None and not (end < aff_lo or start > aff_hi):
            # shift away from affected ORF
            if strand == "-":
                start = max(lo, aff_lo - length - 5)
                end = start + length - 1
            else:
                start = min(hi - length + 1, aff_hi + 5)
                end = start + length - 1
            if end < start or end > hi or start < lo:
                continue

        start0, end_bed = bed_interval(start, end)
        key = (hit["chrom"], start0, end_bed)
        if key in existing:
            continue
        existing.add(key)
        name = f"{hit['gene']}|Non-Overlapping|ATG|pred_extra_{i+1}"
        extras.append("\t".join([hit["chrom"], str(start0), str(end_bed), name, "0", strand]))
    return extras


def write_predicted_demo(rows: list[dict], out_path: Path) -> int:
    # Start from 5ULTRA-consistent hit intervals
    tmp = out_path.with_suffix(".base.bed")
    write_predicted_from_hits(rows, tmp)
    lines = [ln for ln in tmp.read_text().splitlines() if ln.strip()]
    existing: set[tuple] = set()
    for ln in lines:
        parts = ln.split("\t")
        existing.add((parts[0], int(parts[1]), int(parts[2])))

    for hit in rows:
        lines.extend(_extra_predicted(hit, existing))

    tmp.unlink(missing_ok=True)
    out_path.write_text("\n".join(lines) + ("\n" if lines else ""))
    return len(lines)


def write_uorfdb_demo(rows: list[dict], out_tsv: Path, out_bed: Path) -> int:
    """Curated established-style annotations near each hit (demo until real dump filtered).

    Prefer scripts/prepare_uorfdb.sh + data/tracks/uorfdb_uorfs.bed.gz for production.
    """
    header = [
        "Taxon",
        "Assembly",
        "Chr",
        "Symbol",
        "GeneID",
        "GenBankID",
        "SymbolAliases",
        "GeneNames",
        "NCBIID",
        "TranscrStart",
        "TranscrEnd",
        "Strand",
        "TranscrLength",
        "TLSlength",
        "CDSstart",
        "CDSend",
        "TranscrKozakContext",
        "TranscrKozakStrength",
        "ExonStarts",
        "ExonEnds",
        "uORF_ID",
        "uORFstart",
        "uORFend",
        "uORFstartCodon",
        "uORFstopCodon",
        "uORFlength",
        "uORFCDSdistance",
        "uORF5'-capDistance",
        "uORFkozakContext",
        "uORFkozakStrength",
        "uORFtype",
        "uORFreadingFrame",
        "uORFnucleotideSeq",
        "uORFaminoSeq",
        "SharedStartCodon",
    ]

    tsv_rows: list[dict] = []
    seen: set[tuple] = set()

    for hit in rows:
        u = hit["uorf"]
        if u.get("start") is None or u.get("end") is None:
            continue
        strand = hit["strand"] if hit["strand"] in ("+", "-") else "+"
        mane = (hit.get("mane") or ["NA"])[0]
        utr = hit["utr5"]
        tls = utr.get("length") or ""
        mstarts = hit.get("mstart") or []
        cds_start = mstarts[0]["start"] if mstarts else ""
        cds_end = mstarts[0]["end"] if mstarts else ""

        # Established annotation ≈ affected uORF (literature/context stand-in)
        intervals = [(u["start"], u["end"], u.get("type") or "Non-Overlapping", "established")]

        # Plus one slightly shifted "established" ORF for visual dual-track distinction
        lo, hi = sorted((u["start"], u["end"]))
        length = hi - lo + 1
        if length >= 30:
            if strand == "-":
                s2, e2 = lo + 12, hi - 3
            else:
                s2, e2 = lo + 3, hi - 12
            if e2 > s2:
                intervals.append((s2, e2, "Non-Overlapping", "established_alt"))

        # Cap-proximal short ORF inside UTR when space allows
        if utr.get("start") is not None and utr.get("end") is not None:
            ulo, uhi = sorted((utr["start"], utr["end"]))
            if strand == "-":
                s3, e3 = uhi - 45, uhi - 25
            else:
                s3, e3 = ulo + 25, ulo + 45
            if ulo <= s3 < e3 <= uhi:
                intervals.append((s3, e3, "Non-Overlapping", "cap_proximal"))

        for start, end, utype, tag in intervals:
            key = (hit["chrom"], start, end, hit["gene"])
            if key in seen:
                continue
            seen.add(key)
            length = abs(end - start) + 1
            uorf_id = f"{mane}_{tag}"
            tsv_rows.append(
                {
                    "Taxon": "Homo sapiens",
                    "Assembly": "hg38",
                    "Chr": hit["chrom"],
                    "Symbol": hit["gene"],
                    "GeneID": "",
                    "GenBankID": "",
                    "SymbolAliases": "",
                    "GeneNames": "",
                    "NCBIID": mane,
                    "TranscrStart": utr.get("start") or "",
                    "TranscrEnd": utr.get("end") or "",
                    "Strand": strand,
                    "TranscrLength": "",
                    "TLSlength": tls,
                    "CDSstart": cds_start,
                    "CDSend": cds_end,
                    "TranscrKozakContext": hit.get("mkozak") or "",
                    "TranscrKozakStrength": hit.get("mkozak_strength") or "",
                    "ExonStarts": "",
                    "ExonEnds": "",
                    "uORF_ID": uorf_id,
                    "uORFstart": start,
                    "uORFend": end,
                    "uORFstartCodon": u.get("start_codon") or "ATG",
                    "uORFstopCodon": (u.get("stop_codon") or "TGA").split()[0],
                    "uORFlength": length,
                    "uORFCDSdistance": u.get("ustart_mstart_dist") or "",
                    "uORF5'-capDistance": u.get("ustart_cap_dist") or "",
                    "uORFkozakContext": u.get("kozak") or "",
                    "uORFkozakStrength": u.get("kozak_strength") or "",
                    "uORFtype": utype,
                    "uORFreadingFrame": "",
                    "uORFnucleotideSeq": u.get("seq") or "",
                    "uORFaminoSeq": "",
                    "SharedStartCodon": "",
                }
            )

    out_tsv.parent.mkdir(parents=True, exist_ok=True)
    with out_tsv.open("w", newline="") as fh:
        writer = csv.DictWriter(fh, fieldnames=header, delimiter="\t")
        writer.writeheader()
        writer.writerows(tsv_rows)

    # Convert via same logic as production converter
    from convert_uorfdb import convert_uorfdb_tsv

    return convert_uorfdb_tsv(
        out_tsv, out_bed, assembly="hg38", taxon="Homo sapiens"
    )

def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("tsv", type=Path, help="5ULTRA TSV")
    parser.add_argument(
        "-o",
        "--out-dir",
        type=Path,
        default=Path("data/tracks"),
    )
    parser.add_argument(
        "--raw-dir",
        type=Path,
        default=Path("data/raw"),
        help="Where to write curated uORFdb-format demo TSV",
    )
    parser.add_argument(
        "--force-demo-uorfdb",
        action="store_true",
        help="Overwrite uorfdb track with curated demo even if bed.gz exists",
    )
    args = parser.parse_args()

    rows, _ = parse_rows(args.tsv)
    out = args.out_dir
    out.mkdir(parents=True, exist_ok=True)
    args.raw_dir.mkdir(parents=True, exist_ok=True)

    n_pred = write_predicted_demo(rows, out / "predicted_uorfs.bed")
    print(f"predicted_uorfs.bed: {n_pred} intervals")

    real_gz = out / "uorfdb_uorfs.bed.gz"
    real_tbi = out / "uorfdb_uorfs.bed.gz.tbi"
    if real_gz.exists() and real_tbi.exists() and not args.force_demo_uorfdb:
        print(
            f"Keeping existing genome-wide track {real_gz.name} "
            "(skip demo uORFdb overwrite; use --force-demo-uorfdb to replace)"
        )
    else:
        n_est = write_uorfdb_demo(
            rows,
            args.raw_dir / "demo_uorfdb_human.tsv",
            out / "uorfdb_uorfs.bed",
        )
        print(f"uorfdb_uorfs.bed: {n_est} intervals (demo)")


if __name__ == "__main__":
    main()
