#!/usr/bin/env bash
set -euo pipefail

APP_DIR="/home/deployer/projects/immigration97"
LOG_DIR="$APP_DIR/logs"
LOG_FILE="$LOG_DIR/job_agent_germany.log"

mkdir -p "$LOG_DIR"
cd "$APP_DIR"

{
  echo "==== $(date -u '+%Y-%m-%d %H:%M:%S UTC') Job Agent Germany ===="
  .venv/bin/python manage.py scrape_employer_opportunities \
    --countries DE \
    --sector autre \
    --source-url "https://www.arbeitsagentur.de/jobsuche/suche?angebotsart=4" \
    --source-url "https://www.make-it-in-germany.com/en/working-in-germany/job-listings" \
    --source-url "https://www.ausbildung.de/stellen/" \
    --source-url "https://www.azubiyo.de/stellenmarkt/" \
    --source-url "https://www.aubi-plus.de/ausbildung/" \
    --limit 180

  .venv/bin/python manage.py automate_job_agent_offers \
    --publish-verified \
    --limit 260

  .venv/bin/python manage.py cleanup_public_job_offers
  echo
} >> "$LOG_FILE" 2>&1
