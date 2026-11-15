from django.apps import AppConfig


class DeviceSessionsConfig(AppConfig):
    default_auto_field = "django.db.models.BigAutoField"
    name = "device_sessions"
    verbose_name = "Phiên đăng nhập"

    def ready(self):
        from . import signals  # noqa: F401
