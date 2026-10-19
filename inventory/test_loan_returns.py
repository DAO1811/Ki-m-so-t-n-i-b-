from concurrent.futures import ThreadPoolExecutor
from threading import Barrier
from unittest import skipUnless
from uuid import uuid4

from django.contrib.auth import get_user_model
from django.core.exceptions import PermissionDenied, ValidationError
from django.db import connection, connections
from django.test import TestCase, TransactionTestCase

from .loan_returns import return_items, save_return
from .models import Balance, Document, Line, LoanHolding, Product, Warehouse
from .services import close_document, post_document
from .test_support import MANAGER, OPERATOR, grant_functions


class LoanReturnTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        User = get_user_model()
        cls.maker = User.objects.create_user("return-maker", password="1")
        cls.manager = User.objects.create_user("return-manager", password="1")
        cls.outside = User.objects.create_user("return-outside", password="1")
        grant_functions(cls.maker, OPERATOR)
        grant_functions(cls.manager, MANAGER)
        grant_functions(cls.outside, OPERATOR)
        cls.a = Warehouse.objects.create(code="RET-A", name="Kho cho mượn")
        cls.b = Warehouse.objects.create(code="RET-B", name="Kho đang mượn")
        for wh in [cls.a, cls.b]:
            wh.members.add(cls.maker)
            wh.managers.add(cls.manager)
            wh.issue_approvers.add(cls.manager)
        cls.p = Product.objects.create(sku="RET-P", name="Hàng P", unit="Cái")
        cls.q = Product.objects.create(sku="RET-Q", name="Hàng Q", unit="Hộp")
        cls.loan = Document.objects.create(
            kind="LOAN",
            source=cls.a,
            destination=cls.b,
            created_by=cls.maker,
            status="POSTED",
        )
        for product, quantity in [(cls.p, 5), (cls.q, 3)]:
            line = Line.objects.create(
                document=cls.loan,
                product=product,
                quantity=quantity,
                book_value=quantity * 100,
            )
            LoanHolding.objects.create(
                loan_line=line, quantity=quantity, value=quantity * 100
            )

    def save(self, quantities, **extra):
        return save_return(
            self.loan.pk,
            self.maker,
            quantities,
            submission_key=extra.pop("submission_key", uuid4()),
            **extra,
        )

    def test_partial_return_reserves_draft_then_transit_then_credit_only_after_receive(
        self,
    ):
        draft = self.save({self.p.pk: 2, self.q.pk: 0})
        self.assertEqual(draft.lines.count(), 1)
        self.assertEqual(return_items(self.loan)[0]["available"], 3)
        self.assertEqual(return_items(self.loan)[0]["pending_draft"], 2)
        self.assertFalse(Balance.objects.exists())
        post_document(
            draft.pk, self.manager, expected_status="DRAFT", expected_revision=1
        )
        item = return_items(self.loan)[0]
        self.assertEqual(item["in_transit"], 2)
        self.assertEqual(item["available"], 3)
        self.assertEqual(item["pending_draft"], 0)
        self.assertFalse(Balance.objects.exists())
        post_document(
            draft.pk, self.manager, expected_status="TRANSIT", expected_revision=1
        )
        item = return_items(self.loan)[0]
        self.assertEqual(item["returned"], 2)
        self.assertEqual(item["outstanding"], 3)
        self.assertEqual(
            Balance.objects.get(warehouse=self.a, product=self.p).quantity, 2
        )
        holding = LoanHolding.objects.get(
            loan_line__document=self.loan, loan_line__product=self.p
        )
        self.assertEqual(holding.quantity, 3)
        self.assertEqual(holding.value + draft.lines.get().book_value, 500)

    def test_duplicate_and_excess_pending_returns_are_blocked_at_creation(self):
        self.save({self.p.pk: 4})
        with self.assertRaises(ValidationError):
            self.save({self.p.pk: 2})
        self.assertEqual(Document.objects.filter(kind="RETURN").count(), 1)
        with self.assertRaises(ValidationError):
            self.save({999999: 1})
        with self.assertRaises(ValidationError):
            self.save({self.p.pk: 0})
        with self.assertRaises(ValidationError):
            self.save({self.p.pk: "NaN"})

    def test_cancel_releases_draft_and_rejected_edit_rechecks_current_reservations(
        self,
    ):
        draft = self.save({self.p.pk: 4})
        close_document(draft.pk, self.manager, "REJECT", "Kiểm tra lại lượng thực trả")
        other = self.save({self.p.pk: 3})
        with self.assertRaises(ValidationError):
            self.save({self.p.pk: 4}, editing_id=draft.pk, revision=2)
        changed = self.save({self.p.pk: 2}, editing_id=draft.pk, revision=2)
        self.assertEqual(changed.revision, 3)
        self.assertEqual(return_items(self.loan)[0]["available"], 0)
        close_document(other.pk, self.maker, "CANCEL", "Không trả lần này")
        self.assertEqual(return_items(self.loan)[0]["available"], 3)

    def test_idempotent_service_and_http_replay_do_not_create_another_draft(self):
        key = uuid4()
        self.client.force_login(self.maker)
        payload = {"submission_key": str(key), f"quantity_{self.p.pk}": 5}
        first = self.client.post(f"/loans/{self.loan.pk}/return/", payload)
        second = self.client.post(f"/loans/{self.loan.pk}/return/", payload)
        self.assertEqual(first.status_code, 302)
        self.assertEqual(first.url, second.url)
        self.assertEqual(Document.objects.filter(kind="RETURN").count(), 1)
        doc = self.save({self.p.pk: 5}, submission_key=key)
        self.assertEqual(str(doc.import_key), str(key))

    def test_grouped_loan_one_action_and_pending_return_are_visible(self):
        self.client.force_login(self.maker)
        page = self.client.get("/loans/")
        groups = list(page.context["loan_groups"])
        self.assertEqual(len(groups), 1)
        self.assertEqual(len(groups[0]["items"]), 2)
        self.assertContains(page, f"/loans/{self.loan.pk}/return/", count=1)
        draft = self.save({self.p.pk: 1})
        page = self.client.get("/loans/?state=pending")
        self.assertContains(page, f"PK-{draft.pk:06d}")
        self.assertContains(page, "chờ duyệt")

    def test_simple_form_limits_products_and_hides_unrelated_fields(self):
        self.client.force_login(self.maker)
        page = self.client.get(f"/loans/{self.loan.pk}/return/")
        self.assertEqual(page.status_code, 200)
        self.assertContains(page, f'name="quantity_{self.p.pk}"')
        for name in [
            "source",
            "destination",
            "unit_price",
            "counterparty",
            "product",
            "business_date",
        ]:
            self.assertNotContains(page, f'name="{name}"')
        self.assertRedirects(
            self.client.get(f"/operations/return/?loan={self.loan.pk}"),
            f"/loans/{self.loan.pk}/return/",
        )

    def test_permissions_scope_stale_revision_and_tampering(self):
        self.client.force_login(self.outside)
        self.assertEqual(
            self.client.get(f"/loans/{self.loan.pk}/return/").status_code, 404
        )
        with self.assertRaises(PermissionDenied):
            save_return(self.loan.pk, self.outside, {self.p.pk: 1})
        draft = self.save({self.p.pk: 1})
        changed = self.save({self.p.pk: 2}, editing_id=draft.pk, revision=1)
        with self.assertRaises(ValidationError):
            self.save({self.p.pk: 3}, editing_id=draft.pk, revision=1)
        with self.assertRaises(PermissionDenied):
            save_return(
                self.loan.pk,
                self.manager,
                {self.p.pk: 3},
                editing_id=draft.pk,
                revision=changed.revision,
            )
        self.assertEqual(Document.objects.get(pk=draft.pk).lines.get().quantity, 2)

    def test_same_product_in_other_loan_does_not_share_reservations(self):
        other = Document.objects.create(
            kind="LOAN",
            source=self.a,
            destination=self.b,
            created_by=self.maker,
            status="POSTED",
        )
        line = Line.objects.create(
            document=other, product=self.p, quantity=2, book_value=200
        )
        LoanHolding.objects.create(loan_line=line, quantity=2, value=200)
        self.save({self.p.pk: 5})
        self.assertEqual(return_items(other)[0]["available"], 2)

    def test_returns_view_only_sees_pending_return_without_gaining_loan_details(self):
        draft = self.save({self.p.pk: 1})
        grant_functions(self.manager, {"returns_view", "returns_approve"}, level=30)
        self.client.force_login(self.manager)
        page = self.client.get("/loans/")
        self.assertEqual(page.status_code, 200)
        self.assertContains(page, f"PK-{draft.pk:06d}")
        self.assertEqual(len(page.context["loan_groups"]), 0)
        self.assertEqual(
            self.client.get(f"/documents/{self.loan.pk}/").status_code, 403
        )


