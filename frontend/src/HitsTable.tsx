import { useEffect, useMemo, useState } from "react";
import type { Hit } from "./types";
import { csqColor, formatScore, variantLabel, variantLabelShort } from "./utils";

type SortKey =
  | "mode"
  | "gene"
  | "variant"
  | "csq"
  | "translation"
  | "score"
  | "uorf_type";

type SortDir = "asc" | "desc";

type Props = {
  hits: Hit[];
  selectedId: string | null;
  showMode?: boolean;
  pageSize?: number;
  onSelect: (hit: Hit) => void;
};

const PAGE_SIZE_DEFAULT = 25;

const CHROM_ORDER = new Map(
  [
    "chr1", "chr2", "chr3", "chr4", "chr5", "chr6", "chr7", "chr8", "chr9", "chr10",
    "chr11", "chr12", "chr13", "chr14", "chr15", "chr16", "chr17", "chr18", "chr19",
    "chr20", "chr21", "chr22", "chrX", "chrY", "chrM",
  ].map((c, i) => [c, i]),
);

function chromRank(chrom: string): number {
  const key = chrom.toLowerCase().startsWith("chr")
    ? chrom.toLowerCase()
    : `chr${chrom.toLowerCase()}`;
  return CHROM_ORDER.get(key) ?? 999;
}

function compareText(a: string, b: string): number {
  return a.localeCompare(b, undefined, { sensitivity: "base" });
}

function compareHits(a: Hit, b: Hit, key: SortKey): number {
  switch (key) {
    case "mode":
      return compareText(a.mode ?? "", b.mode ?? "");
    case "gene":
      return compareText(a.gene, b.gene);
    case "variant": {
      const chrom = chromRank(a.chrom) - chromRank(b.chrom);
      if (chrom !== 0) return chrom;
      if (a.pos !== b.pos) return a.pos - b.pos;
      const ref = compareText(a.ref, b.ref);
      if (ref !== 0) return ref;
      return compareText(a.alt, b.alt);
    }
    case "csq":
      return compareText(a.csq_class, b.csq_class);
    case "translation":
      return compareText(a.translation || "", b.translation || "");
    case "score": {
      const av = a.score ?? Number.NEGATIVE_INFINITY;
      const bv = b.score ?? Number.NEGATIVE_INFINITY;
      return av - bv;
    }
    case "uorf_type":
      return compareText(a.uorf.type || "", b.uorf.type || "");
    default:
      return 0;
  }
}

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

export function HitsTable({
  hits,
  selectedId,
  showMode = false,
  pageSize = PAGE_SIZE_DEFAULT,
  onSelect,
}: Props) {
  const [sortKey, setSortKey] = useState<SortKey>("score");
  const [sortDir, setSortDir] = useState<SortDir>("desc");
  const [page, setPage] = useState(0);

  const sortedHits = useMemo(() => {
    const copy = [...hits];
    copy.sort((a, b) => {
      const cmp = compareHits(a, b, sortKey);
      return sortDir === "asc" ? cmp : -cmp;
    });
    return copy;
  }, [hits, sortKey, sortDir]);

  const pageCount = Math.max(1, Math.ceil(sortedHits.length / pageSize));

  useEffect(() => {
    setPage(0);
  }, [hits, sortKey, sortDir, pageSize]);

  useEffect(() => {
    if (page > pageCount - 1) setPage(Math.max(0, pageCount - 1));
  }, [page, pageCount]);

  const pageHits = useMemo(() => {
    const start = page * pageSize;
    return sortedHits.slice(start, start + pageSize);
  }, [sortedHits, page, pageSize]);

  function onSort(key: SortKey) {
    if (key === sortKey) {
      setSortDir((d) => (d === "asc" ? "desc" : "asc"));
    } else {
      setSortKey(key);
      setSortDir(key === "score" ? "desc" : "asc");
    }
  }

  if (hits.length === 0) {
    return <p className="empty-table">No matching 5ULTRA candidates.</p>;
  }

  const headerProps = { activeKey: sortKey, dir: sortDir, onSort };
  const from = page * pageSize + 1;
  const to = Math.min(sortedHits.length, (page + 1) * pageSize);

  return (
    <div className="table-wrap">
      <table className="hits-table">
        <thead>
          <tr>
            {showMode ? (
              <SortHeader label="Mode" sortKey="mode" {...headerProps} />
            ) : null}
            <SortHeader label="Gene" sortKey="gene" {...headerProps} />
            <SortHeader label="Variant" sortKey="variant" {...headerProps} />
            <SortHeader label="CSQ" sortKey="csq" {...headerProps} />
            <SortHeader label="Translation" sortKey="translation" {...headerProps} />
            <SortHeader label="Score" sortKey="score" {...headerProps} />
            <SortHeader label="uORF type" sortKey="uorf_type" {...headerProps} />
          </tr>
        </thead>
        <tbody>
          {pageHits.map((hit) => (
            <tr
              key={hit.id}
              className={hit.id === selectedId ? "selected" : undefined}
              onClick={() => onSelect(hit)}
            >
              {showMode ? <td className="mono">{hit.mode ?? "—"}</td> : null}
              <td>
                <strong>{hit.gene}</strong>
              </td>
              <td className="mono variant-cell" title={variantLabel(hit)}>
                {variantLabelShort(hit)}
              </td>
              <td>
                <span
                  className="csq-dot"
                  style={{ background: csqColor(hit.csq_class) }}
                />
                {hit.csq_class}
              </td>
              <td>{hit.translation || "—"}</td>
              <td>{formatScore(hit.score)}</td>
              <td>{hit.uorf.type || "—"}</td>
            </tr>
          ))}
        </tbody>
      </table>
      <div className="pagination">
        <span>
          Showing {from}–{to} of {sortedHits.length}
        </span>
        <div className="pagination-controls">
          <button
            type="button"
            disabled={page === 0}
            onClick={() => setPage((p) => Math.max(0, p - 1))}
          >
            Previous
          </button>
          <span>
            Page {page + 1} / {pageCount}
          </span>
          <button
            type="button"
            disabled={page >= pageCount - 1}
            onClick={() => setPage((p) => Math.min(pageCount - 1, p + 1))}
          >
            Next
          </button>
        </div>
      </div>
    </div>
  );
}
