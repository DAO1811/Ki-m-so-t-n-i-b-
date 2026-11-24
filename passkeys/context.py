from .services import (
    app_lock_applies,
    available,
    has_face_id,
    identity,
    lock_timing,
    recent_password_login,
)


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
        and user.is_authenticated
        and hasattr(request, "session")
        and app_lock_applies(request)
    ):
        away, idle, _gap = lock_timing()
        name, initial = identity(user)
        data.update(
            app_lock_active=True,
            app_lock_away=away,
            app_lock_idle=idle,
            app_lock_idle_minutes=max(1, round(idle / 60)),
            app_lock_name=name,
            app_lock_initial=initial,
            has_face_id=has_face_id(user),
        )
    return data
