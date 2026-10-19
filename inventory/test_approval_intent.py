"""A repeated approval request must never become a receipt confirmation."""

from concurrent.futures import ThreadPoolExecutor
from threading import Barrier
from unittest import skipUnless

from django.contrib.auth import get_user_model
from django.core.exceptions import PermissionDenied, ValidationError
from django.db import close_old_connections, connection, connections
from django.test import Client, TestCase, TransactionTestCase

from .models import Balance, Document, Line, LoanHolding, Movement, Product, Warehouse
from .services import post_document
from .test_support import grant_functions


class ApprovalIntentFixtures:
    def setUp(self):
        User = get_user_model()
        self.admin = User.objects.create_superuser(
            "intent-admin", "intent@example.test", "test-only"
        )
        self.maker = User.objects.create_user("intent-maker")
        self.peer = User.objects.create_user("intent-peer")
        grant_functions(
            self.peer,
            {"loans_approve", "loans_receive", "returns_approve", "returns_receive"},
            level=10,
        )
        self.a = Warehouse.objects.create(code="INTENT-A", name="Kho cho mượn")
        self.b = Warehouse.objects.create(code="INTENT-B", name="Kho mượn")
        for warehouse in [self.a, self.b]:
            warehouse.issue_approvers.add(self.peer)
            warehouse.managers.add(self.peer)
        self.client.force_login(self.admin)

    def make_doc(self, kind):
        product = Product.objects.create(
            sku=f"INTENT-{Product.objects.count()}", name="Hàng kiểm tra xác nhận"
        )
        Balance.objects.create(
            warehouse=self.a, product=product, quantity=10, value=1000
        )
        loan = Document.objects.create(
            kind="LOAN", source=self.a, destination=self.b, created_by=self.maker
        )
        Line.objects.create(document=loan, product=product, quantity=6)
        if kind == "LOAN":
            return loan
        post_document(loan.pk, self.admin)
        post_document(loan.pk, self.admin)
        returned = Document.objects.create(
            kind="RETURN",
            source=self.b,
            destination=self.a,
            loan=loan,
            created_by=self.maker,
        )
        Line.objects.create(document=returned, product=product, quantity=4)
        return returned

    @staticmethod
    def payload(status="DRAFT", revision=1):
        return {"expected_status": status, "expected_revision": revision}


