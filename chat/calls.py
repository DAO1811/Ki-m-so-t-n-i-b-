"""Authenticated WebRTC signaling only. Audio/video is never recorded here."""

import base64
import hashlib
import hmac
import json
from datetime import timedelta

from django.conf import settings
from django.core.exceptions import PermissionDenied, ValidationError
from django.db import transaction
from django.db.models import Sum, TextField
from django.db.models.functions import Cast, Length
from django.http import Http404
from django.utils import timezone

from inventory.access import has_function

from . import access
from .models import Call, CallMember, Signal
from .services import request_key, touch

MAX_PEERS = 6
LIVE = ["RINGING", "ACTIVE"]


def ice_servers(user):
    servers = [{"urls": ["stun:stun.l.google.com:19302"]}]
    urls = [x.strip() for x in settings.CHAT_TURN_URLS.split(",") if x.strip()]
    if urls and settings.CHAT_TURN_SECRET:
        username = f"{int(timezone.now().timestamp()) + 3600}:{user.pk}"
        credential = base64.b64encode(
            hmac.new(
                settings.CHAT_TURN_SECRET.encode(), username.encode(), hashlib.sha1
            ).digest()
        ).decode()
        servers.append({"urls": urls, "username": username, "credential": credential})
    return servers


def finish(call, reason):
    call.status = "ENDED"
    call.end_reason = reason
    call.ended_at = timezone.now()
    call.touched_at = timezone.now()
    call.save(update_fields=["status", "end_reason", "ended_at", "touched_at"])
    call.participants.filter(state="JOINED").update(state="LEFT")
    Signal.objects.filter(call=call).delete()


def expire(call):
    now = timezone.now()
    if call.status not in LIVE:
        return
    stale = call.touched_at < now - timedelta(seconds=100)
    timed_out = call.status == "RINGING" and call.created_at < now - timedelta(
        seconds=60
    )
    if stale or timed_out:
        finish(call, "NO_ANSWER" if timed_out else "DISCONNECTED")
        return
    call.participants.filter(
        state="JOINED", last_seen__lt=now - timedelta(seconds=90)
    ).update(state="LEFT")
    if call.status == "ACTIVE" and call.participants.filter(state="JOINED").count() < 2:
        finish(call, "LEFT")


def sync_members(room):
    for call in room.calls.select_for_update().filter(status__in=LIVE):
        current = set(
            room.members.filter(active=True).values_list("user_id", flat=True)
        )
        call.participants.exclude(user_id__in=current).update(state="LEFT")
        expire(call)


def call_for(user, room_id, call_id, *, locked=False):
    room, member = access.membership(user, room_id, locked=locked)
    access.require_use(user, "chat_call")
    qs = Call.objects.select_for_update() if locked else Call.objects
    call = qs.filter(pk=call_id, room=room).first()
    if not call or call.created_at < member.joined_at:
        raise Http404("Không tìm thấy cuộc gọi.")
    return room, call


def available(user, excluding=None):
    return (
        not CallMember.objects.filter(
            user=user,
            state="JOINED",
            call__status__in=LIVE,
            call__touched_at__gte=timezone.now() - timedelta(seconds=100),
        )
        .exclude(call=excluding)
        .exists()
    )


