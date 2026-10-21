from concurrent.futures import ThreadPoolExecutor
from decimal import Decimal
from unittest import skipUnless

from django.contrib.auth import get_user_model
from django.contrib.auth.models import Permission
from django.core.exceptions import PermissionDenied, ValidationError
from django.db import close_old_connections, connection, connections
from django.test import TestCase, TransactionTestCase

from .forms import ProductForm
from .models import (
    Balance,
    CustomField,
    Document,
    Line,
    LoanHolding,
    Movement,
    Product,
    Warehouse,
)
from .services import capture_lines, post_document
from .test_support import grant_functions


class InventoryTests(TestCase):
    def setUp(self):
        self.admin = get_user_model().objects.create_superuser(
            "owner", "owner@example.test", "test-password-not-production"
        )
        self.admin.user_permissions.add(
            Permission.objects.get(
                content_type__app_label="inventory",
                codename="approve_inventory_adjustment",
            )
        )
        self.maker = get_user_model().objects.create_user("maker")
        self.staff = get_user_model().objects.create_user(
            "worker", password="test-password-not-production"
        )
        grant_functions(
            self.staff,
            {"stock_view", "receipts_view", "documents_view", "products_view"},
        )
        self.a = Warehouse.objects.create(code="A", name="Kho A")
        self.b = Warehouse.objects.create(code="B", name="Kho B")
        self.a.members.add(self.staff)
        self.p = Product.objects.create(sku="P1", name="Hàng 1")

    def doc(
        self,
        kind,
        qty,
        source=None,
        destination=None,
        loan=None,
        post=True,
        note="Kiểm thử nghiệp vụ",
    ):
        d = Document.objects.create(
            kind=kind,
            source=source,
            destination=destination,
            loan=loan,
            note=note,
            created_by=self.maker,
        )
        Line.objects.bulk_create(
            capture_lines(
                d, [Line(document=d, product=self.p, quantity=qty, unit_price=100)]
            )
        )
        if post:
            result = post_document(d.pk, self.admin)
            if result.status == "TRANSIT":
                post_document(d.pk, self.admin)
        return d

    def qty(self, w):
        return Balance.objects.get(warehouse=w, product=self.p).quantity

    def test_receipt_issue_and_card(self):
        self.doc("IN", 10, destination=self.a)
        self.doc("OUT", 3, source=self.a)
        self.assertEqual(self.qty(self.a), 7)
        m = Movement.objects.first()
        self.assertEqual(m.delta, -3)
        self.assertEqual(m.balance_after, 7)

    def test_draft_does_not_affect_stock(self):
        self.doc("IN", 10, destination=self.a, post=False)
        self.assertFalse(Balance.objects.exists())

    def test_no_negative_stock_atomic(self):
        self.doc("IN", 5, destination=self.a)
        with self.assertRaises(ValidationError):
            self.doc("TRANSFER", 6, source=self.a, destination=self.b)
        self.assertEqual(self.qty(self.a), 5)
        self.assertFalse(Balance.objects.filter(warehouse=self.b).exists())
        self.assertEqual(Movement.objects.count(), 1)

    def test_transfer_preserves_total(self):
        self.doc("IN", 10, destination=self.a)
        self.doc("TRANSFER", 4, source=self.a, destination=self.b)
        self.assertEqual(self.qty(self.a), 6)
        self.assertEqual(self.qty(self.b), 4)

    def test_partial_returns_and_overreturn(self):
        self.doc("IN", 10, destination=self.a)
        loan = self.doc("LOAN", 6, source=self.a, destination=self.b)
        self.doc("RETURN", 2, source=self.b, destination=self.a, loan=loan)
        with self.assertRaises(ValidationError):
            self.doc("RETURN", 5, source=self.b, destination=self.a, loan=loan)
        self.doc("RETURN", 4, source=self.b, destination=self.a, loan=loan)
        self.assertEqual(self.qty(self.a), 10)
        self.assertFalse(Balance.objects.filter(warehouse=self.b).exists())
        self.assertEqual(LoanHolding.objects.get().quantity, 0)

    def test_borrowed_stock_cannot_be_issued_or_transferred(self):
        self.doc("IN", 10, destination=self.a)
        self.doc("LOAN", 6, source=self.a, destination=self.b)
        self.assertEqual(LoanHolding.objects.get().quantity, 6)
        self.assertFalse(Balance.objects.filter(warehouse=self.b).exists())
        with self.assertRaises(ValidationError):
            self.doc("OUT", 1, source=self.b)
        with self.assertRaises(ValidationError):
            self.doc("TRANSFER", 1, source=self.b, destination=self.a)
        self.assertEqual(LoanHolding.objects.get().quantity, 6)

    def test_loan_return_preserves_original_value(self):
        self.doc("IN", 10, destination=self.a)
        loan = self.doc("LOAN", 6, source=self.a, destination=self.b)
        d = self.doc("IN", 5, destination=self.b, post=False)
        d.lines.update(unit_price=999)
        post_document(d.pk, self.admin)
        self.doc("RETURN", 2, source=self.b, destination=self.a, loan=loan)
        self.assertEqual(Balance.objects.get(warehouse=self.b).value, 4995)
        self.assertEqual(Balance.objects.get(warehouse=self.a).value, 600)
        self.assertEqual(LoanHolding.objects.get().value, 400)

    def test_loan_cannot_overdraw(self):
        self.doc("IN", 3, destination=self.a)
        with self.assertRaises(ValidationError):
            self.doc("LOAN", 4, source=self.a, destination=self.b)
        self.assertEqual(self.qty(self.a), 3)
        self.assertFalse(LoanHolding.objects.exists())

    def test_return_in_transit_cannot_be_reserved_twice(self):
        self.doc("IN", 10, destination=self.a)
        loan = self.doc("LOAN", 6, source=self.a, destination=self.b)
        d = self.doc(
            "RETURN", 4, source=self.b, destination=self.a, loan=loan, post=False
        )
        post_document(d.pk, self.admin)
        self.assertEqual(self.qty(self.a), 4)
        with self.assertRaises(ValidationError):
            self.doc("RETURN", 3, source=self.b, destination=self.a, loan=loan)
        post_document(d.pk, self.admin)
        self.assertEqual(self.qty(self.a), 8)

    def test_wrong_loan_direction(self):
        self.doc("IN", 10, destination=self.a)
        loan = self.doc("LOAN", 6, source=self.a, destination=self.b)
        with self.assertRaises(ValidationError):
            self.doc("RETURN", 1, source=self.a, destination=self.b, loan=loan)

    def test_count_uses_absolute_quantity(self):
        self.doc("IN", 10, destination=self.a)
        self.doc("COUNT", 7, destination=self.a)
        self.assertEqual(self.qty(self.a), 7)
        self.assertEqual(Movement.objects.first().delta, -3)
        self.doc("COUNT", 0, destination=self.a)
        self.assertEqual(self.qty(self.a), 0)

    def test_adjustment_delta_and_reason(self):
        self.doc("IN", 10, destination=self.a)
        self.doc("ADJUST", -2, destination=self.a)
        self.assertEqual(self.qty(self.a), 8)
        with self.assertRaises(ValidationError):
            self.doc("ADJUST", 1, destination=self.a, note="")

    def test_double_post_rejected(self):
        doc = self.doc("IN", 10, destination=self.a)
        with self.assertRaises(ValidationError):
            post_document(doc.pk, self.admin)
        self.assertEqual(self.qty(self.a), 10)

    def test_posting_permission(self):
        doc = self.doc("IN", 10, destination=self.a, post=False)
        with self.assertRaises(PermissionDenied):
            post_document(doc.pk, self.staff)

    def test_warehouse_scope_even_with_post_permission(self):
        self.staff.user_permissions.add(
            Permission.objects.get(codename="post_document")
        )
        doc = self.doc("IN", 10, destination=self.b, post=False)
        with self.assertRaises(PermissionDenied):
            post_document(doc.pk, self.staff)
        self.client.force_login(self.staff)
        self.assertEqual(self.client.get(f"/documents/{doc.pk}/").status_code, 404)
        self.doc("IN", 8, destination=self.b)
        self.assertNotContains(self.client.get("/stock/"), "Kho B")

    def test_auth_and_csrf(self):
        self.assertEqual(self.client.get("/").status_code, 302)
        from django.test import Client

        client = Client(enforce_csrf_checks=True)
        client.force_login(self.admin)
        doc = self.doc("IN", 10, destination=self.a, post=False)
        self.assertEqual(client.post(f"/documents/{doc.pk}/post/").status_code, 403)

    def test_pages_render_and_exports(self):
        self.doc("IN", 10, destination=self.a)
        self.client.force_login(self.admin)
        for path in [
            "/",
            "/documents/",
            "/documents/new/",
            "/stock/",
            "/ledger/",
            "/loans/",
            "/products/",
            "/products/new/",
        ]:
            with self.subTest(path=path):
                self.assertEqual(self.client.get(path).status_code, 200)
        response = self.client.get("/stock/?export=1")
        self.assertContains(response, "P1")
        self.assertEqual(response["Content-Type"], "text/csv; charset=utf-8-sig")

    def test_document_form_creates_draft(self):
        self.client.force_login(self.admin)
        response = self.client.post(
            "/documents/new/",
            {
                "kind": "IN",
                "destination": self.a.pk,
                "source": "",
                "loan": "",
                "note": "Nhập hàng",
                "form-TOTAL_FORMS": "1",
                "form-INITIAL_FORMS": "0",
                "form-MIN_NUM_FORMS": "1",
                "form-MAX_NUM_FORMS": "50",
                "form-0-product": self.p.pk,
                "form-0-quantity": "12.500",
                "form-0-unit_price": "100",
            },
        )
        self.assertEqual(response.status_code, 302)
        d = Document.objects.get()
        self.assertEqual(d.status, "DRAFT")
        self.assertEqual(d.lines.get().quantity, Decimal("12.5"))
        self.assertFalse(Balance.objects.exists())

    def test_custom_product_fields(self):
        CustomField.objects.create(key="brand", label="Thương hiệu")
        form = ProductForm(
            {
                "sku": "P2",
                "name": "Hàng 2",
                "unit": "Hộp",
                "minimum": 0,
                "extra_brand": "Nhãn A",
            }
        )
        self.assertTrue(form.is_valid(), form.errors)
        self.assertEqual(form.save().extra, {"brand": "Nhãn A"})

    def test_maker_cannot_approve_own_document(self):
        d = self.doc("IN", 1, destination=self.a, post=False)
        self.a.managers.add(self.maker)
        self.a.members.add(self.maker)
        with self.assertRaises(PermissionDenied):
            post_document(d.pk, self.maker)

    def test_transit_separate_source_and_destination_approval(self):
        grant_functions(self.staff, {"transfers_approve"})
        self.doc("IN", 10, destination=self.a)
        d = self.doc("TRANSFER", 4, source=self.a, destination=self.b, post=False)
        self.a.issue_approvers.add(self.staff)
        result = post_document(d.pk, self.staff)
        self.assertEqual(result.status, "TRANSIT")
        self.assertEqual(self.qty(self.a), 6)
        self.assertFalse(Balance.objects.filter(warehouse=self.b).exists())
        with self.assertRaises(PermissionDenied):
            post_document(d.pk, self.staff)
        receiver = get_user_model().objects.create_user("receiver")
        grant_functions(
            receiver,
            {
                "loans_receive",
                "transfers_receive",
                "returns_receive",
                "receipts_approve",
            },
        )
        self.b.managers.add(receiver)
        post_document(d.pk, receiver)
        self.assertEqual(self.qty(self.b), 4)
        self.assertEqual(Balance.objects.get(warehouse=self.b).value, 400)

    def test_only_destination_manager_can_receive(self):
        grant_functions(self.staff, {"receipts_approve"})
        d = self.doc("IN", 1, destination=self.a, post=False)
        self.b.managers.add(self.staff)
        with self.assertRaises(PermissionDenied):
            post_document(d.pk, self.staff)
        self.a.managers.add(self.staff)
        post_document(d.pk, self.staff)
        self.assertEqual(self.qty(self.a), 1)

    def test_issue_requires_admin_designation(self):
        grant_functions(self.staff, {"issues_approve"})
        self.doc("IN", 10, destination=self.a)
        d = self.doc("OUT", 2, source=self.a, post=False)
        self.a.managers.add(self.staff)
        with self.assertRaises(PermissionDenied):
            post_document(d.pk, self.staff)
        self.a.issue_approvers.add(self.staff)
        post_document(d.pk, self.staff)
        self.assertEqual(self.qty(self.a), 8)

    def test_weighted_average_value_and_transfers(self):
        self.doc("IN", 10, destination=self.a)
        d = self.doc("IN", 10, destination=self.a, post=False)
        d.lines.update(unit_price=200)
        post_document(d.pk, self.admin)
        self.assertEqual(Balance.objects.get(warehouse=self.a).value, 3000)
        self.doc("TRANSFER", 4, source=self.a, destination=self.b)
        self.assertEqual(Balance.objects.get(warehouse=self.a).value, 2400)
        self.assertEqual(Balance.objects.get(warehouse=self.b).value, 600)
        self.doc("OUT", 2, source=self.b)
        self.assertEqual(Balance.objects.get(warehouse=self.b).value, 300)

    def test_receipt_requires_explicit_price(self):
        d = self.doc("IN", 10, destination=self.a, post=False)
        d.lines.update(unit_price=None)
        with self.assertRaises(ValidationError):
            post_document(d.pk, self.admin)

    def test_count_value_follows_difference(self):
        self.doc("IN", 10, destination=self.a)
        self.doc("COUNT", 7, destination=self.a)
        self.assertEqual(Balance.objects.get(warehouse=self.a).value, 700)

    def test_csv_formula_escaped(self):
        self.p.name = "=SUM(A1)"
        self.p.save()
        self.doc("IN", 10, destination=self.a)
        self.client.force_login(self.admin)
        self.assertContains(self.client.get("/stock/?export=1"), "'=SUM(A1)")

    def test_invalid_quantity_and_same_warehouse(self):
        for q in [0, -1]:
            with self.assertRaises(ValidationError):
                self.doc("IN", q, destination=self.a)
        with self.assertRaises(ValidationError):
            self.doc("TRANSFER", 1, source=self.a, destination=self.a)

    def test_permissions_cannot_be_bypassed_by_post(self):
        self.client.force_login(self.staff)
        self.assertEqual(self.client.get("/documents/new/").status_code, 403)
        self.assertEqual(
            self.client.post(
                "/products/new/", {"sku": "X", "name": "X", "unit": "Cái", "minimum": 0}
            ).status_code,
            403,
        )


