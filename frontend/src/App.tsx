import { useCallback, useEffect, useMemo, useState } from "react";
import type { FormEvent } from "react";
import {
  getSampleHits,
  listSamples,
  listTracks,
  searchHits,
  ucscLink,
} from "./api";
import { CohortOverview } from "./CohortOverview";
import { DetailPanel } from "./DetailPanel";
import { GenePanelFilter } from "./GenePanelFilter";
import { GenomeBrowser } from "./GenomeBrowser";
import { HitsTable } from "./HitsTable";
import { TrackLegend } from "./TrackLegend";
import type {
  AnalysisMode,
  AppSection,
  GeneFilterSelection,
  Hit,
  ReferenceConfig,
  SampleSummary,
  TrackConfig,
} from "./types";
import { CSQ_COLORS, RECOMMENDED_SCORE_THRESHOLD } from "./utils";

export default function App() {
  const [section, setSection] = useState<AppSection>("browser");
  const [samples, setSamples] = useState<SampleSummary[]>([]);
  const [sampleQuery, setSampleQuery] = useState("");
  const [selectedSample, setSelectedSample] = useState<SampleSummary | null>(null);
  const [mode, setMode] = useState<AnalysisMode>("both");
  const [geneQuery, setGeneQuery] = useState("");
  const [filterGenes, setFilterGenes] = useState<string[]>([]);
  const [filterPanelId, setFilterPanelId] = useState<string | null>(null);
  const [useThreshold, setUseThreshold] = useState(true);
  const [hits, setHits] = useState<Hit[]>([]);
  const [tracks, setTracks] = useState<TrackConfig[]>([]);
  const [reference, setReference] = useState<ReferenceConfig | null>(null);
  const [selected, setSelected] = useState<Hit | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(false);

  const minScore = useThreshold ? RECOMMENDED_SCORE_THRESHOLD : undefined;

  const loadTracks = useCallback(
    async (sampleId: string, analysisMode: AnalysisMode, hit: Hit | null) => {
      const hitMode =
        hit?.mode && hit.mode !== "both" ? (hit.mode as AnalysisMode) : undefined;
      const t = await listTracks(sampleId, analysisMode, hitMode);
      setTracks(t.tracks);
      setReference(t.reference);
    },
    [],
  );

  const loadSampleHits = useCallback(
    async (
      sample: SampleSummary,
      analysisMode: AnalysisMode,
      opts: {
        q?: string;
        genes?: string[];
        panel?: string | null;
        min_score?: number;
      } = {},
    ) => {
      setLoading(true);
      setError(null);
      try {
        const q = opts.q?.trim();
        const panel = opts.panel || undefined;
        const genes =
          panel || !opts.genes?.length ? undefined : opts.genes;
        let resultHits: Hit[];
        if (q) {
          const result = await searchHits(q, sample.sample_id, analysisMode, {
            genes,
            panel,
            min_score: opts.min_score,
          });
          resultHits = result.hits;
        } else {
          const result = await getSampleHits(sample.sample_id, {
            mode: analysisMode,
            genes,
            panel,
            min_score: opts.min_score,
          });
          resultHits = result.hits;
        }
        setHits(resultHits);
        const first = resultHits[0] ?? null;
        setSelected(first);
        await loadTracks(sample.sample_id, analysisMode, first);
      } catch (err) {
        setError(err instanceof Error ? err.message : String(err));
      } finally {
        setLoading(false);
      }
    },
    [loadTracks],
  );

  useEffect(() => {
    void (async () => {
      try {
        const { samples: listed } = await listSamples();
        setSamples(listed);
        const preferred =
          listed.find((s) => s.sample_id === "10_0463") ?? listed[0] ?? null;
        if (preferred) {
          setSelectedSample(preferred);
          setSampleQuery(preferred.sample_id);
          await loadSampleHits(preferred, "both", {
            min_score: RECOMMENDED_SCORE_THRESHOLD,
          });
        }
      } catch (err) {
        setError(err instanceof Error ? err.message : String(err));
      }
    })();
    // eslint-disable-next-line react-hooks/exhaustive-deps -- bootstrap once
  }, []);

  const locus = useMemo(() => {
    if (selected?.window?.locus) return selected.window.locus;
    if (hits[0]?.window?.locus) return hits[0].window.locus;
    return null;
  }, [selected, hits]);

  async function onSelectSample(sample: SampleSummary) {
    setSelectedSample(sample);
    setSampleQuery(sample.sample_id);
    await loadSampleHits(sample, mode, {
      q: geneQuery,
      genes: filterGenes,
      panel: filterPanelId,
      min_score: minScore,
    });
  }

  async function onModeChange(next: AnalysisMode) {
    setMode(next);
    if (!selectedSample) return;
    await loadSampleHits(selectedSample, next, {
      q: geneQuery,
      genes: filterGenes,
      panel: filterPanelId,
      min_score: minScore,
    });
  }

  async function applyFilters(e?: FormEvent) {
    e?.preventDefault();
    if (!selectedSample) return;
    await loadSampleHits(selectedSample, mode, {
      q: geneQuery,
      genes: filterGenes,
      panel: filterPanelId,
      min_score: minScore,
    });
  }

  async function onThresholdChange(checked: boolean) {
    setUseThreshold(checked);
    if (!selectedSample) return;
    await loadSampleHits(selectedSample, mode, {
      q: geneQuery,
      genes: filterGenes,
      panel: filterPanelId,
      min_score: checked ? RECOMMENDED_SCORE_THRESHOLD : undefined,
    });
  }

  async function onGenesChange(sel: GeneFilterSelection) {
    setFilterGenes(sel.genes);
    setFilterPanelId(sel.panelId);
    if (!selectedSample) return;
    await loadSampleHits(selectedSample, mode, {
      q: geneQuery,
      genes: sel.genes,
      panel: sel.panelId,
      min_score: minScore,
    });
  }

  async function onSelectHit(hit: Hit) {
    setSelected(hit);
    if (selectedSample) {
      await loadTracks(selectedSample.sample_id, mode, hit);
    }
  }

  async function onOpenUcsc(hit: Hit) {
    const w = hit.window;
    const { url } = await ucscLink(w.chrom, w.start, w.end);
    window.open(url, "_blank", "noopener,noreferrer");
  }

  async function openSampleFromOverview(sampleId: string, prefillQ: string) {
    const sample = samples.find((s) => s.sample_id === sampleId);
    if (!sample) {
      setError(`Sample not found: ${sampleId}`);
      return;
    }
    setSection("browser");
    setSelectedSample(sample);
    setSampleQuery(sample.sample_id);
    setGeneQuery(prefillQ);
    setFilterGenes([]);
    setFilterPanelId(null);
    await loadSampleHits(sample, mode, {
      q: prefillQ,
      min_score: minScore,
    });
  }

  const filteredSamples = useMemo(() => {
    const q = sampleQuery.trim().toLowerCase();
    if (!q) return samples;
    return samples.filter(
      (s) =>
        s.sample_id.toLowerCase().includes(q) ||
        s.full_sample_name.toLowerCase().includes(q),
    );
  }, [samples, sampleQuery]);

  return (
    <div className={`app${loading ? " is-loading" : ""}`}>
      {loading && section === "browser" ? (
        <div className="loading-overlay" role="status" aria-live="polite">
          <div className="loading-card">
            <div className="spinner" aria-hidden="true" />
            <p>Loading candidates…</p>
          </div>
        </div>
      ) : null}

      <header className="topbar">
        <div>
          <p className="brand">MedGen uORF Explorer</p>
          <p className="tagline">
            Browse 5ULTRA perturbation candidates by sample or across the cohort
          </p>
        </div>
        <nav className="section-nav" aria-label="App sections">
          <button
            type="button"
            className={section === "browser" ? "active" : undefined}
            onClick={() => setSection("browser")}
          >
            Sample browser
          </button>
          <button
            type="button"
            className={section === "overview" ? "active" : undefined}
            onClick={() => setSection("overview")}
          >
            Cohort overview
          </button>
        </nav>
      </header>

      {error ? <div className="banner error">{error}</div> : null}

      {section === "overview" ? (
        <CohortOverview onOpenSample={(sid, q) => void openSampleFromOverview(sid, q)} />
      ) : (
        <>
          <section className="sample-bar">
            <div className="sample-picker">
              <label htmlFor="sample-search">Sample</label>
              <input
                id="sample-search"
                list="sample-list"
                value={sampleQuery}
                onChange={(e) => setSampleQuery(e.target.value)}
                onBlur={() => {
                  const match = samples.find((s) => s.sample_id === sampleQuery);
                  if (match) void onSelectSample(match);
                }}
                placeholder="Sample ID (prefix before -N1)"
              />
              <datalist id="sample-list">
                {filteredSamples.map((s) => (
                  <option key={s.sample_id} value={s.sample_id}>
                    {s.full_sample_name} ({s.total_hits} hits)
                  </option>
                ))}
              </datalist>
            </div>

            <div className="mode-toggle" role="group" aria-label="Analysis mode">
              {(["nosplice", "splice", "both"] as AnalysisMode[]).map((m) => (
                <button
                  key={m}
                  type="button"
                  className={mode === m ? "active" : undefined}
                  onClick={() => void onModeChange(m)}
                >
                  {m}
                </button>
              ))}
            </div>

            <label className="threshold-toggle">
              <input
                type="checkbox"
                checked={useThreshold}
                onChange={(e) => void onThresholdChange(e.target.checked)}
              />
              Score ≥ {RECOMMENDED_SCORE_THRESHOLD}
            </label>

            <form className="search gene-filter" onSubmit={(e) => void applyFilters(e)}>
              <input
                value={geneQuery}
                onChange={(e) => setGeneQuery(e.target.value)}
                placeholder="Filter by gene, CSQ, or chr:pos"
                aria-label="Filter hits"
              />
              <button type="submit" disabled={loading || !selectedSample}>
                {loading ? "Loading…" : "Filter"}
              </button>
            </form>
          </section>

          <p className="threshold-caption">
            Recommended threshold 0.74 captured ~90% of positive controls
            (accuracy 97.5%, sensitivity 90.2%, specificity 99.8% on the training
            set). Enabled by default.
          </p>

          <GenePanelFilter
            genes={filterGenes}
            panelId={filterPanelId}
            onChange={(sel) => void onGenesChange(sel)}
          />

          {selectedSample ? (
            <p className="sample-summary">
              <strong>{selectedSample.sample_id}</strong>
              <span>{selectedSample.full_sample_name}</span>
              <span>
                {selectedSample.nosplice_hits} nosplice ·{" "}
                {selectedSample.splice_hits} splice
              </span>
            </p>
          ) : null}

          <div className="legend">
            <span className="legend-label">CSQ</span>
            {Object.entries(CSQ_COLORS).map(([k, color]) => (
              <span key={k} className="legend-item">
                <i style={{ background: color }} />
                {k}
              </span>
            ))}
            <span className="legend-item">
              <i style={{ background: "#2563eb" }} />
              uORFdb hg38
            </span>
            <span className="legend-item">
              <i style={{ background: "#6b7280" }} />
              5ULTRA 5′ UTR span
            </span>
            <span className="legend-item">
              <i style={{ background: "#dc2626" }} />
              5ULTRA affected uORF
            </span>
          </div>
          <TrackLegend />

          <main className="layout">
            <section className="left">
              <GenomeBrowser
                locus={locus}
                tracks={tracks}
                reference={reference}
                selectedHit={selected}
              />
              <div className="results">
                <div className="results-head">
                  <h2>5ULTRA candidates</h2>
                  <span>
                    {hits.length} hit{hits.length === 1 ? "" : "s"}
                  </span>
                </div>
                <HitsTable
                  hits={hits}
                  selectedId={selected?.id ?? null}
                  showMode={mode === "both"}
                  onSelect={(h) => void onSelectHit(h)}
                />
              </div>
            </section>
            <DetailPanel hit={selected} onOpenUcsc={onOpenUcsc} />
          </main>
        </>
      )}
    </div>
  );
}
