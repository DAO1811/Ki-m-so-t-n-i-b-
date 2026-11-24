"""WebAuthn verification, independent of warehouse permissions and data."""

import base64
import hmac
import json
import re
import secrets
import uuid
from datetime import UTC, datetime, timedelta
from urllib.parse import urlsplit

from django.conf import settings
from django.contrib.auth import get_user_model
from django.contrib.auth.hashers import check_password
from django.db import transaction
from django.utils import timezone
from django.utils.crypto import salted_hmac
from django.utils.http import url_has_allowed_host_and_scheme

from .models import (
    Ceremony,
    PasskeyCredential,
    PasskeyIdentity,
    RateBucket,
    SecurityEvent,
)

TTL = 120
MAX_CREDENTIALS = 10
# Within this many seconds after a password sign-in in the same session, Face ID
# can be turned on without re-typing the password (owner request 23/11/2026).
RECENT_PASSWORD_LOGIN = 600
FALLBACK = "Hãy đăng nhập bằng mật khẩu. Quên mật khẩu, liên hệ quản trị viên."
# Bank-app style lock for every signed-in session (owner requests 23-24/11/2026):
# leaving the app or leaving it untouched asks for Face ID or the password again.
# Defaults; settings APP_LOCK_*_SECONDS override them (see lock_timing).
APP_LOCK_AWAY = 60  # page hidden / app left this long
APP_LOCK_IDLE = 300  # page open but untouched this long
APP_LOCK_SERVER_GAP = 120  # no request at all this long (app closed, phone away)


class PasskeyError(Exception):
    def __init__(
        self,
        message="Chưa xác thực được bằng Face ID. " + FALLBACK,
        status=400,
    ):
        super().__init__(message)
        self.status = status


def configuration():
    rp = getattr(settings, "PASSKEY_RP_ID", "")
    origin = getattr(settings, "PASSKEY_ORIGIN", "")
    url = urlsplit(origin)
    if (
        not getattr(settings, "PASSKEY_ENABLED", True)
        or not rp
        or not rp.isascii()
        or url.hostname != rp
        or url.username
        or url.password
        or url.path not in ("", "/")
        or url.query
        or url.fragment
        or (
            url.scheme != "https"
            and not (settings.DEBUG and url.scheme == "http" and rp == "localhost")
        )
    ):
        raise PasskeyError(
            "Đăng nhập bằng Face ID chưa dùng được trên địa chỉ này. " + FALLBACK,
            503,
        )
    return rp, origin.rstrip("/")


def available():
    try:
        configuration()
        return True
    except (PasskeyError, ValueError):
        return False


def digest(value, salt="binding"):
    return salted_hmac(
        "ksnb.passkeys." + salt, str(value), algorithm="sha256"
    ).hexdigest()


def session_binding(request):
    if not request.session.session_key:
        request.session.create()
    return digest(request.session.session_key)


def bump(scope, identifier, limit, seconds=60):
    now = timezone.now()
    window = int(now.timestamp()) // seconds
    key = digest(f"{scope}:{str(identifier)[:512]}:{window}", "rate")
    with transaction.atomic():
        bucket, _ = RateBucket.objects.select_for_update().get_or_create(
            key=key, defaults={"expires_at": now + timedelta(seconds=seconds * 2)}
        )
        if bucket.expires_at <= now:
            bucket.count = 0
            bucket.expires_at = now + timedelta(seconds=seconds * 2)
            bucket.save(update_fields=["count", "expires_at"])
        if bucket.count >= limit:
            accepted = False
        else:
            bucket.count += 1
            bucket.save(update_fields=["count"])
            accepted = True
    if not accepted:
        raise PasskeyError("Bạn thao tác quá nhiều lần. Chờ một phút rồi thử lại.", 429)


def guard(request, kind, user=None):
    rp, origin = configuration()
    if request.get_host().lower() != urlsplit(origin).netloc.lower():
        raise PasskeyError(
            "Hãy mở đúng địa chỉ phần mềm (kiemsoatnoibolemon.onrender.com). "
            + FALLBACK,
            400,
        )
    # REMOTE_ADDR is trusted by the server; arbitrary forwarded headers are not.
    bump("ip", request.META.get("REMOTE_ADDR", "unknown"), 180)
    binding = session_binding(request)
    bump(kind, binding, 12)
    if user is not None:
        bump("password-confirm", user.pk, 5)
    return rp, origin, binding


