"""Trợ lý AI v2 lookups: each tool honours the asker's grants and warehouses."""

import json

from django.contrib.auth import get_user_model
from django.db import connection
from django.test import TestCase
from django.test.utils import CaptureQueriesContext

from inventory.models import Balance, Document, Line, Product, Warehouse
from inventory.services import post_document
from inventory.test_support import grant_functions

from . import tools

SECRET = "987654"


class ToolPermissionTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        User = get_user_model()
        cls.admin = User.objects.create_superuser("tool-admin")
        cls.staff = User.objects.create_user("tool-staff")
        cls.bare = User.objects.create_user("tool-bare")
        grant_functions(
            cls.staff,
            [
                "assistant_use",
                "products_view",
                "stock_view",
                "ledger_view",
                "receipts_view",
                "warehouses_view",
            ],
        )
        grant_functions(cls.bare, ["assistant_use"])
        cls.own = Warehouse.objects.create(code="OWN", name="Kho được cấp")
        cls.secret = Warehouse.objects.create(code="SECRET", name="Kho ngoài quyền")
        cls.own.members.add(cls.staff, cls.bare)
        cls.product = Product.objects.create(sku="AI001", name="Máy ảnh", minimum=10)
        for warehouse, qty in ((cls.own, 7), (cls.secret, 987654)):
            doc = Document.objects.create(
                kind="IN", destination=warehouse, created_by=cls.admin
            )
            Line.objects.create(
                document=doc, product=cls.product, quantity=qty, unit_price=1
            )
            post_document(doc.pk, cls.admin, confirm_self_approval=True)
        cls.secret_doc = Document.objects.create(
            kind="IN", destination=cls.secret, created_by=cls.admin
        )

    def run_tool(self, user, name, **args):
        return tools.execute(user, name, json.dumps(args))

    def test_stock_ledger_and_documents_never_show_other_warehouses(self):
        for name, args in [
            ("stock", {"sku": "AI001"}),
            ("stock", {"filter": "below_minimum"}),
            ("stock_ledger", {"sku": "AI001"}),
            ("document_search", {}),
            ("warehouses", {}),
        ]:
            with self.subTest(name=name):
                result = self.run_tool(self.staff, name, **args)
                self.assertNotIn("SECRET", result.text)
                self.assertNotIn(SECRET, result.text)
        self.assertIn("tồn 7", self.run_tool(self.staff, "stock", sku="AI001").text)
        self.assertIn(
            "ngoài phạm vi",
            self.run_tool(self.staff, "stock", warehouse_code="SECRET").text,
        )
        self.assertIn(
            "Không có phiếu",
            self.run_tool(
                self.staff, "document_detail", number=f"PK-{self.secret_doc.pk:06d}"
            ).text,
        )

    def test_missing_grants_are_refused_for_every_data_tool(self):
        for name in [
            "product_search",
            "stock",
            "stock_ledger",
            "stocktakes",
            "loans",
            "warehouses",
        ]:
            with self.subTest(name=name):
                result = self.run_tool(self.bare, name)
                self.assertIn("chưa được cấp quyền", result.text)
                self.assertEqual(result.rows, 0)
        self.assertIn("0 phiếu", self.run_tool(self.bare, "document_search").text)
        self.assertIn("0 phiếu", self.run_tool(self.bare, "my_pending_approvals").text)

    def test_admin_sees_everything_it_can_already_see(self):
        result = self.run_tool(self.admin, "stock", sku="AI001")
        self.assertIn("SECRET", result.text)

    def test_bad_arguments_are_rejected_without_queries(self):
        for name, args in [
            ("stock", {"filter": "drop table"}),
            ("document_search", {"kind": "HACK"}),
            ("document_search", {"date_from": "yesterday"}),
            ("document_detail", {"number": "abc"}),
            ("deviations", {"code": "x"}),
            ("stock", {"sku": ["list"]}),
        ]:
            with self.subTest(name=name, args=args):
                result = self.run_tool(self.admin, name, **args)
                self.assertEqual(result.rows, 0)
        self.assertIn("không hợp lệ", tools.execute(self.admin, "stock", "[1]").text)

    def test_lookups_are_select_only_and_bounded(self):
        Product.objects.bulk_create(
            Product(sku=f"MANY-{i}", name=f"Nhiều {i}") for i in range(80)
        )
        with CaptureQueriesContext(connection) as captured:
            for name in tools.TOOLS:
                self.run_tool(self.admin, name, question="trả hàng mượn")
        self.assertTrue(
            all(
                q["sql"].lstrip().upper().startswith(("SELECT", "SAVEPOINT", "RELEASE"))
                for q in captured
            )
        )
        result = self.run_tool(self.admin, "product_search")
        self.assertLessEqual(result.rows, tools.MAX_ROWS)
        self.assertLessEqual(len(result.text.encode()), tools.MAX_TEXT_BYTES + 200)

    def test_guide_tool_answers_how_to_questions(self):
        result = self.run_tool(
            self.bare, "user_guide", question="trả hàng mượn thế nào"
        )
        self.assertIn("Trả hàng", result.text)

    def test_specs_are_valid_function_schemas(self):
        names = [spec["function"]["name"] for spec in tools.specs()]
        self.assertEqual(names, list(tools.TOOLS))
        for spec in tools.specs():
            self.assertEqual(spec["type"], "function")
            self.assertFalse(spec["function"]["parameters"]["additionalProperties"])
        self.assertLess(len(json.dumps(tools.specs(), ensure_ascii=False)), 6000)


class BalanceUnchangedTests(TestCase):
    def test_module_has_no_write_calls(self):
        source = open(tools.__file__, encoding="utf-8").read()
        for word in (".save(", ".delete(", ".update(", ".create(", "bulk_"):
            self.assertNotIn(word, source)
        self.assertFalse(Balance.objects.exists())


class AuditAdminTests(TestCase):
    def test_admin_can_read_but_not_change_the_lookup_log(self):
        import uuid

        from .models import ChatToolAudit

        admin = get_user_model().objects.create_superuser("audit-admin")
        ChatToolAudit.objects.create(
            owner_id=admin.pk, job_id=uuid.uuid4(), tool="stock", rows=3
        )
        self.client.force_login(admin)
        page = self.client.get("/admin/ai_assistant/chattoolaudit/")
        self.assertContains(page, "audit-admin")
        self.assertContains(page, "stock")
        self.assertEqual(
            self.client.get("/admin/ai_assistant/chattoolaudit/add/").status_code, 403
        )
