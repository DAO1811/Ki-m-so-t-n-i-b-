from django.conf import settings
from django.db import models


class DeviceSession(models.Model):
    """One signed-in browser. Deleting the Django session logs that device out."""

    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="device_sessions",
        verbose_name="Tài khoản",
    )
    session_key = models.CharField(max_length=40, unique=True, editable=False)
    device = models.CharField("Thiết bị", max_length=120, blank=True)
    ip = models.CharField("Địa chỉ IP", max_length=45, blank=True)
    created_at = models.DateTimeField("Đăng nhập lúc", auto_now_add=True)
    last_seen = models.DateTimeField("Hoạt động gần nhất", db_index=True)

    class Meta:
        verbose_name = "Thiết bị đang đăng nhập"
        verbose_name_plural = "Thiết bị đang đăng nhập"
        ordering = ["-last_seen"]

    def __str__(self):
        return f"{self.user} · {self.device or 'Thiết bị'}"
