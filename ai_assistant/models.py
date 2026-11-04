"""Only short-lived AI requests and quota metadata, never business records."""

import uuid

from django.db import models
from django.utils import timezone


class ChatUsage(models.Model):
    scope = models.CharField(max_length=40)
    day = models.DateField()
    requests = models.PositiveIntegerField(default=0)
    tokens = models.PositiveIntegerField(default=0)

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=["scope", "day"], name="ai_chat_usage_scope_day"
            )
        ]


class ChatSlot(models.Model):
    id = models.PositiveSmallIntegerField(primary_key=True, default=1)
    lease = models.UUIDField(null=True)
    until = models.DateTimeField(null=True)


class ChatJob(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    owner_id = models.PositiveBigIntegerField()
    session_scope = models.CharField(max_length=64)
    client_key = models.UUIDField()
    request_hash = models.CharField(max_length=64)
    created_at = models.DateTimeField(default=timezone.now, db_index=True)
    expires_at = models.DateTimeField(db_index=True)
    state = models.CharField(max_length=12, default="PENDING")
    payload = models.TextField()  # encrypted, expires after 10 minutes
    output = models.TextField(blank=True)  # encrypted partial answer
    error = models.CharField(
        max_length=40, blank=True
    )  # allowlisted code, no raw provider errors
    reserved_tokens = models.PositiveIntegerField()
    charged_tokens = models.PositiveIntegerField(null=True)
    request_day = models.DateField()

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=["owner_id", "client_key"], name="ai_chat_owner_submission"
            )
        ]
        indexes = [
            models.Index(
                fields=["owner_id", "created_at"], name="ai_chat_owner_created"
            )
        ]
