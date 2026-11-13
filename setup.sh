#!/bin/bash
set -e
echo "=== Installing elilain-music ==="
python3 -m venv .venv
source .venv/bin/activate
pip install -e .
echo "Done. Run: python -m elilain_music"