class ApprovalIntentTests(ApprovalIntentFixtures, TestCase):
    def test_approval_form_contains_the_reviewed_status_and_revision(self):
        doc = self.make_doc("LOAN")
        response = self.client.get(f"/documents/{doc.pk}/")
        self.assertContains(response, 'name="expected_status" value="DRAFT"')
        self.assertContains(response, 'name="expected_revision" value="1"')

    def test_repeated_dispatch_post_does_not_confirm_receipt(self):
        for kind in ["LOAN", "RETURN"]:
            with self.subTest(kind=kind):
                doc = self.make_doc(kind)
                url = f"/documents/{doc.pk}/post/"
                self.assertEqual(self.client.post(url, self.payload()).status_code, 302)
                self.assertEqual(self.client.post(url, self.payload()).status_code, 302)
                doc.refresh_from_db()
                self.assertEqual(doc.status, "TRANSIT")
                self.assertEqual(doc.events.filter(action="DISPATCH").count(), 1)
                self.assertFalse(doc.events.filter(action="POST").exists())
                if kind == "LOAN":
                    self.assertFalse(
                        LoanHolding.objects.filter(loan_line__document=doc).exists()
                    )
                else:
                    self.assertFalse(Movement.objects.filter(document=doc).exists())
                self.assertEqual(
                    self.client.post(url, self.payload("TRANSIT")).status_code, 302
                )
                doc.refresh_from_db()
                self.assertEqual(doc.status, "POSTED")
                self.assertEqual(doc.events.filter(action="POST").count(), 1)

    def test_stale_revision_blocks_approval_until_reviewed_again(self):
        doc = self.make_doc("LOAN")
        Document.objects.filter(pk=doc.pk).update(revision=2)
        doc.lines.update(quantity=3)
        with self.assertRaisesMessage(ValidationError, "Nội dung phiếu đã thay đổi"):
            post_document(
                doc.pk, self.admin, expected_status="DRAFT", expected_revision=1
            )
        self.assertEqual(
            self.client.post(f"/documents/{doc.pk}/post/", self.payload()).status_code,
            302,
        )
        doc.refresh_from_db()
        self.assertEqual(doc.status, "DRAFT")
        self.assertEqual(
            Balance.objects.get(product=doc.lines.get().product).quantity, 10
        )
        self.assertFalse(doc.events.exists())
        post_document(doc.pk, self.admin, expected_status="DRAFT", expected_revision=2)
        self.assertEqual(
            Balance.objects.get(product=doc.lines.get().product).quantity, 7
        )

    def test_http_rejects_missing_or_malformed_approval_intent(self):
        doc = self.make_doc("LOAN")
        for data in [
            {},
            {"expected_status": "DRAFT"},
            {"expected_revision": "1"},
            self.payload("POSTED"),
            self.payload(revision=""),
            self.payload(revision="0"),
            self.payload(revision="-1"),
            self.payload(revision="1.0"),
            self.payload(revision="١"),
            self.payload(revision="2147483648"),
            self.payload(revision="9" * 100),
        ]:
            with self.subTest(data=data):
                response = self.client.post(f"/documents/{doc.pk}/post/", data)
                self.assertEqual(response.status_code, 302)
                doc.refresh_from_db()
                self.assertEqual(doc.status, "DRAFT")
        self.assertFalse(doc.events.exists())
        self.assertEqual(Balance.objects.get().quantity, 10)

    def test_service_rejects_invalid_revision_types(self):
        doc = self.make_doc("LOAN")
        for revision in [True, "1", 0, -1]:
            with self.subTest(revision=revision), self.assertRaises(ValidationError):
                post_document(
                    doc.pk,
                    self.admin,
                    expected_status="DRAFT",
                    expected_revision=revision,
                )
        self.assertFalse(doc.events.exists())

    def test_peer_permission_is_denied_even_with_stale_or_missing_intent(self):
        doc = self.make_doc("LOAN")
        with self.assertRaises(PermissionDenied):
            post_document(
                doc.pk, self.peer, expected_status="TRANSIT", expected_revision=99
            )
        self.client.force_login(self.peer)
        for payload in [{}, self.payload("TRANSIT", 99), self.payload()]:
            self.assertEqual(
                self.client.post(f"/documents/{doc.pk}/post/", payload).status_code,
                403,
            )
        self.assertFalse(doc.events.exists())

    def test_fresh_intent_still_requires_admin_self_approval_confirmation(self):
        doc = self.make_doc("LOAN")
        doc.created_by = self.admin
        doc.creator_level = 40
        doc.save(update_fields=["created_by", "creator_level"])
        self.client.post(f"/documents/{doc.pk}/post/", self.payload())
        doc.refresh_from_db()
        self.assertEqual(doc.status, "DRAFT")
        self.client.post(
            f"/documents/{doc.pk}/post/",
            {**self.payload(), "confirm_self_approval": "yes"},
        )
        doc.refresh_from_db()
        self.assertEqual(doc.status, "TRANSIT")
        self.assertTrue(
            doc.events.get(action="DISPATCH").snapshot["admin_self_approved"]
        )


@skipUnless(connection.vendor == "postgresql", "Requires PostgreSQL row locks")
class ApprovalIntentConcurrencyTests(ApprovalIntentFixtures, TransactionTestCase):
    def test_concurrent_identical_dispatch_posts_cannot_confirm_receipt(self):
        for kind in ["LOAN", "RETURN"]:
            with self.subTest(kind=kind):
                doc = self.make_doc(kind)
                ready = Barrier(2)

                def approve(pk=doc.pk, barrier=ready):
                    close_old_connections()
                    try:
                        client = Client()
                        client.force_login(
                            get_user_model().objects.get(pk=self.admin.pk)
                        )
                        barrier.wait(timeout=10)
                        return client.post(
                            f"/documents/{pk}/post/", self.payload()
                        ).status_code
                    finally:
                        connections.close_all()

                with ThreadPoolExecutor(max_workers=2) as pool:
                    results = list(pool.map(lambda _: approve(), range(2)))
                self.assertEqual(results, [302, 302])
                doc.refresh_from_db()
                self.assertEqual(doc.status, "TRANSIT")
                self.assertEqual(doc.events.filter(action="DISPATCH").count(), 1)
                self.assertFalse(doc.events.filter(action="POST").exists())
                if kind == "LOAN":
                    self.assertFalse(
                        LoanHolding.objects.filter(loan_line__document=doc).exists()
                    )
                else:
                    self.assertFalse(Movement.objects.filter(document=doc).exists())
