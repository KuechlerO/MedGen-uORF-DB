"""Enrich hit payloads with structured genotype / zygosity."""

from __future__ import annotations

from typing import Any


def parse_genotype(genotype: str | None, *, format_field: str = "GT:AD:DP:GQ:PL") -> dict[str, Any]:
    """Parse a VCF sample genotype string into structured fields.

    5ULTRA TSVs carry GATK-style values such as ``1/1:0,36:36:99:…`` with
    FORMAT ``GT:AD:DP:GQ:PL``.
    """
    raw = (genotype or "").strip()
    out: dict[str, Any] = {
        "gt": None,
        "zygosity": "unknown",
        "allele_depths": None,
        "depth": None,
        "gq": None,
    }
    if not raw or raw == ".":
        return out

    keys = [k.strip() for k in (format_field or "GT").split(":") if k.strip()]
    vals = raw.split(":")
    fields = {keys[i]: vals[i] for i in range(min(len(keys), len(vals)))}
    # Always treat the first colon-delimited token as GT if FORMAT unknown
    gt = (fields.get("GT") or vals[0] or "").strip()
    if not gt or gt == ".":
        return out
    out["gt"] = gt

    ad = fields.get("AD")
    if ad and ad != ".":
        depths: list[int] = []
        for part in ad.split(","):
            try:
                depths.append(int(part))
            except ValueError:
                depths = []
                break
        if depths:
            out["allele_depths"] = depths

    for key, dest in (("DP", "depth"), ("GQ", "gq")):
        val = fields.get(key)
        if val and val != ".":
            try:
                out[dest] = int(val)
            except ValueError:
                pass

    out["zygosity"] = _zygosity_from_gt(gt)
    return out


def is_hom_ref_genotype(genotype: str | None) -> bool:
    """True when the primary-sample GT is homozygous reference (0/0 or 0|0)."""
    return parse_genotype(genotype)["zygosity"] == "hom_ref"


def _zygosity_from_gt(gt: str) -> str:
    alleles = [a for a in gt.replace("|", "/").split("/") if a != ""]
    if len(alleles) < 2 or any(a == "." for a in alleles):
        return "unknown"
    try:
        nums = [int(a) for a in alleles]
    except ValueError:
        return "unknown"
    if all(n == 0 for n in nums):
        return "hom_ref"
    if len(set(nums)) == 1:
        return "hom" if nums[0] > 0 else "hom_ref"
    if 0 in nums and any(n > 0 for n in nums):
        return "het"
    return "multi"


def enrich_hit(hit: dict[str, Any]) -> dict[str, Any]:
    """Return a shallow-copied hit with genotype fields attached."""
    out = dict(hit)
    parsed = parse_genotype(out.get("genotype"))
    out["gt"] = parsed["gt"]
    out["zygosity"] = parsed["zygosity"]
    out["allele_depths"] = parsed["allele_depths"]
    out["depth"] = parsed["depth"]
    out["gq"] = parsed["gq"]
    return out


def enrich_hits(hits: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Enrich hits and drop primary-sample homozygous-ref (non-carrier) rows."""
    out: list[dict[str, Any]] = []
    for h in hits:
        enriched = enrich_hit(h)
        if enriched.get("zygosity") == "hom_ref":
            continue
        out.append(enriched)
    return out
