from concurrent.futures import ThreadPoolExecutor
from decimal import Decimal
from io import BytesIO
from threading import Barrier
from unittest import skipUnless
from uuid import uuid4

from django.contrib.auth import get_user_model
from django.core.exceptions import PermissionDenied, ValidationError
from django.core.files.uploadedfile import SimpleUploadedFile
from django.db import connection, connections
from django.test import TestCase, TransactionTestCase, override_settings
from PIL import Image

from .forms import ProductForm
from .models import Balance, Document, Line, Product, StocktakeSession, Warehouse
from .product_import import confirm_product_import, parse_product_workbook
from .services import post_document
from .stocktakes import (
    begin_session,
    cancel_session,
    freeze_session,
    product_from_scan,
    save_count,
    submit_session,
)
from .test_product_import import workbook_upload
from .test_support import grant_functions


class ProductQRWorkflowTests(TestCase):
    def test_auto_manual_required_unique_and_lifetime_identity(self):
        auto = ProductForm(
            {
                "sku": "AUTO",
                "name": "Tự động",
                "unit": "Cái",
                "qr_auto": "True",
                "minimum": 0,
            }
        )
        self.assertTrue(auto.is_valid(), auto.errors)
        first = auto.save()
        self.assertTrue(first.qr_code)
        self.assertTrue(first.qr_auto)
        missing = ProductForm(
            {
                "sku": "MISSING",
                "name": "Thiếu QR",
                "unit": "Cái",
                "qr_auto": "False",
                "minimum": 0,
            }
        )
        self.assertFalse(missing.is_valid())
        self.assertIn("qr_code", missing.errors)
        manual = ProductForm(
            {
                "sku": "MANUAL",
                "name": "QR nhãn cũ",
                "unit": "Bộ",
                "qr_auto": "False",
                "qr_code": "LEMON-EXISTING-001",
                "minimum": 0,
            }
        )
        self.assertTrue(manual.is_valid(), manual.errors)
        item = manual.save()
        self.assertEqual(product_from_scan(item.qr_code), item)
        self.assertEqual(
            product_from_scan(f"https://old.example/q/items/{item.qr_token}/"), item
        )
        self.assertEqual(product_from_scan(first.qr_code), first)
        for code in [item.qr_code, first.sku, "bad code", "DHD:ITEM:" + str(uuid4())]:
            form = ProductForm(
                {
                    "sku": "DUPLICATE",
                    "name": "Sai QR",
                    "unit": "Cái",
                    "qr_auto": "False",
                    "qr_code": code,
                    "minimum": 0,
                }
            )
            self.assertFalse(form.is_valid(), code)
        old = item.qr_code
        item.qr_code = "REPLACEMENT"
        with self.assertRaises(ValidationError):
            item.save()
        item.refresh_from_db()
        self.assertEqual(item.qr_code, old)
        forged = ProductForm(
            {
                "sku": "MANUAL",
                "name": "Đổi tên hợp lệ",
                "unit": "Bộ",
                "qr_auto": "True",
                "qr_code": "FORGED",
                "minimum": 0,
            },
            instance=item,
        )
        self.assertTrue(forged.is_valid(), forged.errors)
        forged.save()
        item.refresh_from_db()
        self.assertEqual(item.qr_code, old)
        self.assertFalse(item.qr_auto)

    def test_sku_cannot_steal_another_products_qr(self):
        Product.objects.create(sku="A", name="A", qr_auto=False, qr_code="LABEL-A")
        form = ProductForm({"sku": "LABEL-A", "name": "B", "unit": "Cái", "minimum": 0})
        self.assertFalse(form.is_valid())
        with self.assertRaises(ValidationError):
            Product.objects.create(sku="LABEL-A", name="B")

    def test_excel_supports_auto_or_existing_qr_and_cross_row_collisions(self):
        admin = get_user_model().objects.create_superuser(
            "qr-excel", "qr@example.test", "1"
        )
        headers = ["Mã hàng", "Tên hàng", "Đơn vị tính", "QR tự động", "Mã QR"]
        preview = parse_product_workbook(
            workbook_upload(
                [
                    ["A", "Hàng A", "Cái", "Không", "EXTERNAL-A"],
                    ["B", "Hàng B", "Bộ", "Có", ""],
                ],
                headers,
            )
        )
        self.assertTrue(preview["valid"], preview)
        created = confirm_product_import(admin, preview["rows"], preview["schema"])
        self.assertEqual(created[0].qr_code, "EXTERNAL-A")
        self.assertFalse(created[0].qr_auto)
        self.assertTrue(created[1].qr_auto)
        for rows in [
            [["C", "C", "Cái", "Không", ""]],
            [["C", "C", "Cái", "Không", "EXTERNAL-A"]],
            [["C", "C", "Cái", "Không", "D"], ["D", "D", "Cái", "Có", ""]],
            [
                ["C", "C", "Cái", "Không", "SHARED"],
                ["D", "D", "Cái", "Không", "SHARED"],
            ],
        ]:
            self.assertFalse(
                parse_product_workbook(workbook_upload(rows, headers))["valid"]
            )
        self.assertEqual(Product.objects.count(), 2)

    @override_settings(DEBUG=True, PRIVATE_MEDIA_PROVIDER="database")
    def test_create_with_image_or_add_later_from_goods_keeps_qr(self):
        admin = get_user_model().objects.create_superuser(
            "qr-photo", "photo@example.test", "1"
        )
        self.client.force_login(admin)

        def photo():
            output = BytesIO()
            Image.new("RGB", (24, 24), "green").save(output, "PNG")
            return SimpleUploadedFile(
                "hang.png", output.getvalue(), content_type="image/png"
            )

        response = self.client.post(
            "/products/new/",
            {
                "sku": "PHOTO",
                "name": "Ảnh lúc tạo",
                "unit": "Cái",
                "minimum": 0,
                "qr_auto": "False",
                "qr_code": "PHOTO-QR",
                "image": photo(),
                "caption": "Ảnh nhận diện",
            },
        )
        self.assertEqual(response.status_code, 302)
        product = Product.objects.get(sku="PHOTO")
        self.assertEqual(product.photos.count(), 1)
        response = self.client.post(
            f"/products/{product.pk}/edit/",
            {
                "sku": "PHOTO",
                "name": "Ảnh thêm sau",
                "unit": "Cái",
                "minimum": 0,
                "image": photo(),
                "caption": "Ảnh tiếp theo",
            },
        )
        self.assertEqual(response.status_code, 302)
        product.refresh_from_db()
        self.assertEqual(product.qr_code, "PHOTO-QR")
        self.assertContains(self.client.get("/products/"), "Cập nhật ảnh")
        self.assertContains(
            self.client.get(f"/products/{product.pk}/edit/"), "Ảnh nhận diện"
        )
        self.assertEqual(
            self.client.get(f"/products/{product.pk}/qr.png").status_code, 200
        )


class StocktakeWorkflowTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        User = get_user_model()
        cls.maker = User.objects.create_user("freeze-maker", password="1")
        cls.other = User.objects.create_user("freeze-other", password="1")
        cls.admin = User.objects.create_superuser(
            "freeze-admin", "admin@example.test", "1"
        )
        cls.ceo = User.objects.create_user("freeze-ceo", password="1")
        for user in [cls.maker, cls.other]:
            grant_functions(
                user,
                {
                    "stocktakes_create",
                    "products_create",
                    "receipts_create",
                    "issues_create",
                    "adjustments_view",
                },
            )
        grant_functions(cls.ceo, {"adjustments_approve", "documents_view"}, level=30)
        cls.a = Warehouse.objects.create(code="FREEZE-A", name="Kho chốt")
        cls.b = Warehouse.objects.create(code="FREEZE-B", name="Kho bình thường")
        for warehouse in [cls.a, cls.b]:
            warehouse.members.add(cls.maker, cls.other)
        cls.p = Product.objects.create(
            sku="F-A", name="Hàng kiểm", qr_auto=False, qr_code="ASSET-0001"
        )
        cls.q = Product.objects.create(sku="F-B", name="Hàng còn lại")

    def receipt(self, warehouse=None, product=None, quantity=3):
        doc = Document.objects.create(
            kind="IN", destination=warehouse or self.a, created_by=self.maker
        )
        Line.objects.create(
            document=doc, product=product or self.p, quantity=quantity, unit_price=100
        )
        post_document(doc.pk, self.admin)
        return doc

    def count(self, session, quantity=2, product=None):
        product = product or self.p
        item = session.items.filter(product=product).first()
        return save_count(
            session.pk,
            self.maker,
            product,
            "SET",
            Decimal(quantity),
            None,
            "Kiểm thực tế",
            uuid4(),
            item.revision if item else 1,
        )

    def test_freeze_ready_begin_modes_and_no_duplicate_session(self):
        self.receipt()
        session = freeze_session(self.a, self.maker)
        self.assertEqual(session.status, "READY")
        self.assertTrue(session.locks_inventory)
        self.assertEqual(session.items.get().book_quantity, 3)
        with self.assertRaises(ValidationError):
            self.count(session)
        with self.assertRaises(ValidationError):
            freeze_session(self.a, self.other)
        grant_functions(self.other, {"products_view"})
        with self.assertRaises(PermissionDenied):
            begin_session(session.pk, self.other, "PAPER")
        session = begin_session(session.pk, self.maker, "PAPER")
        self.assertEqual(session.status, "OPEN")
        self.assertEqual(begin_session(session.pk, self.maker, "PAPER").pk, session.pk)
        with self.assertRaises(ValidationError):
            begin_session(session.pk, self.maker, "QR")
        with self.assertRaises(ValidationError):
            save_count(
                session.pk, self.maker, self.p, "ADD", None, None, "", uuid4(), 1
            )
        self.client.force_login(self.maker)
        self.assertContains(
            self.client.get(f"/stocktakes/{session.pk}/paper/"),
            "Nhập kết quả kiểm kê giấy",
        )
        self.assertContains(
            self.client.get(f"/stocktakes/{session.pk}/report/?worksheet=1"),
            "BẢNG KIỂM ĐẾM THỰC TẾ",
        )

    def test_authorized_counter_can_receive_a_warehouse_frozen_by_admin(self):
        self.receipt()
        session = freeze_session(self.a, self.admin)
        session = begin_session(session.pk, self.other, "PAPER")
        self.assertEqual(session.created_by, self.admin)
        self.assertEqual(session.counted_by, self.other)
        self.assertEqual(session.creator_level, 10)
        with self.assertRaises(PermissionDenied):
            begin_session(session.pk, self.maker, "PAPER")
        save_count(
            session.pk,
            self.other,
            self.p,
            "SET",
            Decimal(2),
            None,
            "Kiểm thực tế",
            uuid4(),
            1,
        )
        doc = submit_session(session.pk, self.other, "Thiếu một")
        self.assertEqual(doc.created_by, self.other)
        post_document(doc.pk, self.ceo)
        self.assertEqual(Balance.objects.get().quantity, 2)

    def test_freeze_blocks_stock_changes_even_admin_but_allows_other_warehouse(self):
        self.receipt()
        session = freeze_session(self.a, self.maker)
        for kind in ["IN", "OUT", "TRANSFER", "LOAN", "COUNT", "ADJUST"]:
            doc = Document.objects.create(
                kind=kind,
                created_by=self.maker,
                source=self.a if kind in {"OUT", "TRANSFER", "LOAN"} else None,
                destination=self.b
                if kind in {"TRANSFER", "LOAN"}
                else (self.a if kind != "OUT" else None),
            )
            Line.objects.create(
                document=doc, product=self.p, quantity=1, unit_price=100
            )
            with self.assertRaises(ValidationError, msg=kind):
                post_document(doc.pk, self.admin)
            doc.refresh_from_db()
            self.assertEqual(doc.status, "DRAFT")
        self.assertEqual(Balance.objects.get(warehouse=self.a).quantity, 3)
        self.receipt(warehouse=self.b)
        self.assertEqual(Balance.objects.get(warehouse=self.b).quantity, 3)
        cancel_session(session.pk, self.admin, "Dừng kiểm để xử lý giao dịch")
        self.receipt()
        self.assertEqual(Balance.objects.get(warehouse=self.a).quantity, 6)

    def test_only_own_adjustment_can_post_then_unlocks(self):
        self.receipt()
        session = begin_session(freeze_session(self.a, self.maker).pk, self.maker, "QR")
        self.assertEqual(product_from_scan("ASSET-0001"), self.p)
        self.count(session)
        doc = submit_session(session.pk, self.maker, "Thiếu một, đề nghị điều chỉnh")
        self.assertEqual(Balance.objects.get().quantity, 3)
        with self.assertRaises(ValidationError):
            self.receipt()
        with self.assertRaises(PermissionDenied):
            post_document(doc.pk, self.maker)
        post_document(doc.pk, self.ceo)
        self.assertEqual(Balance.objects.get().quantity, 2)
        self.receipt()
        self.assertEqual(Balance.objects.get().quantity, 5)

    def test_no_difference_or_cancel_unlocks_without_adjustment(self):
        self.receipt()
        session = begin_session(
            freeze_session(self.a, self.maker).pk, self.maker, "PAPER"
        )
        with self.assertRaises(ValidationError):
            submit_session(session.pk, self.maker, "Chưa đếm không phải 0")
        self.count(session, 3)
        self.assertIsNone(submit_session(session.pk, self.maker, "Đủ hàng"))
        self.receipt()
        ready = freeze_session(self.a, self.maker)
        with self.assertRaises(ValidationError):
            cancel_session(ready.pk, self.maker, "")
        cancel_session(ready.pk, self.maker, "Hủy có lý do")
        self.receipt()

    def paper_payload(self, session, quantities):
        rows = list(session.items.order_by("sku_snapshot", "pk"))
        payload = {
            "action": "save",
            "form-TOTAL_FORMS": str(len(rows)),
            "form-INITIAL_FORMS": str(len(rows)),
            "form-MIN_NUM_FORMS": "0",
            "form-MAX_NUM_FORMS": "25",
        }
        for index, (item, quantity) in enumerate(zip(rows, quantities)):
            payload.update(
                {
                    f"form-{index}-id": str(item.pk),
                    f"form-{index}-revision": str(item.revision),
                    f"form-{index}-counted_quantity": str(quantity),
                    f"form-{index}-unit_price": "",
                    f"form-{index}-note": "Từ bản ký",
                }
            )
        return payload

    def test_paper_page_saves_explicit_zero_and_conflict_rolls_back_whole_page(self):
        self.receipt()
        self.receipt(product=self.q)
        session = begin_session(
            freeze_session(self.a, self.maker).pk, self.maker, "PAPER"
        )
        payload = self.paper_payload(session, [0, 2])
        self.client.force_login(self.maker)
        url = f"/stocktakes/{session.pk}/paper/"
        response = self.client.post(url, payload)
        self.assertEqual(response.status_code, 302)
        self.assertEqual(
            list(
                session.items.order_by("sku_snapshot").values_list(
                    "counted_quantity", flat=True
                )
            ),
            [0, 2],
        )
        stale = self.paper_payload(session, [1, 1])
        self.count(session, 3, self.q)
        response = self.client.post(url, stale)
        self.assertEqual(response.status_code, 200)
        self.assertEqual(
            list(
                session.items.order_by("sku_snapshot").values_list(
                    "counted_quantity", flat=True
                )
            ),
            [0, 3],
        )
        self.assertEqual(Balance.objects.get(product=self.p).quantity, 3)

    def test_paper_extra_item_requires_price_and_cannot_overwrite_existing_count(self):
        self.receipt()
        session = begin_session(
            freeze_session(self.a, self.maker).pk, self.maker, "PAPER"
        )
        self.client.force_login(self.maker)
        url = f"/stocktakes/{session.pk}/paper/"
        response = self.client.post(
            url,
            {
                "action": "extra",
                "code": self.q.sku,
                "quantity": "2",
                "unit_price": "50",
                "note": "Tìm thấy ngoài sổ",
            },
        )
        self.assertEqual(response.status_code, 302)
        self.assertEqual(session.items.get(product=self.q).counted_quantity, 2)
        response = self.client.post(
            url,
            {
                "action": "extra",
                "code": self.q.sku,
                "quantity": "9",
                "unit_price": "50",
            },
        )
        self.assertEqual(response.status_code, 200)
        self.assertEqual(session.items.get(product=self.q).counted_quantity, 2)


@skipUnless(connection.vendor == "postgresql", "PostgreSQL warehouse row locks")
class StocktakeFreezeConcurrencyTests(TransactionTestCase):
    def test_two_freezes_only_one_snapshot_is_created(self):
        warehouse = Warehouse.objects.create(code="FREEZE-RACE", name="Kho race")
        users = [
            get_user_model().objects.create_user(f"freeze-race-{index}")
            for index in range(2)
        ]
        for user in users:
            grant_functions(user, {"stocktakes_create"})
            warehouse.members.add(user)
        barrier = Barrier(2)

        def freeze(index):
            try:
                barrier.wait(timeout=10)
                freeze_session(warehouse, users[index])
                return True
            except ValidationError:
                return False
            finally:
                connections.close_all()

        with ThreadPoolExecutor(max_workers=2) as pool:
            result = list(pool.map(freeze, [0, 1]))
        self.assertEqual(sorted(result), [False, True])
        self.assertEqual(
            StocktakeSession.objects.filter(warehouse=warehouse).count(), 1
        )