def prune():
    now = timezone.now()
    Ceremony.objects.filter(expires_at__lt=now).delete()
    RateBucket.objects.filter(expires_at__lt=now).delete()


def new_ceremony(request, kind, *, user=None, payload=None):
    # Only turning Face ID on confirms a password; the unlock ceremony is bound
    # to the account but limited per session and IP, not by password attempts.
    rp, origin, binding = guard(request, kind, user if kind == "register" else None)
    prune()
    # Replace only ceremonies of the same purpose in this browser session.
    Ceremony.objects.filter(
        session_hash=binding, kind=kind, used_at__isnull=True
    ).update(used_at=timezone.now())
    return Ceremony.objects.create(
        kind=kind,
        session_hash=binding,
        challenge=secrets.token_bytes(32),
        user=user,
        auth_hash=digest(user.get_session_auth_hash(), "auth")
        if user is not None
        else "",
        payload=payload or {},
        expires_at=timezone.now() + timedelta(seconds=TTL),
        rp_id=rp,
        origin=origin,
    )


def take_ceremony(request, raw_id, kind):
    rp, origin, binding = guard(request, kind + "-verify")
    try:
        pk = uuid.UUID(str(raw_id))
    except (ValueError, TypeError, AttributeError):
        raise PasskeyError() from None
    # Consume and commit BEFORE verification, so failed assertions cannot replay.
    with transaction.atomic():
        item = (
            Ceremony.objects.select_for_update()
            .filter(
                pk=pk,
                kind=kind,
                session_hash=binding,
                used_at__isnull=True,
                expires_at__gt=timezone.now(),
            )
            .first()
        )
        # SELECT FOR UPDATE can wait past the timestamp used by its WHERE
        # clause. Authorize against the clock after the lock has been acquired.
        consumed_at = timezone.now()
        if item is None or item.expires_at <= consumed_at:
            raise PasskeyError("Yêu cầu đã hết hạn hoặc đã dùng. Hãy bắt đầu lại.")
        if item.rp_id != rp or item.origin != origin:
            raise PasskeyError()
        if kind == "register" and (
            not request.user.is_authenticated or request.user.pk != item.user_id
        ):
            raise PasskeyError()
        item.used_at = consumed_at
        item.save(update_fields=["used_at"])
    return item


def bytes_to_base64url(value):
    return base64.urlsafe_b64encode(value).decode("ascii").rstrip("=")


def base64url_to_bytes(value):
    return base64.urlsafe_b64decode(value + "=" * (-len(value) % 4))


def binary(value, *, maximum=8192):
    if not isinstance(value, str) or not value or len(value) > maximum * 2:
        raise PasskeyError()
    try:
        decoded = base64url_to_bytes(value)
    except Exception:
        raise PasskeyError() from None
    if not decoded or len(decoded) > maximum or bytes_to_base64url(decoded) != value:
        raise PasskeyError()
    return decoded


def inspect_credential(credential):
    if not isinstance(credential, dict) or credential.get("type") != "public-key":
        raise PasskeyError()
    credential_id = binary(credential.get("id"), maximum=1023)
    if credential_id != binary(credential.get("rawId"), maximum=1023):
        raise PasskeyError()
    response = credential.get("response")
    if not isinstance(response, dict):
        raise PasskeyError()
    try:
        data = json.loads(binary(response.get("clientDataJSON"), maximum=4096))
        if (
            not isinstance(data, dict)
            or data.get("crossOrigin", False) is not False
            or "topOrigin" in data
        ):
            raise PasskeyError()
    except (ValueError, UnicodeError):
        raise PasskeyError() from None
    return credential_id


def mark_password_login(request):
    request.session["password_login_at"] = int(timezone.now().timestamp())


def recent_password_login(request):
    """True for 10 minutes after a password sign-in in this exact session."""
    stamp = request.session.get("password_login_at")
    if type(stamp) is not int or not request.user.is_authenticated:
        return False
    return 0 <= timezone.now().timestamp() - stamp <= RECENT_PASSWORD_LOGIN