@skipUnless(connection.vendor == "postgresql", "Row locking requires PostgreSQL")
class ConcurrencyTests(TransactionTestCase):
    def test_competing_issues_cannot_overdraw(self):
        admin = get_user_model().objects.create_superuser(
            "owner", "owner@example.test", "test-only"
        )
        maker = get_user_model().objects.create_user("maker")
        w = Warehouse.objects.create(code="A", name="A")
        p = Product.objects.create(sku="P", name="P")
        Balance.objects.create(warehouse=w, product=p, quantity=10)
        docs = []
        for _ in range(2):
            d = Document.objects.create(kind="OUT", source=w, created_by=maker)
            Line.objects.create(document=d, product=p, quantity=7)
            docs.append(d.pk)

        def run(pk):
            close_old_connections()
            try:
                post_document(pk, get_user_model().objects.get(pk=admin.pk))
                return True
            except ValidationError:
                return False
            finally:
                connections.close_all()

        with ThreadPoolExecutor(max_workers=2) as pool:
            results = list(pool.map(run, docs))
        self.assertEqual(sorted(results), [False, True])
        self.assertEqual(Balance.objects.get(warehouse=w, product=p).quantity, 3)


class ExcelImportTests(TestCase):
    setUp = InventoryTests.setUp
    qty = InventoryTests.qty

    # Isolated tests use the same warehouse / identity fixtures without duplicating the inventory suite.
    def workbook(self, rows):
        from io import BytesIO

        from django.core.files.uploadedfile import SimpleUploadedFile
        from openpyxl import Workbook

        b = Workbook()
        s = b.active
        for row in rows:
            s.append(row)
        out = BytesIO()
        b.save(out)
        return SimpleUploadedFile(
            "nhap.xlsx",
            out.getvalue(),
            content_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        )

    def test_excel_preview_confirm_and_manager_post(self):
        self.staff.user_permissions.add(Permission.objects.get(codename="add_document"))
        grant_functions(self.staff, {"tools_import", "documents_view"})
        self.client.force_login(self.staff)
        response = self.client.post(
            "/import/receipt/",
            {
                "warehouse": self.a.pk,
                "file": self.workbook(
                    [["ma_hang", "so_luong", "don_gia"], ["P1", 5, 12500]]
                ),
                "note": "Mua vật tư",
            },
        )
        self.assertContains(response, "Xác nhận tạo phiếu nháp")
        self.assertFalse(Document.objects.exists())
        self.assertFalse(Balance.objects.exists())
        key = self.client.session["receipt_import"]["key"]
        response = self.client.post(
            "/import/receipt/", {"confirm": "1", "import_key": key}
        )
        self.assertEqual(response.status_code, 302)
        doc = Document.objects.get()
        self.assertEqual(doc.created_by, self.staff)
        self.assertEqual(doc.status, "DRAFT")
        self.assertFalse(Balance.objects.exists())
        self.client.post("/import/receipt/", {"confirm": "1", "import_key": key})
        self.assertEqual(Document.objects.count(), 1)
        self.a.managers.add(self.maker)
        grant_functions(self.maker, {"receipts_approve"})
        post_document(doc.pk, self.maker)
        self.assertEqual(self.qty(self.a), 5)
        self.assertEqual(Balance.objects.get(warehouse=self.a).value, 62500)

    def test_excel_bad_rows_atomic(self):
        self.client.force_login(self.admin)
        for bad in [
            ["UNKNOWN", 1, 100],
            ["P1", -1, 100],
            ["P1", 1, None],
            ["P1", "=2+2", 100],
            ["P1", 1, -100],
        ]:
            with self.subTest(bad=bad):
                response = self.client.post(
                    "/import/receipt/",
                    {
                        "warehouse": self.a.pk,
                        "file": self.workbook(
                            [["ma_hang", "so_luong", "don_gia"], bad]
                        ),
                    },
                )
                self.assertEqual(response.status_code, 200)
                self.assertNotContains(response, 'name="confirm"')
                self.assertFalse(Document.objects.exists())

    def test_excel_duplicate_sku_rejected(self):
        from .excel import parse_receipt

        with self.assertRaises(ValidationError):
            parse_receipt(
                self.workbook(
                    [["ma_hang", "so_luong", "don_gia"], ["P1", 1, 100], ["P1", 2, 100]]
                )
            )

    def test_excel_template_and_permissions(self):
        self.client.force_login(self.admin)
        r = self.client.get("/import/receipt/template/")
        self.assertEqual(r.status_code, 200)
        self.assertTrue(r.content.startswith(b"PK"))
        self.client.force_login(self.staff)
        self.assertEqual(self.client.get("/import/receipt/").status_code, 403)

    def test_excel_wrong_warehouse_denied(self):
        self.staff.user_permissions.add(Permission.objects.get(codename="add_document"))
        grant_functions(self.staff, {"tools_import", "documents_view"})
        self.client.force_login(self.staff)
        response = self.client.post(
            "/import/receipt/",
            {
                "warehouse": self.b.pk,
                "file": self.workbook(
                    [["ma_hang", "so_luong", "don_gia"], ["P1", 1, 100]]
                ),
            },
        )
        self.assertEqual(response.status_code, 200)
        self.assertNotIn("receipt_import", self.client.session)


