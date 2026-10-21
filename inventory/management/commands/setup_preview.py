import os

from django.conf import settings
from django.contrib.auth import get_user_model
from django.contrib.auth.models import Group
from django.core.management import call_command
from django.core.management.base import BaseCommand, CommandError
from django.db import transaction

from config.preview import validate_preview_environment
from inventory.models import Document, Product, Warehouse


class Command(BaseCommand):
    help = "Chỉ tạo tài khoản và dữ liệu minh họa trong database preview local riêng."

    def handle(self, *args, **options):
        if not settings.DHD_PREVIEW:
            raise CommandError(
                "Chỉ chạy trong bản thử riêng, không dùng trên production."
            )
        validate_preview_environment()
        return self.seed()

    @transaction.atomic
    def seed(self):
        User = get_user_model()
        marker = Group.objects.filter(name="DHD Preview Instance").first()
        if marker is None and (
            User.objects.exists()
            or Warehouse.objects.exists()
            or Product.objects.exists()
            or Document.objects.exists()
        ):
            raise CommandError(
                "Database không trống và chưa được đánh dấu preview. Dừng để bảo vệ dữ liệu."
            )
        password = os.environ.get("DHD_PREVIEW_ADMIN_PASSWORD", "")
        if len(password) < 16:
            raise CommandError(
                "Thiếu mật khẩu thử ngẫu nhiên. Chạy scripts/preview.py setup."
            )
        marker, _ = Group.objects.get_or_create(name="DHD Preview Instance")
        user, created = User.objects.get_or_create(
            username="preview_admin",
            defaults={
                "is_superuser": True,
                "is_staff": True,
                "email": "preview@example.test",
            },
        )
        if not created and not user.groups.filter(pk=marker.pk).exists():
            raise CommandError(
                "Tài khoản hiện có không thuộc bản thử; không thay đổi tài khoản."
            )
        if not user.check_password(password):
            user.set_password(password)
            user.save(update_fields=["password"])
        user.groups.add(marker)
        if (
            not Warehouse.objects.exists()
            and not Product.objects.exists()
            and not Document.objects.exists()
        ):
            call_command("demo_data", stdout=self.stdout)
        self.stdout.write(
            self.style.SUCCESS(
                "Bản thử đã sẵn sàng. Chạy task DHD: Xem tài khoản thử để đăng nhập."
            )
        )
