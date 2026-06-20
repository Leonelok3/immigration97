#!/usr/bin/env bash
set -euo pipefail

APP_DIR="/home/deployer/projects/immigration97"
LOG_DIR="$APP_DIR/logs"
LOG_FILE="$LOG_DIR/job_agent_daily.log"

mkdir -p "$LOG_DIR"
cd "$APP_DIR"

{
  echo "==== $(date -u '+%Y-%m-%d %H:%M:%S UTC') Job Agent daily ===="
  .venv/bin/python manage.py scrape_employer_opportunities \
    --countries CA \
    --sector autre \
    --source-url "https://www.guichetemplois.gc.ca/jobsearch/rechercheemplois?fglo=1&page=1&sort=M" \
    --source-url "https://www.guichetemplois.gc.ca/jobsearch/rechercheemplois?fglo=1&page=2&sort=M" \
    --source-url "https://www.guichetemplois.gc.ca/jobsearch/rechercheemplois?fglo=1&page=3&sort=M" \
    --source-url "https://www.jobbank.gc.ca/jobsearch/jobsearch?fsrc=32" \
    --source-url "https://placeauxjeunes.qc.ca/emplois" \
    --source-url "https://www.emploisnb.ca/jobs" \
    --source-url "https://www.saskjobs.ca/" \
    --source-url "https://www.workbc.ca/search-and-prepare-job/find-jobs" \
    --source-url "https://alis.alberta.ca/occinfo/alberta-job-postings/" \
    --source-url "https://www.emplois.ca/jobs" \
    --limit 220

  .venv/bin/python manage.py automate_job_agent_offers \
    --publish-verified \
    --sync-private \
    --limit 240

  .venv/bin/python manage.py cleanup_public_job_offers
  echo
} >> "$LOG_FILE" 2>&1
