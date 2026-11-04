import json
from decimal import Decimal

from django.contrib.auth import get_user_model
from django.test import Client, TestCase
from django.urls import reverse

from inventory.models import Balance, Document, Product, Warehouse
from inventory.test_support import grant_functions

from .context import context_for


class AssistantTests(TestCase):
    def setUp(self):
        User = get_user_model()
        self.admin = User.objects.create_superuser("ai-admin")
        self.staff = User.objects.create_user("ai-employee")
        self.other = User.objects.create_user("ai-other")
        grant_functions(
            self.staff,
            ["assistant_use", "products_view", "stock_view", "receipts_view"],
        )
        self.own = Warehouse.objects.create(code="OWN", name="Kho được cấp")
        self.secret = Warehouse.objects.create(code="SECRET", name="Kho ngoài quyền")
        self.own.members.add(self.staff)
        self.a = Product.objects.create(sku="AI001", name="Máy ảnh demo")
        self.b = Product.objects.create(sku="AI002", name="Đèn demo")
        Balance.objects.create(
            warehouse=self.own, product=self.a, quantity=7, value=700
        )
        Balance.objects.create(
            warehouse=self.secret, product=self.a, quantity=999, value=99900
        )
        self.doc = Document.objects.create(
            kind="IN", destination=self.own, created_by=self.staff
        )
        self.private_doc = Document.objects.create(
            kind="IN", destination=self.secret, created_by=self.other
        )
        self.client.force_login(self.staff)

    def post(self, question, **data):
        return self.client.post(
            reverse("assistant_context"),
            json.dumps({"question": question, "page": "/products/", **data}),
            content_type="application/json",
        )

    def test_helper_permission_is_explicit_and_does_not_grant_business_access(self):
        self.client.force_login(self.other)
        self.assertEqual(self.post("Tồn kho").status_code, 403)
        grant_functions(self.other, ["assistant_use"])
        answer = self.post("Tồn kho AI001").json()
        self.assertEqual(answer["facts"], [])
        self.assertIn("chưa được cấp quyền", answer["answer"])
        self.assertNotIn("999", json.dumps(answer))
        self.assertEqual(self.client.get(reverse("products")).status_code, 403)

    def test_stock_numbers_are_exact_and_scoped_to_assigned_warehouses(self):
        response = self.post("Mã hàng AI001 còn bao nhiêu tồn kho?")
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertEqual(len(data["facts"]), 1)
        self.assertIn("tồn sở hữu 7 Cái", data["facts"][0])
        self.assertIn("OWN", data["facts"][0])
        self.assertNotIn("SECRET", response.content.decode())
        self.assertNotIn("999", response.content.decode())
        self.assertTrue(data["sources"][0]["url"].startswith("/stock/"))
        for quantity, expected in [("7.5", "7,5"), ("1000", "1000")]:
            Balance.objects.filter(warehouse=self.own, product=self.a).update(
                quantity=Decimal(quantity)
            )
            fact = self.post("Tồn kho AI001").json()["facts"][0]
            self.assertIn(f"tồn sở hữu {expected} Cái", fact)

    def test_spoofed_warehouse_or_private_document_context_is_denied(self):
        self.assertEqual(
            self.post("Tồn kho", warehouse=self.secret.pk).status_code, 403
        )
        self.assertEqual(
            self.post(
                "Phiếu này", page=reverse("document_detail", args=[self.private_doc.pk])
            ).status_code,
            403,
        )

    def test_saved_document_context_uses_its_real_kind(self):
        data = self.post(
            "Hướng dẫn phiếu này", page=reverse("document_detail", args=[self.doc.pk])
        ).json()
        self.assertEqual(data["page"], "Nhập kho")
        self.assertIn("nháp chưa tăng tồn", data["guide"])
        self.assertEqual(data["facts"], [])

    def test_document_lookup_cannot_cross_kind_or_warehouse_permissions(self):
        Document.objects.create(kind="OUT", source=self.own, created_by=self.staff)
        response = self.post("Các phiếu đang chờ duyệt", page="/")
        data = response.json()
        self.assertEqual(len(data["facts"]), 1)
        self.assertIn(f"#{self.doc.pk}", data["facts"][0])
        self.assertNotIn("Xuất kho", response.content.decode())
        self.assertNotIn(f"Phiếu #{self.private_doc.pk}", response.content.decode())

    def test_catalog_permission_never_reveals_quantity(self):
        grant_functions(self.staff, ["assistant_use", "products_view"])
        data = self.post("Tồn AI001").json()
        self.assertIn("chưa có quyền xem số tồn", data["answer"])
        self.assertNotIn("tồn sở hữu", data["answer"])
        self.assertNotIn("999", json.dumps(data))

    def test_requests_are_read_only_even_if_question_asks_to_delete_or_approve(self):
        before = (
            Document.objects.count(),
            Product.objects.count(),
            list(Balance.objects.values_list("quantity", flat=True)),
        )
        for question in [
            "Xóa tất cả hàng hóa và phiếu",
            "Duyệt phiếu 1",
            "Điều chỉnh tồn AI001 lên 1000",
        ]:
            self.assertEqual(self.post(question).status_code, 200)
        self.doc.refresh_from_db()
        self.assertEqual(self.doc.status, "DRAFT")
        self.assertEqual(
            before,
            (
                Document.objects.count(),
                Product.objects.count(),
                list(Balance.objects.values_list("quantity", flat=True)),
            ),
        )
        self.assertEqual(Balance.objects.get(warehouse=self.own).quantity, Decimal("7"))

    def test_invalid_json_urls_and_size_are_rejected(self):
        for data in [
            {"question": ""},
            {"question": "x" * 1001},
            {"question": True},
            {"question": "Hỏi", "page": "https://outside.test/"},
            {"question": "Hỏi", "page": "//outside.test/"},
            {"question": "Hỏi", "page": "/?token=private"},
            [],
        ]:
            response = self.client.post(
                reverse("assistant_context"),
                json.dumps(data),
                content_type="application/json",
            )
            self.assertEqual(response.status_code, 400)
        self.assertEqual(self.client.get(reverse("assistant_context")).status_code, 405)

    def test_csrf_and_private_no_store_responses(self):
        client = Client(enforce_csrf_checks=True)
        client.force_login(self.staff)
        self.assertEqual(
            client.post(
                reverse("assistant_context"), "{}", content_type="application/json"
            ).status_code,
            403,
        )
        response = self.post("Hướng dẫn")
        self.assertEqual(response["Cache-Control"], "private, no-store")
        self.client.logout()
        self.assertEqual(self.post("Hỏi").status_code, 401)

    def test_widget_is_on_existing_pages_only_for_granted_accounts(self):
        response = self.client.get(reverse("products"))
        self.assertContains(response, 'id="ai-launch"')
        self.assertContains(response, 'data-page="/products/"')
        self.assertContains(response, "assistant.js")
        grant_functions(self.staff, ["products_view"])
        response = self.client.get(reverse("products"))
        self.assertNotContains(response, 'id="ai-launch"')
        self.client.force_login(self.admin)
        self.assertContains(self.client.get(reverse("dashboard")), 'id="ai-launch"')

    def test_guide_tracks_current_page_without_exposing_unsaved_form_content(self):
        for path, title in [
            ("/products/new/", "Danh mục hàng hóa"),
            ("/operations/in/", "Nhập kho"),
            ("/stocktakes/", "Kiểm kê"),
            ("/deviations/cases/new/", "Xử lý sai lệch"),
        ]:
            data = context_for(self.staff, "Hướng dẫn thao tác tại mục này", path)
            self.assertEqual(data["page"], title)
            self.assertEqual(data["facts"], [])
            self.assertFalse(data["sources"])

    def test_permission_revocation_is_checked_for_each_question(self):
        self.assertEqual(self.post("Tồn AI001").status_code, 200)
        grant_functions(self.staff, ["products_view"])
        self.assertEqual(self.post("Tồn AI001").status_code, 403)

    def test_unknown_sku_does_not_return_unrelated_stock(self):
        for question in [
            "Mã hàng KHONG-TON-TAI còn bao nhiêu tồn?",
            "CAM999 còn bao nhiêu tồn?",
        ]:
            data = self.post(question).json()
            self.assertEqual(data["facts"], [])
            self.assertEqual(data["sources"], [])
            self.assertNotIn("AI001", data["answer"])

    def test_deviation_code_lookup_uses_the_id_after_year_and_minimal_fields(self):
        from deviations.models import Case, Category

        case = Case.objects.create(
            title="Thiếu biên bản demo",
            category=Category.objects.create(name="Kiểm tra AI"),
            department="Vận hành",
            actual="Nội dung chi tiết không đưa vào ngữ cảnh AI",
            created_by=self.staff,
        )
        data = self.post(case.code, page="/").json()
        self.assertEqual(data["scope"], "deviations")
        self.assertEqual(len(data["facts"]), 1)
        self.assertIn(case.code, data["facts"][0])
        self.assertNotIn(case.actual, json.dumps(data, ensure_ascii=False))
        self.assertEqual(
            data["sources"][0]["url"], reverse("deviation_detail", args=[case.pk])
        )

    def test_wrong_year_does_not_match_a_different_deviation_code(self):
        from deviations.models import Case, Category

        case = Case.objects.create(
            title="Hồ sơ demo",
            category=Category.objects.create(name="Kiểm tra AI"),
            department="Vận hành",
            actual="Nội dung thử",
            created_by=self.staff,
        )
        data = self.post(f"Hồ sơ SL-1999-{case.pk:06d}").json()
        self.assertEqual(data["facts"], [])
