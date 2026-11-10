from django.core.management.base import BaseCommand

from passkeys.services import prune


class Command(BaseCommand):
    help = (
        "Delete expired passkey challenges and throttling buckets; never business data."
    )

    def handle(self, *args, **options):
        prune()
        self.stdout.write("Expired passkey challenges and rate buckets removed.")
