from decimal import Decimal
from io import StringIO
from uuid import uuid4
from django.test import TestCase
from django.contrib.auth import get_user_model
from django.contrib.auth.models import Group
from django.core.management import call_command
from django.core.exceptions import ValidationError
from .models import (
    Warehouse,
    Product,
    Document,
    Line,
    Balance,
    CustomField,
)
from .services import post_document


class WorkspaceTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        User = get_user_model()
        cls.admin = User.objects.create_superuser("admin", "admin@example.test", "a")
        cls.worker = User.objects.create_user("worker", password="a")
        cls.manager = User.objects.create_user("manager", password="a")
        cls.other = User.objects.create_user("other", password="a")
        call_command("setup_roles", stdout=StringIO())
        cls.worker.groups.add(Group.objects.get(name="Nhân viên kho"))
        cls.a = Warehouse.objects.create(code="A", name="Kho Hà Nội")
        cls.b = Warehouse.objects.create(code="B", name="Kho Hồ Chí Minh")
        cls.a.members.add(cls.worker)
        cls.a.managers.add(cls.manager)
        cls.a.issue_approvers.add(cls.manager)
        cls.p = Product.objects.create(sku="P1", name="Giấy A4", unit="Ram", minimum=3)
        cls.q = Product.objects.create(sku="P2", name="Băng keo", unit="Cuộn")

    def doc(
        self,
        kind="IN",
        qty=10,
        source=None,
        destination=None,
        creator=None,
        post=False,
        price=100,
        loan=None,
    ):
        d = Document.objects.create(
            kind=kind,
            source=source,
            destination=destination
            or (self.a if kind in ["IN", "COUNT", "ADJUST"] else None),
            created_by=creator or self.worker,
            loan=loan,
            note="Kiểm thử bản cải tiến",
        )
        Line.objects.create(document=d, product=self.p, quantity=qty, unit_price=price)
        if post:
            result = post_document(d.pk, self.admin)
            if result.status == "TRANSIT":
                post_document(d.pk, self.admin)
        return d

    def payload(self, **overrides):
        data = {
            "kind": "IN",
            "source": "",
            "destination": self.a.pk,
            "loan": "",
            "note": "Mua hàng",
            "form-TOTAL_FORMS": "1",
            "form-INITIAL_FORMS": "0",
            "form-0-product": self.p.pk,
            "form-0-quantity": "5",
            "form-0-unit_price": "100",
        }
        data.update(overrides)
        return data

    def test_all_new_pages_render(self):
        self.client.force_login(self.admin)
        for path in [
            "/",
            "/approvals/",
            "/warehouses/",
            "/warehouses/new/",
            "/team/",
            "/team/new/",
            "/reports/",
            "/custom-fields/",
            "/account/password/",
            "/operations/in/",
            "/operations/out/",
            "/operations/transfer/",
            "/operations/loan/",
            "/operations/return/",
            "/operations/count/",
            "/operations/adjust/",
        ]:
            with self.subTest(path=path):
                self.assertEqual(self.client.get(path).status_code, 200)

    def test_warehouse_scope_persists_and_limits_financial_reports(self):
        self.doc(qty=10, post=True)
        self.doc(qty=20, destination=self.b, post=True)
        self.client.force_login(self.admin)
        self.assertEqual(self.client.get("/").context["total_value"], 3000)
        self.client.post("/workspace/warehouse/", {"warehouse": self.a.pk, "next": "/"})
        self.assertEqual(self.client.get("/").context["total_value"], 1000)
        self.assertEqual(
            list(self.client.get("/reports/").context["warehouse_totals"])[0][
                "warehouse__code"
            ],
            "A",
        )
        csv = self.client.get("/stock/?export=1").content.decode("utf-8-sig")
        import csv as csv_module

        rows = list(csv_module.reader(StringIO(csv)))
        self.assertEqual([row[0] for row in rows[1:]], ["A"])
        self.assertNotIn("\ufeff", csv)
        self.client.post("/workspace/warehouse/", {"warehouse": "", "next": "/"})
        self.assertEqual(self.client.get("/").context["total_value"], 3000)

    def test_table_warehouse_filter_is_retained_on_next_screen(self):
        self.doc(qty=10, post=True)
        self.doc(qty=20, destination=self.b, post=True)
        self.client.force_login(self.admin)
        self.assertEqual(
            self.client.get("/stock/", {"warehouse": self.b.pk}).status_code, 200
        )
        self.assertEqual(self.client.get("/").context["total_value"], 2000)
        self.client.get("/stock/", {"warehouse": ""})
        self.assertEqual(self.client.get("/").context["total_value"], 3000)

    def test_scope_cannot_bypass_permissions_or_redirect_outside_site(self):
        self.client.force_login(self.worker)
        self.assertEqual(
            self.client.post(
                "/workspace/warehouse/", {"warehouse": self.b.pk}
            ).status_code,
            404,
        )
        self.assertEqual(
            self.client.get("/?warehouse=" + str(self.b.pk)).status_code, 404
        )
        self.assertRedirects(
            self.client.post(
                "/workspace/warehouse/",
                {"warehouse": self.a.pk, "next": "https://evil.example/"},
            ),
            "/",
        )

    def test_approval_queue_only_includes_authorized_non_self_documents(self):
        good = self.doc()
        own = self.doc(creator=self.manager)
        foreign = self.doc(destination=self.b)
        self.client.force_login(self.manager)
        response = self.client.get("/approvals/")
        ids = {d.pk for d in response.context["documents"]}
        self.assertIn(good.pk, ids)
        self.assertNotIn(own.pk, ids)
        self.assertNotIn(foreign.pk, ids)
        self.assertEqual(
            self.client.post(f"/documents/{good.pk}/post/").status_code, 302
        )
        self.assertEqual(
            Balance.objects.get(warehouse=self.a, product=self.p).quantity, 10
        )

    def test_shortage_is_rejected_before_a_draft_is_sent(self):
        self.doc(qty=3, post=True)
        self.client.force_login(self.worker)
        for kind in ["OUT", "TRANSFER", "LOAN"]:
            before = Document.objects.count()
            payload = self.payload(
                kind=kind,
                source=self.a.pk,
                destination=self.b.pk if kind != "OUT" else "",
                **{"form-0-quantity": "4", "form-0-unit_price": ""},
            )
            response = self.client.post("/operations/" + kind.lower() + "/", payload)
            self.assertEqual(response.status_code, 200)
            self.assertEqual(Document.objects.count(), before)
            self.assertIn("quantity", response.context["formset"].forms[0].errors)

    def test_fixed_operation_cannot_be_changed_in_post(self):
        self.client.force_login(self.worker)
        response = self.client.post(
            "/operations/in/",
            self.payload(kind="OUT", source=self.a.pk, destination=""),
        )
        self.assertEqual(response.status_code, 200)
        self.assertFalse(Document.objects.exists())

    def test_manual_form_submission_idempotency(self):
        self.client.force_login(self.worker)
        key = str(uuid4())
        for _ in range(2):
            self.assertEqual(
                self.client.post(
                    "/operations/in/", self.payload(submission_key=key)
                ).status_code,
                302,
            )
        self.assertEqual(Document.objects.count(), 1)
        self.assertEqual(Line.objects.count(), 1)
        self.assertFalse(Balance.objects.exists())

    def test_receipt_missing_price_and_negative_issue_rejected_before_save(self):
        self.client.force_login(self.worker)
        self.client.post("/operations/in/", self.payload(**{"form-0-unit_price": ""}))
        self.assertFalse(Document.objects.exists())
        self.client.post(
            "/operations/out/",
            self.payload(
                kind="OUT",
                source=self.a.pk,
                destination="",
                **{"form-0-quantity": "-2"},
            ),
        )
        self.assertFalse(Document.objects.exists())

    def test_line_deletion_does_not_save_deleted_items(self):
        self.client.force_login(self.worker)
        data = self.payload(
            **{
                "form-TOTAL_FORMS": "2",
                "form-0-DELETE": "on",
                "form-0-product": "",
                "form-0-quantity": "",
                "form-1-product": self.q.pk,
                "form-1-quantity": "3",
                "form-1-unit_price": "50",
            }
        )
        self.assertEqual(self.client.post("/operations/in/", data).status_code, 302)
        self.assertEqual(Line.objects.get().product, self.q)

    def test_draft_edit_validates_and_posted_document_is_immutable(self):
        d = self.doc()
        self.client.force_login(self.worker)
        data = self.payload(**{"form-INITIAL_FORMS": "1", "form-0-quantity": "-1"})
        self.assertEqual(
            self.client.post(f"/documents/{d.pk}/edit/", data).status_code, 200
        )
        self.assertEqual(d.lines.get().quantity, 10)
        post_document(d.pk, self.admin)
        self.assertEqual(self.client.get(f"/documents/{d.pk}/edit/").status_code, 404)

    def test_availability_is_scoped_and_reflects_usable_stock_only(self):
        self.doc(qty=10, post=True)
        self.doc(kind="LOAN", qty=6, source=self.a, destination=self.b, post=True)
        self.client.force_login(self.worker)
        response = self.client.get("/api/availability/", {"warehouse": self.a.pk})
        self.assertEqual(Decimal(response.json()["quantities"][str(self.p.pk)]), 4)
        self.assertEqual(
            self.client.get("/api/availability/", {"warehouse": self.b.pk}).status_code,
            404,
        )

    def test_return_form_prefills_and_locks_warehouse_direction(self):
        self.doc(qty=10, post=True)
        loan = self.doc(
            kind="LOAN", qty=6, source=self.a, destination=self.b, post=True
        )
        self.client.force_login(self.admin)
        response = self.client.get("/operations/return/", {"loan": loan.pk})
        form = response.context["form"]
        lines = response.context["formset"]
        self.assertTrue(form.fields["source"].disabled)
        self.assertEqual(form.initial["source"], self.b.pk)
        self.assertEqual(lines.initial[0]["product"], self.p.pk)
        self.assertEqual(lines.initial[0]["quantity"], 6)
        response = self.client.post(
            "/operations/return/",
            self.payload(
                kind="RETURN",
                source="",
                destination="",
                loan=loan.pk,
                **{"form-0-quantity": "2", "form-0-unit_price": ""},
            ),
        )
        self.assertEqual(response.status_code, 302)
        returned = Document.objects.filter(kind="RETURN").get()
        self.assertEqual(returned.source, self.b)
        self.assertEqual(returned.destination, self.a)
        self.assertIsNone(returned.lines.get().unit_price)

    def test_admin_creates_employee_with_freely_chosen_short_password(self):
        self.client.force_login(self.admin)
        response = self.client.post(
            "/team/new/",
            {
                "username": "NV001",
                "first_name": "Nguyễn Văn A",
                "email": "",
                "password": "1",
                "groups": [Group.objects.get(name="Nhân viên kho").pk],
                "is_active": "on",
                "access_warehouses": [self.a.pk],
                "managed_warehouses": [self.a.pk],
            },
        )
        self.assertEqual(response.status_code, 302)
        user = get_user_model().objects.get(username="NV001")
        self.assertTrue(user.check_password("1"))
        self.assertNotEqual(user.password, "1")
        self.assertFalse(user.is_staff)
        self.assertFalse(user.is_superuser)
        self.assertTrue(user.has_perm("inventory.add_document"))
        self.assertTrue(self.a.managers.filter(pk=user.pk).exists())

    def test_employee_changes_password_freely_and_keeps_session_and_username(self):
        self.client.force_login(self.worker)
        response = self.client.post(
            "/account/password/",
            {
                "old_password": "a",
                "new_password1": "2",
                "new_password2": "2",
                "username": "forged",
            },
        )
        self.assertEqual(response.status_code, 302)
        self.worker.refresh_from_db()
        self.assertTrue(self.worker.check_password("2"))
        self.assertEqual(self.worker.username, "worker")
        self.assertEqual(self.client.get("/").status_code, 200)

    def test_password_change_requires_current_password_and_matching_confirmation(self):
        self.client.force_login(self.worker)
        for old, new2 in [("incorrect", "b"), ("a", "different")]:
            self.assertEqual(
                self.client.post(
                    "/account/password/",
                    {"old_password": old, "new_password1": "b", "new_password2": new2},
                ).status_code,
                200,
            )
        self.worker.refresh_from_db()
        self.assertTrue(self.worker.check_password("a"))

    def test_non_admin_cannot_manage_users_or_grant_own_privileges(self):
        self.client.force_login(self.worker)
        for path in ["/team/", "/team/new/", f"/team/{self.worker.pk}/edit/"]:
            self.assertEqual(self.client.get(path).status_code, 403)
        self.assertEqual(
            self.client.post(
                "/warehouses/new/",
                {"code": "X", "name": "X", "managers": [self.worker.pk]},
            ).status_code,
            403,
        )

    def test_edit_employee_keeps_existing_password_and_assigns_warehouses(self):
        self.client.force_login(self.admin)
        response = self.client.post(
            f"/team/{self.worker.pk}/edit/",
            {
                "username": "worker",
                "first_name": "Nhân viên",
                "email": "",
                "password": "",
                "is_active": "on",
                "groups": [Group.objects.get(name="Nhân viên kho").pk],
                "access_warehouses": [self.b.pk],
                "issue_warehouses": [self.b.pk],
            },
        )
        self.assertEqual(response.status_code, 302)
        self.worker.refresh_from_db()
        self.assertTrue(self.worker.check_password("a"))
        self.assertEqual(
            list(self.worker.warehouses.values_list("pk", flat=True)), [self.b.pk]
        )
        self.assertTrue(self.b.issue_approvers.filter(pk=self.worker.pk).exists())

    def test_admin_can_create_warehouse_with_roles_in_same_screen(self):
        self.client.force_login(self.admin)
        response = self.client.post(
            "/warehouses/new/",
            {
                "code": "C",
                "name": "Kho mới",
                "address": "Hà Nội",
                "members": [self.worker.pk],
                "managers": [self.manager.pk],
                "issue_approvers": [self.manager.pk],
            },
        )
        self.assertEqual(response.status_code, 302)
        warehouse = Warehouse.objects.get(code="C")
        self.assertTrue(warehouse.managers.filter(pk=self.manager.pk).exists())

    def test_dashboard_values_come_from_posted_transactions_and_dates(self):
        self.doc(qty=10, post=True)
        self.doc(kind="OUT", qty=2, source=self.a, post=True)
        self.doc(kind="TRANSFER", qty=3, source=self.a, destination=self.b, post=True)
        self.doc(qty=999, post=False)
        self.client.force_login(self.admin)
        response = self.client.get("/")
        self.assertEqual(response.context["inbound_value"], 1000)
        self.assertEqual(response.context["outbound_value"], 200)
        self.assertEqual(response.context["total_value"], 800)
        self.assertEqual(
            sum(row["value"] for row in response.context["chart_warehouses"]), 800
        )
        response = self.client.get("/?from=1900-01-01&to=1900-01-02")
        self.assertEqual(response.context["inbound_value"], 0)
        self.assertEqual(response.context["total_value"], 800)

    def test_invalid_filters_fail_safely(self):
        self.client.force_login(self.admin)
        self.assertEqual(self.client.get("/?from=invalid&to=wrong").status_code, 200)
        self.assertEqual(self.client.get("/ledger/?product=invalid").status_code, 404)
        self.assertEqual(self.client.get("/stock/?warehouse=invalid").status_code, 404)

    def test_add_custom_field_and_use_it_without_admin_site(self):
        self.client.force_login(self.admin)
        self.assertEqual(
            self.client.post(
                "/custom-fields/", {"key": "brand", "label": "Thương hiệu"}
            ).status_code,
            302,
        )
        self.assertTrue(CustomField.objects.filter(key="brand").exists())
        self.assertContains(self.client.get("/products/new/"), "extra_brand")

    def test_excessive_transaction_value_is_rejected_atomically(self):
        d = self.doc(qty=Decimal("9999999999999"), price=Decimal("99999999999999"))
        with self.assertRaises(ValidationError):
            post_document(d.pk, self.admin)
        self.assertFalse(Balance.objects.exists())
