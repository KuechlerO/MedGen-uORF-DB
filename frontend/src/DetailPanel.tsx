import type { ReactNode } from "react";
import type { Hit } from "./types";
import { csqColor, formatScore, variantLabel, variantLabelShort } from "./utils";

type Props = {
  hit: Hit | null;
  onOpenUcsc: (hit: Hit) => void;
};

function Row({ label, value }: { label: string; value: ReactNode }) {
  if (value === null || value === undefined || value === "") return null;
  return (
    <div className="detail-row">
      <dt>{label}</dt>
      <dd>{value}</dd>
    </div>
  );
}

export function DetailPanel({ hit, onOpenUcsc }: Props) {
  if (!hit) {
    return (
      <aside className="detail-panel empty">
        <h2>Hit details</h2>
        <p>Select a 5ULTRA candidate from the table to inspect annotations.</p>
      </aside>
    );
  }

  const u = hit.uorf;

  return (
    <aside className="detail-panel">
      <header>
        <p className="eyebrow">{hit.gene}</p>
        <h2 title={variantLabel(hit)}>{variantLabelShort(hit)}</h2>
        <div className="pill-row">
          <span
            className="pill"
            style={{ background: csqColor(hit.csq_class) }}
          >
            {hit.csq_class}
          </span>
          <span className="pill muted">score {formatScore(hit.score)}</span>
          <span className="pill muted">{hit.translation || "—"}</span>
        </div>
      </header>

      <dl>
        <Row label="Consequence" value={hit.csq} />
        <Row label="Transcripts" value={hit.transcripts.join(", ")} />
        <Row label="MANE" value={hit.mane.join(", ")} />
        <Row label="Strand" value={hit.strand} />
        <Row
          label="5′ UTR"
          value={
            hit.utr5.start != null && hit.utr5.end != null
              ? `${hit.utr5.start}–${hit.utr5.end} (${hit.utr5.length ?? "?"} nt)`
              : null
          }
        />
        <Row
          label="Affected uORF"
          value={
            u.start != null && u.end != null
              ? `${u.start}–${u.end} · ${u.type}`
              : null
          }
        />
        <Row label="uSTART / uSTOP" value={`${u.start_codon} / ${u.stop_codon}`} />
        <Row
          label="uKozak"
          value={u.kozak ? `${u.kozak} (${u.kozak_strength})` : null}
        />
        <Row
          label="Length"
          value={
            u.length != null
              ? `${u.length} nt / ${u.aa_length ?? "?"} aa`
              : null
          }
        />
        <Row label="uORF rank" value={u.rank} />
        <Row label="Ribo-seq support" value={u.ribo_seq} />
        <Row label="uSTART→mSTART" value={u.ustart_mstart_dist} />
        <Row label="Cap→uSTART" value={u.ustart_cap_dist} />
        <Row
          label="Conservation"
          value={
            u.phylop != null
              ? `phyloP ${u.phylop.toFixed(3)} · phastCons ${
                  u.phastcons?.toFixed(3) ?? "—"
                }`
              : null
          }
        />
        <Row label="mKozak" value={`${hit.mkozak} (${hit.mkozak_strength})`} />
        <Row
          label="Constraint"
          value={`LOEUF ${hit.loeuf ?? "—"} · pLI ${hit.pli ?? "—"}`}
        />
        <Row label="Splicing CSQ" value={hit.splicing_csq} />
        <Row label="Genotype" value={hit.genotype || null} />
      </dl>

      {u.seq ? (
        <div className="seq-block">
          <h3>uORF sequence</h3>
          <code>{u.seq}</code>
        </div>
      ) : null}

      <button type="button" className="linkish" onClick={() => onOpenUcsc(hit)}>
        Open locus in UCSC Genome Browser
      </button>
    </aside>
  );
}
