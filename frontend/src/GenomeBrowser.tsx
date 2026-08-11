import { useEffect, useRef } from "react";
import igv from "igv";
import type { Browser } from "igv";
import type { Hit, ReferenceConfig, TrackConfig } from "./types";

type Props = {
  locus: string | null;
  tracks: TrackConfig[];
  reference: ReferenceConfig | null;
  selectedHit: Hit | null;
};

export function GenomeBrowser({ locus, tracks, reference, selectedHit }: Props) {
  const containerRef = useRef<HTMLDivElement | null>(null);
  const browserRef = useRef<Browser | null>(null);
  const readyRef = useRef(false);

  useEffect(() => {
    let cancelled = false;

    async function init() {
      if (!containerRef.current || tracks.length === 0 || !reference) return;
      if (browserRef.current) {
        try {
          await igv.removeBrowser(browserRef.current);
        } catch {
          /* ignore */
        }
        browserRef.current = null;
        readyRef.current = false;
      }

      const igvTracks = tracks.map((t) => {
        const base: Record<string, unknown> = {
          name: t.name,
          type: t.type,
          format: t.format,
          url: t.url,
          displayMode: t.displayMode ?? "EXPANDED",
        };
        if (t.indexURL) base.indexURL = t.indexURL;
        if (t.color) base.color = t.color;
        if (t.removable === false) base.removable = false;
        return base;
      });

      const referenceConfig: Record<string, unknown> = {
        id: reference.id,
        name: reference.name,
        fastaURL: reference.fastaURL,
        indexURL: reference.indexURL,
      };
      if (reference.compressedIndexURL) {
        referenceConfig.compressedIndexURL = reference.compressedIndexURL;
      }
      if (reference.chromosomeOrder) {
        referenceConfig.chromosomeOrder = reference.chromosomeOrder;
      }

      const browser = await igv.createBrowser(containerRef.current, {
        reference: referenceConfig,
        locus: locus ?? "chr16:3442901-3443754",
        showNavigation: true,
        showRuler: true,
        tracks: igvTracks,
      });

      if (cancelled) {
        await igv.removeBrowser(browser);
        return;
      }
      browserRef.current = browser;
      readyRef.current = true;
    }

    void init();

    return () => {
      cancelled = true;
      if (browserRef.current) {
        void igv.removeBrowser(browserRef.current);
        browserRef.current = null;
        readyRef.current = false;
      }
    };
    // Re-init when track/reference identity changes (once on load).
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [tracks, reference]);

  useEffect(() => {
    const browser = browserRef.current;
    if (!browser || !locus || !readyRef.current) return;
    void browser.search(locus);
  }, [locus]);

  return (
    <div className="browser-shell">
      <div className="browser-toolbar">
        <span className="browser-title">
          Genome browser ({reference?.name ?? "hg38"})
        </span>
        {selectedHit ? (
          <span className="browser-hint">
            Focus: {selectedHit.gene} · {selectedHit.csq_class}
          </span>
        ) : (
          <span className="browser-hint">Select a hit to recenter</span>
        )}
      </div>
      <div ref={containerRef} className="igv-host" />
    </div>
  );
}