@skipUnless(connection.vendor == "postgresql", "PostgreSQL loan reservations")
class LoanReturnConcurrencyTests(TransactionTestCase):
    def test_two_simultaneous_drafts_cannot_reserve_same_quantity(self):
        user = get_user_model().objects.create_user("return-race")
        grant_functions(user, OPERATOR)
        a = Warehouse.objects.create(code="RACE-RA", name="Lender")
        b = Warehouse.objects.create(code="RACE-RB", name="Borrower")
        b.members.add(user)
        product = Product.objects.create(sku="RET-RACE", name="Race item")
        loan = Document.objects.create(
            kind="LOAN", source=a, destination=b, created_by=user, status="POSTED"
        )
        line = Line.objects.create(
            document=loan, product=product, quantity=2, book_value=200
        )
        LoanHolding.objects.create(loan_line=line, quantity=2, value=200)
        barrier = Barrier(2)

        def create():
            connections.close_all()
            try:
                barrier.wait(timeout=5)
                save_return(loan.pk, user, {product.pk: 2}, submission_key=uuid4())
                return "saved"
            except ValidationError:
                return "blocked"
            finally:
                connections.close_all()

        with ThreadPoolExecutor(max_workers=2) as pool:
            results = list(pool.map(lambda _: create(), range(2)))
        self.assertCountEqual(results, ["saved", "blocked"])
        self.assertEqual(Document.objects.filter(kind="RETURN").count(), 1)
        self.assertEqual(LoanHolding.objects.get().quantity, 2)
