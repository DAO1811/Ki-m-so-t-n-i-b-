"""Camera comparison evaluation. These decisions never authenticate a user."""

import base64
import hmac
import json
import math
import secrets
import uuid
from datetime import timedelta

from cryptography.fernet import Fernet, InvalidToken
from django.conf import settings
from django.contrib.auth import get_user_model
from django.contrib.auth.hashers import check_password
from django.db import transaction
from django.utils import timezone
from django.utils.crypto import salted_hmac
from django.views.decorators.debug import sensitive_variables

from .models import AuditEvent, FaceChallenge, FaceProfile, RateBucket

CONSENT_VERSION = "camera-evaluation-v1"
TTL = 120
MAX_BODY = 2 * 1024 * 1024


class CameraError(Exception):
    def __init__(
        self, message="Chưa thể hoàn tất kiểm tra camera. Hãy thử lại.", status=400
    ):
        super().__init__(message)
        self.status = status


def cipher():
    if not getattr(settings, "CAMERA_IDENTITY_ENABLED", False):
        raise CameraError("Bản đánh giá camera chưa được bật.", 503)
    try:
        return Fernet(getattr(settings, "CAMERA_IDENTITY_TEMPLATE_KEY", "").encode())
    except (ValueError, TypeError, AttributeError):
        raise CameraError("Bản đánh giá camera chưa sẵn sàng.", 503) from None


def digest(value, purpose="session"):
    return salted_hmac(
        "camera_identity." + purpose, str(value), algorithm="sha256"
    ).hexdigest()


def bump(scope, identifier, limit):
    now = timezone.now()
    key = digest(f"{scope}:{identifier}:{int(now.timestamp()) // 60}", "rate")
    with transaction.atomic():
        bucket, _ = RateBucket.objects.select_for_update().get_or_create(
            key=key, defaults={"expires_at": now + timedelta(minutes=2)}
        )
        if bucket.expires_at <= now:
            bucket.count = 0
            bucket.expires_at = now + timedelta(minutes=2)
        if bucket.count >= limit:
            raise CameraError(
                "Bạn thao tác quá nhiều lần. Vui lòng chờ rồi thử lại.", 429
            )
        bucket.count += 1
        bucket.save(update_fields=["count", "expires_at"])


def guard(request, action):
    cipher()
    bump("ip", request.META.get("REMOTE_ADDR", "unknown"), 30)
    if not request.session.session_key:
        request.session.create()
    binding = digest(request.session.session_key)
    bump(action, binding, 8)
    return binding


def options(request, kind, *, password=None, consent=None, username=None):
    binding = guard(request, "options-" + kind)
    now = timezone.now()
    expired = list(
        FaceChallenge.objects.filter(expires_at__lt=now).values_list("pk", flat=True)[
            :100
        ]
    )
    FaceChallenge.objects.filter(pk__in=expired).delete()
    expired_buckets = list(
        RateBucket.objects.filter(expires_at__lt=now).values_list("pk", flat=True)[:100]
    )
    RateBucket.objects.filter(pk__in=expired_buckets).delete()
    user = None
    auth_hash = ""
    if kind == "ENROLL":
        if not request.user.is_authenticated:
            raise CameraError(
                "Cần đăng nhập bằng mật khẩu trước khi đăng ký camera.", 401
            )
        if consent is not True or not isinstance(password, str) or len(password) > 1024:
            raise CameraError(
                "Cần đồng ý xử lý dữ liệu khuôn mặt và xác nhận mật khẩu."
            )
        bump("password", request.user.pk, 5)
        with transaction.atomic():
            user = get_user_model().objects.select_for_update().get(pk=request.user.pk)
            if not user.is_active or not check_password(password, user.password):
                raise CameraError("Mật khẩu xác nhận chưa đúng.")
            auth_hash = digest(user.get_session_auth_hash(), "auth")
    elif kind == "VERIFY":
        if not isinstance(username, str) or len(username) > 150:
            raise CameraError()
        user = (
            get_user_model().objects.filter(username=username, is_active=True).first()
        )
    else:
        raise CameraError()
    steps = [
        "CENTER",
        *(["LEFT", "RIGHT"] if secrets.randbelow(2) else ["RIGHT", "LEFT"]),
    ]
    FaceChallenge.objects.filter(
        session_hash=binding, kind=kind, used_at__isnull=True
    ).update(used_at=timezone.now())
    challenge = FaceChallenge.objects.create(
        user=user,
        kind=kind,
        session_hash=binding,
        auth_hash=auth_hash,
        steps=steps,
        expires_at=timezone.now() + timedelta(seconds=TTL),
    )
    return {
        "challenge_id": str(challenge.pk),
        "steps": steps,
        "expires_in": TTL,
        **evaluation(),
    }