class BootstrapAdminTests(TestCase):
    def test_initial_admin_created_once_without_password_reset(self):
        from io import StringIO
        from unittest.mock import patch

        from django.core.management import call_command

        with patch.dict(
            "os.environ",
            {
                "INITIAL_ADMIN_USERNAME": "firstadmin",
                "INITIAL_ADMIN_PASSWORD": "Strong-unique-test-password-2026!",
            },
        ):
            out = StringIO()
            call_command("bootstrap_admin", stdout=out)
            user = get_user_model().objects.get(username="firstadmin")
            self.assertTrue(user.is_superuser)
            self.assertNotIn("Strong-unique-test-password-2026!", out.getvalue())
        with patch.dict(
            "os.environ",
            {
                "INITIAL_ADMIN_USERNAME": "firstadmin",
                "INITIAL_ADMIN_PASSWORD": "Another-strong-test-password-2026!",
            },
        ):
            call_command("bootstrap_admin", stdout=StringIO())
            user.refresh_from_db()
            self.assertTrue(user.check_password("Strong-unique-test-password-2026!"))

    def test_existing_user_not_promoted(self):
        from unittest.mock import patch

        from django.core.management import CommandError, call_command

        get_user_model().objects.create_user("worker")
        with patch.dict(
            "os.environ",
            {
                "INITIAL_ADMIN_USERNAME": "worker",
                "INITIAL_ADMIN_PASSWORD": "Strong-unique-test-password-2026!",
            },
        ):
            with self.assertRaises(CommandError):
                call_command("bootstrap_admin")
        self.assertFalse(get_user_model().objects.get(username="worker").is_superuser)
