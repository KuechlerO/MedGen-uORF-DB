#!/usr/bin/env bash
# Convert GENCODE gzip downloads to bgzip + indexes for IGV.js Range requests.
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
REF="${ROOT}/data/reference_genome"

export PATH="/data01/miniforge3/envs/django_primer_design_env/bin:${PATH}"
export LD_LIBRARY_PATH="/data01/miniforge3/envs/django_primer_design_env/lib:${LD_LIBRARY_PATH:-}"

SAMTOOLS="${SAMTOOLS:-}"
if [[ -z "${SAMTOOLS}" ]]; then
  for s in /data01/miniforge3/pkgs/samtools-*/bin/samtools; do
    if "$s" --version >/dev/null 2>&1; then
      SAMTOOLS="$s"
      break
    fi
  done
fi
if [[ -z "${SAMTOOLS}" ]]; then
  echo "samtools not found" >&2
  exit 1
fi

command -v bgzip >/dev/null
command -v tabix >/dev/null

FASTA="${REF}/GRCh38.p14.genome.fa.gz"
GTF="${REF}/gencode.v50.basic.annotation.gtf.gz"
FASTA_ORIG="${REF}/GRCh38.p14.genome.fa.orig.gz"
GTF_ORIG="${REF}/gencode.v50.basic.annotation.gtf.orig.gz"

mkdir -p "${REF}"

is_bgzip() {
  # bgzip -t returns 0 only for bgzip; also require .gzi after faidx for fasta
  bgzip -t "$1" >/dev/null 2>&1
}

echo "==> Preparing FASTA (bgzip + faidx)"
if [[ -f "${FASTA}.fai" && -f "${FASTA}.gzi" ]] && is_bgzip "${FASTA}"; then
  echo "    FASTA already bgzip-indexed, skipping"
else
  # Preserve original gzip download once
  if [[ ! -f "${FASTA_ORIG}" ]]; then
    if [[ -f "${FASTA}" ]]; then
      echo "    Backing up current FASTA → $(basename "${FASTA_ORIG}")"
      mv "${FASTA}" "${FASTA_ORIG}"
    else
      echo "Missing FASTA at ${FASTA} (and no ${FASTA_ORIG})" >&2
      exit 1
    fi
  fi

  rm -f "${FASTA}.fai" "${FASTA}.gzi" "${FASTA}.tmp"
  echo "    Streaming $(basename "${FASTA_ORIG}") → bgzip $(basename "${FASTA}")"
  zcat "${FASTA_ORIG}" | bgzip -@ "$(nproc 2>/dev/null || echo 4)" -c > "${FASTA}.tmp"
  mv "${FASTA}.tmp" "${FASTA}"
  echo "    samtools faidx $(basename "${FASTA}")"
  "${SAMTOOLS}" faidx "${FASTA}"
fi

echo "==> Preparing GENCODE GTF (bgzip + tabix)"
if [[ -f "${GTF}.tbi" ]] && is_bgzip "${GTF}"; then
  echo "    GTF already bgzip+tabix indexed, skipping"
else
  if [[ ! -f "${GTF_ORIG}" ]]; then
    if [[ -f "${GTF}" ]]; then
      echo "    Backing up current GTF → $(basename "${GTF_ORIG}")"
      mv "${GTF}" "${GTF_ORIG}"
    else
      echo "Missing GTF at ${GTF} (and no ${GTF_ORIG})" >&2
      exit 1
    fi
  fi

  rm -f "${GTF}.tbi" "${GTF}.tmp"
  echo "    Sorting + bgzip $(basename "${GTF_ORIG}") → $(basename "${GTF}")"
  # GENCODE “basic” GTF is not strictly position-sorted; tabix requires sorted intervals.
  (
    zcat "${GTF_ORIG}" | grep '^#' || true
    zcat "${GTF_ORIG}" | grep -v '^#' | sort -t $'\t' -k1,1 -k4,4n
  ) | bgzip -@ "$(nproc 2>/dev/null || echo 4)" -c > "${GTF}.tmp"
  mv "${GTF}.tmp" "${GTF}"
  echo "    tabix -p gff $(basename "${GTF}")"
  tabix -f -p gff "${GTF}"
fi

echo "==> Done"
ls -lh "${FASTA}" "${FASTA}.fai" "${FASTA}.gzi" "${GTF}" "${GTF}.tbi"
