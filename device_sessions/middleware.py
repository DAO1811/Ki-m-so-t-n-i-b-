from django.db import DatabaseError

from . import services


class DeviceSessionMiddleware:
    """Refresh the signed-in device's last activity; never blocks a request."""

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        if getattr(request, "user", None) and request.user.is_authenticated:
            try:
                services.touch(request)
            except DatabaseError:
                pass
        return self.get_response(request)
