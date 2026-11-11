# syntax=docker/dockerfile:1
FROM python:3.12-slim
ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1 PIP_NO_CACHE_DIR=1
WORKDIR /app
COPY requirements.txt requirements-camera-evaluation.txt ./
RUN --mount=type=secret,id=proxy_ca \
    if [ -f /run/secrets/proxy_ca ]; then export PIP_CERT=/run/secrets/proxy_ca; fi; \
    pip install --no-cache-dir -r requirements.txt && \
    python -m venv /opt/ksnb-camera && \
    /opt/ksnb-camera/bin/pip install --no-cache-dir -r requirements-camera-evaluation.txt
COPY . .
RUN --mount=type=secret,id=proxy_ca \
    if [ -f /run/secrets/proxy_ca ]; then export SSL_CERT_FILE=/run/secrets/proxy_ca; fi; \
    python scripts/fetch_camera_models.py --destination /opt/ksnb-camera-models && \
    chmod 755 /opt/ksnb-camera-models && chmod 444 /opt/ksnb-camera-models/*
RUN python scripts/build_styles.py --check && python manage.py collectstatic --noinput && useradd --create-home app && chown -R app:app /app
ENV CAMERA_IDENTITY_ENABLED=0 \
    CAMERA_IDENTITY_DERIVE_TEMPLATE_KEY=1 \
    CAMERA_IDENTITY_ENGINE_PYTHON=/opt/ksnb-camera/bin/python \
    CAMERA_IDENTITY_MODEL_DIR=/opt/ksnb-camera-models
USER app
EXPOSE 8000
CMD ["sh", "-c", "python manage.py safe_migrate && python manage.py setup_roles && python manage.py bootstrap_admin && gunicorn config.wsgi:application --bind 0.0.0.0:${PORT:-8000} --workers 2 --timeout 120 --access-logfile - --access-logformat '%(h)s %(t)s %(m)s %(U)s %(s)s %(L)s'"]
