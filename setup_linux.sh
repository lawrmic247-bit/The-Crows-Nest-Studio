#!/usr/bin/env bash
set -euo pipefail
python3 -m venv .venv
.venv/bin/python -m pip install --upgrade pip
.venv/bin/python -m pip install Pillow piper-tts==1.8.0
mkdir -p voices
.venv/bin/python -m piper.download_voices --data-dir voices en_US-lessac-medium
.venv/bin/python studio.py doctor
