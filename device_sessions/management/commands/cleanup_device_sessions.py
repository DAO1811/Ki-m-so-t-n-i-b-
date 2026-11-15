from django.core.management.base import BaseCommand

from device_sessions.services import prune


class Command(BaseCommand):
    help = "Xóa dòng thiết bị của phiên đã hết hạn; không đụng dữ liệu nghiệp vụ."

    def handle(self, *args, **options):
        self.stdout.write(f"Đã xóa {prune()} dòng thiết bị hết hạn.")
