from django.db import models


class LoginThrottle(models.Model):
    """Failed password logins per account name or client IP (never passwords)."""

    SCOPES = [("user", "Tài khoản"), ("ip", "Địa chỉ IP")]
    scope = models.CharField("Loại", max_length=8, choices=SCOPES)
    key = models.CharField("Tài khoản / IP", max_length=150)
    failures = models.PositiveIntegerField("Số lần sai", default=0)
    window_started_at = models.DateTimeField("Bắt đầu đếm")
    locked_until = models.DateTimeField("Khóa đến", null=True, blank=True)
    lockouts = models.PositiveIntegerField("Số lần bị khóa", default=0)
    updated_at = models.DateTimeField("Cập nhật", auto_now=True, db_index=True)

    class Meta:
        verbose_name = "Khóa tạm đăng nhập"
        verbose_name_plural = "Khóa tạm đăng nhập"
        default_permissions = ("view", "delete")
        constraints = [
            models.UniqueConstraint(
                fields=["scope", "key"], name="login_throttle_scope_key"
            )
        ]

    def __str__(self):
        return f"{self.get_scope_display()}: {self.key}"
