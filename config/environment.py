"""Deployment identity: production vs. staging, plus a human release label.

Staging must never reach company services (Drive, email, Groq) even when a key
is configured by mistake. See docs/RELEASE_PROCESS.md.
"""

import os

PRODUCTION = "production"
STAGING = "staging"
ENVIRONMENTS = (PRODUCTION, STAGING)
STAGING_BLOCKED_MESSAGE = "Bản thử không kết nối dịch vụ thật."


def app_environment():
    value = os.environ.get("APP_ENVIRONMENT", PRODUCTION).strip().lower() or PRODUCTION
    if value not in ENVIRONMENTS:
        raise RuntimeError("APP_ENVIRONMENT must be 'production' or 'staging'")
    return value


def is_staging():
    return app_environment() == STAGING


def app_version():
    value = os.environ.get("APP_VERSION", "").strip()
    return value[:64] if value else "unknown"
