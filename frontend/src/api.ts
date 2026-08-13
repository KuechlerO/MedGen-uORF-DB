import type {
  AnalysisMode,
  GenePanelDetail,
  GenePanelSummary,
  Hit,
  OverviewResponse,
  SampleSummary,
  TracksResponse,
} from "./types";

const BASE = (import.meta.env.BASE_URL || "/").replace(/\/$/, "");

export type GeneFilter = {
  genes?: string[];
  panel?: string | null;
};

async function getJson<T>(path: string, init?: RequestInit): Promise<T> {
  const res = await fetch(`${BASE}${path}`, init);
  if (!res.ok) {
    const detail = await res.text();
    throw new Error(detail || res.statusText);
  }
  return res.json() as Promise<T>;
}

async function postJson<T>(path: string, body: unknown): Promise<T> {
  return getJson<T>(path, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(body),
  });
}

/** Prefer panel id; otherwise POST gene list (avoids nginx 414 on large panels). */
function usePostForGenes(filter?: GeneFilter): boolean {
  if (filter?.panel) return true;
  return Boolean(filter?.genes && filter.genes.length > 0);
}

export function listSamples(q?: string) {
  const qs = q ? `?q=${encodeURIComponent(q)}` : "";
  return getJson<{ count: number; samples: SampleSummary[] }>(`/api/samples${qs}`);
}

export function getSample(sampleId: string) {
  return getJson<SampleSummary>(`/api/samples/${encodeURIComponent(sampleId)}`);
}

export function getSampleHits(
  sampleId: string,
  params: {
    mode?: AnalysisMode;
    gene?: string;
    genes?: string[];
    panel?: string | null;
    q?: string;
    min_score?: number;
  } = {},
) {
  const path = `/api/samples/${encodeURIComponent(sampleId)}/hits`;
  if (usePostForGenes(params)) {
    return postJson<{ sample_id: string; mode: string; count: number; hits: Hit[] }>(
      path,
      {
        mode: params.mode ?? "both",
        gene: params.gene,
        genes: params.panel ? undefined : params.genes,
        panel: params.panel || undefined,
        q: params.q,
        min_score: params.min_score,
      },
    );
  }
  const sp = new URLSearchParams();
  if (params.mode) sp.set("mode", params.mode);
  if (params.gene) sp.set("gene", params.gene);
  if (params.q) sp.set("q", params.q);
  if (params.min_score != null) sp.set("min_score", String(params.min_score));
  const qs = sp.toString();
  return getJson<{ sample_id: string; mode: string; count: number; hits: Hit[] }>(
    `${path}${qs ? `?${qs}` : ""}`,
  );
}

export function searchHits(
  q: string,
  sample?: string | null,
  mode: AnalysisMode = "both",
  opts: { genes?: string[]; panel?: string | null; min_score?: number } = {},
) {
  if (usePostForGenes(opts)) {
    return postJson<{ query: string; count: number; hits: Hit[] }>("/api/search", {
      q,
      sample: sample || undefined,
      mode,
      genes: opts.panel ? undefined : opts.genes,
      panel: opts.panel || undefined,
      min_score: opts.min_score,
    });
  }
  const sp = new URLSearchParams({ q });
  if (sample) sp.set("sample", sample);
  sp.set("mode", mode);
  if (opts.min_score != null) sp.set("min_score", String(opts.min_score));
  return getJson<{ query: string; count: number; hits: Hit[] }>(
    `/api/search?${sp.toString()}`,
  );
}

export function listTracks(
  sample?: string | null,
  mode: AnalysisMode = "nosplice",
  hitMode?: AnalysisMode,
) {
  const sp = new URLSearchParams({ mode });
  if (sample) sp.set("sample", sample);
  if (hitMode && hitMode !== "both") sp.set("hit_mode", hitMode);
  return getJson<TracksResponse>(`/api/tracks?${sp.toString()}`);
}

export function listGenePanels(q?: string) {
  const qs = q ? `?q=${encodeURIComponent(q)}` : "";
  return getJson<{ count: number; panels: GenePanelSummary[] }>(
    `/api/gene-panels${qs}`,
  );
}

export function getGenePanel(panelId: string) {
  return getJson<GenePanelDetail>(
    `/api/gene-panels/${encodeURIComponent(panelId)}`,
  );
}

export function getOverviewVariants(params: {
  mode?: AnalysisMode;
  min_score?: number;
  min_samples?: number;
  max_samples?: number;
  genes?: string[];
  panel?: string | null;
  q?: string;
  limit?: number;
  offset?: number;
  sort_by?: string;
  sort_dir?: "asc" | "desc";
  zygosity_mode?: "any" | "uniform" | "all_het" | "all_hom";
} = {}) {
  return postJson<OverviewResponse>("/api/overview/variants", {
    mode: params.mode ?? "both",
    min_score: params.min_score,
    min_samples: params.min_samples,
    max_samples: params.max_samples,
    genes: params.panel ? undefined : params.genes,
    panel: params.panel || undefined,
    q: params.q,
    limit: params.limit ?? 50,
    offset: params.offset ?? 0,
    sort_by: params.sort_by ?? "n_samples",
    sort_dir: params.sort_dir ?? "desc",
    zygosity_mode: params.zygosity_mode ?? "any",
  });
}

export function ucscLink(chrom: string, start: number, end: number) {
  return getJson<{ url: string; position: string }>(
    `/api/ucsc?chrom=${encodeURIComponent(chrom)}&start=${start}&end=${end}`,
  );
}
