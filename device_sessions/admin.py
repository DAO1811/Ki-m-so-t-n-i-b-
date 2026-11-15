from django.contrib import admin, messages

from . import services
from .models import DeviceSession


@admin.register(DeviceSession)
class DeviceSessionAdmin(admin.ModelAdmin):
    list_display = ("user", "device", "ip", "created_at", "last_seen")
    list_filter = ("user",)
    search_fields = ("user__username", "device", "ip")
    readonly_fields = ("user", "device", "ip", "created_at", "last_seen")
    actions = ["logout_selected"]

    @admin.action(description="Đăng xuất các thiết bị đã chọn")
    def logout_selected(self, request, queryset):
        count = services.revoke(queryset)
        self.message_user(request, f"Đã đăng xuất {count} thiết bị.", messages.SUCCESS)

    def get_actions(self, request):
        actions = super().get_actions(request)
        actions.pop("delete_selected", None)
        return actions

    def has_add_permission(self, request):
        return False

    def has_change_permission(self, request, obj=None):
        return False

    def has_delete_permission(self, request, obj=None):
        return False