@transaction.atomic
def start(user, room_id, mode, client_key, device_key):
    room, member, user = access.lock_member(user, room_id)
    access.require_use(user, "chat_call")
    if mode not in {"AUDIO", "VIDEO"}:
        raise ValidationError("Loại cuộc gọi không hợp lệ.")
    key = request_key(client_key)
    session = request_key(device_key)
    previous = Call.objects.filter(initiator=user, client_key=key).first()
    if previous:
        if previous.room_id != room.pk or previous.mode != mode:
            raise ValidationError("Mã cuộc gọi đã được sử dụng.")
        return previous
    for old in room.calls.select_for_update().filter(status__in=LIVE):
        expire(old)
        if old.status in LIVE:
            raise ValidationError("Đã có cuộc gọi trong hội thoại. Chọn tham gia.")
    if not available(user):
        raise ValidationError("Bạn đang tham gia một cuộc gọi khác.")
    if (
        Call.objects.filter(
            initiator=user, created_at__gte=timezone.now() - timedelta(minutes=1)
        ).count()
        >= 5
    ):
        raise ValidationError("Bạn gọi quá nhanh. Chờ một chút rồi thử lại.")
    people = list(
        access.eligible_users().filter(
            chat_memberships__room=room, chat_memberships__active=True
        )
    )
    peers = [p for p in people if has_function(p, "chat_call")]
    if len(peers) < 2:
        raise ValidationError(
            "Cần ít nhất hai thành viên đang hoạt động được cấp quyền gọi."
        )
    call = Call.objects.create(room=room, initiator=user, mode=mode, client_key=key)
    now = timezone.now()
    CallMember.objects.bulk_create(
        [
            CallMember(
                call=call,
                user=p,
                state="JOINED" if p.pk == user.pk else "INVITED",
                last_seen=now if p.pk == user.pk else None,
                joined_at=now if p.pk == user.pk else None,
                session_key=session if p.pk == user.pk else None,
            )
            for p in peers
        ]
    )
    touch(room)
    return call


@transaction.atomic
def act(user, room_id, call_id, command, device_key):
    # Room before call before user. No endpoint permits an Admin membership bypass.
    room, call = call_for(user, room_id, call_id, locked=True)
    user = access.lock_users([user.pk])[user.pk]
    access.require_use(user, "chat_call")
    expire(call)
    peer = call.participants.filter(user=user).first()
    if not peer:
        raise Http404
    if call.status not in LIVE:
        return call
    now = timezone.now()
    session = request_key(device_key)
    if peer.state == "JOINED" and peer.session_key != session:
        raise ValidationError(
            "Bạn đang gọi ở một cửa sổ khác. Kết thúc cuộc gọi ở đó trước."
        )
    if command == "join":
        if not available(user, call):
            raise ValidationError("Bạn đang tham gia một cuộc gọi khác.")
        if (
            peer.state != "JOINED"
            and call.participants.filter(state="JOINED").count() >= MAX_PEERS
        ):
            raise ValidationError("Cuộc gọi đã đủ 6 người.")
        peer.state, peer.last_seen, peer.joined_at = "JOINED", now, now
        peer.session_key = session
        peer.save(update_fields=["state", "last_seen", "joined_at", "session_key"])
        if call.participants.filter(state="JOINED").count() >= 2:
            call.status = "ACTIVE"
    elif command == "heartbeat":
        if peer.state != "JOINED":
            raise PermissionDenied("Bạn chưa tham gia cuộc gọi.")
        peer.last_seen = now
        peer.save(update_fields=["last_seen"])
    elif command in {"leave", "decline"}:
        peer.state = "DECLINED" if command == "decline" else "LEFT"
        peer.save(update_fields=["state"])
        if (
            call.initiator_id == user.pk
            or (
                call.status == "ACTIVE"
                and call.participants.filter(state="JOINED").count() < 2
            )
            or not call.participants.filter(state="INVITED").exists()
            and call.participants.filter(state="JOINED").count() < 2
        ):
            finish(call, "DECLINED" if command == "decline" else "LEFT")
            touch(room)
            return call
    else:
        raise ValidationError("Thao tác cuộc gọi không hợp lệ.")
    call.touched_at = now
    call.save(update_fields=["status", "touched_at"])
    Signal.objects.filter(expires_at__lte=now).delete()
    if command != "heartbeat":
        touch(room)
    return call


