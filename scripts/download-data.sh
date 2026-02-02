#!/bin/bash
#
# Download data release for ban-teemo
#
# Usage:
#   ./scripts/download-data.sh           # Downloads latest (v1.0.0)
#   ./scripts/download-data.sh v0.4.0    # Downloads specific version
#
# Requires: gh CLI (GitHub CLI) - https://cli.github.com/
#
set -e

DATA_VERSION="${1:-v1.0.0}"
OUTPUT_DIR="."
TARBALL="ban-teemo-data.tar.gz"

# Check for gh CLI
if ! command -v gh &> /dev/null; then
    echo "Error: gh CLI required. Install from https://cli.github.com/"
    exit 1
fi

echo "==> Downloading ${DATA_VERSION} from GitHub releases..."

# Download using gh CLI (handles auth for private repos)
gh release download "${DATA_VERSION}" --pattern "${TARBALL}" --dir "${OUTPUT_DIR}"

echo "==> Extracting..."
tar -xzf "${OUTPUT_DIR}/${TARBALL}"

# Cleanup
rm -f "${OUTPUT_DIR}/${TARBALL}"

echo "==> Done!"
echo ""
echo "Contents:"
echo "  - outputs/full_2024_2025_v2/csv/  (CSV data)"
echo "  - knowledge/replay_meta/          (Replay metadata)"
echo "  - data/draft_data.duckdb          (DuckDB database)"