def evaluation():
    return {"mode": "evaluation", "login_permitted": False}


def take(request, raw_id, kind):
    binding = guard(request, "finish-" + kind)
    try:
        challenge_id = uuid.UUID(str(raw_id))
    except (ValueError, TypeError):
        raise CameraError() from None
    with transaction.atomic():
        challenge = (
            FaceChallenge.objects.select_for_update()
            .filter(
                pk=challenge_id,
                kind=kind,
                session_hash=binding,
                used_at__isnull=True,
            )
            .first()
        )
        now = timezone.now()
        if challenge is None or challenge.expires_at <= now:
            raise CameraError("Lần kiểm tra đã hết hạn hoặc đã dùng. Hãy bắt đầu lại.")
        if kind == "ENROLL" and (
            not request.user.is_authenticated or challenge.user_id != request.user.pk
        ):
            raise CameraError()
        challenge.used_at = now
        challenge.save(update_fields=["used_at"])
    return challenge


def vector(values):
    if not isinstance(values, list) or len(values) != 128:
        raise CameraError("Máy xử lý camera trả về dữ liệu chưa hợp lệ.", 503)
    if any(
        isinstance(value, bool)
        or not isinstance(value, (float, int))
        or not math.isfinite(value)
        for value in values
    ):
        raise CameraError("Máy xử lý camera trả về dữ liệu chưa hợp lệ.", 503)
    norm = math.sqrt(sum(value * value for value in values))
    if norm < 1e-8 or not math.isfinite(norm):
        raise CameraError("Máy xử lý camera trả về dữ liệu chưa hợp lệ.", 503)
    return [value / norm for value in values]


@sensitive_variables()
def analyse(frames, steps):
    if not isinstance(frames, list) or not 3 <= len(frames) <= 5:
        raise CameraError("Cần chụp đủ các bước hướng dẫn.")
    for frame in frames:
        if not isinstance(frame, str) or len(frame) > 400000:
            raise CameraError()
        try:
            image = base64.b64decode(frame, validate=True)
        except (ValueError, TypeError):
            raise CameraError() from None
        if not 100 <= len(image) <= 450000 or not image.startswith(b"\xff\xd8"):
            raise CameraError("Ảnh camera chưa hợp lệ.")
    try:
        from .engine import analyse as engine_analyse

        result = engine_analyse(frames)
    except Exception as error:
        if getattr(error, "code", None) in {
            "invalid_frames",
            "invalid_image",
            "no_face",
            "multiple_faces",
            "face_too_small",
            "low_light",
            "blurry",
        }:
            raise CameraError(
                "Ảnh chưa đạt yêu cầu. Cần một khuôn mặt rõ, đủ sáng và đúng tư thế."
            ) from None
        raise CameraError(
            "Máy xử lý camera chưa sẵn sàng. Bạn vẫn có thể dùng mật khẩu.", 503
        ) from None
    try:
        descriptors = [vector(item) for item in result["descriptors"]]
        poses = result["poses"]
        model_id = result["model_id"]
        if (
            len(descriptors) != len(frames)
            or len(poses) != len(frames)
            or not isinstance(model_id, str)
            or not 1 <= len(model_id) <= 120
        ):
            raise CameraError(status=503)
        if any(poses[index].get("label") != step for index, step in enumerate(steps)):
            raise CameraError(
                "Chưa đúng tư thế hướng dẫn. Đây chỉ là kiểm tra chuyển động, không phải chống giả mạo đã kiểm định."
            )
    except (KeyError, TypeError, AttributeError):
        raise CameraError("Máy xử lý camera trả về dữ liệu chưa hợp lệ.", 503) from None
    threshold = getattr(settings, "CAMERA_IDENTITY_MATCH_THRESHOLD", 0.5)
    if (
        not isinstance(threshold, (int, float))
        or not math.isfinite(threshold)
        or not 0 < threshold < 1
    ):
        raise CameraError(status=503)
    return descriptors, model_id, threshold


