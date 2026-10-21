from copy import deepcopy
from datetime import timedelta
from io import BytesIO
from re import sub
from unittest.mock import patch
from zipfile import ZIP_DEFLATED, ZipFile

from django.contrib.auth import get_user_model
from django.core.exceptions import ValidationError
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import TestCase
from django.urls import reverse
from django.utils import timezone
from openpyxl import load_workbook

from .excel import DETAIL_HEADERS, HEADERS, WAREHOUSE_HEADERS
from .models import Balance, Document, Line, Movement, Product, Warehouse
from .receipt_import_views import confirm_receipts
from .services import post_document
from .test_product_import import workbook_upload
from .test_support import grant_functions

COLUMNS = HEADERS + DETAIL_HEADERS + WAREHOUSE_HEADERS


class ReceiptWarehouseTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        User = get_user_model()
        cls.maker = User.objects.create_user("receipt-file-maker")
        cls.head = User.objects.create_user("receipt-file-head")
        grant_functions(cls.maker, {"receipts_create"}, level=10)
        grant_functions(cls.head, {"receipts_approve"}, level=30)
        cls.a = Warehouse.objects.create(code="K01", name="Kho A")
        cls.b = Warehouse.objects.create(code="K02", name="Kho B")
        cls.outside = Warehouse.objects.create(code="HIDDEN", name="Không được cấp")
        for warehouse in [cls.a, cls.b]:
            warehouse.members.add(cls.maker)
            warehouse.managers.add(cls.head)
        cls.p = Product.objects.create(sku="CAM001", name="Camera", unit="Cái")
        cls.url = reverse("receipt_import")

    def setUp(self):
        self.client.force_login(self.maker)

    def upload(self, rows=None, *, warehouse=None, headers=COLUMNS, **kwargs):
        data = {
            "file": workbook_upload(
                rows or [["CAM001", 2, 10, None, None, None, "K01"]], headers
            ),
            "note": "Nhập vật tư",
        }
        if warehouse is not None:
            data["warehouse"] = warehouse.pk
        data.update(kwargs)
        return self.client.post(self.url, data)

    def confirm(self):
        key = self.client.session["receipt_import"]["key"]
        return self.client.post(self.url, {"confirm": 1, "import_key": key})

    def test_actual_receipt_download_has_warehouse_column_and_authorized_codes(self):
        response = self.client.get(reverse("receipt_template"))
        self.assertEqual(response.status_code, 200)
        self.assertIn("mau-nhap-kho-theo-kho.xlsx", response["Content-Disposition"])
        self.assertIn("no-store", response["Cache-Control"])
        book = load_workbook(BytesIO(response.content))
        self.assertEqual([c.value for c in book.worksheets[0][1]], COLUMNS)
        self.assertEqual(
            set(row[0] for row in list(book["Danh sach kho"].values)[1:]),
            {"K01", "K02"},
        )
        self.assertEqual(book.worksheets[0]["G2"].number_format, "@")
        self.assertEqual(book.worksheets[0]["A1001"].number_format, "@")
        self.assertEqual(book.worksheets[0]["G1001"].number_format, "@")
        self.assertEqual(book.worksheets[0].max_row, 1001)
        self.assertIn(
            "1.000 dòng", " ".join(str(r[0]) for r in book["Huong dan"].values)
        )
        book.close()

    def test_existing_product_to_multiple_warehouses_without_common_warehouse(self):
        response = self.upload(
            [
                ["CAM001", 2, 10, None, None, None, "K01"],
                ["CAM001", 3, 20, None, None, None, "K02"],
            ]
        )
        self.assertContains(response, "Kho A")
        self.assertContains(response, "Kho B")
        self.assertEqual(self.client.session["receipt_import"]["document_count"], 2)
        self.assertFalse(Document.objects.exists())
        self.confirm()
        self.assertEqual(Product.objects.count(), 1)
        self.assertEqual(Document.objects.count(), 2)
        self.assertFalse(Balance.objects.exists())
        self.assertFalse(Movement.objects.exists())
        for document in Document.objects.all():
            self.assertEqual(document.status, "DRAFT")
            post_document(document.pk, self.head)
        self.assertEqual(
            (
                Balance.objects.get(warehouse=self.a).quantity,
                Balance.objects.get(warehouse=self.b).value,
            ),
            (2, 60),
        )

    def test_file_warehouse_wins_and_blank_rows_use_common_warehouse(self):
        self.upload(
            [
                ["CAM001", 2, 10, None, None, None, None],
                ["CAM001", 3, 20, None, None, None, "K02"],
            ],
            warehouse=self.a,
        )
        self.confirm()
        self.assertEqual(
            set(Document.objects.values_list("destination_id", flat=True)),
            {self.a.pk, self.b.pk},
        )

    def test_blank_and_explicit_same_warehouse_duplicate_is_blocked(self):
        self.upload(
            [
                ["CAM001", 1, 10, None, None, None, None],
                ["CAM001", 2, 10, None, None, None, "K01"],
            ],
            warehouse=self.a,
        )
        self.assertNotIn("receipt_import", self.client.session)
        self.assertFalse(Document.objects.exists())

    def test_no_fallback_unknown_outside_numeric_warehouse_and_formula_block_entire_file(
        self,
    ):
        for code in [None, "MISSING", "HIDDEN", 1, "=1+1"]:
            with self.subTest(code=code):
                self.upload(
                    [
                        ["CAM001", 1, 10, None, None, None, "K01"],
                        ["CAM001", 1, 10, None, None, None, code],
                    ]
                )
                self.assertNotIn("receipt_import", self.client.session)
                self.assertFalse(Document.objects.exists())

    def test_partial_damage_preserved_and_only_accepted_quantity_is_posted(self):
        self.upload([["CAM001", 7, 10, 10, 2, "Thiếu 1, hỏng 2", "K01"]])
        self.confirm()
        line = Line.objects.get()
        self.assertEqual(
            (
                line.quantity,
                line.expected_quantity,
                line.rejected_quantity,
                line.shortage,
            ),
            (7, 10, 2, 1),
        )
        post_document(Document.objects.get().pk, self.head)
        self.assertEqual(Balance.objects.get().quantity, 7)

    def test_revoked_warehouse_and_changed_product_reject_without_partial_receipts(
        self,
    ):
        self.upload()
        self.a.members.remove(self.maker)
        self.confirm()
        self.assertFalse(Document.objects.exists())
        self.a.members.add(self.maker)
        self.upload()
        Product.objects.filter(pk=self.p.pk).update(unit="Bộ")
        self.confirm()
        self.assertFalse(Document.objects.exists())

    def test_warehouse_code_renamed_after_preview_is_not_silently_used(self):
        self.upload()
        Warehouse.objects.filter(pk=self.a.pk).update(code="RENAMED")
        self.confirm()
        self.assertFalse(Document.objects.exists())

    def test_expired_preview_and_day_rollover_require_upload_again(self):
        for field in ["created_at", "business_date"]:
            self.upload()
            session = self.client.session
            preview = session["receipt_import"]
            if field == "created_at":
                preview[field] = 0
            else:
                preview["details"][field] = str(
                    timezone.localdate() - timedelta(days=1)
                )
            session["receipt_import"] = preview
            session.save()
            self.confirm()
            self.assertFalse(Document.objects.exists())

    def test_second_receipt_failure_rolls_back_first_and_lines(self):
        self.upload(
            [
                ["CAM001", 2, 10, None, None, None, "K01"],
                ["CAM001", 3, 20, None, None, None, "K02"],
            ]
        )
        from .services import audit_document as real_audit

        calls = []

        def audit(document, actor, action):
            calls.append(document.pk)
            if len(calls) == 2:
                raise ValidationError("second receipt failed")
            return real_audit(document, actor, action)

        with patch("inventory.receipt_import_views.audit_document", side_effect=audit):
            self.confirm()
        self.assertEqual(len(calls), 2)
        self.assertFalse(Document.objects.exists())
        self.assertFalse(Line.objects.exists())

    def test_replay_and_direct_repeated_confirmation_do_not_duplicate_receipts(self):
        self.upload(
            [
                ["CAM001", 2, 10, None, None, None, "K01"],
                ["CAM001", 3, 20, None, None, None, "K02"],
            ]
        )
        preview = deepcopy(self.client.session["receipt_import"])
        result = confirm_receipts(self.maker, preview)
        again = confirm_receipts(self.maker, preview)
        self.assertEqual([d.pk for d in result], [d.pk for d in again])
        self.confirm()
        self.assertEqual(Document.objects.count(), 2)
        self.client.post(self.url, {"confirm": 1, "import_key": preview["key"]})
        self.assertEqual(Document.objects.count(), 2)
        key = self.client.session["receipt_import_result"]["key"]
        response = self.client.get(
            reverse("documents") + "?kind=IN&import_batch=" + key
        )
        self.assertEqual(response.context["page_obj"].paginator.count, 2)

    def large_rows(self, count):
        Product.objects.bulk_create(
            [Product(sku=f"R{i}", name=f"Hàng {i}") for i in range(count)]
        )
        return [
            [f"R{i}", 1, 10, None, None, None, "K01" if i < 550 else "K02"]
            for i in range(count)
        ]

    def test_new_template_1000_rows_split_into_20_drafts_by_warehouse(self):
        self.assertContains(self.client.get(self.url), "5 MB / 1.000 dòng")
        response = self.upload(self.large_rows(1000))
        self.assertContains(response, "1000 dòng hợp lệ")
        preview = self.client.session["receipt_import"]
        self.assertEqual(len(preview["rows"]), 1000)
        self.assertEqual(preview["rows"][-1]["sku"], "R999")
        self.assertEqual(preview["rows"][-1]["row_number"], 1001)
        self.assertEqual(preview["document_count"], 20)
        self.confirm()
        self.assertEqual(Document.objects.filter(destination=self.a).count(), 11)
        self.assertEqual(Document.objects.filter(destination=self.b).count(), 9)
        self.assertEqual(Line.objects.count(), 1000)
        self.assertTrue(all(d.lines.count() == 50 for d in Document.objects.all()))
        self.assertFalse(Document.objects.exclude(status="DRAFT").exists())
        self.assertFalse(Balance.objects.exists())
        self.assertFalse(Movement.objects.exists())

    def test_1001_rows_rejected_even_with_understated_excel_dimensions(self):
        rows = self.large_rows(1001)
        for understated in (False, True):
            with self.subTest(understated=understated):
                upload = workbook_upload(rows, COLUMNS)
                if understated:
                    output = BytesIO()
                    with (
                        ZipFile(upload) as source,
                        ZipFile(output, "w", ZIP_DEFLATED) as target,
                    ):
                        for entry in source.infolist():
                            data = source.read(entry.filename)
                            if entry.filename == "xl/worksheets/sheet1.xml":
                                data = sub(
                                    rb'<dimension ref="[^"]+"',
                                    b'<dimension ref="A1:G2"',
                                    data,
                                )
                            target.writestr(entry, data)
                    upload = SimpleUploadedFile("overflow.xlsx", output.getvalue())
                response = self.upload(file=upload)
                self.assertContains(response, "Mẫu mới tối đa 1.000 dòng")
                self.assertNotIn("receipt_import", self.client.session)
                self.assertFalse(Document.objects.exists())

    def test_last_of_1000_rows_is_validated_without_partial_preview(self):
        rows = self.large_rows(1000)
        rows[-1][0] = "MISSING-LAST-PRODUCT"
        response = self.upload(rows)
        self.assertContains(response, "Dòng 1001")
        self.assertContains(response, "MISSING-LAST-PRODUCT")
        self.assertNotIn("receipt_import", self.client.session)
        self.assertFalse(Document.objects.exists())

    def test_legacy_three_and_six_column_files_still_limit_to_50_rows(self):
        rows = self.large_rows(51)
        for headers in (HEADERS, HEADERS + DETAIL_HEADERS):
            with self.subTest(headers=headers):
                response = self.upload(
                    [r[: len(headers)] for r in rows], warehouse=self.a, headers=headers
                )
                self.assertContains(response, "mẫu cũ tối đa 50 mã")
                self.assertNotIn("receipt_import", self.client.session)
                self.assertFalse(Document.objects.exists())
