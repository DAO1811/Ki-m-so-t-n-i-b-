from django.conf import settings

from .environment import STAGING


def environment_context(request):
    return {
        "app_environment": settings.APP_ENVIRONMENT,
        "app_version": settings.APP_VERSION,
        "is_staging": settings.APP_ENVIRONMENT == STAGING,
    }
