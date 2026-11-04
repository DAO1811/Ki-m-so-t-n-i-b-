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
        self.assertNotIn(
            "999",
            json.dumps({key: answer[key] for key in ("answer", "facts", "sources")}),
        )
        self.assertEqual(self.client.get(reverse("products")).status_code, 403)

    def test_stock_numbers_are_exact_and_scoped_to_assigned_warehouses(self):
        response = self.post("Mã hàng AI001 còn bao nhiêu tồn kho?")
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertEqual(len(data["facts"]), 1)
        self.assertIn("tồn sở hữu 7 Cái", data["facts"][0])
        self.assertIn("OWN", data["facts"][0])
        self.assertNotIn("SECRET", response.content.decode())
        self.assertNotIn(
            "999",
            json.dumps({key: data[key] for key in ("answer", "facts", "sources")}),
        )
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
        self.assertNotIn(
            "999",
            json.dumps({key: data[key] for key in ("answer", "facts", "sources")}),
        )

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
            self.assertTrue(all(s["url"].startswith("/") for s in data["sources"]))

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


class AssistantKnowledgeTests(TestCase):
    """Behavioral regressions: real tasks, bounded lookup, fresh rights and data."""

    setUp = AssistantTests.setUp
    post = AssistantTests.post

    def test_cross_page_task_questions_use_the_task_not_current_screen(self):
        tasks = [
            ("Đã mượn hàng muốn trả hàng phải làm sao?", "lệnh mượn gốc", "loans"),
            ("Nhập kho Excel 1000 dòng thế nào?", "1.000 dòng", "receipts"),
            ("Thêm hàng hóa hàng loạt bằng Excel", "500 mã", "products"),
            ("Xuất kho hàng loạt bằng excel", "50 mã", "issues"),
            ("QR tự nhập được không?", "không sửa sau khi đã lưu", "products"),
            ("Tôi cập nhật ảnh sản phẩm ở đâu?", "Danh mục hàng hóa", "products"),
            ("Hóa đơn lần nhập thứ 2 lưu chỗ nào?", "chính phiếu nhập", "receipts"),
            ("Ngày nhập hôm qua được không?", "hôm nay", "receipts"),
            (
                "Kiểm kê bằng QR làm sao?",
                "mỗi lượt quét hợp lệ cộng một đơn vị",
                "stocktakes",
            ),
            ("Không thấy nút duyệt", "cấp, quyền", "approvals"),
            ("Phân quyền nhân viên như thế nào?", "cấp duyệt", "team"),
            ("Chuỗi duyệt sai lệch như thế nào?", "Tổng giám đốc", "deviations"),
            ("Tạo nhóm chat thế nào?", "30 thành viên", "chat"),
            ("API developer key is invalid", "Google Picker", "drive"),
        ]
        for question, expected, topic in tasks:
            with self.subTest(question=question):
                data = self.post(question, page="/").json()
                self.assertEqual(data["scope"], "help")
                self.assertEqual(data["facts"], [])
                self.assertEqual(data["topic"], topic)
                self.assertIn(expected, data["answer"])

    def test_ascii_help_and_unrelated_questions_do_not_list_arbitrary_stock(self):
        for question, expected in [
            ("tra hang da muon lam sao", "lệnh mượn gốc"),
            ("nhap kho excel 1000 dong", "1.000 dòng"),
            ("thoi tiet hom nay", "chưa xác định đủ"),
            ("2 + 2", "chưa xác định đủ"),
        ]:
            data = self.post(question).json()
            self.assertEqual(data["facts"], [])
            self.assertIn(expected, data["answer"])
            self.assertNotIn("AI001", data["answer"])

    def test_current_guides_cover_chat_permissions_and_storage(self):
        for page, title, text in [
            ("/chat/", "Nhắn tin nội bộ", "hội thoại"),
            ("/team/", "Tài khoản & phân quyền", "phân công kho"),
            ("/settings/drive/", "Google Drive", "chọn đúng thư mục"),
            ("/settings/storage/", "Lưu trữ", "Neon"),
        ]:
            data = self.post("Hướng dẫn thao tác tại mục này", page=page).json()
            self.assertEqual(data["page"], title)
            self.assertIn(text, data["answer"])

    def test_links_only_offer_screens_the_account_can_open(self):
        data = self.post("Nhập kho Excel thế nào?").json()
        self.assertEqual(data["sources"], [])
        grant_functions(self.staff, ["assistant_use", "receipts_create"])
        data = self.post("Nhập kho Excel thế nào?").json()
        self.assertEqual(data["sources"][0]["url"], reverse("receipt_import"))
        self.assertEqual(self.client.get(data["sources"][0]["url"]).status_code, 200)
        self.assertEqual(
            self.post("Kết nối Google Drive thế nào?").json()["sources"], []
        )

    def test_live_total_is_complete_within_permissions_and_does_not_mix_units(self):
        Product.objects.bulk_create(
            [Product(sku=f"MANY-{i}", name=f"Thử {i}", unit="Bộ") for i in range(20)]
        )
        Balance.objects.bulk_create(
            [
                Balance(warehouse=self.own, product=p, quantity=2, value=20)
                for p in Product.objects.filter(sku__startswith="MANY-")
            ]
        )
        data = self.post("Tổng giá trị tồn kho hiện tại").json()
        self.assertIn("21 mã hàng", data["answer"])
        self.assertIn("1100 đ", data["answer"])
        self.assertIn("Cái: 7", data["answer"])
        self.assertIn("Bộ: 40", data["answer"])
        self.assertNotIn("999", data["answer"])
        self.assertEqual(data["answer_kind"], "live")
        self.assertFalse(data["can_refine"])

    def test_lookup_name_and_ascii_sku_and_explicit_warehouse(self):
        grant_functions(
            self.staff,
            ["assistant_use", "stock_view", "products_view", "warehouses_view"],
        )
        for question in [
            'Tồn "Máy ảnh"',
            "Máy ảnh còn bao nhiêu?",
            "AI001 còn bao nhiêu tại kho OWN",
            "ton kho AI001",
        ]:
            with self.subTest(question=question):
                data = self.post(question).json()
                self.assertEqual(data["scope"], "stock")
                self.assertEqual(len(data["facts"]), 1)
                self.assertIn("tồn sở hữu 7 Cái", data["answer"])
        self.assertEqual(self.post("Tồn AI001 tại kho SECRET").status_code, 403)
        self.assertEqual(self.post("Tồn AI001 tại kho KHONGCOKHO").status_code, 403)
        self.assertIn("OWN", self.post("Danh sách các kho được xem").json()["answer"])

    def test_repeated_answers_use_new_stock_not_cached_company_data(self):
        first = self.post("Tồn AI001").json()
        Balance.objects.filter(warehouse=self.own, product=self.a).update(quantity=12)
        next_answer = self.post(
            "Vậy còn bao nhiêu?", continuation=first["continuation"]
        ).json()
        self.assertIn("tồn sở hữu 12 Cái", next_answer["answer"])
        self.assertNotIn("tồn sở hữu 7 Cái", next_answer["answer"])

    def test_followup_keeps_sku_and_respects_new_question(self):
        Balance.objects.create(warehouse=self.own, product=self.b, quantity=3, value=30)
        first = self.post("Tồn AI001").json()
        total = self.post(
            "Vậy tổng bao nhiêu?", continuation=first["continuation"]
        ).json()
        self.assertIn("1 mã hàng", total["answer"])
        self.assertIn("700 đ", total["answer"])
        new_sku = self.post(
            "Vậy AI002 còn bao nhiêu?", continuation=total["continuation"]
        ).json()
        self.assertIn("tồn sở hữu 3", new_sku["answer"])
        self.assertNotIn("AI001", new_sku["answer"])
        changed = self.post(
            "Trả hàng mượn thế nào?", continuation=first["continuation"]
        ).json()
        self.assertEqual(changed["scope"], "help")
        self.assertIn("lệnh mượn gốc", changed["answer"])

    def test_continuation_never_overrides_user_page_scope_or_current_rights(self):
        first = self.post("Tồn AI001").json()
        token = first["continuation"]
        self.own.members.remove(self.staff)
        data = self.post("Vậy còn bao nhiêu?", continuation=token).json()
        self.assertEqual(data["facts"], [])
        self.assertNotIn("tồn sở hữu 7", data["answer"])
        self.own.members.add(self.staff)
        self.client.force_login(self.admin)
        private = self.post(f"Phiếu {self.private_doc.pk}").json()["continuation"]
        self.client.force_login(self.staff)
        data = self.post("Vậy tổng bao nhiêu?", continuation=private).json()
        self.assertNotIn(f"#{self.private_doc.pk}", data["answer"])
        data = self.post(
            "Vậy còn bao nhiêu?", continuation=token, warehouse=self.secret.pk
        )
        self.assertEqual(data.status_code, 403)
        self.assertEqual(self.post("Hỏi", continuation=[]).status_code, 400)

    def test_document_lookup_diagnoses_actual_approval_block_without_granting_it(self):
        question = f"Vì sao tôi không duyệt được phiếu {self.doc.pk}?"
        data = self.post(question).json()
        self.assertEqual(data["scope"], "documents")
        self.assertIn("Người lập phiếu không được tự duyệt", data["answer"])
        self.assertFalse(data["can_refine"])
        self.doc.refresh_from_db()
        self.assertEqual(self.doc.status, "DRAFT")
        self.assertNotIn(
            "Tài khoản hiện tại", self.post("Các phiếu chờ duyệt").json()["answer"]
        )

    def test_document_filters_count_all_not_just_display_rows(self):
        Document.objects.bulk_create(
            [
                Document(kind="IN", destination=self.own, created_by=self.staff)
                for _ in range(12)
            ]
        )
        Document.objects.create(
            kind="IN", destination=self.own, created_by=self.staff, status="POSTED"
        )
        data = self.post("Tổng bao nhiêu phiếu nhập chờ duyệt hôm nay?").json()
        self.assertIn("13 phiếu", data["answer"])
        self.assertNotIn("14 phiếu", data["answer"])
        listed = self.post("Các phiếu nhập chờ duyệt").json()
        self.assertEqual(len(listed["sources"]), 8)
        self.assertIn("Có thêm phiếu", listed["answer"])

    def test_drafting_common_business_message_needs_no_model(self):
        data = self.post("Soạn câu nhắc kiểm tra mã hàng, số lượng và đơn giá").json()
        self.assertEqual(data["answer_kind"], "draft")
        self.assertIn("Mẫu nội dung tham khảo", data["answer"])
        self.assertIn("số lượng thực nhận", data["answer"])
        self.assertEqual(data["facts"], [])

    def test_guidance_does_not_claim_unimplemented_modules_or_delete_button(self):
        for question in ["Xóa phiếu kiểm kê thế nào?", "Xóa kiểm kê"]:
            self.assertIn(
                "chưa có thao tác xóa hẳn", self.post(question).json()["answer"]
            )
        data = self.post("Chấm công nhân sự thế nào?").json()
        self.assertIn("chưa có căn cứ", data["answer"])
        self.assertEqual(data["facts"], [])

    def test_lookup_has_bounded_database_round_trips_and_never_calls_network(self):
        from unittest.mock import patch

        from django.db import connection
        from django.test.utils import CaptureQueriesContext

        for question in [
            "Trả hàng mượn làm sao?",
            "Tồn AI001",
            "Tổng tồn kho",
            "Các phiếu chờ duyệt",
        ]:
            with (
                self.subTest(question=question),
                patch(
                    "urllib.request.urlopen",
                    side_effect=AssertionError("No external inference"),
                ),
                CaptureQueriesContext(connection) as captured,
            ):
                data = context_for(self.staff, question, "/products/")
                self.assertLessEqual(len(captured), 12)
                self.assertNotIn("999", data["answer"])
                self.assertTrue(
                    all(q["sql"].lstrip().startswith("SELECT") for q in captured)
                )

    def test_stocktake_live_status_requires_current_function_and_warehouse(self):
        from inventory.models import StocktakeSession

        StocktakeSession.objects.create(
            warehouse=self.own,
            created_by=self.staff,
            status="READY",
            locks_inventory=True,
        )
        StocktakeSession.objects.create(warehouse=self.secret, created_by=self.other)
        self.assertIn(
            "chưa được cấp quyền",
            self.post("Các phiên kiểm kê hiện tại").json()["answer"],
        )
        grant_functions(self.staff, ["assistant_use", "stocktakes_view"])
        data = self.post("Các phiên kiểm kê hiện tại").json()
        self.assertIn("đang khóa kiểm đếm", data["answer"])
        self.assertNotIn("SECRET", data["answer"])
        self.assertEqual(len(data["sources"]), 1)

    def test_document_dates_and_followup_replace_previous_date_filter(self):
        from datetime import timedelta

        from django.utils import timezone

        yesterday = timezone.localdate() - timedelta(days=1)
        Document.objects.create(
            kind="IN",
            destination=self.own,
            created_by=self.staff,
            business_date=yesterday,
        )
        first = self.post("Tổng phiếu nhập hôm nay").json()
        self.assertIn("1 phiếu", first["answer"])
        second = self.post(
            "Vậy hôm qua tổng bao nhiêu phiếu?", continuation=first["continuation"]
        ).json()
        self.assertIn("1 phiếu", second["answer"])
        dated = self.post(f"Tổng phiếu nhập ngày {yesterday:%d/%m/%Y}").json()
        self.assertIn("1 phiếu", dated["answer"])
        self.assertEqual(self.post("Tổng phiếu ngày 31/02/2026").status_code, 400)
        self.assertEqual(
            self.post("Tổng phiếu từ 01/11/2026 đến 01/01/2026").status_code, 400
        )

    def test_historical_stock_is_not_substituted_by_current_balance(self):
        data = self.post("Tồn AI001 hôm qua").json()
        self.assertEqual(data["facts"], [])
        self.assertIn("chưa tính số dư tại ngày quá khứ", data["answer"])
        self.assertNotIn("tồn sở hữu 7", data["answer"])

    def test_catalog_qr_requires_view_right_and_never_returns_stock(self):
        grant_functions(self.staff, ["assistant_use", "products_view"])
        data = self.post("Thông tin mã QR AI001").json()
        self.assertEqual(data["scope"], "catalog")
        self.assertIn(self.a.qr_value, data["answer"])
        self.assertNotIn("tồn sở hữu", data["answer"])
        grant_functions(self.staff, ["assistant_use"])
        data = self.post("Thông tin mã QR AI001").json()
        self.assertEqual(data["facts"], [])
        self.assertNotIn(self.a.qr_value, data["answer"])

    def test_ambiguous_followup_expired_or_tampered_token_requests_identifier(self):
        from unittest.mock import patch

        from django.core import signing

        token = self.post("Tồn AI001").json()["continuation"]
        for bad in ["", token + "changed"]:
            data = self.post(
                "Vậy tổng bao nhiêu?", continuation=bad, page="/stock/"
            ).json()
            self.assertEqual(data["facts"], [])
            self.assertEqual(data["answer_kind"], "clarification")
        with patch(
            "ai_assistant.context.signing.loads", side_effect=signing.SignatureExpired
        ):
            data = context_for(
                self.staff, "Vậy còn bao nhiêu?", "/products/", continuation=token
            )
            self.assertEqual(data["facts"], [])
            self.assertIn("hết hạn", data["answer"])

    def test_warehouse_code_with_digits_is_not_mistaken_for_product_sku(self):
        warehouse = Warehouse.objects.create(code="WH001", name="Kho thử riêng")
        warehouse.members.add(self.staff)
        Balance.objects.create(
            warehouse=warehouse, product=self.a, quantity=4, value=40
        )
        data = self.post("Tồn AI001 tại kho WH001").json()
        self.assertEqual(len(data["facts"]), 1)
        self.assertIn("tồn sở hữu 4", data["answer"])
        self.assertNotIn("tồn sở hữu 7", data["answer"])
        next_answer = self.post(
            "Vậy tổng bao nhiêu?", continuation=data["continuation"]
        ).json()
        self.assertIn("40 đ", next_answer["answer"])
        self.assertNotIn("740 đ", next_answer["answer"])

    def test_suggestion_titles_and_articles_have_real_implementation_evidence(self):
        from pathlib import Path

        from django.conf import settings

        from .knowledge import ARTICLES

        for article in ARTICLES:
            for evidence in article.evidence:
                with self.subTest(article=article.key, evidence=evidence):
                    self.assertTrue((Path(settings.BASE_DIR) / evidence).exists())

    def test_lookup_word_tra_cuu_never_selects_return_kind(self):
        data = self.post("Tra cứu các phiếu nhập đang chờ duyệt").json()
        self.assertEqual(data["scope"], "documents")
        self.assertIn(f"Phiếu #{self.doc.pk}", data["answer"])
        self.assertNotIn("Trả hàng mượn", data["answer"])

    def test_my_documents_filter_is_narrower_than_warehouse_visibility(self):
        Document.objects.create(kind="IN", destination=self.own, created_by=self.other)
        data = self.post("Tổng phiếu nhập của tôi").json()
        self.assertIn("1 phiếu", data["answer"])
        total = self.post("Tổng phiếu nhập").json()
        self.assertIn("2 phiếu", total["answer"])

    def test_new_explicit_document_id_is_not_filtered_by_previous_status(self):
        another = Document.objects.create(
            kind="IN", destination=self.own, created_by=self.staff, status="POSTED"
        )
        first = self.post("Các phiếu nhập chờ duyệt").json()
        data = self.post(
            f"Vậy phiếu {another.pk} trạng thái thế nào?",
            continuation=first["continuation"],
        ).json()
        self.assertIn(f"Phiếu #{another.pk}", data["answer"])
        self.assertIn("Đã ghi sổ", data["answer"])

    def test_submitted_count_uses_same_lock_rule_as_inventory_posting(self):
        from inventory.models import StocktakeSession

        grant_functions(self.staff, ["assistant_use", "stocktakes_view"])
        adjustment = Document.objects.create(
            kind="ADJUST", destination=self.own, created_by=self.staff
        )
        StocktakeSession.objects.create(
            warehouse=self.own,
            created_by=self.staff,
            status="SUBMITTED",
            locks_inventory=True,
            document=adjustment,
        )
        data = self.post("Các phiên kiểm kê hiện tại").json()
        self.assertIn("đang khóa kiểm đếm", data["answer"])
        adjustment.status = "REJECTED"
        adjustment.save(update_fields=["status"])
        data = self.post("Các phiên kiểm kê hiện tại").json()
        self.assertIn("không khóa kiểm đếm", data["answer"])
        guide = self.post("Kiểm kê chốt tồn thế nào?").json()
        self.assertIn("chỉ chốt biên bản chưa tự mở kho", guide["answer"])

    def test_warranty_guidance_does_not_claim_nonexistent_line_fields_or_alerts(self):
        data = self.post("Có cảnh báo hết bảo hành không?").json()
        self.assertIn("chưa có bộ đếm/cảnh báo", data["answer"])
        data = self.post("Tạo phiếu nhập cần điền những gì?").json()
        self.assertIn("chưa có trường bảo hành/lô/serial riêng", data["answer"])

    def test_unknown_questions_never_list_records_due_only_to_current_module(self):
        for page in ["/stock/", "/stocktakes/", "/deviations/", "/products/"]:
            for question in [
                "Thời tiết hôm nay",
                "Hướng dẫn nấu ăn",
                "Kết quả bóng đá hôm nay",
            ]:
                with self.subTest(page=page, question=question):
                    data = self.post(question, page=page).json()
                    self.assertEqual(data["facts"], [])
                    self.assertEqual(data["answer_kind"], "clarification")
                    self.assertIn("chưa xác định đủ", data["answer"])
