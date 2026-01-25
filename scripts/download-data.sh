#!/bin/bash
#
# Download data release for ban-teemo
#
# Usage:
#   ./scripts/download-data.sh           # Downloads latest (v1.0.0)
#   ./scripts/download-data.sh v1.1.0    # Downloads specific version
#
# Requires: gh CLI (GitHub CLI) - https://cli.github.com/
#
set -e

DATA_VERSION="${1:-v1.0.0}"
OUTPUT_DIR="outputs"
TARBALL="data-${DATA_VERSION}.tar.gz"

# Check for gh CLI
if ! command -v gh &> /dev/null; then
    echo "Error: gh CLI required. Install from https://cli.github.com/"
    exit 1
fi

echo "==> Downloading data-${DATA_VERSION} from GitHub releases..."

# Create output directory
mkdir -p "${OUTPUT_DIR}"

# Download using gh CLI (handles auth for private repos)
gh release download "data-${DATA_VERSION}" --pattern "${TARBALL}" --dir "${OUTPUT_DIR}"

echo "==> Extracting to ${OUTPUT_DIR}/..."
tar -xzf "${OUTPUT_DIR}/${TARBALL}" -C "${OUTPUT_DIR}"

# Cleanup
rm -f "${OUTPUT_DIR}/${TARBALL}"

echo "==> Done! Data available at ${OUTPUT_DIR}/full_2024_2025_v2/"
echo ""
echo "Contents:"
ls -la "${OUTPUT_DIR}/full_2024_2025_v2/csv/" 2>/dev/null || echo "  (extraction directory may vary)"
