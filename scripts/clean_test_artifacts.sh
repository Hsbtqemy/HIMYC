#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT_DIR"

echo "Cleaning local test runtime artifacts..."

rm -rf \
  tests/__pycache__ \
  tests/.cache \
  tests/episodes \
  tests/runs

rm -f \
  tests/corpus.db \
  tests/config.toml \
  tests/series_index.json \
  tests/character_names.json \
  tests/episode_prep_status.json \
  tests/episode_segmentation_options.json

echo "Done."
