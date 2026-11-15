from django.contrib.auth.signals import user_logged_in, user_logged_out
from django.dispatch import receiver

from . import services


@receiver(user_logged_in)
def on_login(sender, request, user, **kwargs):
    if request is not None and hasattr(request, "session"):
        services.record(request, user)


@receiver(user_logged_out)
def on_logout(sender, request, user, **kwargs):
    if request is not None and hasattr(request, "session"):
        services.forget(request.session.session_key)
