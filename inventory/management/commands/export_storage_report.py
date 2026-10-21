import json
from datetime import timedelta

import psycopg
from django.core.exceptions import ValidationError
from django.core.management.base import BaseCommand, CommandError
from django.db import DatabaseError
from django.utils import timezone

from inventory.storage_reports import export_month


class Command(BaseCommand):
    help = "Export and verify one completed month's management report to the connected Drive folder. Never deletes source data."

    def add_arguments(self, parser):
        parser.add_argument(
            "--period", help="YYYY-MM; defaults to the previous completed month"
        )

    def handle(self, *args, **options):
        period = options["period"] or (
            timezone.localdate().replace(day=1) - timedelta(days=1)
        ).strftime("%Y-%m")
        try:
            result = export_month(period)
        except (ValidationError, DatabaseError, psycopg.Error):
            raise CommandError(
                "Chưa xác nhận báo cáo trên Drive. Kiểm tra kết nối trong phần mềm; dữ liệu gốc giữ nguyên."
            ) from None
        self.stdout.write(
            json.dumps(
                {
                    "period": result["period"],
                    "rows": result["rows"],
                    "state": result["state"],
                }
            )
        )
