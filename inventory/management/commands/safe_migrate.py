import psycopg
from django.core.management import call_command
from django.core.management.base import BaseCommand, CommandError
from django.db import DatabaseError, connection

from inventory.release_backup import SNAPSHOT_SCHEMA, deploy_connection, ensure_snapshot


class Command(BaseCommand):
    help = "Keep a consistent private data snapshot before migrating PostgreSQL."

    def handle(self, *args, **options):
        if connection.vendor != "postgresql":
            call_command("migrate", interactive=False, stdout=self.stdout)
            return
        try:
            with deploy_connection() as db:
                ensure_snapshot(db)
                self.stdout.write(f"Pre-upgrade snapshot verified: {SNAPSHOT_SCHEMA}")
                call_command("migrate", interactive=False, stdout=self.stdout)
        except (psycopg.Error, DatabaseError, RuntimeError):
            # Never echo connection parameters or database rows in Render logs.
            raise CommandError(
                "Không thể hoàn tất bản chụp / nâng cấp dữ liệu. Bản mới chưa khởi động; "
                "kiểm tra snapshot và nhật ký migration trước khi thử lại."
            ) from None
