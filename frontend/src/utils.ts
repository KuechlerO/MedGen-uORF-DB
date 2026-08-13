export const CSQ_COLORS: Record<string, string> = {
  uStart_loss: "#b45309",
  uStart_gain: "#0f766e",
  uStop_loss: "#7c3aed",
  uStop_gain: "#dc2626",
  uORF_missense: "#2563eb",
  uORF_synonymous: "#64748b",
  unknown: "#6b7280",
};

export const RECOMMENDED_SCORE_THRESHOLD = 0.74;

export function csqColor(csqClass: string): string {
  return CSQ_COLORS[csqClass] ?? CSQ_COLORS.unknown;
}

export function formatScore(score: number | null | undefined): string {
  if (score === null || score === undefined || Number.isNaN(score)) return "—";
  return score.toFixed(3);
}

export function shortAllele(allele: string, maxLen = 12): string {
  if (!allele) return "—";
  if (allele.length <= maxLen) return allele;
  return `${allele.slice(0, maxLen)}…(+${allele.length - maxLen} bp)`;
}

export function variantLabel(hit: {
  chrom: string;
  pos: number;
  ref: string;
  alt: string;
}): string {
  return `${hit.chrom}:${hit.pos} ${hit.ref}>${hit.alt}`;
}

export function variantLabelShort(hit: {
  chrom: string;
  pos: number;
  ref: string;
  alt: string;
}): string {
  return `${hit.chrom}:${hit.pos} ${shortAllele(hit.ref)}>${shortAllele(hit.alt)}`;
}

export function parseGeneList(text: string): string[] {
  const seen = new Set<string>();
  const out: string[] = [];
  for (const token of text.split(/[\s,;]+/)) {
    const g = token.trim().toUpperCase();
    if (!g || seen.has(g)) continue;
    seen.add(g);
    out.push(g);
  }
  return out;
}

const ZYGOSITY_LABELS: Record<string, string> = {
  het: "Heterozygous",
  hom: "Homozygous",
  hom_ref: "Homozygous ref",
  multi: "Multi-allelic",
  unknown: "Unknown",
};

/** Soft chip colors for cohort overview sample tiles. */
export const ZYGOSITY_COLORS: Record<string, { bg: string; border: string; text: string }> = {
  het: { bg: "#dbeafe", border: "#93c5fd", text: "#1e3a8a" },
  hom: { bg: "#ffedd5", border: "#fdba74", text: "#9a3412" },
  hom_ref: { bg: "#f3f4f6", border: "#d1d5db", text: "#4b5563" },
  multi: { bg: "#ede9fe", border: "#c4b5fd", text: "#5b21b6" },
  unknown: { bg: "#f8fafc", border: "#cbd5e1", text: "#64748b" },
};

export function formatZygosity(zygosity: string | null | undefined): string {
  if (!zygosity) return "—";
  return ZYGOSITY_LABELS[zygosity] ?? zygosity;
}

export function zygosityStyle(zygosity: string | null | undefined) {
  return ZYGOSITY_COLORS[zygosity || "unknown"] ?? ZYGOSITY_COLORS.unknown;
}

/** GeneCards gene page. */
export function geneCardsUrl(gene: string): string | null {
  const symbol = (gene || "").trim();
  if (!symbol) return null;
  return `https://www.genecards.org/cgi-bin/carddisp.pl?gene=${encodeURIComponent(symbol)}`;
}

/**
 * gnomAD v4 variant page (GRCh38 / hg38).
 * ID format: chrom-pos-ref-alt without a chr prefix.
 */
export function gnomadVariantUrl(variant: {
  chrom: string;
  pos: number;
  ref: string;
  alt: string;
}): string | null {
  const chrom = (variant.chrom || "").replace(/^chr/i, "");
  const ref = (variant.ref || "").trim();
  const alt = (variant.alt || "").trim();
  if (!chrom || !variant.pos || !ref || !alt) return null;
  const id = `${chrom}-${variant.pos}-${ref}-${alt}`;
  return `https://gnomad.broadinstitute.org/variant/${encodeURIComponent(id)}?dataset=gnomad_r4`;
}
