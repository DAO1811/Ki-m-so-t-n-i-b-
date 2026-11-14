import math

from django.contrib.auth.forms import AuthenticationForm
from django.core.exceptions import ValidationError
from django.utils import timezone

from . import services

LOCK_MESSAGE = (
    "Đăng nhập tạm khóa do nhập sai nhiều lần. Vui lòng thử lại sau {minutes} phút "
    "hoặc liên hệ quản trị viên."
)


class GuardedAuthenticationForm(AuthenticationForm):
    """Django's login form plus database-backed lockout. Same message for every
    account name, existing or not."""

    def _locked(self, until):
        minutes = max(1, math.ceil((until - timezone.now()).total_seconds() / 60))
        return ValidationError(
            LOCK_MESSAGE.format(minutes=minutes), code="login_locked"
        )

    def clean(self):
        username = self.cleaned_data.get("username")
        ip = services.client_ip(self.request) if self.request else "unknown"
        until = services.locked_until(username, ip)
        if until:
            raise self._locked(until)
        try:
            cleaned = super().clean()
        except ValidationError as exc:
            if getattr(exc, "code", None) == "invalid_login":
                until = services.register_failure(username, ip)
                if until:
                    raise self._locked(until) from exc
            raise
        services.clear_account(username)
        return cleaned
