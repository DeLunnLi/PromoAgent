#!/usr/bin/env bash
# Source2Launch test and launch-assets smoke script.

set -euo pipefail

echo "Source2Launch test and generate"
echo

echo "[1/3] Python tests"
npm run test:python
echo

echo "[2/3] Optional API key check"
if [[ -n "${SOURCE2LAUNCH_MODELSCOPE_API_KEY:-}" ]]; then
  echo "  SOURCE2LAUNCH_MODELSCOPE_API_KEY is configured."
else
  echo "  SOURCE2LAUNCH_MODELSCOPE_API_KEY is not configured; continuing in local evidence mode."
fi
echo

echo "[3/3] Generate launch-assets"
python3 -m source2launch.cli optimize . --output launch-assets/
echo

echo "Generated files:"
find launch-assets -maxdepth 2 -type f | sort | sed 's#^#  - #'
