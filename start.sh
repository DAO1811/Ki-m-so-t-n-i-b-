#!/usr/bin/env bash
set -euo pipefail
python manage.py prepare_runtime
exec gunicorn config.wsgi:application --bind "0.0.0.0:${PORT:-8000}" --workers "${WEB_CONCURRENCY:-2}" --access-logfile - --access-logformat '%(h)s %(t)s %(m)s %(U)s %(s)s %(L)s'
