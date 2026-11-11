"""Isolated storage for the optional camera-identity evaluation module."""

import uuid

from django.conf import settings
from django.db import models


class FaceProfile(models.Model):
    user = models.OneToOneField(settings.AUTH_USER_MODEL, on_delete=models.CASCADE)
    encrypted_template = models.BinaryField(editable=False)
    model_id = models.CharField(max_length=120)
    consent_version = models.CharField(max_length=40)
    consented_at = models.DateTimeField()
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)


class FaceChallenge(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL, null=True, on_delete=models.CASCADE
    )
    kind = models.CharField(
        max_length=10, choices=[("ENROLL", "Enroll"), ("VERIFY", "Verify")]
    )
    session_hash = models.CharField(max_length=64)
    auth_hash = models.CharField(max_length=64, blank=True)
    steps = models.JSONField(default=list)
    expires_at = models.DateTimeField(db_index=True)
    used_at = models.DateTimeField(null=True)


class RateBucket(models.Model):
    key = models.CharField(max_length=64, primary_key=True)
    count = models.PositiveIntegerField(default=0)
    expires_at = models.DateTimeField(db_index=True)


class AuditEvent(models.Model):
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL, null=True, on_delete=models.SET_NULL
    )
    action = models.CharField(max_length=32)
    created_at = models.DateTimeField(auto_now_add=True)
