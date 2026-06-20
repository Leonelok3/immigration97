#!/usr/bin/env bash
set -euo pipefail

APP_DIR="/home/deployer/projects/immigration97"
LOG_DIR="$APP_DIR/logs"
LOG_FILE="$LOG_DIR/job_agent_spain.log"

mkdir -p "$LOG_DIR"
cd "$APP_DIR"

{
  echo "==== $(date -u '+%Y-%m-%d %H:%M:%S UTC') Job Agent Spain ===="
  .venv/bin/python manage.py scrape_employer_opportunities \
    --countries ES \
    --sector agriculture \
    --query 'Espana agricultura campo temporero peon agricola contratacion en origen permiso de trabajo alojamiento oferta empleo rural' \
    --limit 120
  .venv/bin/python manage.py scrape_employer_opportunities \
    --countries ES \
    --sector construction \
    --query 'Espana construccion albanil peon obra soldador permiso de trabajo trabajadores extranjeros oferta empleo rural' \
    --limit 100
  .venv/bin/python manage.py scrape_employer_opportunities \
    --countries ES \
    --sector hotellerie \
    --query 'Espana hosteleria restaurante camarero cocinero ayudante cocina alojamiento permiso de trabajo oferta empleo rural' \
    --limit 100
  .venv/bin/python manage.py scrape_employer_opportunities \
    --countries ES \
    --sector hotellerie \
    --source-url "https://www.hosteleo.com/ofertas-trabajo/" \
    --source-url "https://www.hosteleo.com/es/camarero" \
    --source-url "https://www.hosteleo.com/es/cocinero" \
    --source-url "https://www.hosteleo.com/es/ayudante-de-cocina" \
    --source-url "https://www.hosteleo.com/es/limpieza" \
    --source-url "https://www.turijobs.com/ofertas-trabajo/espana" \
    --limit 120
  .venv/bin/python manage.py scrape_employer_opportunities \
    --countries ES \
    --sector industrie \
    --query 'Espana fabrica operario produccion manipulador envasado almacen trabajadores extranjeros permiso de trabajo oferta empleo rural' \
    --limit 100
  .venv/bin/python manage.py scrape_employer_opportunities \
    --countries ES \
    --sector industrie \
    --source-url "https://jobs.eurofirms.com/es/es/trabajo/" \
    --limit 80
  .venv/bin/python manage.py automate_job_agent_offers \
    --publish-verified \
    --limit 260
  .venv/bin/python manage.py cleanup_public_job_offers
  echo
} >> "$LOG_FILE" 2>&1
