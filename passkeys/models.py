import uuid

from django.conf import settings
from django.db import models


class PasskeyIdentity(models.Model):
    user = models.OneToOneField(settings.AUTH_USER_MODEL, on_delete=models.CASCADE)
    handle = models.UUIDField(default=uuid.uuid4, unique=True, editable=False)


class PasskeyCredential(models.Model):
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE)
    credential_id = models.CharField(max_length=1400, unique=True, editable=False)
    public_key = models.BinaryField(editable=False)
    sign_count = models.PositiveBigIntegerField(default=0)
    label = models.CharField(max_length=80)
    backup_eligible = models.BooleanField(default=False)
    backed_up = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)
    last_used_at = models.DateTimeField(null=True, blank=True)
    revoked_at = models.DateTimeField(null=True, blank=True)


class Ceremony(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    kind = models.CharField(
        max_length=10, choices=[("register", "Register"), ("login", "Login")]
    )
    session_hash = models.CharField(max_length=64)
    challenge = models.BinaryField()
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL, null=True, on_delete=models.CASCADE
    )
    auth_hash = models.CharField(max_length=64, blank=True)
    payload = models.JSONField(default=dict)
    expires_at = models.DateTimeField(db_index=True)
    used_at = models.DateTimeField(null=True)
    rp_id = models.CharField(max_length=253)
    origin = models.CharField(max_length=300)


class RateBucket(models.Model):
    key = models.CharField(max_length=64, primary_key=True)
    count = models.PositiveIntegerField(default=0)
    expires_at = models.DateTimeField(db_index=True)


class SecurityEvent(models.Model):
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL, null=True, on_delete=models.SET_NULL
    )
    action = models.CharField(max_length=32)
    created_at = models.DateTimeField(auto_now_add=True)
