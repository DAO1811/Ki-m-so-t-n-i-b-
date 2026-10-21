from concurrent.futures import ThreadPoolExecutor
from threading import Event
from unittest import skipUnless

from django.contrib.admin.models import LogEntry
from django.contrib.auth import get_user_model
from django.core.exceptions import PermissionDenied
from django.db import connection, connections, transaction
from django.db.migrations.executor import MigrationExecutor
from django.test import TestCase, TransactionTestCase
from psycopg import sql

from .access import FUNCTION_KEYS
from .models import (
    Balance,
    CustomField,
    Document,
    FunctionAccess,
    Line,
    Product,
    Warehouse,
)
from .services import approval_documents_for, can_approve, post_document
from .test_support import grant_functions


class HierarchyTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        User = get_user_model()
        cls.admin = User.objects.create_superuser(
            "hier-admin", "hier@example.test", "1"
        )
        cls.staff = User.objects.create_user("hier-staff", password="1")
        cls.leader = User.objects.create_user("hier-leader", password="1")
        cls.head = User.objects.create_user("hier-head", password="1")
        cls.other = User.objects.create_user("hier-other", password="1")
        cls.users = [(cls.staff, 10), (cls.leader, 20), (cls.head, 30), (cls.admin, 40)]
        cls.a = Warehouse.objects.create(code="HIER-A", name="Hierarchy A")
        cls.b = Warehouse.objects.create(code="HIER-B", name="Hierarchy B")
        cls.product = Product.objects.create(sku="HIER", name="Hierarchy item")
        for user, level in cls.users[:-1]:
            grant_functions(user, FUNCTION_KEYS, level=level)
            cls.a.members.add(user)
            cls.a.managers.add(user)
            cls.a.issue_approvers.add(user)
        grant_functions(cls.other, FUNCTION_KEYS, level=30)

    def doc(self, maker, kind="IN", status="DRAFT", warehouse=None):
        warehouse = warehouse or self.a
        doc = Document.objects.create(
            kind=kind,
            status=status,
            created_by=maker,
            note="Kiểm tra phân cấp",
            source=warehouse if kind in ["OUT", "TRANSFER", "LOAN", "RETURN"] else None,
            destination=self.b
            if kind in ["TRANSFER", "LOAN", "RETURN"]
            else warehouse
            if kind != "OUT"
            else None,
        )
        Line.objects.create(
            document=doc, product=self.product, quantity=1, unit_price=100
        )
        return doc

    def test_approval_matrix_all_kinds_and_both_transfer_stages(self):
        for kind in ["IN", "OUT", "TRANSFER", "LOAN", "RETURN", "ADJUST", "COUNT"]:
            for maker, maker_level in self.users:
                doc = self.doc(maker, kind)
                for reviewer, reviewer_level in self.users:
                    with self.subTest(
                        kind=kind, maker=maker_level, reviewer=reviewer_level
                    ):
                        self.assertEqual(
                            can_approve(doc, reviewer),
                            reviewer.is_superuser or reviewer_level > maker_level,
                        )
                        self.assertEqual(
                            approval_documents_for(reviewer).filter(pk=doc.pk).exists(),
                            can_approve(doc, reviewer),
                        )
                if kind in ["TRANSFER", "LOAN", "RETURN"]:
                    doc.status = "TRANSIT"
                    doc.destination = self.a
                    doc.save()
                    for reviewer, level in self.users:
                        self.assertEqual(
                            can_approve(doc, reviewer),
                            reviewer.is_superuser or level > maker_level,
                        )
                        self.assertEqual(
                            approval_documents_for(reviewer).filter(pk=doc.pk).exists(),
                            can_approve(doc, reviewer),
                        )

    def test_ordinary_self_same_or_lower_cannot_change_stock_even_with_confirmation(
        self,
    ):
        doc = self.doc(self.head)
        for reviewer in [self.head, self.staff, self.leader]:
            with self.assertRaises(PermissionDenied):
                post_document(doc.pk, reviewer, confirm_self_approval=True)
        self.assertFalse(Balance.objects.exists())
        doc.refresh_from_db()
        self.assertEqual(doc.status, "DRAFT")

    def test_admin_self_approval_requires_acknowledgment_and_audits_once(self):
        doc = self.doc(self.admin)
        self.client.force_login(self.admin)
        page = self.client.get(f"/documents/{doc.pk}/")
        self.assertContains(page, 'name="confirm_self_approval"')
        self.assertContains(page, "Bạn đang tự duyệt phiếu của mình.")
        self.client.post(
            f"/documents/{doc.pk}/post/",
            {"expected_status": "DRAFT", "expected_revision": 1},
        )
        self.assertFalse(Balance.objects.exists())
        self.client.post(
            f"/documents/{doc.pk}/post/",
            {
                "confirm_self_approval": "yes",
                "expected_status": "DRAFT",
                "expected_revision": 1,
            },
        )
        doc.refresh_from_db()
        self.assertEqual(doc.status, "POSTED")
        self.assertEqual(Balance.objects.get().quantity, 1)
        event = doc.events.get(action="POST")
        self.assertTrue(event.snapshot["admin_self_approved"])
        self.assertEqual(event.snapshot["actor_level"], 40)
        self.client.post(
            f"/documents/{doc.pk}/post/",
            {
                "confirm_self_approval": "yes",
                "expected_status": "DRAFT",
                "expected_revision": 1,
            },
        )
        self.assertEqual(Balance.objects.get().quantity, 1)
        self.assertEqual(doc.events.filter(action="POST").count(), 1)
        self.assertContains(
            self.client.get(f"/documents/{doc.pk}/"), "Admin tổng tự duyệt"
        )

    def test_higher_rank_still_needs_function_and_warehouse_grants(self):
        doc = self.doc(self.staff)
        self.assertFalse(can_approve(doc, self.other))
        self.a.managers.add(self.other)
        self.assertTrue(can_approve(doc, self.other))
        grant_functions(self.other, {"receipts_view"}, level=30)
        self.assertFalse(can_approve(doc, self.other))
        self.assertFalse(approval_documents_for(self.other).filter(pk=doc.pk).exists())

    def test_maker_demotion_does_not_lower_old_document_requirement(self):
        doc = self.doc(self.head)
        FunctionAccess.objects.filter(user=self.head).update(approval_level=10)
        self.assertFalse(can_approve(doc, self.leader))
        self.assertFalse(approval_documents_for(self.leader).filter(pk=doc.pk).exists())
        self.assertTrue(can_approve(doc, self.admin))

    def test_maker_promotion_applies_to_pending_documents_and_inactive_reviewer_denied(
        self,
    ):
        doc = self.doc(self.staff)
        FunctionAccess.objects.filter(user=self.staff).update(approval_level=30)
        self.assertFalse(can_approve(doc, self.leader))
        self.assertFalse(approval_documents_for(self.leader).filter(pk=doc.pk).exists())
        self.leader.is_active = False
        self.leader.save()
        self.assertFalse(can_approve(doc, self.leader))

    def test_admin_monitoring_includes_own_rejected_and_completed_records(self):
        own = self.doc(self.admin)
        rejected = self.doc(self.head, status="REJECTED", warehouse=self.b)
        posted = self.doc(self.staff, status="POSTED")
        self.client.force_login(self.admin)
        page = self.client.get("/approvals/?warehouse=")
        self.assertContains(page, f"PK-{own.pk:06d}")
        self.assertContains(page, f"PK-{rejected.pk:06d}")
        self.assertNotContains(page, f"PK-{posted.pk:06d}")
        self.assertContains(
            self.client.get("/approvals/?status=POSTED"), f"PK-{posted.pk:06d}"
        )
        self.assertContains(
            self.client.get("/documents/?warehouse="), f"PK-{posted.pk:06d}"
        )
        self.client.force_login(self.leader)
        self.assertNotContains(
            self.client.get("/approvals/?scope=all"), f"PK-{own.pk:06d}"
        )
        self.assertEqual(self.client.get(f"/documents/{rejected.pk}/").status_code, 404)

    def payload(self, **extra):
        return dict(
            username="hier-other",
            job_title="Trưởng phòng mua hàng",
            approval_level=30,
            function_permissions=["receipts_approve", "receipts_create"],
            is_active="on",
            managed_warehouses=[self.a.pk],
            access_warehouses=[self.a.pk],
            access_revision=1,
            **extra,
        )

    def test_employee_title_rank_grants_saved_together_and_logged(self):
        self.client.force_login(self.admin)
        self.assertEqual(
            self.client.post(
                f"/team/{self.other.pk}/edit/", self.payload()
            ).status_code,
            302,
        )
        access = FunctionAccess.objects.get(user=self.other)
        self.assertEqual(access.job_title, "Trưởng phòng mua hàng")
        self.assertEqual(access.approval_level, 30)
        self.assertIn("approval_level", LogEntry.objects.latest("id").change_message)
        stale = self.payload()
        stale["approval_level"] = 20
        self.assertEqual(
            self.client.post(f"/team/{self.other.pk}/edit/", stale).status_code, 200
        )
        access.refresh_from_db()
        self.assertEqual(access.approval_level, 30)

    def test_admin_cannot_accidentally_grant_staff_approval_or_make_rank_admin(self):
        self.client.force_login(self.admin)
        for level in [10, 40]:
            payload = self.payload()
            payload["approval_level"] = level
            self.assertEqual(
                self.client.post(f"/team/{self.other.pk}/edit/", payload).status_code,
                200,
            )
        access = FunctionAccess.objects.get(user=self.other)
        self.assertEqual(access.approval_level, 30)
        self.other.refresh_from_db()
        self.assertFalse(self.other.is_superuser)

    def test_admin_form_displays_admin_rank_and_does_not_downgrade_it(self):
        self.client.force_login(self.admin)
        page = self.client.get(f"/team/{self.admin.pk}/edit/")
        self.assertContains(page, "Admin tổng · Toàn quyền")
        response = self.client.post(
            f"/team/{self.admin.pk}/edit/",
            {
                "username": self.admin.username,
                "is_active": "on",
                "access_revision": 0,
                "approval_level": 10,
                "job_title": "Quản trị công ty",
            },
        )
        self.assertEqual(response.status_code, 302)
        self.admin.refresh_from_db()
        self.assertTrue(self.admin.is_superuser)
        self.assertTrue(can_approve(self.doc(self.admin), self.admin))

    def test_custom_field_create_and_rename_preserve_product_data(self):
        self.client.force_login(self.admin)
        self.assertEqual(
            self.client.post("/custom-fields/", {"label": "Xuất xứ"}).status_code, 302
        )
        field = CustomField.objects.get(label="Xuất xứ")
        original_key = field.key
        self.product.extra = {original_key: "Việt Nam"}
        self.product.save()
        self.assertEqual(
            self.client.post(
                "/custom-fields/", {"field_id": field.pk, "label": "Nước sản xuất"}
            ).status_code,
            302,
        )
        field.refresh_from_db()
        self.product.refresh_from_db()
        self.assertEqual(field.key, original_key)
        self.assertEqual(self.product.extra[original_key], "Việt Nam")
        self.assertContains(
            self.client.get(f"/products/{self.product.pk}/edit/"), "Nước sản xuất"
        )
        self.assertNotContains(self.client.get("/custom-fields/"), 'name="key"')
        response = self.client.post("/custom-fields/", {"label": "Nước sản xuất"})
        self.assertEqual(response.status_code, 200)
        self.assertEqual(CustomField.objects.count(), 1)
        self.assertContains(response, "Tên thông tin này đã có")




