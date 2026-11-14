import os

from django.contrib.auth import get_user_model
from django.core.management.base import BaseCommand, CommandError
from django.db import transaction

MIN_ADMIN_PASSWORD_LENGTH = 12


class Command(BaseCommand):
    help = "Khởi tạo quản trị viên lần đầu từ biến bảo mật của hosting; không đổi mật khẩu đã có."

    @transaction.atomic
    def handle(self, *args, **kwargs):
        User = get_user_model()
        if User.objects.filter(is_superuser=True).exists():
            self.stdout.write("Đã có quản trị viên; không tạo lại hoặc đổi mật khẩu.")
            return
        username = os.environ.get("INITIAL_ADMIN_USERNAME")
        password = os.environ.get("INITIAL_ADMIN_PASSWORD")
        if not username and not password:
            self.stdout.write(
                "Chưa có quản trị viên. Dùng createsuperuser hoặc cấu hình INITIAL_ADMIN_USERNAME / INITIAL_ADMIN_PASSWORD trong hosting."
            )
            return
        if not username or not password:
            raise CommandError(
                "Cần cả INITIAL_ADMIN_USERNAME và INITIAL_ADMIN_PASSWORD."
            )
        if User.objects.filter(username=username).exists():
            raise CommandError(
                "Tên tài khoản đã tồn tại; không tự nâng quyền người dùng có sẵn."
            )
        user = User(username=username, email=os.environ.get("INITIAL_ADMIN_EMAIL", ""))
        # Employees may choose passwords freely (AUTH_PASSWORD_VALIDATORS = []);
        # only this first, all-powerful account has a minimum of its own.
        if len(password) < MIN_ADMIN_PASSWORD_LENGTH:
            raise CommandError(
                f"Mật khẩu Admin đầu tiên cần ít nhất {MIN_ADMIN_PASSWORD_LENGTH} ký tự."
            )
        if password.casefold() == username.casefold():
            raise CommandError(
                "Mật khẩu Admin đầu tiên không được trùng tên tài khoản."
            )
        User.objects.create_superuser(
            username=username, email=user.email, password=password
        )
        self.stdout.write(
            self.style.SUCCESS(
                "Đã tạo quản trị viên lần đầu; hãy xóa INITIAL_ADMIN_PASSWORD khỏi cấu hình hosting sau khi đăng nhập."
            )
        )
