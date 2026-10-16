from unittest.mock import patch
from html.parser import HTMLParser
from urllib.parse import parse_qs, urljoin, urlsplit
from django.db import DatabaseError, connection
from hashlib import sha256
from django.contrib.auth import get_user_model
from django.contrib.auth.models import Group, Permission
from django.contrib.admin.models import LogEntry
from django.core.exceptions import PermissionDenied
from django.test import TestCase, Client, override_settings

from .access import FUNCTION_KEYS, has_function
from .models import (
    FunctionAccess,
    Warehouse,
    Product,
    Document,
    Line,
    Balance,
    StoredFile,
    ReceiptAttachment,
)
from .services import can_approve, post_document
from .stocktakes import start_session
from .test_support import grant_functions


class FunctionAccessTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        User = get_user_model()
        cls.admin = User.objects.create_superuser(
            "admin_access", "admin@example.test", "1"
        )
        cls.worker = User.objects.create_user("limited", password="1")
        cls.maker = User.objects.create_user("maker_access", password="1")
        cls.a = Warehouse.objects.create(code="ACCESS-A", name="Kho được giao")
        cls.b = Warehouse.objects.create(code="ACCESS-B", name="Kho ngoài quyền")
        cls.a.members.add(cls.worker, cls.maker)
        cls.p = Product.objects.create(sku="ACCESS-ITEM", name="Hàng kiểm tra quyền")
        Balance.objects.create(warehouse=cls.a, product=cls.p, quantity=5, value=500)
        cls.receipt = cls.doc("IN", cls.a)
        cls.issue = cls.doc("OUT", cls.a)
        cls.foreign = cls.doc("IN", cls.b)
        cls.adjustment = cls.doc("ADJUST", cls.a, quantity=-1)

    @classmethod
    def doc(cls, kind, warehouse, quantity=1):
        doc = Document.objects.create(
            kind=kind,
            created_by=cls.maker,
            source=warehouse if kind == "OUT" else None,
            destination=None if kind == "OUT" else warehouse,
            note="Kiểm tra cấp quyền",
        )
        Line.objects.create(
            document=doc, product=cls.p, quantity=quantity, unit_price=100
        )
        return doc

    def payload(self, kind="IN"):
        return {
            "kind": kind,
            "destination": self.a.pk if kind != "OUT" else "",
            "source": self.a.pk if kind == "OUT" else "",
            "form-TOTAL_FORMS": "1",
            "form-INITIAL_FORMS": "0",
            "form-0-product": self.p.pk,
            "form-0-quantity": "1",
            "form-0-unit_price": "100",
            "note": "Kiểm tra lập phiếu",
        }

    def employee_payload(self, codes=(), revision=0, **extra):
        return {
            "username": self.worker.username,
            "is_active": "on",
            "password": "",
            "access_revision": revision,
            "access_warehouses": [self.a.pk],
            "function_permissions": list(codes),
            **extra,
        }

    def test_admin_has_every_function_without_individual_grants(self):
        self.assertFalse(FunctionAccess.objects.filter(user=self.admin).exists())
        self.assertFalse(self.admin.user_permissions.exists())
        self.assertTrue(all(has_function(self.admin, key) for key in FUNCTION_KEYS))
        self.assertTrue(can_approve(self.adjustment, self.admin))
        self.client.force_login(self.admin)
        for url in [
            "/",
            "/products/",
            "/products/new/",
            "/warehouses/",
            "/warehouses/new/",
            "/team/",
            "/team/new/",
            "/reports/",
            "/ledger/",
            "/stock/",
            "/documents/",
            "/stocktakes/",
            "/approvals/",
            "/settings/drive/",
            "/custom-fields/",
            "/import/receipt/",
        ]:
            with self.subTest(url=url):
                self.assertEqual(self.client.get(url).status_code, 200)
        post_document(self.adjustment.pk, self.admin)
        self.assertEqual(Balance.objects.get(warehouse=self.a).quantity, 4)

    def test_admin_full_access_does_not_bypass_maker_review_separation(self):
        self.receipt.created_by = self.admin
        self.receipt.save()
        with self.assertRaises(PermissionDenied):
            post_document(self.receipt.pk, self.admin)
        self.assertEqual(Balance.objects.get(warehouse=self.a).quantity, 5)

    def test_account_without_grants_has_no_business_pages_or_data(self):
        self.client.force_login(self.worker)
        home = self.client.get("/")
        self.assertContains(home, "Không gian làm việc của bạn")
        self.assertNotContains(home, self.p.sku)
        self.assertNotContains(home, 'id="global-warehouse"')
        for url in [
            "/products/",
            "/warehouses/",
            "/documents/",
            f"/documents/{self.receipt.pk}/",
            "/stock/",
            "/ledger/",
            "/reports/",
            "/loans/",
            "/stocktakes/",
            "/approvals/",
            "/team/",
            "/team/new/",
            "/import/receipt/",
            "/custom-fields/",
            "/api/availability/?warehouse=" + str(self.a.pk),
        ]:
            with self.subTest(url=url):
                self.assertEqual(self.client.get(url).status_code, 403)
        self.assertEqual(self.client.get("/account/password/").status_code, 200)

    def test_admin_grants_receipts_without_granting_issue_or_approval(self):
        self.client.force_login(self.admin)
        r = self.client.post(
            f"/team/{self.worker.pk}/edit/", self.employee_payload(["receipts_create"])
        )
        self.assertEqual(r.status_code, 302)
        self.client.force_login(self.worker)
        page = self.client.get("/operations/in/")
        self.assertEqual(page.status_code, 200)
        self.assertNotContains(page, 'href="/operations/out/"')
        self.assertNotContains(page, 'href="/approvals/"')
        self.assertEqual(
            self.client.post("/operations/in/", self.payload()).status_code, 302
        )
        count = Document.objects.count()
        for url in ["/operations/out/", "/documents/new/"]:
            self.assertEqual(
                self.client.post(url, self.payload("OUT")).status_code, 403
            )
        self.assertEqual(Document.objects.count(), count)
        self.assertEqual(
            self.client.post(f"/documents/{self.receipt.pk}/post/").status_code, 403
        )

    def test_view_only_permission_cannot_create_edit_or_cancel(self):
        grant_functions(self.worker, {"receipts_view"})
        self.client.force_login(self.worker)
        self.assertEqual(
            self.client.get(f"/documents/{self.receipt.pk}/").status_code, 200
        )
        self.assertEqual(self.client.get("/documents/?kind=IN").status_code, 200)
        self.assertEqual(self.client.get("/documents/").status_code, 403)
        for url in [
            "/operations/in/",
            f"/documents/{self.receipt.pk}/edit/",
            f"/documents/{self.receipt.pk}/close/cancel/",
        ]:
            self.assertEqual(self.client.post(url, self.payload()).status_code, 403)
        self.receipt.refresh_from_db()
        self.assertEqual(self.receipt.status, "DRAFT")

    def test_permission_and_warehouse_assignment_are_both_required_to_approve(self):
        self.a.managers.add(self.worker)
        grant_functions(self.worker, {"receipts_view"})
        self.assertFalse(can_approve(self.receipt, self.worker))
        grant_functions(self.worker, {"receipts_approve"})
        self.assertTrue(can_approve(self.receipt, self.worker))
        self.assertFalse(can_approve(self.foreign, self.worker))
        self.client.force_login(self.worker)
        self.assertEqual(
            self.client.get(f"/documents/{self.foreign.pk}/").status_code, 404
        )
        self.a.managers.remove(self.worker)
        self.assertFalse(can_approve(self.receipt, self.worker))

    def test_read_only_receipt_navigation_keeps_allowed_document_type(self):
        class Links(HTMLParser):
            def __init__(self):
                super().__init__()
                self.links = {}
                self.href = None
                self.label = ""

            def handle_starttag(self, tag, attrs):
                if tag == "a":
                    self.href = dict(attrs).get("href")
                    self.label = ""

            def handle_data(self, data):
                if self.href is not None:
                    self.label += data

            def handle_endtag(self, tag):
                if tag == "a" and self.href is not None:
                    self.links[self.label.strip()] = self.href
                    self.href = None

        grant_functions(self.worker, {"receipts_view"})
        self.client.force_login(self.worker)
        response = self.client.get("/documents/?kind=IN&q=absent&status=DRAFT")
        self.assertEqual(response.status_code, 200)
        self.assertNotContains(response, 'value="">Tất cả nghiệp vụ')
        parser = Links()
        parser.feed(response.content.decode())
        for label in [
            "Tất cả phiếu",
            "Phiếu tôi lập",
            "Chờ duyệt",
            "Chờ nhận hàng",
            "Hoàn tất",
            "Yêu cầu sửa",
            "Đã hủy",
            "Xóa bộ lọc",
        ]:
            with self.subTest(label=label):
                target = urljoin("/documents/?kind=IN", parser.links[label])
                self.assertEqual(parse_qs(urlsplit(target).query)["kind"], ["IN"])
                page = self.client.get(target)
                self.assertEqual(page.status_code, 200)
                self.assertNotContains(page, f'href="/documents/{self.issue.pk}/"')
                self.assertNotContains(page, f'href="/documents/{self.foreign.pk}/"')
        reset = self.client.get(parser.links["Xóa bộ lọc"])
        self.assertContains(reset, f'href="/documents/{self.receipt.pk}/"')

    def test_document_list_filters_out_ungranted_types_even_with_forged_filter(self):
        grant_functions(self.worker, {"documents_view", "receipts_view"})
        self.client.force_login(self.worker)
        self.assertNotContains(
            self.client.get("/documents/?kind=OUT"),
            f'href="/documents/{self.issue.pk}/"',
        )
        self.assertEqual(
            self.client.get(f"/documents/{self.issue.pk}/").status_code, 403
        )

    def test_role_or_model_permission_cannot_restore_revoked_function(self):
        role = Group.objects.create(name="Nhóm rộng")
        role.permissions.set(
            Permission.objects.filter(content_type__app_label="inventory")
        )
        self.worker.groups.add(role)
        self.worker.user_permissions.set(
            Permission.objects.filter(content_type__app_label="inventory")
        )
        grant_functions(self.worker, set())
        self.client.force_login(self.worker)
        for url in ["/operations/in/", "/products/", "/reports/", "/stocktakes/"]:
            self.assertEqual(self.client.get(url).status_code, 403)

    def test_revocation_blocks_an_already_logged_in_account_next_request(self):
        grant_functions(self.worker, {"receipts_create"})
        self.client.force_login(self.worker)
        self.assertEqual(self.client.get("/operations/in/").status_code, 200)
        admin_client = Client()
        admin_client.force_login(self.admin)
        self.assertEqual(
            admin_client.post(
                f"/team/{self.worker.pk}/edit/", self.employee_payload([], revision=1)
            ).status_code,
            302,
        )
        self.assertEqual(
            self.client.post("/operations/in/", self.payload()).status_code, 403
        )

    def test_export_is_separate_from_view_permission(self):
        grant_functions(self.worker, {"stock_view"})
        self.client.force_login(self.worker)
        page = self.client.get("/stock/")
        self.assertContains(page, self.p.sku)
        self.assertNotContains(page, 'name="export"')
        self.assertEqual(self.client.get("/stock/?export=1").status_code, 403)
        grant_functions(self.worker, {"stock_view", "tools_export"})
        csv = self.client.get("/stock/?export=1")
        self.assertEqual(csv.status_code, 200)
        self.assertIn(self.p.sku.encode(), csv.content)

    @override_settings(DEBUG=True)
    def test_product_view_does_not_expose_stock_or_invoice_files(self):
        grant_functions(self.worker, {"products_view"})
        data = b"private-invoice-example"
        file = StoredFile.objects.create(
            sha256=sha256(data).hexdigest(),
            context_key="receipt:permission",
            data=data,
            size=len(data),
            content_type="application/pdf",
        )
        ReceiptAttachment.objects.create(
            document=self.receipt,
            file=file,
            filename="private.pdf",
            invoice_number="PRIVATE-INVOICE",
            uploaded_by=self.admin,
        )
        self.client.force_login(self.worker)
        page = self.client.get(f"/products/{self.p.pk}/")
        self.assertNotContains(page, "Tồn tại các kho")
        self.assertNotContains(page, "PRIVATE-INVOICE")
        self.assertNotContains(page, "In tem QR")
        self.assertEqual(self.client.get(f"/files/{file.pk}/").status_code, 404)
        grant_functions(self.worker, {"files_view"})
        self.assertEqual(self.client.get(f"/files/{file.pk}/").status_code, 200)
        self.assertEqual(
            self.client.post(
                f"/attachments/{file.receiptattachment_set.get().pk}/void/",
                {"reason": "Không được xóa"},
            ).status_code,
            403,
        )

    def test_warehouse_catalog_editor_cannot_change_access_assignments(self):
        grant_functions(self.worker, {"warehouses_edit"})
        self.a.managers.add(self.admin)
        self.client.force_login(self.worker)
        response = self.client.post(
            f"/warehouses/{self.a.pk}/edit/",
            {
                "code": self.a.code,
                "name": "Tên kho được sửa",
                "address": "",
                "managers": [self.worker.pk],
                "members": [self.maker.pk],
                "issue_approvers": [self.worker.pk],
            },
        )
        self.assertEqual(response.status_code, 302)
        self.assertTrue(self.a.managers.filter(pk=self.admin.pk).exists())
        self.assertFalse(self.a.managers.filter(pk=self.worker.pk).exists())
        self.assertTrue(self.a.members.filter(pk=self.worker.pk).exists())
        self.assertFalse(self.a.issue_approvers.filter(pk=self.worker.pk).exists())

    def test_staff_flag_cannot_bypass_company_admin_controls(self):
        self.worker.is_staff = True
        self.worker.save()
        self.worker.user_permissions.set(Permission.objects.all())
        self.client.force_login(self.worker)
        self.assertEqual(self.client.get("/admin/").status_code, 302)
        self.assertEqual(
            self.client.post(
                f"/team/{self.worker.pk}/edit/",
                self.employee_payload(FUNCTION_KEYS, is_superuser="on"),
            ).status_code,
            403,
        )
        self.worker.refresh_from_db()
        self.assertFalse(self.worker.is_superuser)

    def test_stale_permission_edit_does_not_overwrite_or_change_password(self):
        self.client.force_login(self.admin)
        first = self.employee_payload(["receipts_create"], password="new-password")
        self.assertEqual(
            self.client.post(f"/team/{self.worker.pk}/edit/", first).status_code, 302
        )
        stale = self.employee_payload(["issues_create"], password="stale-password")
        response = self.client.post(f"/team/{self.worker.pk}/edit/", stale)
        self.assertContains(response, "không ghi đè bản mới")
        self.worker.refresh_from_db()
        self.assertTrue(self.worker.check_password("new-password"))
        self.assertTrue(has_function(self.worker, "receipts_create"))
        self.assertFalse(has_function(self.worker, "issues_create"))
        self.assertEqual(
            LogEntry.objects.filter(
                object_id=str(self.worker.pk), content_type__model="user"
            ).count(),
            1,
        )
        self.assertNotIn("new-password", LogEntry.objects.latest("id").change_message)

    def test_invalid_grants_and_csrf_fail_without_partial_updates(self):
        self.client.force_login(self.admin)
        r = self.client.post(
            f"/team/{self.worker.pk}/edit/", self.employee_payload(["admin_all"])
        )
        self.assertEqual(r.status_code, 200)
        self.assertFalse(FunctionAccess.objects.filter(user=self.worker).exists())
        client = Client(enforce_csrf_checks=True)
        client.force_login(self.admin)
        self.assertEqual(
            client.post(
                f"/team/{self.worker.pk}/edit/",
                self.employee_payload(["receipts_create"]),
            ).status_code,
            403,
        )

    def test_counting_cannot_continue_after_function_is_revoked(self):
        grant_functions(self.worker, {"stocktakes_create"})
        session = start_session(self.a, self.worker)
        grant_functions(self.worker, {"stocktakes_view"})
        self.client.force_login(self.worker)
        page = self.client.get(f"/stocktakes/{session.pk}/")
        self.assertEqual(page.status_code, 200)
        self.assertNotContains(
            page, 'action="/stocktakes/' + str(session.pk) + '/cancel/"'
        )
        self.assertEqual(
            self.client.post(f"/stocktakes/{session.pk}/count/", {}).status_code, 403
        )
        self.assertEqual(
            self.client.post(
                f"/stocktakes/{session.pk}/cancel/", {"reason": "Không còn quyền"}
            ).status_code,
            403,
        )
        self.assertIsNone(session.items.get().counted_quantity)

    def test_team_view_is_read_only_and_cannot_grant_permissions(self):
        grant_functions(self.worker, {"team_view"})
        self.client.force_login(self.worker)
        page = self.client.get("/team/")
        self.assertEqual(page.status_code, 200)
        self.assertNotContains(page, 'href="/team/new/"')
        self.assertNotContains(page, f'href="/team/{self.worker.pk}/edit/"')
        self.assertEqual(
            self.client.get(f"/team/{self.worker.pk}/edit/").status_code, 403
        )

    def test_release_health_checks_database_and_hides_connection_errors(self):
        if connection.vendor == "postgresql":
            with override_settings(DEBUG=False):
                self.assertEqual(self.client.get("/healthz/").status_code, 503)
        with override_settings(DEBUG=True):
            response = self.client.get("/healthz/")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["status"], "ok")
        with patch(
            "config.health.connection.cursor",
            side_effect=DatabaseError("private-database-details"),
        ):
            response = self.client.get("/healthz/")
        self.assertEqual(response.status_code, 503)
        self.assertNotIn(b"private-database-details", response.content)
        self.assertEqual(response["Cache-Control"], "no-store")
