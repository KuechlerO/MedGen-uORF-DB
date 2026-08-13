# 5ULTRA TSV column dictionary (fields used by this app)

Genome build expected: **hg38** (`chr*` contig names).

| Column | Role in explorer |
|--------|------------------|
| CHROM, POS, REF, ALT | Variant identity → VCF track + hit ID |
| CSQ, Translation, 5ULTRA_Score | Consequence class, effect, prioritization |
| GENE, TRANSCRIPT, MANE | Search + detail panel |
| 5UTR_START/END, 5UTR_LENGTH, STRAND | **5ULTRA 5′ UTR span** track; locus windowing |
| mSTART, mSTART_CODON, mKOZAK* | Main ORF start context |
| uORF_START/END, uORF_TYPE, uSTART_CODON, uSTOP_CODON | **5ULTRA affected uORF** track + detail panel |
| uKOZAK*, uORF_LENGTH, uORF_AA_LENGTH, uORF_SEQ, uORF_rank | Detail panel |
| Ribo_seq, uSTART_*_DIST, uSTART_PHYLOP/PHASTCONS | Evidence / conservation |
| LOEUF, pLI | Gene constraint |
| SpliceAI, Splicing_CSQ | Optional splicing context |
| FORMAT + sample column | Genotype from the **first** sample column after `FORMAT`; parsed as **zygosity** (het/hom), GT, AD, DP, GQ. Primary-sample **homozygous ref** (`0/0` / `0|0`) rows are omitted (non-carriers in multi-sample VCFs). |

Unknown columns after `FORMAT` are treated as sample genotype fields; only the first is used as the primary sample.

## External linkouts

| Resource | URL pattern |
|----------|-------------|
| **gnomAD v4** (GRCh38) | `https://gnomad.broadinstitute.org/variant/{chrom}-{pos}-{ref}-{alt}?dataset=gnomad_r4` (no `chr` prefix) |
| **GeneCards** | `https://www.genecards.org/cgi-bin/carddisp.pl?gene={SYMBOL}` |

Shown in the hits table, cohort overview, and detail panel. INFO `AF` in the TSV is sample/site allele fraction, not population frequency.

## Gene panels

Curated panels + Genomics England PanelApp + **OMIM genes** (`data/genePanels/mim2gene.txt`, panel id `omim:genes`) filter hits by gene symbol.

## IGV track provenance

| Track | Source |
|-------|--------|
| GENCODE v50 basic | Local GRCh38 gene models |
| uORFdb hg38 | Filtered human hg38 dump (`prepare_uorfdb.sh`) — not sample-specific |
| 5ULTRA 5′ UTR span | Per-sample BED from `5UTR_START`/`5UTR_END` in the 5ULTRA TSV |
| 5ULTRA affected uORF | Per-sample BED from `uORF_START`/`uORF_END` of the affected uORF |
| 5ULTRA variants | Per-sample VCF of candidate alleles |

## Score threshold

A **5ULTRA_Score ≥ 0.74** threshold captured ~90% of positive controls on the training set (accuracy 97.5%, sensitivity 90.2%, specificity 99.8%). The UI exposes this as a recommended filter.
