from .services import APP_LOCK_AFTER, app_lock_applies, available, recent_password_login


def passkey_context(request):
    data = {"passkeys_available": available()}
    user = getattr(request, "user", None)
    if (
        data["passkeys_available"]
        and user is not None
        and user.is_authenticated
        and hasattr(request, "session")
        and "passkey_credential_id" not in request.session
        and recent_password_login(request)
    ):
        # Just signed in with a password: offer to turn on Face ID here.
        data["passkey_offer"] = True
    if (
        user is not None
        and hasattr(request, "session")
        and data["passkeys_available"]
        and app_lock_applies(request)
    ):
        data["app_lock_active"] = True
        data["app_lock_after"] = APP_LOCK_AFTER
    return data
