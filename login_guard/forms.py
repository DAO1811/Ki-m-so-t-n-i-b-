from django.contrib.auth.forms import AuthenticationForm
from django.core.exceptions import ValidationError

from . import services

# One message for every lock (account, unknown name, IP) so the response never
# reveals whether an account exists or is an Admin.
LOCK_MESSAGE = (
    "Đăng nhập đã bị khóa do nhập sai mật khẩu nhiều lần. "
    "Vui lòng liên hệ quản trị viên để mở khóa."
)


class GuardedAuthenticationForm(AuthenticationForm):
    """Django's login form plus database-backed lockout."""

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        # "webauthn" lets iPhone/Android show the saved Face ID / fingerprint
        # sign-in above the keyboard when the username field is tapped.
        self.fields["username"].widget.attrs["autocomplete"] = "username webauthn"
        # Bank-style: ask browsers not to auto-fill or keep the password.
        self.fields["password"].widget.attrs.update(
            autocomplete="off", placeholder="Nhập mật khẩu"
        )

    def _locked(self):
        return ValidationError(LOCK_MESSAGE, code="login_locked")

    def clean(self):
        username = self.cleaned_data.get("username")
        ip = services.client_ip(self.request) if self.request else "unknown"
        if services.is_locked(username, ip):
            raise self._locked()
        try:
            cleaned = super().clean()
        except ValidationError as exc:
            if getattr(exc, "code", None) == "invalid_login":
                if services.register_failure(username, ip):
                    raise self._locked() from exc
            raise
        services.clear_account(username)
        return cleaned
