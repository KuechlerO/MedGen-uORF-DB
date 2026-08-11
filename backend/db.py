"""SQLite access for multi-sample 5ULTRA catalog."""

from __future__ import annotations

import json
import sqlite3
from functools import lru_cache
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
DB_PATH = ROOT / "data" / "catalog" / "uorf.db"
SUMMARY_PATH = ROOT / "data" / "catalog" / "samples.json"


def db_available() -> bool:
    return DB_PATH.exists()


@lru_cache(maxsize=1)
def get_connection() -> sqlite3.Connection:
    if not DB_PATH.exists():
        raise FileNotFoundError(f"Missing catalog DB: {DB_PATH}")
    conn = sqlite3.connect(DB_PATH, check_same_thread=False)
    conn.row_factory = sqlite3.Row
    return conn


def reload_db() -> None:
    get_connection.cache_clear()


def _normalize_gene_list(genes: list[str] | None) -> list[str]:
    if not genes:
        return []
    seen: set[str] = set()
    out: list[str] = []
    for g in genes:
        sym = (g or "").strip().upper()
        if not sym or sym in seen:
            continue
        seen.add(sym)
        out.append(sym)
    return out


def list_samples(q: str | None = None, limit: int = 500) -> list[dict[str, Any]]:
    conn = get_connection()
    if q:
        like = f"%{q.strip()}%"
        cur = conn.execute(
            """
            SELECT sample_id, full_sample_name,
                   SUM(CASE WHEN mode='nosplice' THEN hit_count ELSE 0 END) AS nosplice_hits,
                   SUM(CASE WHEN mode='splice' THEN hit_count ELSE 0 END) AS splice_hits
            FROM samples
            WHERE dataset='5ultra'
              AND (sample_id LIKE ? OR full_sample_name LIKE ?)
            GROUP BY sample_id, full_sample_name
            ORDER BY sample_id
            LIMIT ?
            """,
            (like, like, limit),
        )
    else:
        cur = conn.execute(
            """
            SELECT sample_id, full_sample_name,
                   SUM(CASE WHEN mode='nosplice' THEN hit_count ELSE 0 END) AS nosplice_hits,
                   SUM(CASE WHEN mode='splice' THEN hit_count ELSE 0 END) AS splice_hits
            FROM samples
            WHERE dataset='5ultra'
            GROUP BY sample_id, full_sample_name
            ORDER BY sample_id
            LIMIT ?
            """,
            (limit,),
        )
    out = []
    for row in cur.fetchall():
        ns = row["nosplice_hits"] or 0
        sp = row["splice_hits"] or 0
        modes = []
        if ns:
            modes.append("nosplice")
        if sp:
            modes.append("splice")
        out.append(
            {
                "sample_id": row["sample_id"],
                "full_sample_name": row["full_sample_name"],
                "nosplice_hits": ns,
                "splice_hits": sp,
                "total_hits": ns + sp,
                "modes": modes,
            }
        )
    return out


def get_sample(sample_id: str) -> dict[str, Any] | None:
    samples = list_samples(q=sample_id, limit=1000)
    for s in samples:
        if s["sample_id"] == sample_id:
            return s
    return None


def _mode_clause(mode: str) -> tuple[str, list[str]]:
    if mode == "both":
        return "mode IN ('nosplice', 'splice')", []
    if mode in ("nosplice", "splice"):
        return "mode = ?", [mode]
    raise ValueError(f"Invalid mode: {mode}")


def _gene_in_clause(genes: list[str]) -> tuple[str, list[str]]:
    placeholders = ", ".join("?" for _ in genes)
    return f"UPPER(gene) IN ({placeholders})", genes


def query_hits(
    sample_id: str,
    *,
    mode: str = "both",
    gene: str | None = None,
    genes: list[str] | None = None,
    q: str | None = None,
    min_score: float | None = None,
    limit: int = 5000,
) -> list[dict[str, Any]]:
    conn = get_connection()
    mode_sql, mode_args = _mode_clause(mode)
    clauses = ["sample_id = ?", "dataset = '5ultra'", mode_sql]
    args: list[Any] = [sample_id, *mode_args]

    gene_list = _normalize_gene_list(genes)
    if gene and not gene_list:
        clauses.append("UPPER(gene) = ?")
        args.append(gene.strip().upper())
    elif gene_list:
        gin, gargs = _gene_in_clause(gene_list)
        clauses.append(gin)
        args.extend(gargs)
    if min_score is not None:
        clauses.append("score >= ?")
        args.append(min_score)
    if q:
        like = f"%{q.strip()}%"
        clauses.append(
            "(gene LIKE ? OR chrom LIKE ? OR csq_class LIKE ? OR hit_id LIKE ? OR payload LIKE ?)"
        )
        args.extend([like, like, like, like, like])

    sql = f"""
        SELECT payload FROM hits
        WHERE {' AND '.join(clauses)}
        ORDER BY score DESC, gene, pos
        LIMIT ?
    """
    args.append(limit)
    cur = conn.execute(sql, args)
    hits = [json.loads(row["payload"]) for row in cur.fetchall()]
    return hits