def register_options(request, password, label):
    from webauthn import generate_registration_options, options_to_json
    from webauthn.helpers.structs import (
        AuthenticatorAttachment,
        AuthenticatorSelectionCriteria,
        PublicKeyCredentialDescriptor,
        ResidentKeyRequirement,
        UserVerificationRequirement,
    )

    ceremony = new_ceremony(
        request, "register", user=request.user, payload={"label": label}
    )
    if not (
        (password and check_password(password, request.user.password))
        or (not password and recent_password_login(request))
    ):
        ceremony.used_at = timezone.now()
        ceremony.save(update_fields=["used_at"])
        raise PasskeyError(
            "Mật khẩu xác nhận chưa đúng. Quên mật khẩu, liên hệ quản trị viên."
        )
    with transaction.atomic():
        user = get_user_model().objects.select_for_update().get(pk=request.user.pk)
        if not user.is_active or not hmac.compare_digest(
            ceremony.auth_hash, digest(user.get_session_auth_hash(), "auth")
        ):
            raise PasskeyError()
        credentials = list(
            PasskeyCredential.objects.filter(user=user, revoked_at__isnull=True)
        )
        if len(credentials) >= MAX_CREDENTIALS:
            raise PasskeyError(
                "Tài khoản đã bật Face ID trên tối đa 10 thiết bị. "
                "Gỡ một thiết bị cũ trước khi thêm."
            )
        identity, _ = PasskeyIdentity.objects.get_or_create(user=user)
        options = generate_registration_options(
            rp_id=ceremony.rp_id,
            rp_name="DHD KSNB",
            user_name=user.get_username(),
            user_display_name=user.get_full_name() or user.get_username(),
            user_id=identity.handle.bytes,
            challenge=bytes(ceremony.challenge),
            timeout=TTL * 1000,
            authenticator_selection=AuthenticatorSelectionCriteria(
                authenticator_attachment=AuthenticatorAttachment.PLATFORM,
                resident_key=ResidentKeyRequirement.REQUIRED,
                require_resident_key=True,
                user_verification=UserVerificationRequirement.REQUIRED,
            ),
            exclude_credentials=[
                PublicKeyCredentialDescriptor(id=binary(c.credential_id, maximum=1023))
                for c in credentials
            ],
        )
    return {
        "ceremony_id": str(ceremony.pk),
        "publicKey": json.loads(options_to_json(options)),
    }


def register_finish(request, raw_id, credential):
    from webauthn import verify_registration_response
    from webauthn.helpers.structs import CredentialDeviceType

    ceremony = take_ceremony(request, raw_id, "register")
    inspect_credential(credential)
    try:
        result = verify_registration_response(
            credential=credential,
            expected_challenge=bytes(ceremony.challenge),
            expected_rp_id=ceremony.rp_id,
            expected_origin=ceremony.origin,
            require_user_presence=True,
            require_user_verification=True,
        )
    except Exception:
        raise PasskeyError() from None
    with transaction.atomic():
        user = get_user_model().objects.select_for_update().get(pk=ceremony.user_id)
        if not user.is_active or not hmac.compare_digest(
            ceremony.auth_hash, digest(user.get_session_auth_hash(), "auth")
        ):
            raise PasskeyError()
        if (
            PasskeyCredential.objects.filter(user=user, revoked_at__isnull=True).count()
            >= MAX_CREDENTIALS
        ):
            raise PasskeyError("Tài khoản đã bật Face ID trên tối đa 10 thiết bị.")
        PasskeyCredential.objects.create(
            user=user,
            credential_id=bytes_to_base64url(result.credential_id),
            public_key=result.credential_public_key,
            sign_count=result.sign_count,
            label=ceremony.payload["label"],
            backup_eligible=result.credential_device_type
            == CredentialDeviceType.MULTI_DEVICE,
            backed_up=result.credential_backed_up,
        )
        SecurityEvent.objects.create(user=user, action="registered")


def safe_next(value):
    return (
        value
        if isinstance(value, str)
        and len(value) <= 2000
        and value.startswith("/")
        and "\\" not in value
        and url_has_allowed_host_and_scheme(
            value, allowed_hosts=set(), require_https=True
        )
        else "/"
    )


def login_options(request, next_url):
    from webauthn import generate_authentication_options, options_to_json
    from webauthn.helpers.structs import UserVerificationRequirement

    ceremony = new_ceremony(request, "login", payload={"next": safe_next(next_url)})
    options = generate_authentication_options(
        rp_id=ceremony.rp_id,
        challenge=bytes(ceremony.challenge),
        timeout=TTL * 1000,
        user_verification=UserVerificationRequirement.REQUIRED,
    )
    return {
        "ceremony_id": str(ceremony.pk),
        "publicKey": json.loads(options_to_json(options)),
    }


