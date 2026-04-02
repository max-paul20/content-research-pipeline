#!/bin/bash
set -euo pipefail

cd "$(dirname "$0")"
mkdir -p data/logs
source venv/bin/activate
python3 main.py >> data/logs/cron.log 2>&1