def search_hits_global(
    q: str,
    *,
    sample_id: str | None = None,
    mode: str = "both",
    genes: list[str] | None = None,
    min_score: float | None = None,
    limit: int = 500,
) -> list[dict[str, Any]]:
    conn = get_connection()
    query = q.strip()
    if not query:
        return []

    mode_sql, mode_args = _mode_clause(mode)
    clauses = ["dataset = '5ultra'", mode_sql]
    args: list[Any] = list(mode_args)

    if sample_id:
        clauses.append("sample_id = ?")
        args.append(sample_id)

    gene_list = _normalize_gene_list(genes)
    if gene_list:
        gin, gargs = _gene_in_clause(gene_list)
        clauses.append(gin)
        args.extend(gargs)

    if min_score is not None:
        clauses.append("score >= ?")
        args.append(min_score)

    like = f"%{query.upper()}%"
    clauses.append(
        "(UPPER(gene) LIKE ? OR UPPER(csq_class) LIKE ? OR chrom LIKE ? OR hit_id LIKE ? OR CAST(pos AS TEXT) LIKE ?)"
    )
    args.extend([like, like, f"%{query}%", f"%{query}%", f"%{query}%"])

    sql = f"""
        SELECT payload FROM hits
        WHERE {' AND '.join(clauses)}
        ORDER BY score DESC
        LIMIT ?
    """
    args.append(limit)
    cur = conn.execute(sql, args)
    return [json.loads(row["payload"]) for row in cur.fetchall()]


