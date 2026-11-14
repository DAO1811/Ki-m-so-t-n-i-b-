"""Password-login throttling stored in the database (shared by all workers).

Policy: per account name, LOGIN_USER_MAX_FAILURES wrong passwords within the
window lock that name for LOGIN_LOCK_SECONDS; per client IP the threshold is
LOGIN_IP_MAX_FAILURES (higher, because an office may share one public IP).
Messages are identical whether or not the account exists. Passkey sign-in and
existing sessions are not affected.
"""

import ipaddress
import logging
from datetime import timedelta

from django.conf import settings
from django.db import IntegrityError, transaction
from django.utils import timezone

from .models import LoginThrottle

logger = logging.getLogger(__name__)


def _setting(name, default):
    return int(getattr(settings, name, default))


def window():
    return timedelta(seconds=_setting("LOGIN_WINDOW_SECONDS", 900))


def lock_duration():
    return timedelta(seconds=_setting("LOGIN_LOCK_SECONDS", 900))


def limits():
    return {
        "user": _setting("LOGIN_USER_MAX_FAILURES", 5),
        "ip": _setting("LOGIN_IP_MAX_FAILURES", 20),
    }


def normalize_username(username):
    return str(username or "").strip().casefold()[:150]


def _valid_ip(value):
    try:
        return str(ipaddress.ip_address(value.strip()))
    except ValueError:
        return ""


def client_ip(request):
    """Client IP behind LOGIN_TRUSTED_PROXY_HOPS reverse proxies.

    A proxy appends the address it saw to X-Forwarded-For, so with N trusted
    proxies only the N-th entry from the right is trustworthy; anything left of
    it may be supplied by the client. With 0 hops REMOTE_ADDR is used.
    """
    hops = _setting("LOGIN_TRUSTED_PROXY_HOPS", 0)
    remote = _valid_ip(request.META.get("REMOTE_ADDR", "")) or "unknown"
    if hops <= 0:
        return remote
    chain = [
        part
        for part in request.META.get("HTTP_X_FORWARDED_FOR", "").split(",")
        if part.strip()
    ]
    if len(chain) < hops:
        return remote
    return _valid_ip(chain[-hops]) or remote


def _keys(username, ip):
    keys = [("ip", ip)]
    name = normalize_username(username)
    if name:
        keys.insert(0, ("user", name))
    return keys


def locked_until(username, ip):
    """Latest active lock for this account name or IP, else None."""
    now = timezone.now()
    until = None
    for scope, key in _keys(username, ip):
        row = (
            LoginThrottle.objects.filter(scope=scope, key=key, locked_until__gt=now)
            .values_list("locked_until", flat=True)
            .first()
        )
        if row and (until is None or row > until):
            until = row
    return until


def _locked_row(scope, key, now):
    try:
        with transaction.atomic():
            row, _ = LoginThrottle.objects.select_for_update().get_or_create(
                scope=scope, key=key, defaults={"window_started_at": now}
            )
    except IntegrityError:
        # Another worker created it first.
        row = LoginThrottle.objects.select_for_update().get(scope=scope, key=key)
    return row


@transaction.atomic
def register_failure(username, ip):
    """Count one wrong password; return the lock expiry if a lock now applies."""
    now = timezone.now()
    caps = limits()
    result = None
    for scope, key in _keys(username, ip):
        row = _locked_row(scope, key, now)
        if row.locked_until and row.locked_until > now:
            result = max(result or row.locked_until, row.locked_until)
            continue
        if row.locked_until or now - row.window_started_at > window():
            row.failures, row.window_started_at, row.locked_until = 0, now, None
        row.failures += 1
        if row.failures >= caps[scope]:
            row.locked_until = now + lock_duration()
            row.lockouts += 1
            result = max(result or row.locked_until, row.locked_until)
            logger.warning(
                "Password login locked: scope=%s key=%s failures=%d",
                scope,
                key,
                row.failures,
            )
        row.save()
    return result


def clear_account(username):
    LoginThrottle.objects.filter(
        scope="user", key=normalize_username(username)
    ).delete()


def purge(older_than=None):
    """Delete counters with no active lock that were last touched long ago."""
    cutoff = timezone.now() - (older_than or timedelta(days=1))
    deleted, _ = (
        LoginThrottle.objects.filter(updated_at__lt=cutoff)
        .exclude(locked_until__gt=timezone.now())
        .delete()
    )
    return deleted