class HierarchyMigrationTests(TransactionTestCase):
    def test_schema_0016_accounts_documents_drive_and_values_survive(self):
        from . import release_backup as backup

        old = [("inventory", "0016_preserve_assigned_function_access")]
        latest = [("inventory", "0018_product_qr_stocktake_workflow")]
        try:
            executor = MigrationExecutor(connection)
            executor.migrate(old)
            apps = executor.loader.project_state(old).apps
            User = apps.get_model("auth", "User")
            Access = apps.get_model("inventory", "FunctionAccess")
            Doc = apps.get_model("inventory", "Document")
            Wh = apps.get_model("inventory", "Warehouse")
            Drive = apps.get_model("inventory", "DriveConnection")
            manager = User.objects.create(
                username="hier-legacy-head", password="retain-hash"
            )
            staff = User.objects.create(username="hier-legacy-staff")
            admin = User.objects.create(username="hier-legacy-admin", is_superuser=True)
            Access.objects.create(
                user_id=manager.pk,
                permissions=["receipts_approve", "receipts_view"],
                revision=7,
            )
            wh = Wh.objects.create(code="HIER-OLD", name="Kho cũ")
            legacy_doc = Doc.objects.create(
                kind="IN", destination=wh, created_by=manager
            )
            admin_doc = Doc.objects.create(kind="IN", destination=wh, created_by=admin)
            Drive.objects.create(
                account_email="owner@example.test",
                encrypted_refresh_token="retain-encrypted-token",
                connected_by=admin,
                folder_id="retain-root",
            )
            if connection.vendor == "postgresql":
                with backup.deploy_connection() as db:
                    manifest = backup.ensure_snapshot(db)
                    self.assertIn(
                        "0016_preserve_assigned_function_access",
                        [
                            row[1]
                            for row in manifest["migrations"]
                            if row[0] == "inventory"
                        ],
                    )
            MigrationExecutor(connection).migrate(latest)
            self.assertEqual(
                FunctionAccess.objects.get(user_id=manager.pk).approval_level, 30
            )
            self.assertEqual(FunctionAccess.objects.get(user_id=manager.pk).revision, 7)
            self.assertEqual(
                FunctionAccess.objects.get(user_id=staff.pk).approval_level, 10
            )
            self.assertEqual(
                FunctionAccess.objects.get(user_id=staff.pk).permissions, []
            )
            self.assertEqual(Document.objects.get(pk=legacy_doc.pk).creator_level, 30)
            self.assertEqual(Document.objects.get(pk=admin_doc.pk).creator_level, 40)
            self.assertEqual(
                get_user_model().objects.get(pk=manager.pk).password, "retain-hash"
            )
            from .models import DriveConnection

            self.assertEqual(
                DriveConnection.objects.get().encrypted_refresh_token,
                "retain-encrypted-token",
            )
            self.assertEqual(DriveConnection.objects.get().folder_id, "retain-root")
        finally:
            MigrationExecutor(connection).migrate(latest)
            if connection.vendor == "postgresql":
                with backup.direct_connection() as db:
                    db.execute(
                        sql.SQL("DROP SCHEMA IF EXISTS {} CASCADE").format(
                            sql.Identifier(backup.SNAPSHOT_SCHEMA)
                        )
                    )


