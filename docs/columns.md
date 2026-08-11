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
| FORMAT + sample column | Genotype carried into VCF |

Unknown columns after `FORMAT` are treated as the sample genotype field.

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
