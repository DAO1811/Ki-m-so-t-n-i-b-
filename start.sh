#!/usr/bin/env bash
set -euo pipefail
python manage.py safe_migrate
python manage.py setup_roles
python manage.py bootstrap_admin
if [ "${APP_ENVIRONMENT:-production}" = "staging" ]; then
  # Staging only: load sample data once the owner has set STAGING_SEED_PASSWORD.
  python manage.py seed_staging --auto
fi
exec gunicorn config.wsgi:application --bind "0.0.0.0:${PORT:-8000}" --workers "${WEB_CONCURRENCY:-2}" --timeout "${GUNICORN_TIMEOUT:-120}" --access-logfile - --access-logformat '%(h)s %(t)s %(m)s %(U)s %(s)s %(L)s'