def similarity(left, right):
    return sum(a * b for a, b in zip(left, right, strict=True))


@sensitive_variables()
def finish(request, raw_id, frames, kind):
    challenge = take(request, raw_id, kind)
    descriptors, model_id, threshold = analyse(frames, challenge.steps)
    if kind == "ENROLL":
        if any(
            similarity(descriptors[0], item) < threshold for item in descriptors[1:]
        ):
            raise CameraError(
                "Các ảnh chưa nhất quán. Hãy kiểm tra lại ánh sáng và khuôn mặt."
            )
        template = vector(
            [
                sum(values) / len(descriptors)
                for values in zip(*descriptors, strict=True)
            ]
        )
        encrypted = cipher().encrypt(
            json.dumps(
                {
                    "descriptor": template,
                    "user_id": challenge.user_id,
                    "model_id": model_id,
                    "consent_version": CONSENT_VERSION,
                },
                separators=(",", ":"),
            ).encode()
        )
        with transaction.atomic():
            user = (
                get_user_model()
                .objects.select_for_update()
                .filter(pk=challenge.user_id)
                .first()
            )
            if (
                user is None
                or not user.is_active
                or not hmac.compare_digest(
                    challenge.auth_hash, digest(user.get_session_auth_hash(), "auth")
                )
            ):
                raise CameraError()
            FaceProfile.objects.update_or_create(
                user=user,
                defaults={
                    "encrypted_template": encrypted,
                    "model_id": model_id,
                    "consent_version": CONSENT_VERSION,
                    "consented_at": timezone.now(),
                },
            )
            AuditEvent.objects.create(user=user, action="enrolled_evaluation")
        return {"ok": True, **evaluation()}
    matched = False
    with transaction.atomic():
        user = (
            get_user_model()
            .objects.select_for_update()
            .filter(pk=challenge.user_id, is_active=True)
            .first()
        )
        profile = FaceProfile.objects.filter(user=user).first() if user else None
        if profile is not None:
            try:
                payload = json.loads(
                    cipher().decrypt(bytes(profile.encrypted_template))
                )
                if (
                    not isinstance(payload, dict)
                    or payload.get("user_id") != user.pk
                    or payload.get("model_id") != profile.model_id
                ):
                    raise CameraError("Bản đánh giá camera chưa sẵn sàng.", 503)
                template = vector(payload["descriptor"])
            except (InvalidToken, ValueError, TypeError, KeyError):
                raise CameraError("Bản đánh giá camera chưa sẵn sàng.", 503) from None
            matched = profile.model_id == model_id and all(
                similarity(template, item) >= threshold for item in descriptors
            )
        AuditEvent.objects.create(
            user=user,
            action="matched_evaluation" if matched else "not_matched_evaluation",
        )
    return {"matched": matched, **evaluation()}


def remove(request, password):
    guard(request, "remove")
    if not isinstance(password, str) or len(password) > 1024:
        raise CameraError()
    with transaction.atomic():
        user = (
            get_user_model()
            .objects.select_for_update()
            .filter(pk=request.user.pk, is_active=True)
            .first()
        )
        if user is None or not check_password(password, user.password):
            raise CameraError("Mật khẩu xác nhận chưa đúng.")
        FaceProfile.objects.filter(user=user).delete()
        FaceChallenge.objects.filter(
            user=user, kind="ENROLL", used_at__isnull=True
        ).update(used_at=timezone.now())
        AuditEvent.objects.create(user=user, action="removed_evaluation")
