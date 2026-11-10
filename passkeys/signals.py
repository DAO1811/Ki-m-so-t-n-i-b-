from django.contrib.auth.signals import user_logged_in
from django.dispatch import receiver


@receiver(user_logged_in, dispatch_uid="passkeys.clear_previous_login_method")
def clear_previous_login_method(sender, request, **kwargs):
    # Django preserves same-user sessions on password login. A new password
    # login is no longer dependent on the previously used passkey. Passkey
    # login explicitly sets its own tag after auth.login sends this signal.
    if request is not None:
        request.session.pop("passkey_credential_id", None)