def login_finish(request, raw_id, credential):
    from webauthn import verify_authentication_response
    from webauthn.helpers.structs import CredentialDeviceType

    ceremony = take_ceremony(request, raw_id, "login")
    inspect_credential(credential)
    with transaction.atomic():
        # Same lock order as enrollment/removal: account, then credential.
        initial = (
            PasskeyCredential.objects.filter(
                credential_id=credential["id"], revoked_at__isnull=True
            )
            .values("user_id")
            .first()
        )
        if initial is None:
            raise PasskeyError()
        user = (
            get_user_model()
            .objects.select_for_update()
            .filter(pk=initial["user_id"])
            .first()
        )
        if user is None:
            raise PasskeyError()
        current = (
            PasskeyCredential.objects.select_for_update()
            .filter(credential_id=credential["id"], user=user, revoked_at__isnull=True)
            .first()
        )
        identity = PasskeyIdentity.objects.filter(user=user).first()
        if current is None or identity is None or not user.is_active:
            raise PasskeyError()
        if (
            binary(credential["response"].get("userHandle"), maximum=64)
            != identity.handle.bytes
        ):
            raise PasskeyError()
        try:
            result = verify_authentication_response(
                credential=credential,
                expected_challenge=bytes(ceremony.challenge),
                expected_rp_id=ceremony.rp_id,
                expected_origin=ceremony.origin,
                credential_public_key=bytes(current.public_key),
                credential_current_sign_count=0
                if current.backup_eligible
                else current.sign_count,
                require_user_verification=True,
            )
        except Exception:
            raise PasskeyError() from None
        if (
            result.credential_device_type == CredentialDeviceType.MULTI_DEVICE
        ) != current.backup_eligible:
            raise PasskeyError()
        current.sign_count = max(current.sign_count, result.new_sign_count)
        current.backed_up = result.credential_backed_up
        current.last_used_at = timezone.now()
        current.save(update_fields=["sign_count", "backed_up", "last_used_at"])
        from django.contrib.auth import login

        login(request, user, backend="django.contrib.auth.backends.ModelBackend")
        request.session["passkey_credential_id"] = str(current.pk)
        SecurityEvent.objects.create(user=user, action="authenticated")
    return ceremony.payload["next"]


def app_lock_applies(request):
    """Every signed-in session uses the bank-style lock (APP_LOCK_ENABLED)."""
    return request.user.is_authenticated and getattr(settings, "APP_LOCK_ENABLED", True)


def lock_timing():
    """(away, idle, server gap) in seconds, with floors that keep the app usable."""
    away = max(15, int(getattr(settings, "APP_LOCK_AWAY_SECONDS", APP_LOCK_AWAY)))
    idle = max(60, int(getattr(settings, "APP_LOCK_IDLE_SECONDS", APP_LOCK_IDLE)))
    gap = max(
        90,
        away,
        int(getattr(settings, "APP_LOCK_SERVER_GAP_SECONDS", APP_LOCK_SERVER_GAP)),
    )
    return away, idle, gap


def identity(user):
    """Name and avatar letter shown on the bank-style sign-in screens."""
    name = (user.get_full_name() or user.get_username()).strip()
    # Vietnamese given name is the last word ("Đào Hữu Đạo" -> "Đ").
    words = re.findall(r"[^\W\d_]+", re.sub(r"\([^)]*\)", " ", name))
    return name, ((words[-1] if words else name)[:1] or "?").upper()


def has_face_id(user):
    """The account turned on Face ID on at least one device."""
    return (
        user.is_authenticated
        and available()
        and PasskeyCredential.objects.filter(
            user=user, revoked_at__isnull=True
        ).exists()
    )


def now_seconds():
    # Real wall-clock time away from the app. Read directly so that tests which
    # patch time.time or timezone.now for other features never lock a session.
    return int(datetime.now(UTC).timestamp())


def lock(request):
    request.session["app_locked"] = True


def mark_unlocked(request):
    request.session.pop("app_locked", None)
    request.session["app_seen_at"] = now_seconds()


def unlock_options(request):
    from webauthn import generate_authentication_options, options_to_json
    from webauthn.helpers.structs import (
        PublicKeyCredentialDescriptor,
        UserVerificationRequirement,
    )

    if not app_lock_applies(request):
        raise PasskeyError("Phiên này không cần mở khóa.", 409)
    ceremony = new_ceremony(request, "unlock", user=request.user)
    credentials = list(
        PasskeyCredential.objects.filter(user=request.user, revoked_at__isnull=True)
    )
    if not credentials:
        raise PasskeyError("Tài khoản chưa bật Face ID. " + FALLBACK)
    options = generate_authentication_options(
        rp_id=ceremony.rp_id,
        challenge=bytes(ceremony.challenge),
        timeout=TTL * 1000,
        user_verification=UserVerificationRequirement.REQUIRED,
        allow_credentials=[
            PublicKeyCredentialDescriptor(id=binary(c.credential_id, maximum=1023))
            for c in credentials
        ],
    )
    return {
        "ceremony_id": str(ceremony.pk),
        "publicKey": json.loads(options_to_json(options)),
    }


