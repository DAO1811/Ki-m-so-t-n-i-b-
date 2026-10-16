#!/usr/bin/env bash
set -euo pipefail
python manage.py migrate --noinput
python manage.py setup_roles
python manage.py bootstrap_admin
exec gunicorn config.wsgi:application --bind "0.0.0.0:${PORT:-8000}" --workers "${WEB_CONCURRENCY:-2}" --access-logfile -
