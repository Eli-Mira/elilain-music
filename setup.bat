@echo off
echo === Installing elilain-music ===
python -m venv .venv
.venv\Scripts\activate
pip install -e .
echo Done. Run: python -m elilain_music
