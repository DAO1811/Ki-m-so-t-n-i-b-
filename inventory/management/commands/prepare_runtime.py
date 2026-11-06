"""Prepare a web process without loading Django three separate times."""

from time import monotonic

from django.core.management import call_command
from django.core.management.base import BaseCommand


class Command(BaseCommand):
    help = "Verify the release snapshot, migrate, then initialize missing roles/admin."

    def handle(self, *args, **options):
        # Keep the existing commands and ordering. In particular, no later phase
        # or web server may start when snapshot validation/migration fails.
        # Do not wrap this in an outer transaction: safe_migrate owns its lock
        # and snapshot transaction, and migrate owns its migration boundaries.
        for name in ("safe_migrate", "setup_roles", "bootstrap_admin"):
            started = monotonic()
            self.stdout.write(f"startup phase={name} state=starting")
            self.stdout.flush()
            call_command(name, stdout=self.stdout, stderr=self.stderr)
            self.stdout.write(
                f"startup phase={name} state=ready "
                f"duration_seconds={monotonic() - started:.3f}"
            )
            self.stdout.flush()
