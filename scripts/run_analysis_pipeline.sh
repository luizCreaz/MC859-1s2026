#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT"

echo "==> Building mesoregion subgraphs"
python3 scripts/graph-builders/build_mesoregion_subgraphs.py

echo "==> Running assortativity analysis"
python3 scripts/graph-algorithms/assortativity/calculate_assortativity.py

echo "==> Running betweenness centrality analysis"
python3 scripts/graph-algorithms/betweeness-centrality/calculate_betweenness_centrality.py

echo "==> Generating report tables and charts"
python3 scripts/graph-algorithms/generate_report_tables.py

echo "==> Done. Report artifacts: results/report/"
