from django.conf import settings


def camera_context(request):
    return {"camera_identity_enabled": settings.CAMERA_IDENTITY_ENABLED}