def unlock_finish(request, raw_id, credential):
    from webauthn import verify_authentication_response
    from webauthn.helpers.structs import CredentialDeviceType

    if not app_lock_applies(request):
        raise PasskeyError("Phiên này không cần mở khóa.", 409)
    ceremony = take_ceremony(request, raw_id, "unlock")
    if ceremony.user_id != request.user.pk:
        raise PasskeyError()
    inspect_credential(credential)
    with transaction.atomic():
        # Same lock order as sign-in: account, then credential.
        user = (
            get_user_model()
            .objects.select_for_update()
            .filter(pk=request.user.pk, is_active=True)
            .first()
        )
        current = (
            PasskeyCredential.objects.select_for_update()
            .filter(credential_id=credential["id"], user=user, revoked_at__isnull=True)
            .first()
            if user is not None
            else None
        )
        identity = PasskeyIdentity.objects.filter(user=user).first()
        if current is None or identity is None:
            raise PasskeyError()
        handle = credential["response"].get("userHandle")
        if handle is not None and binary(handle, maximum=64) != identity.handle.bytes:
            raise PasskeyError()
        try:
            result = verify_authentication_response(
                credential=credential,
                expected_challenge=bytes(ceremony.challenge),
                expected_rp_id=ceremony.rp_id,
                expected_origin=ceremony.origin,
                credential_public_key=bytes(current.public_key),
                credential_current_sign_count=0
                if current.backup_eligible
                else current.sign_count,
                require_user_verification=True,
            )
        except Exception:
            raise PasskeyError() from None
        if (
            result.credential_device_type == CredentialDeviceType.MULTI_DEVICE
        ) != current.backup_eligible:
            raise PasskeyError()
        current.sign_count = max(current.sign_count, result.new_sign_count)
        current.backed_up = result.credential_backed_up
        current.last_used_at = timezone.now()
        current.save(update_fields=["sign_count", "backed_up", "last_used_at"])
        SecurityEvent.objects.create(user=user, action="unlocked")
    mark_unlocked(request)


def unlock_with_password(request, password):
    """Sign back in to a locked session with the password (any account).

    Wrong passwords count toward the same lockout as the login page (owner
    rule 14/11/2026: 5 wrong passwords lock an employee until an Admin unlocks).
    """
    from login_guard import services as login_guard
    from login_guard.forms import LOCK_MESSAGE

    if not app_lock_applies(request):
        raise PasskeyError("Phiên này không cần mở khóa.", 409)
    username = request.user.get_username()
    ip = login_guard.client_ip(request)
    if login_guard.is_locked(username, ip):
        raise PasskeyError(LOCK_MESSAGE, 403)
    bump("ip", request.META.get("REMOTE_ADDR", "unknown"), 180)
    bump("password-confirm", request.user.pk, 5)
    if not check_password(password, request.user.password):
        if login_guard.register_failure(username, ip):
            raise PasskeyError(LOCK_MESSAGE, 403)
        raise PasskeyError("Mật khẩu chưa đúng. Quên mật khẩu, liên hệ quản trị viên.")
    login_guard.clear_account(username)
    mark_unlocked(request)
    # Counts as a fresh password sign-in: Face ID can be turned on right away.
    mark_password_login(request)


def revoke(request, pk, password):
    guard(request, "revoke", request.user)
    with transaction.atomic():
        user = get_user_model().objects.select_for_update().get(pk=request.user.pk)
        if not user.is_active or not check_password(password, user.password):
            raise PasskeyError("Mật khẩu xác nhận chưa đúng.")
        key = (
            PasskeyCredential.objects.select_for_update()
            .filter(pk=pk, user=user, revoked_at__isnull=True)
            .first()
        )
        if key is None:
            raise PasskeyError("Thiết bị này không còn bật Face ID.", 404)
        key.revoked_at = timezone.now()
        key.save(update_fields=["revoked_at"])
        SecurityEvent.objects.create(user=user, action="revoked")
