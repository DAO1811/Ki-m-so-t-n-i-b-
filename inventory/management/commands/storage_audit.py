import json

from django.core.management.base import BaseCommand, CommandError
from django.db import DatabaseError

from inventory.storage_audit import measure_storage


class Command(BaseCommand):
    help = "Measure storage without modifying or exporting company business data."

    def handle(self, *args, **options):
        try:
            report = measure_storage()
        except DatabaseError:
            raise CommandError(
                "Không đo được dung lượng. Không có dữ liệu nào bị xóa hoặc di chuyển."
            ) from None
        self.stdout.write(json.dumps(report, ensure_ascii=False, indent=2))
