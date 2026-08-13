# MedGen uORF Explorer

Web app that places **5ULTRA** uORF perturbation candidates in a genome-browser context alongside established (uORFdb-style) annotations.

Genome build: **GRCh38 / hg38**.

## Quick start

Corporate HTTP proxies can break localhost calls from the shell; the Vite UI talking to the API on the same machine is unaffected. If `curl` to `127.0.0.1` fails, use `curl --noproxy '*' …`.

```bash
# 1) Ingest the 5ULTRA cohort (splice + nosplice TSVs → SQLite + per-sample tracks)
#    Expects data/5ULTRA/{nosplice,splice}/*.tsv
bash scripts/prepare_cohort.sh

# 2) Prepare local GRCh38 + GENCODE for IGV (bgzip + indexes; once)
#    Place downloads in data/reference_genome/:
#      GRCh38.p14.genome.fa.gz
#      gencode.v50.basic.annotation.gtf.gz
bash scripts/prepare_reference.sh

# 2b) Prepare human uORFdb track (once; scans ~6 GB dump)
#     Place download at data/uORFdb/uORF_dump_uORFdb.tsv
bash scripts/prepare_uorfdb.sh

# 3) API (http://localhost:8001) — serves /api, /tracks, /reference
#    (default port 8001 to avoid clashes; override with PORT=…)
bash scripts/start_api.sh

# 4) UI (http://localhost:5173) — proxies /api, /tracks, /reference → :8001
bash scripts/start_ui.sh
```

Open the UI, pick a **sample ID** (prefix before `-N1`, e.g. `10_0463`), toggle **nosplice / splice / both**, and inspect hits in IGV plus the detail drawer.

API docs: http://localhost:8001/docs

## Multi-sample cohort

The explorer is **sample-first**: each WGS sample has separate **nosplice** and **splice** 5ULTRA runs.

| Step | Output |
|------|--------|
| `bash scripts/prepare_cohort.sh` | `data/catalog/uorf.db` (SQLite) |
| | `data/catalog/samples.json` (sample summary) |
| | `data/tracks/by_sample/{sample_id}/{mode}/` (VCF + BED per sample) |

**Sample ID** = token before `-N1` in filenames like `10_0463-N1-DNA1-WGS1__…__.hg38.5ULTRA.tsv`.

Drop future datasets under `data/<dataset>/…` and extend `ingest/ingest_cohort.py` with a new `dataset` tag.

### Verify a sample

```bash
python3 -c "
import sqlite3
c = sqlite3.connect('data/catalog/uorf.db')
for mode in ('nosplice','splice'):
    n = c.execute('SELECT hit_count FROM samples WHERE sample_id=? AND mode=?', ('10_0463', mode)).fetchone()
    print('10_0463', mode, n[0] if n else 0)
"
```

## Single-file demo (legacy)

For a one-off TSV (e.g. [`example.tsv`](example.tsv)) without the full cohort:

```bash
python3 ingest/run_ingest.py example.tsv
```

This writes `data/tracks/hits.json` and global demo tracks. The API falls back to these when `data/catalog/uorf.db` is missing.

## Deploy on s-bih-mantomias (nginx + Docker)

Serve the app under **`/uorf-explorer/`** (port **8092**). `/kuechleo/` is already used by the CRISPR tool.

### 1. Prerequisites on the host

Catalog + tracks + reference must already exist (mounted into the container):

```bash
bash scripts/prepare_cohort.sh
bash scripts/prepare_reference.sh   # if not done
bash scripts/prepare_uorfdb.sh      # if not done
```

### 2. Docker Compose

Append the service from [`deploy/docker-compose.snippet.yml`](deploy/docker-compose.snippet.yml) to the shared compose file, then:

```bash
cd /data01/git-userfolder   # or wherever docker-compose.yml lives
sudo docker compose build kuechleo_uorf_explorer
sudo docker compose up -d kuechleo_uorf_explorer
```

### 3. Nginx

Add the block from [`deploy/nginx.snippet.conf`](deploy/nginx.snippet.conf) to `/etc/nginx/sites-enabled/django-devs.conf`, then:

```bash
sudo nginx -t && sudo systemctl reload nginx
```

### 4. Open

http://s-bih-mantomias.charite.de/uorf-explorer/

`PUBLIC_BASE_PATH` / `VITE_BASE_PATH` must match the nginx location. Trailing slash on `proxy_pass …8092/;` strips `/uorf-explorer` so the container still serves `/api`, `/tracks`, `/`.

## Local reference genome


IGV uses **locally hosted** GRCh38 sequence + GENCODE v50 (same origin via `/reference`), which avoids UCSC `hg38.2bit` CORS failures and speeds up locus switches.

