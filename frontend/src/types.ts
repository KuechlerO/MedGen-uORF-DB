export type AnalysisMode = "nosplice" | "splice" | "both";

export type SampleSummary = {
  sample_id: string;
  full_sample_name: string;
  nosplice_hits: number;
  splice_hits: number;
  total_hits: number;
  modes: AnalysisMode[];
};

export type UorfAnnotation = {
  start: number | null;
  end: number | null;
  type: string;
  start_codon: string;
  stop_codon: string;
  kozak: string;
  kozak_strength: string;
  length: number | null;
  aa_length: number | null;
  seq: string;
  rank: string;
  ribo_seq: number | null;
  ustart_mstart_dist: number | null;
  ustart_cap_dist: number | null;
  phylop: number | null;
  phastcons: number | null;
};

export type Hit = {
  id: string;
  index: number;
  chrom: string;
  pos: number;
  ref: string;
  alt: string;
  csq: string;
  csq_class: string;
  translation: string;
  score: number | null;
  gene: string;
  transcripts: string[];
  mane: string[];
  strand: string;
  utr5: { start: number | null; end: number | null; length: number | null };
  mstart: { start: number; end: number }[];
  mstart_codon: string;
  mkozak: string;
  mkozak_strength: string;
  uorf_counts: Record<string, number | null>;
  uorf: UorfAnnotation;
  spliceai: string;
  splicing_csq: string;
  loeuf: number | null;
  pli: number | null;
  sample: string | null;
  sample_id?: string;
  mode?: AnalysisMode;
  full_sample_name?: string;
  genotype: string;
  gt?: string | null;
  zygosity?: "het" | "hom" | "hom_ref" | "multi" | "unknown";
  allele_depths?: number[] | null;
  depth?: number | null;
  gq?: number | null;
  window: {
    chrom: string;
    start: number;
    end: number;
    locus: string;
  };
};

export type TrackConfig = {
  id: string;
  name: string;
  type: string;
  format: string;
  url: string;
  indexURL?: string;
  color?: string;
  displayMode?: string;
  source?: string;
  removable?: boolean;
};

export type ReferenceConfig = {
  id: string;
  name: string;
  fastaURL: string;
  indexURL: string;
  compressedIndexURL?: string;
  chromosomeOrder?: string[];
};

export type TracksResponse = {
  genome: string;
  reference: ReferenceConfig;
  reference_ready: boolean;
  sample?: string | null;
  mode?: string;
  tracks: TrackConfig[];
};

export type GenePanelSummary = {
  id: string;
  name: string;
  source: string;
  version?: string;
  curated: boolean;
  gene_count: number;
  hyperlink?: string;
  disease_group?: string;
  disease_sub_group?: string;
};

export type GeneFilterSelection = {
  genes: string[];
  panelId: string | null;
};

export type GenePanelDetail = GenePanelSummary & {
  genes: string[];
};

export type OverviewSample = {
  sample_id: string;
  zygosity: "het" | "hom" | "hom_ref" | "multi" | "unknown" | string;
  gt?: string | null;
};

export type OverviewVariant = {
  gene: string;
  chrom: string;
  pos: number;
  ref: string;
  alt: string;
  csq_class: string | null;
  max_score: number | null;
  n_samples: number;
  n_hits: number;
  n_het?: number;
  n_hom?: number;
  n_other?: number;
  sample_ids: string[];
  samples?: OverviewSample[];
  modes: string[];
};

export type OverviewResponse = {
  total: number;
  limit: number;
  offset: number;
  summary: {
    total_variants: number;
    multi_sample: number;
    singleton: number;
  };
  variants: OverviewVariant[];
};

export type AppSection = "browser" | "overview";

