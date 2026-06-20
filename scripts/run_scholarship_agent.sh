#!/usr/bin/env bash
set -euo pipefail

APP_DIR="/home/deployer/projects/immigration97"
LOG_DIR="$APP_DIR/logs"
LOG_FILE="$LOG_DIR/scholarship_agent.log"

mkdir -p "$LOG_DIR"
cd "$APP_DIR"

{
  echo "==== $(date -u '+%Y-%m-%d %H:%M:%S UTC') Scholarship Agent ===="
  .venv/bin/python manage.py scrape_scholarship_offers \
    --query 'official scholarship international students Africa fully funded master phd deadline application' \
    --limit 80
  .venv/bin/python manage.py scrape_scholarship_offers \
    --source-url "https://www.daad.de/en/studying-in-germany/scholarships/daad-scholarships/" \
    --source-url "https://www.campusfrance.org/en/eiffel-scholarship-program-of-excellence" \
    --source-url "https://www.chevening.org/scholarships/" \
    --source-url "https://www.commonwealthscholarships.org/" \
    --source-url "https://www.studyinaustralia.gov.au/en/plan-your-studies/scholarships" \
    --source-url "https://www.educanada.ca/scholarships-bourses/index.aspx?lang=eng" \
    --source-url "https://www.studyinjapan.go.jp/en/planning/scholarships/" \
    --source-url "https://www.turkiyeburslari.gov.tr/" \
    --limit 120
  .venv/bin/python manage.py cleanup_scholarship_offers
  echo
} >> "$LOG_FILE" 2>&1
