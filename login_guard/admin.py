from django.contrib import admin, messages

from . import services
from .models import LoginThrottle


@admin.register(LoginThrottle)
class LoginThrottleAdmin(admin.ModelAdmin):
    """Read-only audit of lockouts; unlocking deletes the row immediately."""

    list_display = (
        "scope",
        "key",
        "admin_unlock_required",
        "failures",
        "locked_until",
        "lockouts",
        "updated_at",
    )
    list_filter = ("scope", "admin_unlock_required")
    search_fields = ("key",)
    ordering = ("-admin_unlock_required", "-updated_at")
    readonly_fields = list_display + ("window_started_at",)
    actions = ["unlock_selected"]

    @admin.action(description="Mở khóa các dòng đã chọn")
    def unlock_selected(self, request, queryset):
        count = services.unlock(list(queryset))
        self.message_user(
            request,
            f"Đã mở khóa {count} dòng. Nếu nhân viên quên mật khẩu, đặt lại tại "
            "Quản lý nhân viên → Sửa.",
            messages.SUCCESS,
        )

    def has_add_permission(self, request):
        return False

    def has_change_permission(self, request, obj=None):
        return False
