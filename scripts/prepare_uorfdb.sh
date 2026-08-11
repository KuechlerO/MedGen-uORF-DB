#!/usr/bin/env bash
# Filter uORFdb dump to Homo sapiens / hg38 and build a tabix-indexed BED track.
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
DUMP="${1:-${ROOT}/data/uORFdb/uORF_dump_uORFdb.tsv}"
OUT_DIR="${ROOT}/data/tracks"
BED_UNSORTED="${OUT_DIR}/uorfdb_uorfs.unsorted.bed"
BED="${OUT_DIR}/uorfdb_uorfs.bed"
BED_GZ="${OUT_DIR}/uorfdb_uorfs.bed.gz"

export PATH="/data01/miniforge3/envs/django_primer_design_env/bin:${PATH}"
export LD_LIBRARY_PATH="/data01/miniforge3/envs/django_primer_design_env/lib:${LD_LIBRARY_PATH:-}"

command -v bgzip >/dev/null
command -v tabix >/dev/null

if [[ ! -f "${DUMP}" ]]; then
  echo "Missing uORFdb dump: ${DUMP}" >&2
  echo "Place uORF_dump_uORFdb.tsv under data/uORFdb/ or pass the path as \$1." >&2
  exit 1
fi

mkdir -p "${OUT_DIR}"

echo "==> Converting (Homo sapiens / hg38) → unsorted BED"
python3 "${ROOT}/ingest/convert_uorfdb.py" "${DUMP}" \
  -o "${BED_UNSORTED}" \
  --taxon "Homo sapiens" \
  --assembly hg38

echo "==> Sorting BED"
sort -k1,1 -k2,2n "${BED_UNSORTED}" > "${BED}"
rm -f "${BED_UNSORTED}"

echo "==> bgzip + tabix"
rm -f "${BED_GZ}" "${BED_GZ}.tbi"
bgzip -@ "$(nproc 2>/dev/null || echo 4)" -c "${BED}" > "${BED_GZ}"
tabix -f -p bed "${BED_GZ}"
# Keep plain BED only if tiny (demo); for genome-wide dump prefer .bed.gz
# Remove uncompressed BED to save space when large
BED_LINES=$(wc -l < "${BED}")
if [[ "${BED_LINES}" -gt 100000 ]]; then
  echo "    Removing uncompressed BED (${BED_LINES} lines); serving .bed.gz"
  rm -f "${BED}"
fi

echo "==> Done"
ls -lh "${BED_GZ}" "${BED_GZ}.tbi"
echo "Intervals: $(bgzip -dc "${BED_GZ}" | wc -l)"
