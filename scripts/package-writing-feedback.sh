#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "${SCRIPT_DIR}/.." && pwd)"
SOURCE_DIR="${REPO_ROOT}/writing-feedback"
OUTPUT_DIR="${1:-${REPO_ROOT}}"

if [[ ! -d "${SOURCE_DIR}" ]]; then
  echo "missing source directory: ${SOURCE_DIR}" >&2
  exit 1
fi

if ! command -v zip >/dev/null 2>&1; then
  echo "zip command not found" >&2
  exit 1
fi

mkdir -p "${OUTPUT_DIR}"

timestamp="$(date +%Y%m%d-%H%M%S)"
commit_id="$(git -C "${REPO_ROOT}" rev-parse --short HEAD 2>/dev/null || echo nogit)"
zip_name="writing-feedback-${timestamp}-${commit_id}.zip"
output_path="${OUTPUT_DIR%/}/${zip_name}"

(
  cd "${REPO_ROOT}"
  zip -rq "${output_path}" writing-feedback \
    -x "*/.DS_Store" \
    -x "writing-feedback/config/gemini_ocr.json" \
    -x "*/__pycache__/*" \
    -x "*/.pytest_cache/*"
)

echo "${output_path}"