@skipUnless(connection.vendor == "postgresql", "PostgreSQL row locks")
class HierarchyConcurrencyTests(TransactionTestCase):
    def test_approval_waits_for_account_change_and_uses_new_rank(self):
        User = get_user_model()
        maker = User.objects.create_user("hier-lock-maker")
        reviewer = User.objects.create_user("hier-lock-reviewer")
        grant_functions(maker, {"receipts_create"}, level=10)
        grant_functions(reviewer, {"receipts_approve"}, level=30)
        wh = Warehouse.objects.create(code="HIER-LOCK", name="Lock test")
        wh.managers.add(reviewer)
        doc = Document.objects.create(kind="IN", destination=wh, created_by=maker)
        product = Product.objects.create(sku="HIER-LOCK", name="Lock product")
        Line.objects.create(document=doc, product=product, quantity=1, unit_price=100)
        ready = Event()

        def approve():
            connections.close_all()
            try:
                ready.set()
                post_document(doc.pk, reviewer)
                return "approved"
            except PermissionDenied:
                return "denied"
            finally:
                connections.close_all()

        with ThreadPoolExecutor(max_workers=1) as pool:
            with transaction.atomic():
                User.objects.select_for_update().get(pk=reviewer.pk)
                FunctionAccess.objects.filter(user=reviewer).update(approval_level=10)
                future = pool.submit(approve)
                self.assertTrue(ready.wait(5))
            self.assertEqual(future.result(timeout=10), "denied")
        self.assertFalse(Balance.objects.exists())
        doc.refresh_from_db()
        self.assertEqual(doc.status, "DRAFT")