def overview_variants(
    *,
    mode: str = "both",
    min_score: float | None = None,
    min_samples: int | None = None,
    max_samples: int | None = None,
    genes: list[str] | None = None,
    q: str | None = None,
    limit: int = 50,
    offset: int = 0,
    sort_by: str = "n_samples",
    sort_dir: str = "desc",
) -> dict[str, Any]:
    """Aggregate hits by (gene, chrom, pos, ref, alt) across samples."""
    conn = get_connection()
    mode_sql, mode_args = _mode_clause(mode)
    where = ["dataset = '5ultra'", mode_sql]
    args: list[Any] = list(mode_args)

    if min_score is not None:
        where.append("score >= ?")
        args.append(min_score)

    gene_list = _normalize_gene_list(genes)
    if gene_list:
        gin, gargs = _gene_in_clause(gene_list)
        where.append(gin)
        args.extend(gargs)

    if q:
        like = f"%{q.strip()}%"
        where.append("(gene LIKE ? OR chrom LIKE ? OR csq_class LIKE ?)")
        args.extend([like, like, like])

    where_sql = " AND ".join(where)
    having: list[str] = []
    having_args: list[Any] = []
    if min_samples is not None:
        having.append("COUNT(DISTINCT sample_id) >= ?")
        having_args.append(min_samples)
    if max_samples is not None:
        having.append("COUNT(DISTINCT sample_id) <= ?")
        having_args.append(max_samples)
    having_sql = f" HAVING {' AND '.join(having)}" if having else ""

    sort_columns = {
        "gene": "gene COLLATE NOCASE",
        "variant": "chrom COLLATE NOCASE, pos, ref, alt",
        "csq": "csq_class COLLATE NOCASE",
        "max_score": "max_score",
        "n_samples": "n_samples",
        "n_hits": "n_hits",
        "modes": "modes COLLATE NOCASE",
    }
    sort_key = sort_by if sort_by in sort_columns else "n_samples"
    direction = "ASC" if (sort_dir or "").lower() == "asc" else "DESC"
    # Put NULLs last for score-like columns when descending / first when ascending
    nulls = "NULLS LAST" if direction == "DESC" else "NULLS FIRST"
    if sort_key == "variant":
        order_sql = f"chrom COLLATE NOCASE {direction}, pos {direction}, ref {direction}, alt {direction}"
    elif sort_key in ("max_score", "n_samples", "n_hits"):
        order_sql = f"{sort_columns[sort_key]} {direction} {nulls}"
    else:
        order_sql = f"{sort_columns[sort_key]} {direction}"
    # Stable tie-breakers
    if sort_key != "n_samples":
        order_sql += ", n_samples DESC"
    if sort_key != "max_score":
        order_sql += ", max_score DESC"
    order_sql += ", gene, chrom, pos"

    base_cte = f"""
        WITH filtered AS (
            SELECT
                gene,
                chrom,
                pos,
                json_extract(payload, '$.ref') AS ref,
                json_extract(payload, '$.alt') AS alt,
                sample_id,
                mode,
                score,
                csq_class
            FROM hits
            WHERE {where_sql}
        ),
        grouped AS (
            SELECT
                gene,
                chrom,
                pos,
                ref,
                alt,
                COUNT(DISTINCT sample_id) AS n_samples,
                COUNT(*) AS n_hits,
                MAX(score) AS max_score,
                GROUP_CONCAT(DISTINCT sample_id) AS sample_ids,
                GROUP_CONCAT(DISTINCT mode) AS modes,
                (
                    SELECT f2.csq_class
                    FROM filtered f2
                    WHERE f2.gene = filtered.gene
                      AND f2.chrom = filtered.chrom
                      AND f2.pos = filtered.pos
                      AND IFNULL(f2.ref, '') = IFNULL(filtered.ref, '')
                      AND IFNULL(f2.alt, '') = IFNULL(filtered.alt, '')
                    ORDER BY f2.score DESC NULLS LAST
                    LIMIT 1
                ) AS csq_class
            FROM filtered
            GROUP BY gene, chrom, pos, ref, alt
            {having_sql}
        )
    """

    count_sql = base_cte + " SELECT COUNT(*) FROM grouped"
    total = conn.execute(count_sql, [*args, *having_args]).fetchone()[0]

    # Summary counts without min/max sample having (for cards)
    summary_sql = f"""
        WITH filtered AS (
            SELECT
                gene, chrom, pos,
                json_extract(payload, '$.ref') AS ref,
                json_extract(payload, '$.alt') AS alt,
                sample_id
            FROM hits
            WHERE {where_sql}
        ),
        grouped AS (
            SELECT gene, chrom, pos, ref, alt,
                   COUNT(DISTINCT sample_id) AS n_samples
            FROM filtered
            GROUP BY gene, chrom, pos, ref, alt
        )
        SELECT
            COUNT(*) AS total_variants,
            SUM(CASE WHEN n_samples >= 2 THEN 1 ELSE 0 END) AS multi_sample,
            SUM(CASE WHEN n_samples = 1 THEN 1 ELSE 0 END) AS singleton
        FROM grouped
    """
    summary_row = conn.execute(summary_sql, args).fetchone()

    list_sql = (
        base_cte
        + f"""
        SELECT * FROM grouped
        ORDER BY {order_sql}
        LIMIT ? OFFSET ?
        """
    )
    rows = conn.execute(list_sql, [*args, *having_args, limit, offset]).fetchall()

    variants = []
    for row in rows:
        sample_ids = sorted(
            {s for s in (row["sample_ids"] or "").split(",") if s},
            key=str.lower,
        )
        modes = sorted({m for m in (row["modes"] or "").split(",") if m})
        variants.append(
            {
                "gene": row["gene"],
                "chrom": row["chrom"],
                "pos": row["pos"],
                "ref": row["ref"] or "",
                "alt": row["alt"] or "",
                "csq_class": row["csq_class"],
                "max_score": row["max_score"],
                "n_samples": row["n_samples"],
                "n_hits": row["n_hits"],
                "sample_ids": sample_ids,
                "modes": modes,
            }
        )

    return {
        "total": total,
        "limit": limit,
        "offset": offset,
        "summary": {
            "total_variants": summary_row["total_variants"] or 0,
            "multi_sample": summary_row["multi_sample"] or 0,
            "singleton": summary_row["singleton"] or 0,
        },
        "variants": variants,
    }


def catalog_stats() -> dict[str, Any]:
    if not db_available():
        return {"available": False}
    conn = get_connection()
    sample_count = conn.execute(
        "SELECT COUNT(DISTINCT sample_id) FROM samples WHERE dataset='5ultra'"
    ).fetchone()[0]
    hit_count = conn.execute(
        "SELECT COUNT(*) FROM hits WHERE dataset='5ultra'"
    ).fetchone()[0]
    return {
        "available": True,
        "sample_count": sample_count,
        "hit_count": hit_count,
        "db_path": str(DB_PATH),
    }
