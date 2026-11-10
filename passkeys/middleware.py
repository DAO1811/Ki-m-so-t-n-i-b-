from django.contrib.auth import logout
from django.db import DatabaseError

from .models import PasskeyCredential


class PasskeySessionMiddleware:
    """Revocation affects passkey sessions; ordinary password sessions are untouched."""

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        raw = request.session.get("passkey_credential_id")
        if raw is not None:
            raw = str(raw)
            valid = False
            if (
                request.user.is_authenticated
                and raw.isascii()
                and raw.isdigit()
                and len(raw) <= 18
            ):
                try:
                    valid = PasskeyCredential.objects.filter(
                        pk=raw, user_id=request.user.pk, revoked_at__isnull=True
                    ).exists()
                except DatabaseError:
                    valid = False
            if not valid:
                logout(request)
        return self.get_response(request)
