#!/usr/bin/env bash
set -euo pipefail
python -m pip install -r requirements.txt
if [[ "${CAMERA_IDENTITY_ENABLED:-0}" == "1" ]]; then
  : "${CAMERA_IDENTITY_ENGINE_PYTHON:?Set an absolute engine Python path}"
  : "${CAMERA_IDENTITY_MODEL_DIR:?Set an absolute model directory}"
  if [[ "$CAMERA_IDENTITY_ENGINE_PYTHON" != /*/bin/python || "$CAMERA_IDENTITY_MODEL_DIR" != /* ]]; then
    echo "Camera engine and model paths must be absolute" >&2
    exit 1
  fi
  camera_environment="${CAMERA_IDENTITY_ENGINE_PYTHON%/bin/python}"
  python -m venv "$camera_environment"
  "$CAMERA_IDENTITY_ENGINE_PYTHON" -m pip install -r requirements-camera-evaluation.txt
  python scripts/fetch_camera_models.py --destination "$CAMERA_IDENTITY_MODEL_DIR"
fi
python scripts/build_styles.py --check
python manage.py collectstatic --noinput
