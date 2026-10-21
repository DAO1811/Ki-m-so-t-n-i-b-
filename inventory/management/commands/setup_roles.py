from django.contrib.auth.models import Group, Permission
from django.core.management.base import BaseCommand


class Command(BaseCommand):
    help = "Khởi tạo vai trò mặc định; không tạo tài khoản hay mật khẩu."

    def handle(self, *args, **kwargs):
        roles = {
            "Nhân viên kho": [
                "add_document",
                "view_document",
                "view_product",
                "view_warehouse",
            ],
            "Quản lý kho": [
                "add_document",
                "view_document",
                "post_document",
                "add_product",
                "change_product",
                "view_product",
                "view_warehouse",
            ],
            "Chỉ xem báo cáo": ["view_document", "view_product", "view_warehouse"],
        }
        for name, codes in roles.items():
            group, created = Group.objects.get_or_create(name=name)
            if created:
                group.permissions.set(
                    Permission.objects.filter(
                        content_type__app_label="inventory", codename__in=codes
                    )
                )
        self.stdout.write(
            self.style.SUCCESS(
                "Đã chuẩn bị 3 vai trò; giữ nguyên các vai trò đã được tùy chỉnh."
            )
        )
