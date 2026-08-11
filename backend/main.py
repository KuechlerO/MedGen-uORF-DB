"""FastAPI backend for MedGen uORF explorer."""

from __future__ import annotations

import json
import os
import re
from functools import lru_cache
from pathlib import Path
from typing import Any

from db import (
    catalog_stats,
    db_available,
    get_sample,
    list_samples,
    overview_variants,
    query_hits,
    search_hits_global,
)
from fastapi import FastAPI, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from gene_panels import get_panel, list_panels, resolve_panel_genes
from pydantic import BaseModel, Field

ROOT = Path(__file__).resolve().parents[1]
TRACKS = ROOT / "data" / "tracks"
BY_SAMPLE = TRACKS / "by_sample"
REFERENCE = ROOT / "data" / "reference_genome"
FRONTEND_DIST = ROOT / "frontend" / "dist"

# Public URL prefix when behind nginx (e.g. /uorf-explorer). Empty for local root.
PUBLIC_BASE_PATH = os.environ.get("PUBLIC_BASE_PATH", "").rstrip("/")

FASTA_NAME = "GRCh38.p14.genome.fa.gz"
GTF_NAME = "gencode.v50.basic.annotation.gtf.gz"

CHROMOSOME_ORDER = [
    "chr1", "chr2", "chr3", "chr4", "chr5", "chr6", "chr7", "chr8", "chr9", "chr10",
    "chr11", "chr12", "chr13", "chr14", "chr15", "chr16", "chr17", "chr18", "chr19",
    "chr20", "chr21", "chr22", "chrX", "chrY", "chrM",
]


def public_url(path: str) -> str:
    """Prefix a site-absolute path with PUBLIC_BASE_PATH for browser/IGV fetches."""
    if not path.startswith("/"):
        path = f"/{path}"
    return f"{PUBLIC_BASE_PATH}{path}" if PUBLIC_BASE_PATH else path


