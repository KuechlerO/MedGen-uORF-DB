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
