import { useEffect, useMemo, useState } from "react";
import type { ChangeEvent } from "react";
import { getGenePanel, listGenePanels } from "./api";
import type { GeneFilterSelection, GenePanelSummary } from "./types";
import { parseGeneList } from "./utils";

const UNCATEGORIZED = "(Uncategorized)";

type Props = {
  genes: string[];
  panelId: string | null;
  onChange: (selection: GeneFilterSelection) => void;
  /** If false, selecting a panel only updates local state; parent applies on demand. */
  applyImmediately?: boolean;
};

function groupLabel(value: string | undefined): string {
  const v = (value || "").trim();
  return v || UNCATEGORIZED;
}

export function GenePanelFilter({
  genes,
  panelId,
  onChange,
  applyImmediately = true,
}: Props) {
  const [panels, setPanels] = useState<GenePanelSummary[]>([]);
  const [selectedPanelId, setSelectedPanelId] = useState(panelId ?? "");
  const [customText, setCustomText] = useState(genes.join("\n"));
  const [diseaseGroup, setDiseaseGroup] = useState("");
  const [diseaseSubGroup, setDiseaseSubGroup] = useState("");
  const [loadingPanel, setLoadingPanel] = useState(false);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    void (async () => {
      try {
        const { panels: listed } = await listGenePanels();
        setPanels(listed);
      } catch (err) {
        setError(err instanceof Error ? err.message : String(err));
      }
    })();
  }, []);

  useEffect(() => {
    setSelectedPanelId(panelId ?? "");
  }, [panelId]);

  const curated = useMemo(() => panels.filter((p) => p.curated), [panels]);
  const gel = useMemo(() => panels.filter((p) => !p.curated), [panels]);

  const diseaseGroups = useMemo(() => {
    const set = new Set<string>();
    for (const p of gel) set.add(groupLabel(p.disease_group));
    return Array.from(set).sort((a, b) => a.localeCompare(b));
  }, [gel]);

  const diseaseSubGroups = useMemo(() => {
    if (!diseaseGroup) return [];
    const set = new Set<string>();
    for (const p of gel) {
      if (groupLabel(p.disease_group) !== diseaseGroup) continue;
      set.add(groupLabel(p.disease_sub_group));
    }
    return Array.from(set).sort((a, b) => a.localeCompare(b));
  }, [gel, diseaseGroup]);

  const gelPanelsInSub = useMemo(() => {
    if (!diseaseGroup || !diseaseSubGroup) return [];
    return gel
      .filter(
        (p) =>
          groupLabel(p.disease_group) === diseaseGroup &&
          groupLabel(p.disease_sub_group) === diseaseSubGroup,
      )
      .sort((a, b) => a.name.localeCompare(b.name));
  }, [gel, diseaseGroup, diseaseSubGroup]);

  async function applyPanel(nextPanelId: string) {
    if (!nextPanelId) return;
    setLoadingPanel(true);
    setError(null);
    try {
      const panel = await getGenePanel(nextPanelId);
      setSelectedPanelId(nextPanelId);
      setCustomText(panel.genes.join("\n"));
      onChange({ genes: panel.genes, panelId: nextPanelId });
    } catch (err) {
      setError(err instanceof Error ? err.message : String(err));
    } finally {
      setLoadingPanel(false);
    }
  }

  function applyCustom() {
    const parsed = parseGeneList(customText);
    setSelectedPanelId("");
    onChange({ genes: parsed, panelId: null });
  }

  function clearGenes() {
    setSelectedPanelId("");
    setCustomText("");
    setDiseaseGroup("");
    setDiseaseSubGroup("");
    onChange({ genes: [], panelId: null });
  }

  async function onFile(e: ChangeEvent<HTMLInputElement>) {
    const file = e.target.files?.[0];
    if (!file) return;
    const text = await file.text();
    const lines = text.split(/\r?\n/);
    const body =
      lines[0] && /gene|symbol/i.test(lines[0]) && !/^[A-Z0-9-]+$/i.test(lines[0].trim())
        ? lines.slice(1).join("\n")
        : text;
    const parsed = parseGeneList(body.replace(/,/g, "\n"));
    setCustomText(parsed.join("\n"));
    setSelectedPanelId("");
    onChange({ genes: parsed, panelId: null });
    e.target.value = "";
  }

  return (
    <div className="gene-panel-filter">
      <div className="filter-row">
        <span className="filter-label">Gene panels</span>
        <div className="panel-chips">
          {curated.map((p) => (
            <button
              key={p.id}
              type="button"
              className={selectedPanelId === p.id ? "active" : undefined}
              disabled={loadingPanel}
              onClick={() => void applyPanel(p.id)}
              title={`${p.source} · ${p.gene_count} genes`}
            >
              {p.name}
              <span>{p.gene_count}</span>
            </button>
          ))}
        </div>
      </div>

      <div className="filter-row gel-cascade">
        <span className="filter-label">Genomics England</span>
        <select
          value={diseaseGroup}
          onChange={(e) => {
            setDiseaseGroup(e.target.value);
            setDiseaseSubGroup("");
            setSelectedPanelId((id) => (id.startsWith("gel:") ? "" : id));
          }}
          aria-label="Disease group"
        >
          <option value="">Disease group…</option>
          {diseaseGroups.map((g) => (
            <option key={g} value={g}>
              {g}
            </option>
          ))}
        </select>
        <select
          value={diseaseSubGroup}
          onChange={(e) => {
            setDiseaseSubGroup(e.target.value);
            setSelectedPanelId((id) => (id.startsWith("gel:") ? "" : id));
          }}
          disabled={!diseaseGroup}
          aria-label="Disease sub-group"
        >
          <option value="">Disease sub-group…</option>
          {diseaseSubGroups.map((g) => (
            <option key={g} value={g}>
              {g}
            </option>
          ))}
        </select>
        <select
          value={selectedPanelId.startsWith("gel:") ? selectedPanelId : ""}
          onChange={(e) => void applyPanel(e.target.value)}
          disabled={loadingPanel || !diseaseSubGroup}
          aria-label="Panel name"
        >
          <option value="">Panel name…</option>
          {gelPanelsInSub.map((p) => (
            <option key={p.id} value={p.id}>
              {p.name} ({p.gene_count})
            </option>
          ))}
        </select>
      </div>

      <div className="filter-row custom-genes">
        <label htmlFor="custom-genes">Custom gene list</label>
        <textarea
          id="custom-genes"
          rows={3}
          value={customText}
          onChange={(e) => setCustomText(e.target.value)}
          placeholder="BRCA1&#10;TP53&#10;… (comma or newline separated)"
        />
        <div className="custom-actions">
          <button type="button" onClick={applyCustom}>
            {applyImmediately ? "Apply genes" : "Set genes"} ({parseGeneList(customText).length})
          </button>
          <label className="file-upload">
            Upload file
            <input type="file" accept=".txt,.csv,.tsv" onChange={(e) => void onFile(e)} />
          </label>
          <button type="button" className="linkish-inline" onClick={clearGenes}>
            Clear
          </button>
          {genes.length > 0 || panelId ? (
            <span className="gene-count-badge">
              {panelId ? `Panel active · ${genes.length} genes` : `${genes.length} genes active`}
            </span>
          ) : null}
        </div>
      </div>
      {error ? <p className="inline-error">{error}</p> : null}
    </div>
  );
}