def signal_payload(kind, data):
    if not isinstance(data, dict) or len(json.dumps(data)) > 70000:
        raise ValidationError("Dữ liệu kết nối không hợp lệ.")
    if kind in {"OFFER", "ANSWER"}:
        if (
            set(data) != {"type", "sdp"}
            or data["type"] != kind.lower()
            or not isinstance(data["sdp"], str)
            or not data["sdp"].startswith("v=0")
            or len(data["sdp"]) > 65000
        ):
            raise ValidationError("Mô tả kết nối không hợp lệ.")
    elif kind == "ICE":
        if (
            set(data) - {"candidate", "sdpMid", "sdpMLineIndex", "usernameFragment"}
            or not isinstance(data.get("candidate"), str)
            or len(data["candidate"]) > 4000
            or data.get("sdpMid") is not None
            and (not isinstance(data["sdpMid"], str) or len(data["sdpMid"]) > 100)
            or data.get("sdpMLineIndex") is not None
            and (
                type(data["sdpMLineIndex"]) is not int
                or not 0 <= data["sdpMLineIndex"] <= 20
            )
        ):
            raise ValidationError("Thông tin mạng không hợp lệ.")
        if data.get("usernameFragment") is not None and (
            not isinstance(data["usernameFragment"], str)
            or len(data["usernameFragment"]) > 256
        ):
            raise ValidationError("Thông tin mạng không hợp lệ.")
    else:
        raise ValidationError("Loại tín hiệu không hợp lệ.")
    return data


@transaction.atomic
def signal(user, room_id, call_id, target_id, kind, data, client_key, device_key):
    room, call = call_for(user, room_id, call_id, locked=True)
    user = access.lock_users([user.pk])[user.pk]
    access.require_use(user, "chat_call")
    expire(call)
    if call.status not in LIVE:
        raise ValidationError("Cuộc gọi đã kết thúc.")
    if not call.participants.filter(
        user=user, state="JOINED", session_key=request_key(device_key)
    ).exists():
        raise PermissionDenied("Thiết bị chưa tham gia cuộc gọi.")
    peers = set(
        call.participants.filter(state="JOINED").values_list("user_id", flat=True)
    )
    current = set(
        access.eligible_users()
        .filter(chat_memberships__room=room, chat_memberships__active=True)
        .values_list("pk", flat=True)
    )
    if user.pk not in peers or target_id == user.pk or target_id not in peers & current:
        raise PermissionDenied(
            "Tín hiệu chỉ được gửi giữa người đang tham gia cuộc gọi."
        )
    target = access.eligible_users().get(pk=target_id)
    if not has_function(target, "chat_call"):
        raise PermissionDenied
    data = signal_payload(kind, data)
    key = request_key(client_key)
    old = Signal.objects.filter(call=call, sender=user, client_key=key).first()
    if old:
        if old.target_id != target_id or old.kind != kind or old.payload != data:
            raise ValidationError("Mã tín hiệu đã dùng cho nội dung khác.")
        return old
    now = timezone.now()
    Signal.objects.filter(expires_at__lte=now).delete()
    used = (
        Signal.objects.filter(call=call, sender=user).aggregate(
            n=Sum(Length(Cast("payload", TextField())))
        )["n"]
        or 0
    )
    if used + len(json.dumps(data)) > 512 * 1024:
        raise ValidationError("Quá nhiều dữ liệu kết nối. Hãy kết nối lại.")
    if Signal.objects.filter(call=call, sender=user).count() >= 600:
        raise ValidationError("Quá nhiều tín hiệu kết nối. Hãy kết nối lại.")
    return Signal.objects.create(
        call=call,
        sender=user,
        target_id=target_id,
        kind=kind,
        payload=data,
        client_key=key,
        expires_at=now + timedelta(seconds=120),
    )


def signals(user, room_id, call_id, after=0, device_key=None):
    room, call = call_for(user, room_id, call_id)
    peer = call.participants.filter(user=user, state="JOINED").first()
    if call.status not in LIVE or peer is None:
        return call, []
    if peer.session_key != request_key(device_key):
        raise PermissionDenied("Thiết bị chưa tham gia cuộc gọi.")
    allowed = list(room.members.filter(active=True).values_list("user_id", flat=True))
    result = Signal.objects.filter(
        call=call,
        target=user,
        sender_id__in=allowed,
        expires_at__gt=timezone.now(),
        pk__gt=after,
    ).order_by("pk")[:100]
    return call, list(result)
