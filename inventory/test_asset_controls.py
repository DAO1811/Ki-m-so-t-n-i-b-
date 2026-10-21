from datetime import timedelta
from io import BytesIO, StringIO
from unittest.mock import patch

from django.contrib.auth import get_user_model
from django.contrib.auth.models import Group, Permission
from django.core.exceptions import PermissionDenied, ValidationError
from django.core.files.uploadedfile import SimpleUploadedFile
from django.core.management import call_command
from django.test import TestCase
from django.utils import timezone
from openpyxl import Workbook

from .excel import DETAIL_HEADERS, HEADERS, parse_receipt
from .forms import DocumentForm, LineFormSet, ProductForm
from .models import Balance, Document, Line, Movement, Product, Warehouse
from .services import capture_lines, close_document, post_document
from .test_support import MANAGER, OPERATOR, grant_functions


class AssetControlTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        User = get_user_model()
        cls.maker = User.objects.create_user("maker", password="1")
        cls.manager = User.objects.create_user("manager", password="1")
        cls.admin = User.objects.create_superuser("admin", "admin@example.test", "1")
        cls.admin.user_permissions.add(
            Permission.objects.get(
                content_type__app_label="inventory",
                codename="approve_inventory_adjustment",
            )
        )
        call_command("setup_roles", stdout=StringIO())
        cls.maker.groups.add(Group.objects.get(name="Nhân viên kho"))
        grant_functions(cls.maker, OPERATOR)
        grant_functions(cls.manager, MANAGER)
        cls.a = Warehouse.objects.create(code="A", name="Kho A")
        cls.b = Warehouse.objects.create(code="B", name="Kho B")
        cls.a.members.add(cls.maker)
        cls.a.managers.add(cls.manager)
        cls.a.issue_approvers.add(cls.manager)
        cls.b.managers.add(cls.manager)
        cls.p = Product.objects.create(sku="P", name="Giấy", unit="Ram")

    def payload(self, **overrides):
        data = {
            "kind": "IN",
            "destination": self.a.pk,
            "business_date": str(timezone.localdate()),
            "revision": "1",
            "form-TOTAL_FORMS": "1",
            "form-INITIAL_FORMS": "0",
            "form-0-product": self.p.pk,
            "form-0-quantity": "7",
            "form-0-unit_price": "100",
            "note": "Mua cho công ty",
        }
        data.update(overrides)
        return data

    def doc(self, kind="IN", quantity=10, post=False, **fields):
        doc = Document.objects.create(
            kind=kind,
            destination=self.a if kind in ["IN", "COUNT", "ADJUST"] else self.b,
            source=self.a if kind in ["TRANSFER", "LOAN"] else None,
            created_by=self.maker,
            note="Kiểm soát",
            **fields,
        )
        Line.objects.bulk_create(
            capture_lines(
                doc,
                [Line(document=doc, product=self.p, quantity=quantity, unit_price=100)],
            )
        )
        if post:
            result = post_document(doc.pk, self.admin)
            if result.status == "TRANSIT":
                post_document(doc.pk, self.admin)
            doc.refresh_from_db()
        return doc

    def excel(self, row):
        book = Workbook()
        book.active.append(HEADERS + DETAIL_HEADERS)
        book.active.append(row)
        file = BytesIO()
        book.save(file)
        file.seek(0)
        return file

    def test_metadata_and_partial_receipt_only_accepted_enters_stock(self):
        self.client.force_login(self.maker)
        response = self.client.post(
            "/operations/in/",
            self.payload(
                reference_number="HD-123",
                reference_date=str(timezone.localdate()),
                counterparty="NCC A",
                department="Hành chính",
                received_by="Thủ kho",
                **{
                    "form-0-expected_quantity": "10",
                    "form-0-rejected_quantity": "2",
                    "form-0-note": "2 hỏng không nhận, giao thiếu 1",
                },
            ),
        )
        self.assertEqual(response.status_code, 302)
        doc = Document.objects.get()
        self.assertEqual(doc.reference_number, "HD-123")
        self.assertEqual(doc.events.get().action, "CREATE")
        line = doc.lines.get()
        self.assertEqual(line.shortage, 1)
        self.assertFalse(Balance.objects.exists())
        post_document(doc.pk, self.manager)
        self.assertEqual(Balance.objects.get().quantity, 7)
        self.assertEqual(Balance.objects.get().value, 700)
        self.assertEqual(doc.events.count(), 2)

    def test_receipt_discrepancies_require_reason_and_reconcile(self):
        for expected, rejected, note in [
            ("6", "0", "Dư"),
            ("10", "-1", "Sai"),
            ("10", "2", ""),
            ("10", "0", ""),
        ]:
            with self.subTest(expected=expected, rejected=rejected, note=note):
                fs = LineFormSet(
                    self.payload(
                        **{
                            "form-0-expected_quantity": expected,
                            "form-0-rejected_quantity": rejected,
                            "form-0-note": note,
                        }
                    ),
                    kind="IN",
                )
                self.assertFalse(fs.is_valid())

    def test_service_rechecks_discrepancy_even_without_form(self):
        doc = self.doc()
        doc.lines.update(expected_quantity=12, rejected_quantity=1)
        with self.assertRaises(ValidationError):
            post_document(doc.pk, self.manager)
        self.assertFalse(Movement.objects.exists())

    def test_past_and_future_dates_blocked_at_form_and_post(self):
        for offset in [-1, 1]:
            day = timezone.localdate() + timedelta(days=offset)
            with self.subTest(day=day):
                form = DocumentForm(
                    self.payload(business_date=str(day)),
                    user=self.maker,
                    fixed_kind="IN",
                )
                self.assertFalse(form.is_valid())
                doc = self.doc(business_date=day)
                with self.assertRaises(ValidationError):
                    post_document(doc.pk, self.manager)
        self.assertFalse(Balance.objects.exists())

    def test_old_draft_edit_rolls_to_today_then_can_approve(self):
        doc = self.doc(business_date=timezone.localdate() - timedelta(days=1))
        self.client.force_login(self.maker)
        response = self.client.get(f"/documents/{doc.pk}/edit/")
        self.assertEqual(
            response.context["form"]["business_date"].value(), timezone.localdate()
        )
        self.assertEqual(
            self.client.post(f"/documents/{doc.pk}/edit/", self.payload()).status_code,
            302,
        )
        doc.refresh_from_db()
        self.assertEqual(doc.business_date, timezone.localdate())
        post_document(doc.pk, self.manager)

    def test_transfer_can_receive_next_day_without_rewriting_dispatch_date(self):
        self.doc(post=True)
        doc = self.doc(kind="TRANSFER", quantity=3)
        post_document(doc.pk, self.manager)
        tomorrow = timezone.localdate() + timedelta(days=1)
        with patch("inventory.services.timezone.localdate", return_value=tomorrow):
            post_document(doc.pk, self.manager)
        doc.refresh_from_db()
        self.assertEqual(doc.status, "POSTED")
        self.assertNotEqual(doc.business_date, tomorrow)
        self.assertEqual(
            list(doc.events.values_list("action", flat=True)), ["DISPATCH", "POST"]
        )

    def test_due_date_and_reference_date_rules(self):
        yesterday = timezone.localdate() - timedelta(days=1)
        for data in [
            self.payload(
                due_date=str(yesterday),
                kind="LOAN",
                source=self.a.pk,
                destination=self.b.pk,
            ),
            self.payload(reference_date=str(yesterday)),
        ]:
            self.assertFalse(DocumentForm(data, user=self.maker).is_valid())

    def test_stocktake_blocks_changed_stock_including_zero_net_changes(self):
        self.doc(post=True)
        count = self.doc(kind="COUNT", quantity=9)
        self.doc(kind="ADJUST", quantity=1, post=True)
        self.doc(kind="ADJUST", quantity=-1, post=True)
        with self.assertRaisesMessage(ValidationError, "tồn đã biến động"):
            post_document(count.pk, self.admin)
        self.assertEqual(Balance.objects.get().quantity, 10)
        self.assertFalse(count.events.exists())

    def test_stocktake_snapshot_reports_difference_and_updates_after_recount(self):
        self.doc(post=True)
        self.client.force_login(self.maker)
        response = self.client.post(
            "/operations/count/", self.payload(kind="COUNT", **{"form-0-quantity": "8"})
        )
        self.assertRedirects(response, "/stocktakes/")
        self.assertFalse(Document.objects.filter(kind="COUNT").exists())
        from decimal import Decimal
        from uuid import uuid4

        from .stocktakes import (
            begin_session,
            freeze_session,
            save_count,
            submit_session,
        )

        session = begin_session(
            freeze_session(self.a, self.maker).pk, self.maker, "PAPER"
        )
        save_count(
            session.pk,
            self.maker,
            self.p,
            "SET",
            Decimal(8),
            None,
            "Kiểm lại",
            uuid4(),
            1,
        )
        count = submit_session(session.pk, self.maker, "Thiếu 2, đã kiểm lại")
        line = count.lines.get()
        self.assertEqual(line.stocktake_quantity, 10)
        self.assertEqual(line.count_difference, -2)
        post_document(count.pk, self.admin)
        self.assertEqual(Balance.objects.get().quantity, 8)

    def test_legacy_stocktake_requires_new_snapshot(self):
        count = self.doc(kind="COUNT")
        count.lines.update(stocktake_version=None)
        with self.assertRaisesMessage(ValidationError, "lưu mốc tồn"):
            post_document(count.pk, self.admin)

    def test_item_identity_snapshots_and_unit_protection(self):
        doc = self.doc(post=True)
        form = ProductForm(
            {"sku": "NEW", "name": "Tên mới", "unit": "Thùng", "minimum": 0},
            instance=self.p,
        )
        self.assertFalse(form.is_valid())
        self.assertIn("sku", form.errors)
        self.assertIn("unit", form.errors)
        self.p.name = "Tên mới"
        self.p.save()
        self.client.force_login(self.admin)
        response = self.client.get(f"/documents/{doc.pk}/")
        self.assertContains(response, "Giấy")
        self.assertEqual(doc.lines.get().name_snapshot, "Giấy")

    def test_edit_keeps_previous_snapshot_and_blocks_stale_revision(self):
        self.client.force_login(self.maker)
        self.client.post("/operations/in/", self.payload())
        doc = Document.objects.get()
        self.client.post(
            f"/documents/{doc.pk}/edit/", self.payload(**{"form-0-quantity": "6"})
        )
        self.assertEqual(doc.events.first().snapshot["lines"][0]["quantity"], "7.000")
        stale = self.client.post(
            f"/documents/{doc.pk}/edit/", self.payload(**{"form-0-quantity": "4"})
        )
        self.assertRedirects(stale, f"/documents/{doc.pk}/edit/")
        self.assertEqual(doc.lines.get().quantity, 6)
        self.assertEqual(doc.events.count(), 2)

    def test_request_changes_resubmit_cancel_and_audit(self):
        doc = self.doc()
        close_document(doc.pk, self.manager, "REJECT", "Thiếu chứng từ")
        with self.assertRaises(ValidationError):
            post_document(doc.pk, self.manager)
        self.client.force_login(self.maker)
        self.assertEqual(
            self.client.post(
                f"/documents/{doc.pk}/edit/", self.payload(revision="2")
            ).status_code,
            302,
        )
        doc.refresh_from_db()
        self.assertEqual(doc.status, "DRAFT")
        self.assertEqual(
            doc.events.first().snapshot["closure_reason"], "Thiếu chứng từ"
        )
        close_document(doc.pk, self.maker, "CANCEL", "Không mua nữa")
        with self.assertRaises(ValidationError):
            post_document(doc.pk, self.manager)
        self.assertFalse(Balance.objects.exists())
        self.assertEqual(
            list(doc.events.values_list("action", flat=True)),
            ["REJECT", "EDIT", "CANCEL"],
        )

    def test_close_requires_reason_authority_and_unposted_state(self):
        doc = self.doc()
        with self.assertRaises(ValidationError):
            close_document(doc.pk, self.manager, "REJECT", "")
        with self.assertRaises(PermissionDenied):
            close_document(doc.pk, self.maker, "REJECT", "Tự duyệt")
        posted = self.doc(post=True)
        with self.assertRaises(PermissionDenied):
            close_document(posted.pk, self.admin, "CANCEL", "Xóa lịch sử")

    def test_excel_extended_details_and_metadata_survive_preview_confirm(self):
        file = SimpleUploadedFile(
            "nhap.xlsx", self.excel(["P", 7, 100, 10, 2, "Thiếu 1, hỏng 2"]).read()
        )
        self.client.force_login(self.maker)
        response = self.client.post(
            "/import/receipt/",
            {
                "warehouse": self.a.pk,
                "file": file,
                "business_date": str(timezone.localdate()),
                "reference_number": "EX-1",
                "counterparty": "NCC Excel",
            },
        )
        self.assertEqual(response.status_code, 200)
        preview = self.client.session["receipt_import"]
        self.assertEqual(preview["rows"][0]["shortage"], "1")
        self.client.post(
            "/import/receipt/", {"confirm": "1", "import_key": preview["key"]}
        )
        doc = Document.objects.get()
        self.assertEqual(doc.reference_number, "EX-1")
        self.assertEqual(doc.lines.get().rejected_quantity, 2)
        self.assertEqual(doc.lines.get().shortage, 1)
        self.assertEqual(doc.events.count(), 1)
        post_document(doc.pk, self.manager)
        self.assertEqual(Balance.objects.get().quantity, 7)

    def test_excel_invalid_details_no_partial_result(self):
        for row in [
            ["P", 7, 100, 8, 2, "Sai tổng"],
            ["P", 7, 100, 10, 0, ""],
            ["P", 7, 100, 10, -1, "Âm"],
            ["P", 7, 100, "=8+2", 2, "Công thức"],
        ]:
            with self.subTest(row=row), self.assertRaises(ValidationError):
                parse_receipt(self.excel(row))

    def test_report_and_source_warning_scoped(self):
        self.client.force_login(self.maker)
        self.client.post(
            "/operations/in/",
            self.payload(
                reference_number="DUP",
                counterparty="NCC",
                **{"form-0-expected_quantity": "10", "form-0-note": "Thiếu 3"},
            ),
        )
        doc = Document.objects.get()
        other = self.doc(reference_number="DUP", counterparty="NCC")
        self.assertContains(
            self.client.get(f"/documents/{doc.pk}/"), "tránh nhập trùng"
        )
        response = self.client.get("/reports/")
        self.assertEqual(len(response.context["receipt_exceptions"]), 1)
        self.client.get("/", {"warehouse": self.a.pk})
        close_document(doc.pk, self.maker, "CANCEL", "Trùng phiếu")
        self.assertEqual(
            len(self.client.get("/reports/").context["receipt_exceptions"]), 0
        )
        self.assertEqual(other.status, "DRAFT")

    def test_html_notes_are_escaped_in_detail_and_audit(self):
        self.client.force_login(self.maker)
        self.client.post(
            "/operations/in/", self.payload(note="<script>alert(1)</script>")
        )
        response = self.client.get(f"/documents/{Document.objects.get().pk}/")
        self.assertNotContains(response, "<script>alert(1)</script>")
        self.assertContains(response, "&lt;script&gt;")

    def test_excel_preview_cannot_be_confirmed_the_next_day(self):
        self.client.force_login(self.maker)
        file = SimpleUploadedFile(
            "nhap.xlsx", self.excel(["P", 7, 100, None, None, None]).read()
        )
        self.client.post("/import/receipt/", {"warehouse": self.a.pk, "file": file})
        preview = self.client.session["receipt_import"]
        with patch(
            "inventory.views.timezone.localdate",
            return_value=timezone.localdate() + timedelta(days=1),
        ):
            self.assertRedirects(
                self.client.post(
                    "/import/receipt/", {"confirm": "1", "import_key": preview["key"]}
                ),
                "/import/receipt/",
            )
        self.assertFalse(Document.objects.exists())

    def test_rejected_and_cancelled_pages_do_not_claim_to_be_posted(self):
        doc = self.doc()
        close_document(doc.pk, self.manager, "REJECT", "Thiếu hóa đơn")
        self.client.force_login(self.maker)
        response = self.client.get(f"/documents/{doc.pk}/")
        self.assertContains(response, "Thiếu hóa đơn")
        self.assertNotContains(response, "Đã ghi sổ bởi")
        close_document(doc.pk, self.maker, "CANCEL", "Không mua")
        response = self.client.get(f"/documents/{doc.pk}/")
        self.assertContains(response, "Đã hủy")
        self.assertNotContains(response, "Sửa phiếu</a>")

    def test_outsider_cannot_view_audit_or_close_foreign_document(self):
        outsider = get_user_model().objects.create_user("outside", password="1")
        grant_functions(outsider, {"receipts_view", "receipts_create"})
        self.client.force_login(self.maker)
        self.client.post("/operations/in/", self.payload())
        doc = Document.objects.get()
        self.client.force_login(outsider)
        self.assertEqual(self.client.get(f"/documents/{doc.pk}/").status_code, 404)
        self.assertEqual(
            self.client.post(
                f"/documents/{doc.pk}/close/cancel/", {"reason": "Khác kho"}
            ).status_code,
            404,
        )

    def test_document_csv_includes_control_details_and_escapes_formula(self):
        self.client.force_login(self.maker)
        self.client.post(
            "/operations/in/",
            self.payload(
                reference_number="=1+1",
                counterparty="Nhà cung cấp",
                received_by="Thủ kho",
            ),
        )
        response = self.client.get(
            "/documents/",
            {
                "export": "1",
                "from": str(timezone.localdate()),
                "to": str(timezone.localdate()),
            },
        )
        text = response.content.decode("utf-8-sig")
        self.assertIn("'=1+1", text)
        self.assertIn("Ngày thực tế", text)
        self.assertIn("Thủ kho", text)
        self.assertNotIn("\ufeff", text)
        self.assertEqual(
            self.client.get("/documents/", {"q": "9" * 5000}).status_code, 200
        )

    def test_ledger_uses_each_transfer_leg_date(self):
        from datetime import datetime

        self.doc(post=True)
        transfer = self.doc(kind="TRANSFER", quantity=3, post=True)
        yesterday = timezone.localdate() - timedelta(days=1)
        old_timestamp = timezone.make_aware(
            datetime.combine(yesterday, datetime.min.time())
        )
        Movement.objects.filter(document=transfer, warehouse=self.a).update(
            created_at=old_timestamp
        )
        Document.objects.filter(pk=transfer.pk).update(business_date=yesterday)
        self.client.force_login(self.admin)
        response = self.client.get(
            "/ledger/",
            {
                "warehouse": self.b.pk,
                "from": str(timezone.localdate()),
                "to": str(timezone.localdate()),
            },
        )
        rows = list(response.context["movements"])
        self.assertEqual(len(rows), 1)
        self.assertEqual(rows[0].business_date, timezone.localdate())
        self.assertEqual(rows[0].document.business_date, yesterday)

    def test_fully_rejected_receipt_records_dispute_without_stock(self):
        self.client.force_login(self.maker)
        self.client.post(
            "/operations/in/",
            self.payload(
                **{
                    "form-0-quantity": "0",
                    "form-0-expected_quantity": "10",
                    "form-0-rejected_quantity": "10",
                    "form-0-note": "Không nhận toàn bộ do bị ướt",
                }
            ),
        )
        doc = Document.objects.get()
        post_document(doc.pk, self.manager)
        self.assertFalse(Balance.objects.exists())
        self.assertFalse(Movement.objects.exists())
        self.assertEqual(doc.lines.get().rejected_quantity, 10)
        self.assertEqual(
            parse_receipt(self.excel(["P", 0, 100, 10, 10, "Hỏng toàn bộ"]))[0][
                "quantity"
            ],
            "0",
        )

    def test_zero_receipt_without_discrepancy_is_invalid(self):
        fs = LineFormSet(self.payload(**{"form-0-quantity": "0"}), kind="IN")
        self.assertFalse(fs.is_valid())
        with self.assertRaises(ValidationError):
            parse_receipt(self.excel(["P", 0, 100, None, None, None]))
