#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "$0")"
mkdir -p out/audio out/raw
python3 tts.py
node render.mjs
