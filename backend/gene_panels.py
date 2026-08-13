"""Load curated + Genomics England + OMIM gene panels from data/genePanels/."""

from __future__ import annotations

import csv
from functools import lru_cache
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
PANELS_DIR = ROOT / "data" / "genePanels"
OVERVIEW = PANELS_DIR / "panels_overview.csv"
GE_PANELS = PANELS_DIR / "genomicsEngland_panels_extended.csv"
MIM2GENE = PANELS_DIR / "mim2gene.txt"


def _normalize_genes(raw: list[str] | str) -> list[str]:
    if isinstance(raw, str):
        tokens = raw.replace(";", ",").split(",")
    else:
        tokens = raw
    seen: set[str] = set()
    out: list[str] = []
    for token in tokens:
        g = token.strip().upper()
        if not g or g in seen:
            continue
        seen.add(g)
        out.append(g)
    return out


@lru_cache(maxsize=1)
def load_all_panels() -> dict[str, dict[str, Any]]:
    """Return panel_id → {id, name, source, curated, genes}."""
    panels: dict[str, dict[str, Any]] = {}

    if OVERVIEW.exists():
        with OVERVIEW.open(newline="", encoding="utf-8") as fh:
            for row in csv.DictReader(fh):
                number = (row.get("number") or "").strip()
                input_file = (row.get("input_file") or "").strip()
                if not number or not input_file:
                    continue
                path = PANELS_DIR / input_file
                if not path.exists():
                    continue
                genes: list[str] = []
                with path.open(newline="", encoding="utf-8") as pf:
                    for prow in csv.DictReader(pf):
                        sym = (prow.get("genesymbol") or prow.get("symbol") or "").strip()
                        if sym:
                            genes.append(sym)
                genes = _normalize_genes(genes)
                pid = f"curated:{number}"
                panels[pid] = {
                    "id": pid,
                    "name": (row.get("name") or input_file).strip(),
                    "source": (row.get("source") or "curated").strip(),
                    "version": (row.get("version") or "").strip(),
                    "hyperlink": (row.get("hyperlink") or "").strip(),
                    "curated": True,
                    "gene_count": len(genes),
                    "genes": genes,
                }

    if GE_PANELS.exists():
        with GE_PANELS.open(newline="", encoding="utf-8") as fh:
            for row in csv.DictReader(fh):
                ge_id = (row.get("id") or "").strip()
                if not ge_id:
                    continue
                genes = _normalize_genes(row.get("gene_list") or "")
                pid = f"gel:{ge_id}"
                panels[pid] = {
                    "id": pid,
                    "name": (row.get("name") or f"Panel {ge_id}").strip(),
                    "source": "Genomics England PanelApp",
                    "version": (row.get("version") or "").strip(),
                    "disease_group": (row.get("disease_group") or "").strip(),
                    "disease_sub_group": (row.get("disease_sub_group") or "").strip(),
                    "curated": False,
                    "gene_count": len(genes),
                    "genes": genes,
                }

    omim = _load_omim_genes()
    if omim:
        panels["omim:genes"] = omim

    return panels


def _load_omim_genes() -> dict[str, Any] | None:
    """Build an OMIM gene panel from mim2gene.txt (gene entries with HGNC symbols)."""
    if not MIM2GENE.exists():
        return None
    genes: list[str] = []
    version = ""
    with MIM2GENE.open(encoding="utf-8") as fh:
        for line in fh:
            if line.startswith("#"):
                if line.startswith("# Generated:"):
                    version = line.split(":", 1)[1].strip()
                continue
            parts = line.rstrip("\n").split("\t")
            if len(parts) < 4:
                continue
            entry_type = parts[1].strip().lower()
            # OMIM gene / gene+phenotype loci with an approved symbol
            if entry_type not in {"gene", "gene/phenotype"}:
                continue
            symbol = parts[3].strip()
            if symbol:
                genes.append(symbol)
    genes = _normalize_genes(genes)
    if not genes:
        return None
    return {
        "id": "omim:genes",
        "name": "OMIM genes",
        "source": "OMIM",
        "version": version,
        "hyperlink": "https://www.omim.org/",
        "curated": True,
        "gene_count": len(genes),
        "genes": genes,
    }


def list_panels(q: str | None = None) -> list[dict[str, Any]]:
    panels = load_all_panels()
    items = []
    q_norm = (q or "").strip().lower()
    for p in panels.values():
        if q_norm and q_norm not in p["name"].lower() and q_norm not in p["source"].lower():
            continue
        items.append(
            {
                "id": p["id"],
                "name": p["name"],
                "source": p["source"],
                "version": p.get("version", ""),
                "curated": p["curated"],
                "gene_count": p["gene_count"],
                "hyperlink": p.get("hyperlink", ""),
                "disease_group": p.get("disease_group", ""),
                "disease_sub_group": p.get("disease_sub_group", ""),
            }
        )
    # Curated first, then name
    items.sort(key=lambda x: (not x["curated"], x["name"].lower()))
    return items


def get_panel(panel_id: str) -> dict[str, Any] | None:
    panels = load_all_panels()
    p = panels.get(panel_id)
    if not p:
        return None
    return {
        "id": p["id"],
        "name": p["name"],
        "source": p["source"],
        "version": p.get("version", ""),
        "curated": p["curated"],
        "gene_count": p["gene_count"],
        "genes": p["genes"],
        "hyperlink": p.get("hyperlink", ""),
        "disease_group": p.get("disease_group", ""),
        "disease_sub_group": p.get("disease_sub_group", ""),
    }


def resolve_panel_genes(panel_id: str | None) -> list[str] | None:
    if not panel_id:
        return None
    panel = get_panel(panel_id)
    if not panel:
        return None
    return panel["genes"]
