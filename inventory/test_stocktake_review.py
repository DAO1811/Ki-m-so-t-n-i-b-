from django.core.exceptions import PermissionDenied, ValidationError
from django.test import Client, TestCase
from django.urls import reverse

from . import test_stocktake_workflow as fixtures
from .access import FUNCTION_KEYS
from .models import Balance, Movement, StocktakeDeletion, StocktakeEvent
from .services import post_document
from .stocktakes import (
    active_sessions,
    begin_session,
    delete_session,
    freeze_session,
    submit_session,
)
from .test_support import grant_functions


class StocktakeReviewTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        fixtures.StocktakeWorkflowTests.setUpTestData.__func__(cls)

    receipt = fixtures.StocktakeWorkflowTests.receipt
    count = fixtures.StocktakeWorkflowTests.count

    def pending(self):
        self.receipt()
        session = freeze_session(self.a, self.maker)
        begin_session(session.pk, self.maker, "QR")
        self.count(session, 2)
        document = submit_session(session.pk, self.maker, "Thiếu một hàng")
        session.refresh_from_db()
        return session, document

    def delete_payload(self, session):
        session.refresh_from_db()
        return {
            "confirmation": f"KK-{session.pk:06d}",
            "reason": "Phiếu tạo nhầm",
            "expected_status": session.status,
            "expected_document_status": session.document.status
            if session.document_id
            else "",
            "expected_revision": session.document.revision
            if session.document_id
            else 0,
        }

    def test_ceo_can_reject_with_reason_without_stock_change_and_warehouse_reopens(
        self,
    ):
        session, document = self.pending()
        self.client.force_login(self.ceo)
        self.assertContains(
            self.client.get(reverse("stocktake_detail", args=[session.pk])),
            "Không duyệt",
        )
        response = self.client.post(
            reverse("stocktake_reject", args=[session.pk]),
            {"reason": "Đếm chưa đúng", "expected_revision": document.revision},
        )
        self.assertEqual(response.status_code, 302)
        document.refresh_from_db()
        session.refresh_from_db()
        self.assertEqual(document.status, "REJECTED")
        self.assertEqual(document.closure_reason, "Đếm chưa đúng")
        self.assertNotContains(
            self.client.get(reverse("stocktake_detail", args=[session.pk])),
            "Kho chưa mở phiên kiểm kê tiếp theo",
        )
        self.assertFalse(session.locks_inventory)
        self.assertFalse(active_sessions().filter(pk=session.pk).exists())
        self.assertEqual(Balance.objects.get(warehouse=self.a).quantity, 3)
        self.assertEqual(Movement.objects.count(), 1)
        self.assertEqual(
            StocktakeEvent.objects.filter(session=session, action="REJECT").count(), 1
        )
        with self.assertRaises(ValidationError):
            post_document(document.pk, self.admin)
        self.receipt(quantity=1)
        self.assertEqual(Balance.objects.get(warehouse=self.a).quantity, 4)

    def test_reject_requires_permission_reason_fresh_revision_post_and_csrf(self):
        session, document = self.pending()
        url = reverse("stocktake_reject", args=[session.pk])
        self.client.force_login(self.maker)
        self.assertEqual(
            self.client.post(url, {"reason": "No", "expected_revision": 1}).status_code,
            403,
        )
        self.client.force_login(self.ceo)
        self.assertEqual(self.client.get(url).status_code, 405)
        for reason, revision in [("", document.revision), ("X", document.revision + 1)]:
            self.client.post(url, {"reason": reason, "expected_revision": revision})
            document.refresh_from_db()
            self.assertEqual(document.status, "DRAFT")
        csrf = Client(enforce_csrf_checks=True)
        csrf.cookies = self.client.cookies
        self.assertEqual(
            csrf.post(
                url, {"reason": "X", "expected_revision": document.revision}
            ).status_code,
            403,
        )

    def test_admin_deletes_ready_and_open_sessions_releases_only_their_warehouse(self):
        self.receipt()
        other = freeze_session(self.b, self.maker)
        for started in (False, True):
            session = freeze_session(self.a, self.maker)
            if started:
                begin_session(session.pk, self.maker, "PAPER")
            item_ids = list(session.items.values_list("pk", flat=True))
            payload = self.delete_payload(session)
            delete_session(session.pk, self.admin, **payload)
            session.refresh_from_db()
            self.assertTrue(session.is_deleted)
            self.assertFalse(session.locks_inventory)
            self.assertFalse(active_sessions().filter(pk=session.pk).exists())
            self.assertTrue(active_sessions().filter(pk=other.pk).exists())
            self.assertEqual(list(session.items.values_list("pk", flat=True)), item_ids)
            self.receipt(quantity=1)
        self.assertEqual(Balance.objects.get(warehouse=self.a).quantity, 5)

    def test_pending_adjustment_is_cancelled_on_delete_without_posting(self):
        session, document = self.pending()
        self.client.force_login(self.admin)
        self.client.post(
            reverse("stocktake_delete", args=[session.pk]), self.delete_payload(session)
        )
        document.refresh_from_db()
        session.refresh_from_db()
        self.assertEqual(document.status, "CANCELLED")
        self.assertFalse(active_sessions().filter(pk=session.pk).exists())
        self.assertEqual(document.lines.count(), 1)
        self.assertEqual(Balance.objects.get(warehouse=self.a).quantity, 3)
        with self.assertRaises(ValidationError):
            post_document(document.pk, self.ceo)
        self.receipt(quantity=1)

    def test_posted_deletion_preserves_ledger_and_does_not_unlock_a_new_count(self):
        session, document = self.pending()
        post_document(document.pk, self.ceo)
        new = freeze_session(self.a, self.maker)
        before = list(Movement.objects.values_list("pk", "delta", "balance_after"))
        delete_session(session.pk, self.admin, **self.delete_payload(session))
        document.refresh_from_db()
        self.assertEqual(document.status, "POSTED")
        self.assertEqual(Balance.objects.get(warehouse=self.a).quantity, 2)
        self.assertEqual(
            list(Movement.objects.values_list("pk", "delta", "balance_after")), before
        )
        self.assertTrue(active_sessions().filter(pk=new.pk).exists())
        with self.assertRaises(ValidationError):
            self.receipt(quantity=1)

    def test_only_admin_can_delete_even_staff_with_all_function_grants(self):
        session, _ = self.pending()
        self.other.is_staff = True
        self.other.save(update_fields=["is_staff"])
        grant_functions(self.other, FUNCTION_KEYS, level=30)
        self.client.force_login(self.other)
        payload = self.delete_payload(session)
        self.assertEqual(
            self.client.post(
                reverse("stocktake_delete", args=[session.pk]), payload
            ).status_code,
            403,
        )
        with self.assertRaises(PermissionDenied):
            delete_session(session.pk, self.other, **payload)
        self.assertFalse(StocktakeDeletion.objects.exists())

    def test_deleted_history_visible_only_to_admin_and_cannot_be_deleted_twice(self):
        session, _ = self.pending()
        payload = self.delete_payload(session)
        delete_session(session.pk, self.admin, **payload)
        self.client.force_login(self.maker)
        self.assertEqual(
            self.client.get(reverse("stocktake_detail", args=[session.pk])).status_code,
            404,
        )
        self.assertEqual(
            self.client.get(reverse("stocktake_report", args=[session.pk])).status_code,
            404,
        )
        self.assertEqual(
            self.client.get(reverse("stocktakes"), {"deleted": "1"}).status_code, 403
        )
        self.client.force_login(self.admin)
        self.assertNotIn(
            session, list(self.client.get(reverse("stocktakes")).context["sessions"])
        )
        self.assertIn(
            session,
            list(
                self.client.get(reverse("stocktakes"), {"deleted": "1"}).context[
                    "sessions"
                ]
            ),
        )
        self.assertContains(
            self.client.get(reverse("stocktake_detail", args=[session.pk])),
            "Phiếu tạo nhầm",
        )
        with self.assertRaises(ValidationError):
            delete_session(session.pk, self.admin, **payload)
        self.assertEqual(StocktakeDeletion.objects.count(), 1)

    def test_delete_rejects_missing_reason_confirmation_and_changed_approval(self):
        session, document = self.pending()
        original = self.delete_payload(session)
        for changes in [{"reason": ""}, {"confirmation": "wrong"}]:
            payload = {**original, **changes}
            with self.assertRaises(ValidationError):
                delete_session(session.pk, self.admin, **payload)
        post_document(document.pk, self.ceo)
        with self.assertRaises(ValidationError):
            delete_session(session.pk, self.admin, **original)
        self.assertFalse(StocktakeDeletion.objects.exists())

    def test_pending_count_allows_trades_but_not_a_second_count_or_adjustment(self):
        from .models import Document, Line

        session, _ = self.pending()
        self.assertFalse(session.locks_inventory)
        self.receipt(quantity=4)
        with self.assertRaises(ValidationError):
            freeze_session(self.a, self.maker)
        for kind in ("COUNT", "ADJUST"):
            other = Document.objects.create(
                kind=kind, destination=self.a, created_by=self.maker, note="Kiểm khác"
            )
            Line.objects.create(
                document=other, product=self.p, quantity=1, unit_price=100
            )
            with self.assertRaisesMessage(ValidationError, "chờ quyết định"):
                post_document(other.pk, self.admin)
        self.assertEqual(Balance.objects.get(warehouse=self.a).quantity, 7)

    def test_approval_applies_delta_to_current_balance_without_overwriting_new_trades(
        self,
    ):
        from .models import Document, Line

        session, document = self.pending()  # book 3, counted 2 => -1
        self.receipt(quantity=5)
        out = Document.objects.create(kind="OUT", source=self.a, created_by=self.maker)
        Line.objects.create(document=out, product=self.p, quantity=2)
        post_document(out.pk, self.admin)
        post_document(document.pk, self.ceo)
        self.assertEqual(Balance.objects.get(warehouse=self.a).quantity, 5)
        self.assertEqual(Balance.objects.get(warehouse=self.a).value, 500)
        item = session.items.get()
        self.assertEqual(
            (item.book_quantity, item.counted_quantity, item.difference), (3, 2, -1)
        )
        self.assertEqual(Movement.objects.get(document=document).delta, -1)
        with self.assertRaises(ValidationError):
            post_document(document.pk, self.ceo)

    def test_negative_adjustment_cannot_make_current_stock_negative(self):
        from .models import Document, Line

        _, document = self.pending()
        out = Document.objects.create(kind="OUT", source=self.a, created_by=self.maker)
        Line.objects.create(document=out, product=self.p, quantity=3)
        post_document(out.pk, self.admin)
        before = Movement.objects.count()
        with self.assertRaises(ValidationError):
            post_document(document.pk, self.ceo)
        document.refresh_from_db()
        self.assertEqual(document.status, "DRAFT")
        self.assertEqual(Balance.objects.get(warehouse=self.a).quantity, 0)
        self.assertEqual(Movement.objects.count(), before)

    def test_positive_discrepancy_keeps_receipts_and_rejection_does_not_reverse_them(
        self,
    ):
        from .stocktakes import reject_session

        self.receipt()
        session = begin_session(
            freeze_session(self.a, self.maker).pk, self.maker, "PAPER"
        )
        self.count(session, 5)
        document = submit_session(session.pk, self.maker, "Thừa hai")
        self.receipt(quantity=4)
        post_document(document.pk, self.ceo)
        self.assertEqual(Balance.objects.get(warehouse=self.a).quantity, 9)
        later = begin_session(freeze_session(self.a, self.maker).pk, self.maker, "QR")
        self.count(later, 8)
        rejected = submit_session(later.pk, self.maker, "Thiếu một")
        self.receipt(quantity=2)
        reject_session(
            later.pk,
            self.ceo,
            "Không chấp thuận điều chỉnh",
            expected_revision=rejected.revision,
        )
        self.assertEqual(Balance.objects.get(warehouse=self.a).quantity, 11)
        self.assertTrue(freeze_session(self.a, self.maker).locks_inventory)

    def test_sealed_adjustment_tampering_is_rejected(self):
        _, document = self.pending()
        document.lines.update(quantity=-2)
        with self.assertRaisesMessage(ValidationError, "không khớp"):
            post_document(document.pk, self.ceo)
        self.assertEqual(Balance.objects.get(warehouse=self.a).quantity, 3)

    def test_finalized_count_can_be_approved_later_without_backdating_ledger(self):
        from datetime import timedelta

        from django.utils import timezone

        session, document = self.pending()
        yesterday = timezone.localdate() - timedelta(days=1)
        type(session).objects.filter(pk=session.pk).update(business_date=yesterday)
        type(document).objects.filter(pk=document.pk).update(business_date=yesterday)
        self.receipt(quantity=2)
        post_document(document.pk, self.ceo)
        document.refresh_from_db()
        self.assertEqual(document.business_date, timezone.localdate())
        self.assertEqual(document.events.last().snapshot["count_date"], str(yesterday))
        self.assertEqual(Balance.objects.get(warehouse=self.a).quantity, 4)

    def test_positive_adjustment_uses_frozen_cost_when_stock_was_fully_issued(self):
        from .models import Document, Line

        self.receipt()
        session = begin_session(freeze_session(self.a, self.maker).pk, self.maker, "QR")
        self.count(session, 5)
        adjustment = submit_session(session.pk, self.maker, "Thừa hai")
        out = Document.objects.create(kind="OUT", source=self.a, created_by=self.maker)
        Line.objects.create(document=out, product=self.p, quantity=3)
        post_document(out.pk, self.admin)
        post_document(adjustment.pk, self.ceo)
        balance = Balance.objects.get(warehouse=self.a)
        self.assertEqual((balance.quantity, balance.value), (2, 200))
