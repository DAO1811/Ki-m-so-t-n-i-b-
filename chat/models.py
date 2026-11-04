"""Private rooms: superusers are not automatically participants. No admin registration."""

from uuid import uuid4

from django.conf import settings
from django.db import models
from django.db.models import Q


class Room(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid4, editable=False)
    kind = models.CharField(
        max_length=8, choices=[("DIRECT", "Cá nhân"), ("GROUP", "Nhóm")]
    )
    title = models.CharField(max_length=100, blank=True)
    direct_key = models.CharField(max_length=80, null=True, unique=True, editable=False)
    owner = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        related_name="owned_chat_rooms",
    )
    last_seq = models.PositiveBigIntegerField(default=0)
    revision = models.PositiveBigIntegerField(default=1)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now_add=True, db_index=True)

    class Meta:
        default_permissions = ()


class Member(models.Model):
    room = models.ForeignKey(Room, on_delete=models.CASCADE, related_name="members")
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        related_name="chat_memberships",
    )
    active = models.BooleanField(default=True)
    joined_seq = models.PositiveBigIntegerField(default=0)
    read_seq = models.PositiveBigIntegerField(default=0)
    joined_at = models.DateTimeField(auto_now_add=True)
    typing_until = models.DateTimeField(null=True)

    class Meta:
        default_permissions = ()
        constraints = [
            models.UniqueConstraint(fields=["room", "user"], name="chat_one_membership")
        ]


class Message(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid4, editable=False)
    room = models.ForeignKey(Room, on_delete=models.PROTECT, related_name="messages")
    seq = models.PositiveBigIntegerField()
    sender = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT)
    client_key = models.UUIDField()
    text = models.TextField(max_length=4000, blank=True)
    sticker = models.CharField(max_length=32, blank=True)
    reply_to = models.ForeignKey(
        "self", null=True, blank=True, on_delete=models.PROTECT
    )
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        default_permissions = ()
        ordering = ["seq"]
        constraints = [
            models.UniqueConstraint(fields=["room", "seq"], name="chat_one_sequence"),
            models.UniqueConstraint(
                fields=["sender", "client_key"], name="chat_one_send_request"
            ),
        ]
        indexes = [models.Index(fields=["sender", "created_at"])]


class Attachment(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid4, editable=False)
    message = models.ForeignKey(
        Message, on_delete=models.PROTECT, related_name="attachments"
    )
    file = models.ForeignKey(
        "inventory.StoredFile",
        on_delete=models.PROTECT,
        related_name="chat_attachments",
    )
    filename = models.CharField(max_length=150)

    class Meta:
        default_permissions = ()


class Reaction(models.Model):
    message = models.ForeignKey(
        Message, on_delete=models.CASCADE, related_name="reactions"
    )
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE)
    emoji = models.CharField(max_length=12)

    class Meta:
        default_permissions = ()
        constraints = [
            models.UniqueConstraint(
                fields=["message", "user"], name="chat_one_reaction"
            )
        ]


class Call(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid4, editable=False)
    room = models.ForeignKey(Room, on_delete=models.PROTECT, related_name="calls")
    initiator = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT)
    client_key = models.UUIDField()
    mode = models.CharField(
        max_length=8, choices=[("AUDIO", "Thoại"), ("VIDEO", "Video")]
    )
    status = models.CharField(
        max_length=12,
        default="RINGING",
        choices=[
            ("RINGING", "Đang mời"),
            ("ACTIVE", "Đang gọi"),
            ("ENDED", "Đã kết thúc"),
        ],
    )
    created_at = models.DateTimeField(auto_now_add=True)
    touched_at = models.DateTimeField(auto_now_add=True)
    ended_at = models.DateTimeField(null=True)
    end_reason = models.CharField(max_length=40, blank=True)

    class Meta:
        default_permissions = ()
        constraints = [
            models.UniqueConstraint(
                fields=["room"],
                condition=Q(status__in=["RINGING", "ACTIVE"]),
                name="chat_one_active_room_call",
            ),
            models.UniqueConstraint(
                fields=["initiator", "client_key"], name="chat_one_call_request"
            ),
        ]


class CallMember(models.Model):
    session_key = models.UUIDField(null=True)
    call = models.ForeignKey(
        Call, on_delete=models.CASCADE, related_name="participants"
    )
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT)
    state = models.CharField(
        max_length=10,
        default="INVITED",
        choices=[
            ("INVITED", "Được mời"),
            ("JOINED", "Đang tham gia"),
            ("LEFT", "Đã rời"),
            ("DECLINED", "Từ chối"),
        ],
    )
    last_seen = models.DateTimeField(null=True)
    joined_at = models.DateTimeField(null=True)

    class Meta:
        default_permissions = ()
        constraints = [
            models.UniqueConstraint(
                fields=["call", "user"], name="chat_one_call_member"
            )
        ]


class Signal(models.Model):
    call = models.ForeignKey(Call, on_delete=models.CASCADE)
    sender = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="sent_chat_signals",
    )
    target = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="received_chat_signals",
    )
    client_key = models.UUIDField()
    kind = models.CharField(max_length=8)
    payload = models.JSONField()
    created_at = models.DateTimeField(auto_now_add=True)
    expires_at = models.DateTimeField(db_index=True)

    class Meta:
        default_permissions = ()
        constraints = [
            models.UniqueConstraint(
                fields=["call", "sender", "client_key"], name="chat_one_signal_request"
            )
        ]
        indexes = [models.Index(fields=["call", "target", "id"])]
