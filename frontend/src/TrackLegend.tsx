export function TrackLegend() {
  return (
    <details className="track-legend">
      <summary>Track sources</summary>
      <ul>
        <li>
          <strong>GENCODE v50 basic</strong> — local transcript models (reference
          annotation).
        </li>
        <li>
          <strong>uORFdb hg38</strong> — genome-wide human uORFs from the uORFdb
          dump (not sample-specific).
        </li>
        <li>
          <strong>5ULTRA 5′ UTR span</strong> — from 5ULTRA columns{" "}
          <code>5UTR_START</code>/<code>5UTR_END</code> (TLS / 5′ UTR of the
          annotated transcript for each candidate in this sample).
        </li>
        <li>
          <strong>5ULTRA affected uORF</strong> — from 5ULTRA{" "}
          <code>uORF_START</code>/<code>uORF_END</code> for the uORF interval
          affected by the candidate variant (same sample + mode).
        </li>
        <li>
          <strong>5ULTRA variants</strong> — candidate SNVs/indels from the
          5ULTRA TSV for this sample.
        </li>
      </ul>
    </details>
  );
}
