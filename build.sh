#!/usr/bin/env bash
set -euo pipefail
python -m pip install -r requirements.txt
python scripts/build_styles.py --check
python manage.py collectstatic --noinput
