"""Track and revoke signed-in devices (chủ phần mềm duyệt mục 4.3, 14/11/2026).

Only this app's table and Django's own session rows are touched. A device is
logged out by deleting its Django session; its next request is anonymous.
"""

import re
from datetime import timedelta

from django.contrib.sessions.models import Session
from django.db import transaction
from django.utils import timezone

from login_guard.services import client_ip

from .models import DeviceSession

TOUCH_EVERY = timedelta(minutes=5)


def describe(user_agent):
    ua = user_agent or ""
    browser = next(
        (
            name
            for pattern, name in (
                (r"Edg/", "Edge"),
                (r"OPR/|Opera", "Opera"),
                (r"CriOS|Chrome/", "Chrome"),
                (r"FxiOS|Firefox/", "Firefox"),
                (r"Safari/", "Safari"),
            )
            if re.search(pattern, ua)
        ),
        "Trình duyệt",
    )
    system = next(
        (
            name
            for pattern, name in (
                (r"iPhone|iPad|iOS", "iPhone/iPad"),
                (r"Android", "Android"),
                (r"Windows", "Windows"),
                (r"Mac OS X|Macintosh", "macOS"),
                (r"Linux", "Linux"),
            )
            if re.search(pattern, ua)
        ),
        "",
    )
    return f"{browser} trên {system}" if system else browser


def record(request, user):
    key = request.session.session_key
    if not key:
        request.session.save()
        key = request.session.session_key
    now = timezone.now()
    DeviceSession.objects.update_or_create(
        session_key=key,
        defaults={
            "user": user,
            "device": describe(request.META.get("HTTP_USER_AGENT", ""))[:120],
            "ip": client_ip(request)[:45],
            "last_seen": now,
        },
    )


def touch(request):
    """Keep last_seen fresh (at most once per TOUCH_EVERY per device)."""
    key = request.session.session_key
    if not key:
        return
    now = timezone.now()
    updated = DeviceSession.objects.filter(
        session_key=key, user_id=request.user.pk, last_seen__lt=now - TOUCH_EVERY
    ).update(last_seen=now)
    if not updated and not DeviceSession.objects.filter(session_key=key).exists():
        # Sessions opened before this feature existed are registered lazily.
        record(request, request.user)


@transaction.atomic
def revoke(rows):
    rows = list(rows)
    keys = [row.session_key for row in rows]
    Session.objects.filter(session_key__in=keys).delete()
    DeviceSession.objects.filter(pk__in=[row.pk for row in rows]).delete()
    return len(rows)


def forget(session_key):
    if session_key:
        DeviceSession.objects.filter(session_key=session_key).delete()


def prune():
    """Drop rows whose Django session already expired or disappeared."""
    live = Session.objects.filter(expire_date__gt=timezone.now()).values("session_key")
    return DeviceSession.objects.exclude(session_key__in=live).delete()[0]
