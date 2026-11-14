from django.contrib import admin

from .models import ChatToolAudit


@admin.register(ChatToolAudit)
class ChatToolAuditAdmin(admin.ModelAdmin):
    """Read-only log of AI lookups: who, when, which tool, how many rows."""

    list_display = ("created_at", "owner_name", "tool", "rows")
    list_filter = ("tool",)
    ordering = ("-created_at",)

    @admin.display(description="Người hỏi")
    def owner_name(self, obj):
        from django.contrib.auth import get_user_model

        user = get_user_model().objects.filter(pk=obj.owner_id).first()
        return user.username if user else obj.owner_id

    def has_add_permission(self, request):
        return False

    def has_change_permission(self, request, obj=None):
        return False

    def has_delete_permission(self, request, obj=None):
        return False
