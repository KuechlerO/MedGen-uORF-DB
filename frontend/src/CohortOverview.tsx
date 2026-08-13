import { Fragment, useCallback, useState } from "react";
import type { MouseEvent } from "react";
import { getOverviewVariants } from "./api";
import { GenePanelFilter } from "./GenePanelFilter";
import type { AnalysisMode, OverviewResponse, OverviewVariant } from "./types";
import {
  RECOMMENDED_SCORE_THRESHOLD,
  csqColor,
  formatScore,
  formatZygosity,
  geneCardsUrl,
  gnomadVariantUrl,
  variantLabelShort,
  zygosityStyle,
} from "./utils";

type Props = {
  onOpenSample: (sampleId: string, prefillQ: string) => void;
};

type SampleScope = "all" | "multi" | "singleton";

type ZygosityMode = "any" | "uniform" | "all_het" | "all_hom";

type SortKey =
  | "gene"
  | "variant"
  | "csq"
  | "max_score"
  | "n_samples"
  | "n_hits"
  | "n_het"
  | "modes";

type SortDir = "asc" | "desc";

type AppliedFilters = {
  mode: AnalysisMode;
  useThreshold: boolean;
  sampleScope: SampleScope;
  zygosityMode: ZygosityMode;
  genes: string[];
  panelId: string | null;
  q: string;
};

const DEFAULT_APPLIED: AppliedFilters = {
  mode: "both",
  useThreshold: true,
  sampleScope: "all",
  zygosityMode: "any",
  genes: [],
  panelId: null,
  q: "",
};

function SortHeader({
  label,
  sortKey,
  activeKey,
  dir,
  onSort,
}: {
  label: string;
  sortKey: SortKey;
  activeKey: SortKey;
  dir: SortDir;
  onSort: (key: SortKey) => void;
}) {
  const active = sortKey === activeKey;
  return (
    <th
      className={`sortable${active ? " sorted" : ""}`}
      aria-sort={active ? (dir === "asc" ? "ascending" : "descending") : "none"}
      onClick={() => onSort(sortKey)}
    >
      <span className="th-label">{label}</span>
      <span className="sort-icon" aria-hidden="true">
        {active ? (dir === "asc" ? "▲" : "▼") : "↕"}
      </span>
    </th>
  );
}

