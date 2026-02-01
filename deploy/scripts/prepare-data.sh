#!/bin/bash
# =============================================================================
# Prepare Data for Deployment
# =============================================================================
# This script packages data files for deployment since they are gitignored.
#
# Usage:
#   ./deploy/scripts/prepare-data.sh          # Create data archive
#   ./deploy/scripts/prepare-data.sh extract  # Extract data archive
#
# The archive can be:
#   1. Uploaded as a GitHub Release asset
#   2. Stored in cloud storage (S3, GCS, R2)
#   3. Committed to a separate deployment branch

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd "$SCRIPT_DIR/../.." && pwd)"
CSV_DIR="$PROJECT_ROOT/outputs/full_2024_2025_v2/csv"
KNOWLEDGE_DIR="$PROJECT_ROOT/knowledge"
DUCKDB_FILE="$PROJECT_ROOT/data/draft_data.duckdb"
ARCHIVE_NAME="ban-teemo-data.tar.gz"

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

log_info() { echo -e "${GREEN}[INFO]${NC} $1"; }
log_warn() { echo -e "${YELLOW}[WARN]${NC} $1"; }
log_error() { echo -e "${RED}[ERROR]${NC} $1"; }

create_archive() {
    log_info "Creating data archive..."

    # Verify data exists
    if [[ ! -d "$CSV_DIR" ]]; then
        log_error "CSV directory not found: $CSV_DIR"
        log_info "Run the data ingestion scripts first to populate this directory."
        exit 1
    fi

    if [[ ! -d "$KNOWLEDGE_DIR" ]]; then
        log_error "Knowledge directory not found: $KNOWLEDGE_DIR"
        exit 1
    fi

    if [[ ! -f "$DUCKDB_FILE" ]]; then
        log_error "DuckDB file not found: $DUCKDB_FILE"
        log_info "Run: cd backend && uv run python scripts/build_duckdb.py"
        exit 1
    fi

    cd "$PROJECT_ROOT"

    # Create archive with data files
    # Note: data/draft_data.duckdb is the pre-built database used by the app
    tar -czvf "$ARCHIVE_NAME" \
        outputs/full_2024_2025_v2/csv \
        knowledge \
        data/draft_data.duckdb

    # Show archive info
    ARCHIVE_SIZE=$(du -h "$ARCHIVE_NAME" | cut -f1)
    log_info "Archive created: $ARCHIVE_NAME ($ARCHIVE_SIZE)"

    # Generate checksum
    sha256sum "$ARCHIVE_NAME" > "$ARCHIVE_NAME.sha256"
    log_info "Checksum saved: $ARCHIVE_NAME.sha256"

    echo ""
    log_info "Next steps:"
    echo "  1. Upload to GitHub Release:"
    echo "     gh release create v0.1.0 $ARCHIVE_NAME --title 'v0.1.0'"
    echo ""
    echo "  2. Or upload to Cloudflare R2/S3:"
    echo "     aws s3 cp $ARCHIVE_NAME s3://your-bucket/data/"
}

extract_archive() {
    log_info "Extracting data archive..."

    cd "$PROJECT_ROOT"

    if [[ ! -f "$ARCHIVE_NAME" ]]; then
        log_error "Archive not found: $ARCHIVE_NAME"
        log_info "Download it first or run without arguments to create it."
        exit 1
    fi

    # Verify checksum if available
    if [[ -f "$ARCHIVE_NAME.sha256" ]]; then
        log_info "Verifying checksum..."
        sha256sum -c "$ARCHIVE_NAME.sha256"
    fi

    # Extract
    tar -xzvf "$ARCHIVE_NAME"

    log_info "Data extracted successfully!"
}

# Main
case "${1:-create}" in
    create)
        create_archive
        ;;
    extract)
        extract_archive
        ;;
    *)
        echo "Usage: $0 [create|extract]"
        exit 1
        ;;
esac
