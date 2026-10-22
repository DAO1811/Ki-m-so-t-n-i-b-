"""Local-only preview boundary; rejects production URLs before database writes."""

import os
from urllib.parse import urlsplit


def validate_preview_environment(environ=None):
    env = os.environ if environ is None else environ
    url = urlsplit(env.get("DATABASE_URL", ""))
    if (
        env.get("DHD_PREVIEW") != "1"
        or env.get("DEBUG") != "1"
        or env.get("RENDER_EXTERNAL_HOSTNAME")
        or url.scheme not in {"postgres", "postgresql"}
        or url.hostname not in {"db", "127.0.0.1", "localhost"}
        or url.username != "dhd_preview"
        or url.path not in {"/dhd_preview", "/test_dhd_preview"}
        or url.query
        or url.fragment
    ):
        raise RuntimeError(
            "Bản thử chỉ dùng PostgreSQL local dhd_preview, DEBUG=1 và DHD_PREVIEW=1. "
            "Không dùng cấu hình Render/Neon hoặc dữ liệu công ty."
        )


def preview_context(request):
    from django.conf import settings

    return {"is_preview": settings.DHD_PREVIEW}