export function CohortOverview({ onOpenSample }: Props) {
  const [draftMode, setDraftMode] = useState<AnalysisMode>(DEFAULT_APPLIED.mode);
  const [draftThreshold, setDraftThreshold] = useState(DEFAULT_APPLIED.useThreshold);
  const [draftScope, setDraftScope] = useState<SampleScope>(DEFAULT_APPLIED.sampleScope);
  const [draftZygosity, setDraftZygosity] = useState<ZygosityMode>(
    DEFAULT_APPLIED.zygosityMode,
  );
  const [draftGenes, setDraftGenes] = useState<string[]>([]);
  const [draftPanelId, setDraftPanelId] = useState<string | null>(null);
  const [draftQ, setDraftQ] = useState("");

  const [applied, setApplied] = useState<AppliedFilters | null>(null);
  const [offset, setOffset] = useState(0);
  const [sortKey, setSortKey] = useState<SortKey>("n_samples");
  const [sortDir, setSortDir] = useState<SortDir>("desc");
  const [data, setData] = useState<OverviewResponse | null>(null);
  const [expanded, setExpanded] = useState<string | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const limit = 50;

  const runQuery = useCallback(
    async (
      filters: AppliedFilters,
      pageOffset: number,
      sort: { key: SortKey; dir: SortDir },
    ) => {
      setLoading(true);
      setError(null);
      try {
        const result = await getOverviewVariants({
          mode: filters.mode,
          min_score: filters.useThreshold
            ? RECOMMENDED_SCORE_THRESHOLD
            : undefined,
          min_samples:
            filters.sampleScope === "multi"
              ? 2
              : filters.sampleScope === "singleton"
                ? 1
                : undefined,
          max_samples: filters.sampleScope === "singleton" ? 1 : undefined,
          genes: filters.panelId
            ? undefined
            : filters.genes.length
              ? filters.genes
              : undefined,
          panel: filters.panelId,
          q: filters.q.trim() || undefined,
          limit,
          offset: pageOffset,
          sort_by: sort.key,
          sort_dir: sort.dir,
          zygosity_mode: filters.zygosityMode,
        });
        setData(result);
        setApplied(filters);
        setOffset(pageOffset);
      } catch (err) {
        setError(err instanceof Error ? err.message : String(err));
      } finally {
        setLoading(false);
      }
    },
    [],
  );

  function currentDraft(): AppliedFilters {
    return {
      mode: draftMode,
      useThreshold: draftThreshold,
      sampleScope: draftScope,
      zygosityMode: draftZygosity,
      genes: draftGenes,
      panelId: draftPanelId,
      q: draftQ,
    };
  }

  function applyFilters() {
    void runQuery(currentDraft(), 0, { key: sortKey, dir: sortDir });
  }

  function goPage(nextOffset: number) {
    if (!applied) return;
    void runQuery(applied, nextOffset, { key: sortKey, dir: sortDir });
  }

  function onSort(key: SortKey) {
    const nextDir: SortDir =
      key === sortKey
        ? sortDir === "asc"
          ? "desc"
          : "asc"
        : key === "gene" || key === "variant" || key === "csq" || key === "modes"
          ? "asc"
          : "desc";
    setSortKey(key);
    setSortDir(nextDir);
    if (!applied) return;
    void runQuery(applied, 0, { key, dir: nextDir });
  }

  function rowKey(v: OverviewVariant) {
    return `${v.gene}|${v.chrom}|${v.pos}|${v.ref}|${v.alt}`;
  }

  const pageCount = data ? Math.max(1, Math.ceil(data.total / limit)) : 1;
  const page = Math.floor(offset / limit);
  const headerProps = { activeKey: sortKey, dir: sortDir, onSort };

  return (
    <section className={`cohort-overview${loading ? " is-loading" : ""}`}>
      {loading ? (
        <div className="loading-overlay" role="status" aria-live="polite">
          <div className="loading-card">
            <div className="spinner" aria-hidden="true" />
            <p>Computing cohort overview…</p>
          </div>
        </div>
      ) : null}

      <div className="overview-summary">
        <div className="stat-card">
          <span className="stat-value">{data?.summary.total_variants ?? "—"}</span>
          <span className="stat-label">Unique variants</span>
        </div>
        <div className="stat-card">
          <span className="stat-value">{data?.summary.multi_sample ?? "—"}</span>
          <span className="stat-label">In ≥2 samples</span>
        </div>
        <div className="stat-card">
          <span className="stat-value">{data?.summary.singleton ?? "—"}</span>
          <span className="stat-label">Singletons</span>
        </div>
      </div>

      <div className="filter-toolbar">
        <div className="mode-toggle" role="group" aria-label="Analysis mode">
          {(["nosplice", "splice", "both"] as AnalysisMode[]).map((m) => (
            <button
              key={m}
              type="button"
              className={draftMode === m ? "active" : undefined}
              onClick={() => setDraftMode(m)}
              disabled={loading}
            >
              {m}
            </button>
          ))}
        </div>

        <div className="mode-toggle" role="group" aria-label="Sample frequency">
          {(
            [
              ["all", "All"],
              ["multi", "Multi-sample"],
              ["singleton", "Singletons"],
            ] as const
          ).map(([id, label]) => (
            <button
              key={id}
              type="button"
              className={draftScope === id ? "active" : undefined}
              onClick={() => setDraftScope(id)}
              disabled={loading}
            >
              {label}
            </button>
          ))}
        </div>

        <div className="mode-toggle" role="group" aria-label="Zygosity uniformity">
          {(
            [
              ["any", "Any zygosity"],
              ["uniform", "Uniform"],
              ["all_het", "All het"],
              ["all_hom", "All hom"],
            ] as const
          ).map(([id, label]) => (
            <button
              key={id}
              type="button"
              className={draftZygosity === id ? "active" : undefined}
              onClick={() => setDraftZygosity(id)}
              disabled={loading}
              title={
                id === "uniform"
                  ? "Only variants where every sample is heterozygous, or every sample is homozygous"
                  : id === "all_het"
                    ? "Only variants where every sample is heterozygous"
                    : id === "all_hom"
                      ? "Only variants where every sample is homozygous"
                      : "No zygosity uniformity filter"
              }
            >
              {label}
            </button>
          ))}
        </div>

        <label className="threshold-toggle">
          <input
            type="checkbox"
            checked={draftThreshold}
            disabled={loading}
            onChange={(e) => setDraftThreshold(e.target.checked)}
          />
          Score ≥ {RECOMMENDED_SCORE_THRESHOLD} (recommended)
        </label>

        <div className="search gene-filter">
          <input
            value={draftQ}
            disabled={loading}
            onChange={(e) => setDraftQ(e.target.value)}
            placeholder="Filter gene / CSQ / chrom"
          />
          <button type="button" disabled={loading} onClick={applyFilters}>
            {loading ? "Loading…" : "Apply filters"}
          </button>
        </div>
      </div>

      <p className="threshold-caption">
        Threshold 0.74 captured ~90% of positive controls (accuracy 97.5%,
        sensitivity 90.2%, specificity 99.8% on the training set). Filters are
        applied only when you click <strong>Apply filters</strong>.
      </p>

      <fieldset disabled={loading} className="filter-fieldset">
        <GenePanelFilter
          genes={draftGenes}
          panelId={draftPanelId}
          applyImmediately={false}
          onChange={(sel) => {
            setDraftGenes(sel.genes);
            setDraftPanelId(sel.panelId);
          }}
        />
      </fieldset>

      {error ? <div className="banner error">{error}</div> : null}

      <div className="results overview-table-wrap">
        <div className="results-head">
          <h2>Cohort variants</h2>
          <span>
            {applied
              ? `${data?.total ?? 0} unique · page ${page + 1}/${pageCount}`
              : "No query yet — set filters and click Apply"}
          </span>
        </div>
        {!applied ? (
          <p className="empty-table">
            Choose filters above, then click <strong>Apply filters</strong> to
            load the cohort overview.
          </p>
        ) : !data || data.variants.length === 0 ? (
          <p className="empty-table">No variants match these filters.</p>
        ) : (
          <div className="table-wrap">
            <table className="hits-table">
              <thead>
                <tr>
                  <SortHeader label="Gene" sortKey="gene" {...headerProps} />
                  <SortHeader label="Variant" sortKey="variant" {...headerProps} />
                  <SortHeader label="CSQ" sortKey="csq" {...headerProps} />
                  <SortHeader
                    label="Max score"
                    sortKey="max_score"
                    {...headerProps}
                  />
                  <SortHeader
                    label="Samples"
                    sortKey="n_samples"
                    {...headerProps}
                  />
                  <SortHeader label="Zygosity" sortKey="n_het" {...headerProps} />
                  <SortHeader label="Hits" sortKey="n_hits" {...headerProps} />
                  <SortHeader label="Modes" sortKey="modes" {...headerProps} />
                  <th>Links</th>
                </tr>
              </thead>
              <tbody>
                {data.variants.map((v) => {
                  const key = rowKey(v);
                  const open = expanded === key;
                  const geneUrl = geneCardsUrl(v.gene);
                  const gnomadUrl = gnomadVariantUrl(v);
                  return (
                    <Fragment key={key}>
                      <tr
                        className={open ? "selected" : undefined}
                        onClick={() => setExpanded(open ? null : key)}
                      >
                        <td>
                          {geneUrl ? (
                            <a
                              className="ext-link"
                              href={geneUrl}
                              target="_blank"
                              rel="noopener noreferrer"
                              onClick={(e: MouseEvent) => e.stopPropagation()}
                            >
                              <strong>{v.gene}</strong>
                            </a>
                          ) : (
                            <strong>{v.gene}</strong>
                          )}
                        </td>
                        <td
                          className="mono variant-cell"
                          title={`${v.chrom}:${v.pos} ${v.ref}>${v.alt}`}
                        >
                          {variantLabelShort(v)}
                        </td>
                        <td>
                          {v.csq_class ? (
                            <>
                              <span
                                className="csq-dot"
                                style={{ background: csqColor(v.csq_class) }}
                              />
                              {v.csq_class}
                            </>
                          ) : (
                            "—"
                          )}
                        </td>
                        <td>{formatScore(v.max_score)}</td>
                        <td>{v.n_samples}</td>
                        <td
                          className="zygosity-summary"
                          title={
                            (v.n_other ?? 0) > 0
                              ? `${v.n_het ?? 0} heterozygous · ${v.n_hom ?? 0} homozygous · ${v.n_other} other`
                              : `${v.n_het ?? 0} heterozygous · ${v.n_hom ?? 0} homozygous`
                          }
                        >
                          <span className="zyg-count het">{v.n_het ?? 0} het</span>
                          <span className="zyg-sep">·</span>
                          <span className="zyg-count hom">{v.n_hom ?? 0} hom</span>
                          {(v.n_other ?? 0) > 0 ? (
                            <>
                              <span className="zyg-sep">·</span>
                              <span className="zyg-count other">{v.n_other} other</span>
                            </>
                          ) : null}
                        </td>
                        <td>{v.n_hits}</td>
                        <td className="mono">{v.modes.join(", ") || "—"}</td>
                        <td
                          className="link-cell"
                          onClick={(e: MouseEvent) => e.stopPropagation()}
                        >
                          {gnomadUrl ? (
                            <a
                              className="ext-link"
                              href={gnomadUrl}
                              target="_blank"
                              rel="noopener noreferrer"
                            >
                              gnomAD
                            </a>
                          ) : (
                            "—"
                          )}
                        </td>
                      </tr>
                      {open ? (
                        <tr className="expand-row">
                          <td colSpan={9}>
                            <div className="zygosity-legend" aria-label="Zygosity legend">
                              {(
                                [
                                  ["het", "Heterozygous"],
                                  ["hom", "Homozygous"],
                                  ["multi", "Multi-allelic"],
                                  ["unknown", "Unknown"],
                                ] as const
                              ).map(([zyg, label]) => {
                                const style = zygosityStyle(zyg);
                                return (
                                  <span
                                    key={zyg}
                                    className="zygosity-legend-item"
                                    style={{
                                      background: style.bg,
                                      borderColor: style.border,
                                      color: style.text,
                                    }}
                                  >
                                    {label}
                                  </span>
                                );
                              })}
                            </div>
                            <div className="sample-chip-list">
                              {(v.samples?.length
                                ? v.samples
                                : v.sample_ids.map((sample_id) => ({
                                    sample_id,
                                    zygosity: "unknown" as const,
                                    gt: null,
                                  }))
                              ).map((s) => {
                                const style = zygosityStyle(s.zygosity);
                                return (
                                  <button
                                    key={s.sample_id}
                                    type="button"
                                    className="sample-chip"
                                    title={`${s.sample_id} · ${formatZygosity(s.zygosity)}${
                                      s.gt ? ` (${s.gt})` : ""
                                    }`}
                                    style={{
                                      background: style.bg,
                                      borderColor: style.border,
                                      color: style.text,
                                    }}
                                    onClick={(e) => {
                                      e.stopPropagation();
                                      onOpenSample(s.sample_id, `${v.chrom}:${v.pos}`);
                                    }}
                                  >
                                    {s.sample_id}
                                  </button>
                                );
                              })}
                            </div>
                          </td>
                        </tr>
                      ) : null}
                    </Fragment>
                  );
                })}
              </tbody>
            </table>
            <div className="pagination">
              <span>
                Showing {offset + 1}–
                {Math.min(offset + limit, data.total)} of {data.total}
              </span>
              <div className="pagination-controls">
                <button
                  type="button"
                  disabled={offset === 0 || loading}
                  onClick={() => goPage(Math.max(0, offset - limit))}
                >
                  Previous
                </button>
                <button
                  type="button"
                  disabled={offset + limit >= data.total || loading}
                  onClick={() => goPage(offset + limit)}
                >
                  Next
                </button>
              </div>
            </div>
          </div>
        )}
      </div>
    </section>
  );
}
