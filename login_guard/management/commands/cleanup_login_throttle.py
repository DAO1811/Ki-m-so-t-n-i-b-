from datetime import timedelta

from django.core.management.base import BaseCommand

from login_guard.services import purge


class Command(BaseCommand):
    help = (
        "Xóa bộ đếm đăng nhập sai đã cũ (không còn khóa); không đụng dữ liệu nghiệp vụ."
    )

    def add_arguments(self, parser):
        parser.add_argument("--days", type=int, default=1)

    def handle(self, *args, days, **options):
        deleted = purge(timedelta(days=max(days, 0)))
        self.stdout.write(f"Đã xóa {deleted} bộ đếm đăng nhập cũ.")
