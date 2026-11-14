from django.contrib import admin

from .models import LoginThrottle


@admin.register(LoginThrottle)
class LoginThrottleAdmin(admin.ModelAdmin):
    """Read-only audit of lockouts; deleting a row unlocks it immediately."""

    list_display = (
        "scope",
        "key",
        "failures",
        "locked_until",
        "lockouts",
        "updated_at",
    )
    list_filter = ("scope",)
    search_fields = ("key",)
    ordering = ("-updated_at",)
    readonly_fields = list_display + ("window_started_at",)

    def has_add_permission(self, request):
        return False

    def has_change_permission(self, request, obj=None):
        return False
