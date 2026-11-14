"""Password-login throttling stored in the database (shared by all workers).

Policy (owner decision 14/11/2026): LOGIN_USER_MAX_FAILURES wrong passwords
within the window lock an account name until an Admin unlocks it. Superuser
accounts instead unlock after LOGIN_LOCK_SECONDS, otherwise a single attacker
could lock every Admin out with nobody left to unlock. Per client IP the
threshold is LOGIN_IP_MAX_FAILURES (higher, because an office may share one
public IP) and always expires. Names that match no account behave exactly like
employee accounts, so responses never reveal whether an account exists.
Passkey sign-in and existing sessions are not affected.
"""

import ipaddress
import logging
from datetime import timedelta

from django.conf import settings
from django.contrib.auth import get_user_model
from django.db import IntegrityError, transaction
from django.db.models import Q
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


def _active(now):
    return Q(admin_unlock_required=True) | Q(locked_until__gt=now)


def is_locked(username, ip):
    """True while this account name or IP has an active lock."""
    now = timezone.now()
    return any(
        LoginThrottle.objects.filter(_active(now), scope=scope, key=key).exists()
        for scope, key in _keys(username, ip)
    )


def _is_superuser_name(name):
    return (
        get_user_model()
        .objects.filter(username__iexact=name, is_superuser=True, is_active=True)
        .exists()
    )


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
    """Count one wrong password; return True if a lock now applies."""
    now = timezone.now()
    caps = limits()
    locked = False
    for scope, key in _keys(username, ip):
        row = _locked_row(scope, key, now)
        if row.admin_unlock_required or (row.locked_until and row.locked_until > now):
            locked = True
            continue
        if row.locked_until or now - row.window_started_at > window():
            row.failures, row.window_started_at, row.locked_until = 0, now, None
        row.failures += 1
        if row.failures >= caps[scope]:
            if scope == "user" and not _is_superuser_name(key):
                row.admin_unlock_required = True
            else:
                row.locked_until = now + lock_duration()
            row.lockouts += 1
            locked = True
            logger.warning(
                "Password login locked: scope=%s key=%s failures=%d",
                scope,
                key,
                row.failures,
            )
        row.save()
    return locked


def clear_account(username):
    LoginThrottle.objects.filter(
        scope="user", key=normalize_username(username)
    ).delete()


def _existing_names():
    return {
        name.casefold()
        for name in get_user_model().objects.values_list("username", flat=True)
    }


def locked_accounts():
    """Locks of real accounts waiting for an Admin (shown to Admins)."""
    rows = LoginThrottle.objects.filter(scope="user", admin_unlock_required=True)
    names = _existing_names()
    return [row for row in rows.order_by("-updated_at") if row.key in names]


def unlock(rows):
    return LoginThrottle.objects.filter(pk__in=[row.pk for row in rows]).delete()[0]


def purge(older_than=None):
    """Delete stale counters. Admin-required locks of real accounts are kept
    until an Admin unlocks them; those of names with no account are dropped."""
    now = timezone.now()
    cutoff = now - (older_than or timedelta(days=1))
    stale = LoginThrottle.objects.filter(updated_at__lt=cutoff).exclude(
        locked_until__gt=now
    )
    names = _existing_names()
    keep = [
        row.pk
        for row in stale.filter(scope="user", admin_unlock_required=True)
        if row.key in names
    ]
    deleted, _ = stale.exclude(pk__in=keep).delete()
    return deleted
