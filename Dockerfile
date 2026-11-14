FROM python:3.12-slim
ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1 PIP_NO_CACHE_DIR=1 DEBUG=0
WORKDIR /app
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
COPY . .
# collectstatic only reads static files; build-time flags never reach the runtime image.
RUN python scripts/build_styles.py --check && DEBUG=1 SECRET_KEY=build-only-collectstatic python manage.py collectstatic --noinput && useradd --create-home app && chown -R app:app /app
USER app
EXPOSE 8000
CMD ["bash", "start.sh"]