| Asset | Path after `prepare_reference.sh` |
|-------|-----------------------------------|
| Sequence (bgzip) | `data/reference_genome/GRCh38.p14.genome.fa.gz` (+ `.fai`, `.gzi`) |
| Genes (bgzip+tabix) | `data/reference_genome/gencode.v50.basic.annotation.gtf.gz` (+ `.tbi`) |
| Original gzip backups | `*.orig.gz` (kept so you can re-run prepare) |

`prepare_reference.sh` needs `bgzip`, `tabix`, and `samtools` (htsilib). On this host the script looks under the `django_primer_design_env` conda env / pkgs.

## Human uORFdb track

Filter the multi-species [uORFdb](https://www.bioinformatics.uni-muenster.de/tools/uorfdb/download) dump to **Homo sapiens / hg38** (~2.4 M intervals) and serve as a tabix-indexed BED:

```bash
# expects data/uORFdb/uORF_dump_uORFdb.tsv
bash scripts/prepare_uorfdb.sh
# → data/tracks/uorfdb_uorfs.bed.gz (+ .tbi)
```

## What you see

| Track | Meaning |
|-------|---------|
| GENCODE v50 basic | Transcript structure (local) |
| uORFdb hg38 | Human hg38 uORFs from uORFdb (or curated demo if dump not prepared) |
| 5′ UTR | TLS span for the selected sample |
| Perturbed uORFs | Affected uORF spans colored by 5ULTRA score |
| 5ULTRA variants | Candidate SNVs for the selected sample |

When **both** modes are active, IGV tracks follow the selected hit’s mode (nosplice by default).

## Project layout

```
ingest/                 # TSV → SQLite / VCF / BED
data/5ULTRA/            # Cohort TSVs (splice/, nosplice/)
data/catalog/           # uorf.db + samples.json
data/tracks/by_sample/  # Per-sample IGV tracks
data/reference_genome/  # Local GRCh38 + GENCODE (bgzip/indexed)
data/uORFdb/            # Full uORFdb dump (filter with prepare_uorfdb.sh)
backend/                # FastAPI sample catalog + static /tracks + /reference
frontend/               # Vite + React + IGV.js
scripts/                # prepare_*.sh, start_*.sh
```

## API

- `GET /api/health` — reference readiness + catalog stats
- `GET /api/samples?q=` — list/filter samples with hit counts
- `GET /api/samples/{sample_id}` — sample summary + available modes
- `GET /api/samples/{sample_id}/hits?mode=nosplice|splice|both&gene=&q=&min_score=`
- `GET /api/search?q=&sample=&mode=` — scoped gene/variant search
- `GET /api/tracks?sample=&mode=&hit_mode=` — IGV reference + track configs
- `GET /api/ucsc?chrom=&start=&end=` — UCSC deep-link helper
- `GET /tracks/*` — static BED/VCF/JSON
- `GET /reference/*` — local fasta/GTF (+ indexes)

Legacy gene endpoints (`/api/genes`, `/api/gene/{symbol}`) return **410** when the cohort catalog is present.

## Ingest only

```bash
# Full cohort
bash scripts/prepare_cohort.sh

# Single TSV
python3 ingest/run_ingest.py path/to/your_5ultra.tsv
python3 ingest/parse_5ultra.py example.tsv -o data/tracks
```

## Column notes (5ULTRA)

Key fields used for visualization: `CHROM`, `POS`, `REF`, `ALT`, `CSQ`, `Translation`, `5ULTRA_Score`, `GENE`, `TRANSCRIPT`, `5UTR_*`, `STRAND`, `mSTART`, `uORF_START`/`END`, Kozak / conservation / Ribo-seq fields. **nosplice** TSVs omit `SpliceAI` / `Splicing_CSQ`; **splice** TSVs include them. Sample genotype columns (anything after `FORMAT` that is not a fixed annotation field) are parsed into zygosity (het/hom) for the UI and carried through into the VCF.

Gene panels include curated lists, Genomics England PanelApp, and **OMIM genes** from `data/genePanels/mim2gene.txt`.

The UI links each gene to [GeneCards](https://www.genecards.org/) and each variant to [gnomAD v4](https://gnomad.broadinstitute.org/) (`chrom-pos-ref-alt` on GRCh38). See [`docs/columns.md`](docs/columns.md).

## License / citation

When using uORFdb dumps, cite [Manske et al., NAR 2023](https://doi.org/10.1093/nar/gkac899). 5ULTRA annotations follow the [5ULTRA](https://hgidsoft.rockefeller.edu/5ULTRA/) tool and associated publication.
