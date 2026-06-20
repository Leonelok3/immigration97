#!/usr/bin/env bash
set -euo pipefail

PROJECT_DIR="/home/deployer/projects/immigration97"
LOG_DIR="$PROJECT_DIR/logs"

mkdir -p "$LOG_DIR"
cd "$PROJECT_DIR"

./.venv/bin/python manage.py run_daily_job_pipeline \
  --countries CA,NZ,AU,EU \
  --limit 80 \
  --publish-limit 70 \
  --include-review \
  >> "$LOG_DIR/daily_job_pipeline.log" 2>&1