app = FastAPI(
    title="MedGen uORF Explorer",
    description="Browse 5ULTRA perturbation candidates by sample in genome context.",
    version="0.2.0",
    # nginx strips PUBLIC_BASE_PATH via proxy_pass …/; leave root_path empty.
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@lru_cache(maxsize=1)
def load_hits_legacy() -> dict[str, Any]:
    path = TRACKS / "hits.json"
    if not path.exists():
        raise FileNotFoundError(
            f"Missing {path}. Run: python ingest/run_ingest.py example.tsv"
        )
    return json.loads(path.read_text())


def reference_status() -> dict[str, Any]:
    fasta = REFERENCE / FASTA_NAME
    gtf = REFERENCE / GTF_NAME
    return {
        "directory": str(REFERENCE),
        "fasta": fasta.exists(),
        "fasta_fai": (REFERENCE / f"{FASTA_NAME}.fai").exists(),
        "fasta_gzi": (REFERENCE / f"{FASTA_NAME}.gzi").exists(),
        "gtf": gtf.exists(),
        "gtf_tbi": (REFERENCE / f"{GTF_NAME}.tbi").exists(),
        "ready": all(
            [
                fasta.exists(),
                (REFERENCE / f"{FASTA_NAME}.fai").exists(),
                gtf.exists(),
                (REFERENCE / f"{GTF_NAME}.tbi").exists(),
            ]
        ),
    }


def _reference_config() -> dict[str, Any]:
    ref_base = public_url("/reference")
    reference: dict[str, Any] = {
        "id": "hg38",
        "name": "GRCh38.p14 (local)",
        "fastaURL": f"{ref_base}/{FASTA_NAME}",
        "indexURL": f"{ref_base}/{FASTA_NAME}.fai",
        "chromosomeOrder": CHROMOSOME_ORDER,
    }
    if (REFERENCE / f"{FASTA_NAME}.gzi").exists():
        reference["compressedIndexURL"] = f"{ref_base}/{FASTA_NAME}.gzi"
    return reference


def _uorfdb_track(base: str | None = None) -> dict[str, Any]:
    base = base or public_url("/tracks")
    uorfdb_gz = TRACKS / "uorfdb_uorfs.bed.gz"
    uorfdb_tbi = TRACKS / "uorfdb_uorfs.bed.gz.tbi"
    uorfdb_bed = TRACKS / "uorfdb_uorfs.bed"
    if uorfdb_gz.exists() and uorfdb_tbi.exists():
        return {
            "id": "uorfdb",
            "name": "uORFdb hg38",
            "type": "annotation",
            "format": "bed",
            "url": f"{base}/uorfdb_uorfs.bed.gz",
            "indexURL": f"{base}/uorfdb_uorfs.bed.gz.tbi",
            "color": "#2563eb",
            "displayMode": "EXPANDED",
            "source": "uORFdb",
        }
    track = {
        "id": "uorfdb",
        "name": "uORFdb hg38 (demo)",
        "type": "annotation",
        "format": "bed",
        "url": f"{base}/uorfdb_uorfs.bed",
        "color": "#2563eb",
        "displayMode": "EXPANDED",
        "source": "demo",
    }
    if not uorfdb_bed.exists():
        track["name"] = "uORFdb hg38 (missing — run prepare_uorfdb.sh)"
    return track


def _gene_track(ref: dict[str, Any], ref_base: str | None = None) -> dict[str, Any]:
    ref_base = ref_base or public_url("/reference")
    if ref["gtf"] and ref["gtf_tbi"]:
        return {
            "id": "genes",
            "name": "GENCODE v50 basic",
            "type": "annotation",
            "format": "gtf",
            "url": f"{ref_base}/{GTF_NAME}",
            "indexURL": f"{ref_base}/{GTF_NAME}.tbi",
            "source": "local",
            "removable": False,
            "displayMode": "EXPANDED",
        }
    return {
        "id": "genes",
        "name": "RefSeq Genes (remote fallback)",
        "type": "annotation",
        "format": "refgene",
        "url": "https://s3.amazonaws.com/igv.org.genomes/hg38/ncbiRefSeq.sorted.txt.gz",
        "indexURL": "https://s3.amazonaws.com/igv.org.genomes/hg38/ncbiRefSeq.sorted.txt.gz.tbi",
        "source": "igv.org",
        "removable": False,
    }


def _sample_track_base(sample_id: str, mode: str) -> str:
    return public_url(f"/tracks/by_sample/{sample_id}/{mode}")


def _resolve_track_mode(mode: str, hit_mode: str | None) -> str:
    if mode == "both":
        return hit_mode if hit_mode in ("splice", "nosplice") else "nosplice"
    return mode


@app.get("/api/health")
def health() -> dict[str, Any]:
    ref = reference_status()
    catalog = catalog_stats()
    payload: dict[str, Any] = {
        "ok": True,
        "genome": "hg38",
        "public_base_path": PUBLIC_BASE_PATH or "/",
        "reference": ref,
        "catalog": catalog,
    }
    if catalog.get("available"):
        payload["sample_count"] = catalog.get("sample_count")
        payload["hit_count"] = catalog.get("hit_count")
    else:
        try:
            data = load_hits_legacy()
            payload["hit_count"] = data.get("hit_count")
            payload["gene_count"] = data.get("gene_count")
            payload["legacy"] = True
        except FileNotFoundError as exc:
            payload["ok"] = False
            payload["error"] = str(exc)
    return payload


@app.get("/api/samples")
def api_list_samples(q: str | None = Query(None)) -> dict[str, Any]:
    if not db_available():
        raise HTTPException(
            status_code=503,
            detail="Catalog not built. Run: bash scripts/prepare_cohort.sh",
        )
    samples = list_samples(q=q)
    return {"count": len(samples), "samples": samples}


@app.get("/api/samples/{sample_id}")
def api_get_sample(sample_id: str) -> dict[str, Any]:
    if not db_available():
        raise HTTPException(status_code=503, detail="Catalog not built")
    sample = get_sample(sample_id)
    if not sample:
        raise HTTPException(status_code=404, detail=f"Sample not found: {sample_id}")
    return sample


def _parse_genes_param(
    genes: str | None = None,
    genes_list: list[str] | None = None,
) -> list[str] | None:
    collected: list[str] = []
    if genes:
        collected.extend(genes.replace(";", ",").split(","))
    if genes_list:
        collected.extend(genes_list)
    out = [g.strip() for g in collected if g and g.strip()]
    return out or None


def _resolve_genes(
    *,
    genes: str | None = None,
    genes_list: list[str] | None = None,
    panel: str | None = None,
) -> list[str] | None:
    """Prefer panel id (avoids huge URLs); otherwise use explicit gene lists."""
    if panel:
        resolved = resolve_panel_genes(panel)
        if resolved is None:
            raise HTTPException(status_code=404, detail=f"Panel not found: {panel}")
        return resolved
    return _parse_genes_param(genes, genes_list)


class HitsFilterBody(BaseModel):
    mode: str = Field("both", pattern="^(nosplice|splice|both)$")
    gene: str | None = None
    genes: list[str] | None = None
    panel: str | None = None
    q: str | None = None
    min_score: float | None = None
    limit: int = Field(5000, ge=1, le=20000)


class SearchFilterBody(BaseModel):
    q: str = Field(..., min_length=1)
    sample: str | None = None
    mode: str = Field("both", pattern="^(nosplice|splice|both)$")
    genes: list[str] | None = None
    panel: str | None = None
    min_score: float | None = None


class OverviewFilterBody(BaseModel):
    mode: str = Field("both", pattern="^(nosplice|splice|both)$")
    min_score: float | None = None
    min_samples: int | None = Field(None, ge=1)
    max_samples: int | None = Field(None, ge=1)
    genes: list[str] | None = None
    panel: str | None = None
    q: str | None = None
    limit: int = Field(50, ge=1, le=500)
    offset: int = Field(0, ge=0)
    sort_by: str = Field(
        "n_samples",
        pattern="^(gene|variant|csq|max_score|n_samples|n_hits|modes)$",
    )
    sort_dir: str = Field("desc", pattern="^(asc|desc)$")


def _run_sample_hits(
    sample_id: str,
    *,
    mode: str,
    gene: str | None,
    gene_filter: list[str] | None,
    q: str | None,
    min_score: float | None,
    limit: int,
) -> dict[str, Any]:
    if not db_available():
        raise HTTPException(status_code=503, detail="Catalog not built")
    if not get_sample(sample_id):
        raise HTTPException(status_code=404, detail=f"Sample not found: {sample_id}")
    hits = query_hits(
        sample_id,
        mode=mode,
        gene=gene,
        genes=gene_filter,
        q=q,
        min_score=min_score,
        limit=limit,
    )
    return {"sample_id": sample_id, "mode": mode, "count": len(hits), "hits": hits}


@app.get("/api/samples/{sample_id}/hits")
def api_sample_hits_get(
    sample_id: str,
    mode: str = Query("both", pattern="^(nosplice|splice|both)$"),
    gene: str | None = Query(None),
    genes: str | None = Query(None, description="Comma-separated gene symbols (small lists)"),
    panel: str | None = Query(None, description="Gene panel id (preferred for large panels)"),
    q: str | None = Query(None),
    min_score: float | None = Query(None),
    limit: int = Query(5000, ge=1, le=20000),
) -> dict[str, Any]:
    return _run_sample_hits(
        sample_id,
        mode=mode,
        gene=gene,
        gene_filter=_resolve_genes(genes=genes, panel=panel),
        q=q,
        min_score=min_score,
        limit=limit,
    )


@app.post("/api/samples/{sample_id}/hits")
def api_sample_hits_post(sample_id: str, body: HitsFilterBody) -> dict[str, Any]:
    return _run_sample_hits(
        sample_id,
        mode=body.mode,
        gene=body.gene,
        gene_filter=_resolve_genes(genes_list=body.genes, panel=body.panel),
        q=body.q,
        min_score=body.min_score,
        limit=body.limit,
    )


LOCUS_RE = re.compile(
    r"^(?:chr)?(?P<chrom>[0-9XYM]+):(?P<pos>\d+)(?:-(?P<end>\d+))?$",
    re.IGNORECASE,
)


def _run_search(
    *,
    query: str,
    sample: str | None,
    mode: str,
    gene_filter: list[str] | None,
    min_score: float | None,
) -> dict[str, Any]:
    if db_available():
        hits = search_hits_global(
            query,
            sample_id=sample,
            mode=mode,
            genes=gene_filter,
            min_score=min_score,
        )
        return {"query": query, "count": len(hits), "hits": hits, "sample": sample, "mode": mode}

    data = load_hits_legacy()
    q_upper = query.upper()
    hits: list[dict[str, Any]] = []
    locus = LOCUS_RE.match(query.replace(",", ""))
    if locus:
        chrom_token = locus.group("chrom")
        chrom = chrom_token if chrom_token.lower().startswith("chr") else f"chr{chrom_token}"
        pos = int(locus.group("pos"))
        end = int(locus.group("end")) if locus.group("end") else pos
        for hit in data["hits"]:
            if hit["chrom"].lower() != chrom.lower():
                continue
            if end == pos:
                if hit["pos"] == pos:
                    hits.append(hit)
            else:
                window = hit.get("window") or {}
                if window.get("start", 0) <= end and window.get("end", 0) >= pos:
                    hits.append(hit)
    else:
        for hit in data["hits"]:
            if q_upper in hit["gene"].upper():
                hits.append(hit)
                continue
            if any(q_upper in t.upper() for t in hit.get("transcripts") or []):
                hits.append(hit)
                continue
            if q_upper in hit.get("csq", "").upper():
                hits.append(hit)
    if gene_filter:
        allowed = {g.upper() for g in gene_filter}
        hits = [h for h in hits if h.get("gene", "").upper() in allowed]
    if min_score is not None:
        hits = [h for h in hits if (h.get("score") or 0) >= min_score]
    hits = sorted(hits, key=lambda h: (-(h.get("score") or 0), h.get("gene", ""), h.get("pos", 0)))
    return {"query": query, "count": len(hits), "hits": hits}


@app.get("/api/search")
def search_get(
    q: str = Query(..., min_length=1),
    sample: str | None = Query(None),
    mode: str = Query("both", pattern="^(nosplice|splice|both)$"),
    genes: str | None = Query(None),
    panel: str | None = Query(None),
    min_score: float | None = Query(None),
) -> dict[str, Any]:
    return _run_search(
        query=q.strip(),
        sample=sample,
        mode=mode,
        gene_filter=_resolve_genes(genes=genes, panel=panel),
        min_score=min_score,
    )


@app.post("/api/search")
def search_post(body: SearchFilterBody) -> dict[str, Any]:
    return _run_search(
        query=body.q.strip(),
        sample=body.sample,
        mode=body.mode,
        gene_filter=_resolve_genes(genes_list=body.genes, panel=body.panel),
        min_score=body.min_score,
    )


@app.get("/api/gene-panels")
def api_list_gene_panels(q: str | None = Query(None)) -> dict[str, Any]:
    panels = list_panels(q=q)
    return {"count": len(panels), "panels": panels}


@app.get("/api/gene-panels/{panel_id:path}")
def api_get_gene_panel(panel_id: str) -> dict[str, Any]:
    panel = get_panel(panel_id)
    if not panel:
        raise HTTPException(status_code=404, detail=f"Panel not found: {panel_id}")
    return panel


def _run_overview(
    *,
    mode: str,
    min_score: float | None,
    min_samples: int | None,
    max_samples: int | None,
    gene_filter: list[str] | None,
    q: str | None,
    limit: int,
    offset: int,
    sort_by: str = "n_samples",
    sort_dir: str = "desc",
) -> dict[str, Any]:
    if not db_available():
        raise HTTPException(status_code=503, detail="Catalog not built")
    return overview_variants(
        mode=mode,
        min_score=min_score,
        min_samples=min_samples,
        max_samples=max_samples,
        genes=gene_filter,
        q=q,
        limit=limit,
        offset=offset,
        sort_by=sort_by,
        sort_dir=sort_dir,
    )


@app.get("/api/overview/variants")
def api_overview_variants_get(
    mode: str = Query("both", pattern="^(nosplice|splice|both)$"),
    min_score: float | None = Query(None),
    min_samples: int | None = Query(None, ge=1),
    max_samples: int | None = Query(None, ge=1),
    genes: str | None = Query(None),
    panel: str | None = Query(None),
    q: str | None = Query(None),
    limit: int = Query(50, ge=1, le=500),
    offset: int = Query(0, ge=0),
    sort_by: str = Query(
        "n_samples",
        pattern="^(gene|variant|csq|max_score|n_samples|n_hits|modes)$",
    ),
    sort_dir: str = Query("desc", pattern="^(asc|desc)$"),
) -> dict[str, Any]:
    return _run_overview(
        mode=mode,
        min_score=min_score,
        min_samples=min_samples,
        max_samples=max_samples,
        gene_filter=_resolve_genes(genes=genes, panel=panel),
        q=q,
        limit=limit,
        offset=offset,
        sort_by=sort_by,
        sort_dir=sort_dir,
    )


@app.post("/api/overview/variants")
def api_overview_variants_post(body: OverviewFilterBody) -> dict[str, Any]:
    return _run_overview(
        mode=body.mode,
        min_score=body.min_score,
        min_samples=body.min_samples,
        max_samples=body.max_samples,
        gene_filter=_resolve_genes(genes_list=body.genes, panel=body.panel),
        q=body.q,
        limit=body.limit,
        offset=body.offset,
        sort_by=body.sort_by,
        sort_dir=body.sort_dir,
    )


@app.get("/api/tracks")
def list_tracks(
    sample: str | None = Query(None),
    mode: str = Query("nosplice", pattern="^(nosplice|splice|both)$"),
    hit_mode: str | None = Query(None),
) -> dict[str, Any]:
    ref = reference_status()
    reference = _reference_config()
    tracks: list[dict[str, Any]] = [_gene_track(ref), _uorfdb_track()]

    track_mode = _resolve_track_mode(mode, hit_mode)
    if sample and db_available() and get_sample(sample):
        base = _sample_track_base(sample, track_mode)
        tracks.extend(
            [
                {
                    "id": "utr5",
                    "name": f"5ULTRA 5′ UTR span ({sample})",
                    "type": "annotation",
                    "format": "bed",
                    "url": f"{base}/utr5.bed",
                    "color": "#6b7280",
                    "displayMode": "EXPANDED",
                },
                {
                    "id": "perturbed",
                    "name": f"5ULTRA affected uORF ({track_mode})",
                    "type": "annotation",
                    "format": "bed",
                    "url": f"{base}/perturbed_uorfs.bed",
                    "color": "#dc2626",
                    "displayMode": "EXPANDED",
                },
                {
                    "id": "variants",
                    "name": f"5ULTRA variants ({track_mode})",
                    "type": "variant",
                    "format": "vcf",
                    "url": f"{base}/variants.vcf",
                    "color": "#ea580c",
                },
            ]
        )
    else:
        base = public_url("/tracks")
        tracks.extend(
            [
                {
                    "id": "utr5",
                    "name": "5ULTRA 5′ UTR span",
                    "type": "annotation",
                    "format": "bed",
                    "url": f"{base}/utr5.bed",
                    "color": "#6b7280",
                    "displayMode": "EXPANDED",
                },
                {
                    "id": "perturbed",
                    "name": "5ULTRA affected uORF",
                    "type": "annotation",
                    "format": "bed",
                    "url": f"{base}/perturbed_uorfs.bed",
                    "color": "#dc2626",
                    "displayMode": "EXPANDED",
                },
                {
                    "id": "variants",
                    "name": "5ULTRA variants",
                    "type": "variant",
                    "format": "vcf",
                    "url": f"{base}/variants.vcf",
                    "color": "#ea580c",
                },
            ]
        )

    return {
        "genome": "hg38",
        "reference": reference,
        "reference_ready": ref["ready"],
        "reference_status": ref,
        "sample": sample,
        "mode": track_mode,
        "tracks": tracks,
    }


# Legacy gene endpoints (demo hits.json fallback)
@app.get("/api/genes")
def list_genes() -> dict[str, Any]:
    if db_available():
        raise HTTPException(
            status_code=410,
            detail="Use /api/samples and /api/samples/{id}/hits with the cohort catalog",
        )
    data = load_hits_legacy()
    genes = [
        {
            "gene": g["gene"],
            "chrom": g["chrom"],
            "start": g["start"],
            "end": g["end"],
            "locus": g["locus"],
            "hit_count": g["hit_count"],
            "max_score": g["max_score"],
        }
        for g in data["genes"]
    ]
    return {"genes": genes}


@app.get("/api/gene/{symbol}")
def get_gene(symbol: str) -> dict[str, Any]:
    if db_available():
        raise HTTPException(status_code=410, detail="Use /api/samples/{id}/hits")
    data = load_hits_legacy()
    symbol_u = symbol.upper()
    for gene in data["genes"]:
        if gene["gene"].upper() == symbol_u:
            return gene
    raise HTTPException(status_code=404, detail=f"Gene not found: {symbol}")


@app.get("/api/ucsc")
def ucsc_link(
    chrom: str = Query(...),
    start: int = Query(...),
    end: int = Query(...),
) -> dict[str, str]:
    position = f"{chrom}:{start}-{end}"
    url = (
        "https://genome.ucsc.edu/cgi-bin/hgTracks"
        f"?db=hg38&position={position}"
    )
    return {"url": url, "position": position}


if TRACKS.exists():
    app.mount("/tracks", StaticFiles(directory=str(TRACKS)), name="tracks")
if REFERENCE.exists():
    app.mount("/reference", StaticFiles(directory=str(REFERENCE)), name="reference")

# Production UI (built with Vite base = PUBLIC_BASE_PATH/). Mount last.
if FRONTEND_DIST.is_dir() and (FRONTEND_DIST / "index.html").exists():
    assets_dir = FRONTEND_DIST / "assets"
    if assets_dir.is_dir():
        app.mount("/assets", StaticFiles(directory=str(assets_dir)), name="assets")

    @app.get("/")
    def spa_index() -> FileResponse:
        return FileResponse(FRONTEND_DIST / "index.html")


def create_app() -> FastAPI:
    return app


if __name__ == "__main__":
    import uvicorn

    port = int(os.environ.get("PORT", "8001"))
    uvicorn.run("main:app", host="0.0.0.0", port=port, reload=True)
