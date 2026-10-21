from concurrent.futures import ThreadPoolExecutor
from unittest import skipUnless
from uuid import uuid4

from django.core.exceptions import PermissionDenied, ValidationError
from django.db import close_old_connections, connection, connections
from django.test import TransactionTestCase

from . import test_qr_records as fixtures
from .models import Balance, Movement, StocktakeEvent
from .services import close_document, post_document
from .stocktakes import save_count, start_session, submit_session


@skipUnless(connection.vendor == "postgresql", "Requires PostgreSQL row locks")
class QRConcurrencyTests(TransactionTestCase):
    def setUp(self):
        fixtures.QRStocktakeTests.setUpTestData.__func__(type(self))

    receipt = fixtures.QRStocktakeTests.receipt

    def execute(self, operation):
        close_old_connections()
        try:
            operation()
            return "ok"
        except (PermissionDenied, ValidationError):
            return "blocked"
        finally:
            connections.close_all()

    def test_concurrent_retries_of_one_scan_count_once(self):
        session = start_session(self.a, self.maker)
        request_id = uuid4()

        def scan():
            save_count(
                session.pk, self.maker, self.p, "ADD", None, None, "", request_id, 1
            )

        with ThreadPoolExecutor(max_workers=2) as pool:
            results = list(pool.map(self.execute, [scan, scan]))
        self.assertEqual(results, ["ok", "ok"])
        self.assertEqual(session.items.get().counted_quantity, 1)
        self.assertEqual(
            StocktakeEvent.objects.filter(session=session, action="ADD").count(), 1
        )

    def test_ceo_approval_racing_with_cancellation_is_atomic(self):
        self.receipt()
        session = start_session(self.a, self.maker)
        save_count(session.pk, self.maker, self.p, "SET", 2, None, "", uuid4(), 1)
        doc = submit_session(session.pk, self.maker, "Thiếu 1")
        operations = [
            lambda: post_document(doc.pk, self.ceo),
            lambda: close_document(
                doc.pk, self.maker, "CANCEL", "Dừng xử lý để kiểm kê lại"
            ),
        ]
        with ThreadPoolExecutor(max_workers=2) as pool:
            results = list(pool.map(self.execute, operations))
        self.assertEqual(results.count("ok"), 1)
        doc.refresh_from_db()
        if doc.status == "POSTED":
            self.assertEqual(Balance.objects.get().quantity, 2)
            self.assertEqual(Movement.objects.filter(document=doc).count(), 1)
        else:
            self.assertEqual(doc.status, "CANCELLED")
            self.assertEqual(Balance.objects.get().quantity, 3)
            self.assertFalse(Movement.objects.filter(document=doc).exists())
