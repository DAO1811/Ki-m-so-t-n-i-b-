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

    def test_approval_racing_rejection_or_admin_delete_has_only_one_decision(self):
        from .stocktakes import delete_session, reject_session

        for action in ("reject", "delete"):
            with self.subTest(action=action):
                self.receipt()
                session = start_session(self.a, self.maker)
                # Include every SKU at this snapshot, retaining a shortage of one.
                for item in session.items.all():
                    save_count(
                        session.pk,
                        self.maker,
                        item.product,
                        "SET",
                        item.book_quantity - 1,
                        None,
                        "",
                        uuid4(),
                        1,
                    )
                doc = submit_session(session.pk, self.maker, "Thiếu 1")
                before = Balance.objects.get().quantity

                def decide():
                    if action == "reject":
                        reject_session(
                            session.pk,
                            self.ceo,
                            "Không duyệt điều chỉnh",
                            expected_revision=doc.revision,
                        )
                    else:
                        delete_session(
                            session.pk,
                            self.admin,
                            "Phiếu thử",
                            confirmation=f"KK-{session.pk:06d}",
                            expected_status="SUBMITTED",
                            expected_document_status="DRAFT",
                            expected_revision=doc.revision,
                        )

                with ThreadPoolExecutor(max_workers=2) as pool:
                    results = list(
                        pool.map(
                            self.execute,
                            [lambda: post_document(doc.pk, self.ceo), decide],
                        )
                    )
                self.assertEqual(results.count("ok"), 1)
                doc.refresh_from_db()
                movements = Movement.objects.filter(document=doc).count()
                self.assertEqual(movements, 1 if doc.status == "POSTED" else 0)
                self.assertEqual(Balance.objects.get().quantity, before - movements)

    def test_receipt_racing_approval_preserves_both_operations(self):
        from django.contrib.auth import get_user_model

        from .models import Document, Line

        self.receipt()
        session = start_session(self.a, self.maker)
        save_count(session.pk, self.maker, self.p, "SET", 2, None, "", uuid4(), 1)
        adjustment = submit_session(session.pk, self.maker, "Thiếu một")
        separate = get_user_model().objects.create_superuser(
            "race-unrelated", "race@example.test", "1"
        )
        receipt = Document.objects.create(
            kind="IN", destination=self.a, created_by=separate
        )
        Line.objects.create(
            document=receipt, product=self.p, quantity=5, unit_price=100
        )
        with ThreadPoolExecutor(max_workers=2) as pool:
            results = list(
                pool.map(
                    self.execute,
                    [
                        lambda: post_document(adjustment.pk, self.ceo),
                        lambda: post_document(
                            receipt.pk, separate, confirm_self_approval=True
                        ),
                    ],
                )
            )
        self.assertEqual(results, ["ok", "ok"])
        self.assertEqual(Balance.objects.get().quantity, 7)
        self.assertEqual(
            Movement.objects.filter(document__in=[receipt, adjustment]).count(), 2
        )
