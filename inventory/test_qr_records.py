from datetime import timedelta
from decimal import Decimal
from io import BytesIO, StringIO
from uuid import uuid4
from unittest.mock import patch

from django.contrib.auth import get_user_model
from django.contrib.auth.models import Group, Permission
from django.core.exceptions import PermissionDenied, ValidationError
from django.core.files.uploadedfile import SimpleUploadedFile
from django.core.management import call_command
from django.test import TestCase, override_settings
from django.utils import timezone
from PIL import Image
from pypdf import PdfWriter

from .models import (
    Product,
    Warehouse,
    Document,
    Line,
    Balance,
    StoredFile,
    StocktakeSession,
    StocktakeEvent,
    DriveConnection,
)
from .services import post_document, can_approve, approval_documents_for
from .stocktakes import start_session, save_count, submit_session, product_from_scan
from .media import validate_upload, add_product_photo, add_receipt_attachment


class QRStocktakeTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        User = get_user_model()
        cls.maker = User.objects.create_user("counter", password="1")
        cls.manager = User.objects.create_user("manager", password="1")
        cls.ceo = User.objects.create_user("ceo", password="1")
        cls.admin = User.objects.create_superuser("owner", "owner@example.test", "1")
        cls.outsider = User.objects.create_user("outside", password="1")
        call_command("setup_roles", stdout=StringIO())
        cls.maker.groups.add(Group.objects.get(name="Nhân viên kho"))
        cls.ceo.user_permissions.add(
            Permission.objects.get(
                content_type__app_label="inventory",
                codename="approve_inventory_adjustment",
            )
        )
        cls.a = Warehouse.objects.create(code="QA", name="Kho kiểm thử QR")
        cls.b = Warehouse.objects.create(code="QB", name="Kho khác")
        cls.a.members.add(cls.maker)
        cls.a.managers.add(cls.manager)
        cls.a.issue_approvers.add(cls.manager)
        cls.p = Product.objects.create(sku="QR-A", name="Hàng A", unit="Cái")
        cls.q = Product.objects.create(sku="QR-B", name="Hàng B", unit="Hộp")

    def receipt(self, product=None, quantity=3):
        doc = Document.objects.create(
            kind="IN", destination=self.a, created_by=self.maker
        )
        Line.objects.create(
            document=doc, product=product or self.p, quantity=quantity, unit_price=100
        )
        post_document(doc.pk, self.manager)
        return doc

    def count(
        self,
        session,
        quantity=None,
        mode="ADD",
        product=None,
        revision=None,
        request_id=None,
        price=None,
    ):
        product = product or self.p
        item = session.items.filter(product=product).first()
        return save_count(
            session.pk,
            self.maker,
            product,
            mode,
            Decimal(str(quantity)) if quantity is not None else None,
            Decimal(str(price)) if price is not None else None,
            "",
            request_id or uuid4(),
            revision or (item.revision if item else 1),
        )

    def test_scan_to_adjustment_requires_ceo_and_changes_only_approved_delta(self):
        self.receipt()
        session = start_session(self.a, self.maker)
        self.count(session)
        self.count(session)
        self.assertEqual(Balance.objects.get().quantity, 3)
        doc = submit_session(session.pk, self.maker, "Thiếu 1 cái, đề nghị xử lý")
        self.assertEqual(doc.kind, "ADJUST")
        self.assertEqual(doc.lines.get().quantity, -1)
        self.assertEqual(doc.lines.get().stocktake_quantity, 3)
        self.assertEqual(Balance.objects.get().quantity, 3)
        self.assertFalse(can_approve(doc, self.manager))
        self.assertFalse(can_approve(doc, self.admin))
        for actor in [self.manager, self.admin, self.maker]:
            with (
                self.subTest(actor=actor.username),
                self.assertRaises(PermissionDenied),
            ):
                post_document(doc.pk, actor)
        self.assertIn(doc, approval_documents_for(self.ceo))
        self.client.force_login(self.ceo)
        self.assertEqual(self.client.get(f"/documents/{doc.pk}/").status_code, 200)
        self.assertEqual(
            self.client.get(f"/stocktakes/{session.pk}/report/").status_code, 200
        )
        post_document(doc.pk, self.ceo)
        self.assertEqual(Balance.objects.get().quantity, 2)
        self.assertEqual(Balance.objects.get().value, 200)
        self.assertEqual(doc.events.last().actor_id, self.ceo.pk)

    def test_retries_do_not_count_twice_or_accept_changed_payload(self):
        self.receipt()
        session = start_session(self.a, self.maker)
        request_id = uuid4()
        first, replay = self.count(session, revision=1, request_id=request_id)
        repeated, replay = self.count(session, revision=1, request_id=request_id)
        self.assertTrue(replay)
        self.assertEqual(repeated.counted_quantity, 1)
        with self.assertRaises(ValidationError):
            self.count(
                session, quantity=5, mode="SET", revision=1, request_id=request_id
            )
        self.assertEqual(
            StocktakeEvent.objects.filter(session=session, action="ADD").count(), 1
        )
        self.assertEqual(first.counted_quantity, 1)

    def test_report_and_adjustment_preserve_names_when_catalog_is_edited(self):
        from .forms import ProductForm

        self.receipt()
        session = start_session(self.a, self.maker)
        self.count(session, quantity=2, mode="SET")
        Product.objects.filter(pk=self.p.pk).update(name="Tên đã đổi sau mở phiên")
        doc = submit_session(session.pk, self.maker, "Thiếu một đơn vị")
        self.assertEqual(doc.lines.get().name_snapshot, "Hàng A")
        session.refresh_from_db()
        self.assertEqual(session.workflow_status, "Chờ Tổng giám đốc duyệt điều chỉnh")
        post_document(doc.pk, self.ceo)
        session.refresh_from_db()
        self.assertEqual(session.workflow_status, "Hoàn tất, đã điều chỉnh tồn")
        self.client.force_login(self.ceo)
        page = self.client.get(f"/stocktakes/{session.pk}/report/")
        self.assertContains(page, "Hàng A")
        self.assertNotContains(page, "Tên đã đổi sau mở phiên")
        # A found item without an earlier receipt also keeps its counting identity.
        self.count(start_session(self.a, self.maker), product=self.q)
        form = ProductForm(
            {"sku": "CHANGED", "name": "Tên khác", "unit": "Khác", "minimum": "0"},
            instance=self.q,
        )
        self.assertFalse(form.is_valid())
        self.assertIn("sku", form.errors)
        self.assertIn("unit", form.errors)

    def test_stale_count_revision_blocked(self):
        session = start_session(self.a, self.maker)
        self.count(session, revision=1)
        with self.assertRaises(ValidationError):
            self.count(session, revision=1)

    def test_unseen_is_not_zero_and_explicit_zero_is_counted(self):
        self.receipt()
        session = start_session(self.a, self.maker)
        self.assertIsNone(session.items.get().counted_quantity)
        with self.assertRaises(ValidationError):
            submit_session(session.pk, self.maker, "Chưa đếm")
        self.count(session, quantity=0, mode="SET")
        doc = submit_session(session.pk, self.maker, "Không tìm thấy hàng")
        self.assertEqual(doc.lines.get().quantity, -3)

    def test_no_difference_does_not_create_adjustment(self):
        self.receipt()
        session = start_session(self.a, self.maker)
        self.count(session, quantity=3, mode="SET")
        self.assertIsNone(submit_session(session.pk, self.maker, "Khớp sổ"))
        session.refresh_from_db()
        self.assertEqual(session.status, "COMPLETED")
        self.assertFalse(Document.objects.filter(kind="ADJUST").exists())

    def test_new_found_item_requires_valuation_before_submission(self):
        session = start_session(self.a, self.maker)
        self.count(session, product=self.q)
        with self.assertRaises(ValidationError):
            submit_session(session.pk, self.maker, "Hàng ngoài sổ")
        self.count(session, quantity=1, mode="SET", product=self.q, price=0)
        doc = submit_session(session.pk, self.maker, "Hàng biếu, giá trị 0")
        post_document(doc.pk, self.ceo)
        self.assertEqual(Balance.objects.get(product=self.q).quantity, 1)

    def test_warehouse_movement_blocks_before_and_after_submission(self):
        self.receipt()
        session = start_session(self.a, self.maker)
        self.count(session, quantity=2, mode="SET")
        doc = submit_session(session.pk, self.maker, "Thiếu 1")
        self.receipt(product=self.q)
        with self.assertRaises(ValidationError):
            post_document(doc.pk, self.ceo)
        with self.assertRaises(ValidationError):
            submit_session(start_session(self.a, self.maker).pk, self.maker, "Chưa đếm")
        self.assertEqual(Balance.objects.get(product=self.p).quantity, 3)

    def test_session_frozen_after_submit_and_origin_document_not_editable(self):
        self.receipt()
        session = start_session(self.a, self.maker)
        self.count(session, quantity=2, mode="SET")
        doc = submit_session(session.pk, self.maker, "Thiếu")
        self.assertEqual(submit_session(session.pk, self.maker, "Gửi lại").pk, doc.pk)
        with self.assertRaises(ValidationError):
            self.count(session)
        self.client.force_login(self.maker)
        self.assertEqual(self.client.get(f"/documents/{doc.pk}/edit/").status_code, 403)

    def test_expired_session_and_permission_revocation_block_counting(self):
        session = start_session(self.a, self.maker)
        StocktakeSession.objects.filter(pk=session.pk).update(
            business_date=timezone.localdate() - timedelta(days=1)
        )
        with self.assertRaises(ValidationError):
            self.count(session)
        StocktakeSession.objects.filter(pk=session.pk).update(
            business_date=timezone.localdate()
        )
        self.a.members.remove(self.maker)
        with self.assertRaises(PermissionDenied):
            self.count(session)
        self.client.force_login(self.maker)
        self.assertEqual(
            self.client.get(f"/stocktakes/{session.pk}/lookup/?code=QR-A").status_code,
            404,
        )

    def test_ceo_cannot_self_approve_and_group_membership_is_not_explicit_grant(self):
        self.receipt()
        doc = Document.objects.create(
            kind="ADJUST",
            destination=self.a,
            created_by=self.ceo,
            note="Không tự duyệt",
        )
        Line.objects.create(document=doc, product=self.p, quantity=-1)
        with self.assertRaises(PermissionDenied):
            post_document(doc.pk, self.ceo)
        permission = Permission.objects.get(
            content_type__app_label="inventory", codename="approve_inventory_adjustment"
        )
        role = Group.objects.create(name="Vai trò thử")
        role.permissions.add(permission)
        self.manager.groups.add(role)
        doc.created_by = self.maker
        doc.save()
        self.assertFalse(can_approve(doc, self.manager))
        self.ceo.user_permissions.clear()
        self.assertFalse(can_approve(doc, self.ceo))

    def test_scan_resolution_and_qr_image_are_authenticated(self):
        self.assertEqual(
            product_from_scan(
                f"https://old-host.example/q/items/{self.p.qr_token}/"
            ).pk,
            self.p.pk,
        )
        self.assertEqual(product_from_scan(self.p.sku).pk, self.p.pk)
        with self.assertRaises(ValidationError):
            product_from_scan("https://malicious.example/arbitrary")
        self.assertEqual(
            self.client.get(f"/products/{self.p.pk}/qr.png").status_code, 302
        )
        self.client.force_login(self.maker)
        response = self.client.get(f"/products/{self.p.pk}/qr.png")
        self.assertEqual(response["Content-Type"], "image/png")
        self.assertTrue(response.content.startswith(b"\x89PNG"))

    def test_other_warehouse_cannot_lookup_or_modify_session(self):
        session = start_session(self.a, self.maker)
        self.client.force_login(self.outsider)
        for route in ["", "lookup/?code=QR-A", "report/"]:
            self.assertEqual(
                self.client.get(f"/stocktakes/{session.pk}/" + route).status_code, 404
            )
        with self.assertRaises(PermissionDenied):
            start_session(self.b, self.maker)

    def test_numeric_filters_are_bounded_and_old_sessions_can_be_closed(self):
        self.client.force_login(self.admin)
        huge = "9" * 5000
        for url in [
            "/?warehouse=" + huge,
            "/api/availability/?warehouse=" + huge,
            "/ledger/?product=" + huge,
            "/operations/return/?loan=" + huge,
        ]:
            with self.subTest(url=url[:45]):
                self.assertEqual(self.client.get(url).status_code, 404)
        session = start_session(self.a, self.maker)
        StocktakeSession.objects.filter(pk=session.pk).update(
            business_date=timezone.localdate() - timedelta(days=1)
        )
        self.client.post(
            f"/stocktakes/{session.pk}/cancel/",
            {"reason": "Đóng phiên hết ngày, mở phiên kiểm kê mới"},
        )
        session.refresh_from_db()
        self.assertEqual(session.status, "CANCELLED")


@override_settings(DEBUG=True, PRIVATE_MEDIA_PROVIDER="database")
class RecordMediaTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        QRStocktakeTests.setUpTestData.__func__(cls)

    receipt = QRStocktakeTests.receipt

    def image(self):
        output = BytesIO()
        Image.new("RGB", (24, 24), "green").save(output, format="PNG")
        return SimpleUploadedFile(
            "hang.png", output.getvalue(), content_type="image/png"
        )

    def pdf(self):
        output = BytesIO()
        writer = PdfWriter()
        writer.add_blank_page(width=200, height=200)
        writer.write(output)
        return SimpleUploadedFile(
            "hoa-don.pdf", output.getvalue(), content_type="application/pdf"
        )

    def test_product_creation_produces_qr_and_optional_photo(self):
        self.client.force_login(self.admin)
        response = self.client.post(
            "/products/new/",
            {
                "sku": "NEW",
                "name": "Hàng mới",
                "unit": "Cái",
                "minimum": "0",
                "image": self.image(),
            },
        )
        product = Product.objects.get(sku="NEW")
        self.assertRedirects(response, f"/products/{product.pk}/")
        self.assertIsNotNone(product.qr_token)
        self.assertEqual(product.photos.count(), 1)
        file = product.photos.get().file
        self.assertEqual(file.content_type, "image/jpeg")
        self.assertNotEqual(bytes(file.data), b"")

    def test_same_batch_many_products_has_one_file_and_separate_receipts_are_grouped(
        self,
    ):
        doc = self.receipt()
        Line.objects.create(document=doc, product=self.q, quantity=1, unit_price=100)
        upload = self.pdf()
        validated = validate_upload(upload)
        first = add_receipt_attachment(
            doc, self.maker, validated, upload.name, invoice_number="HD-1"
        )
        repeated = add_receipt_attachment(
            doc, self.maker, validated, upload.name, invoice_number="HD-1"
        )
        self.assertEqual(first.pk, repeated.pk)
        self.assertEqual(StoredFile.objects.count(), 1)
        second = self.receipt()
        add_receipt_attachment(
            second, self.maker, validated, upload.name, invoice_number="HD-2"
        )
        self.client.force_login(self.maker)
        response = self.client.get(f"/products/{self.p.pk}/")
        self.assertContains(response, "HD-1")
        self.assertContains(response, "HD-2")
        self.assertEqual(len(response.context["receipts"]), 2)

    def test_invoice_files_are_not_public_or_accessible_from_unassigned_warehouse(self):
        doc = self.receipt()
        upload = self.pdf()
        attachment = add_receipt_attachment(
            doc, self.maker, validate_upload(upload), upload.name, invoice_number="HD-1"
        )
        url = f"/files/{attachment.file_id}/"
        self.assertEqual(self.client.get(url).status_code, 302)
        self.client.force_login(self.outsider)
        self.assertEqual(self.client.get(url).status_code, 404)
        self.client.force_login(self.maker)
        response = self.client.get(url)
        self.assertEqual(response.status_code, 200)
        self.assertIn("attachment", response["Content-Disposition"])
        self.assertEqual(
            b"".join(response.streaming_content), bytes(attachment.file.data)
        )

    def test_invalid_uploads_and_database_limit_fail_without_partial_metadata(self):
        for name, data in [
            ("x.jpg", b"not-image"),
            ("x.pdf", b"not-pdf"),
            ("x.svg", b"<svg/>"),
            (
                "x.xml",
                b'<!DOCTYPE x [<!ENTITY e SYSTEM "file:///etc/passwd">]><x>&e;</x>',
            ),
        ]:
            with self.subTest(name=name), self.assertRaises(ValidationError):
                validate_upload(
                    SimpleUploadedFile(name, data), photo=name.endswith(".jpg")
                )
        with (
            override_settings(PRIVATE_MEDIA_LIMIT_BYTES=1),
            self.assertRaises(ValidationError),
        ):
            add_product_photo(
                self.p, self.admin, validate_upload(self.image(), photo=True)
            )
        self.assertFalse(StoredFile.objects.exists())
        self.assertFalse(self.p.photos.exists())

    @override_settings(PRIVATE_MEDIA_PROVIDER="drive")
    @patch("inventory.drive.upload", return_value="private-drive-file-id")
    def test_drive_provider_stores_only_pointer_and_verified_hash(self, upload_mock):
        photo = add_product_photo(
            self.p, self.admin, validate_upload(self.image(), photo=True)
        )
        self.assertIsNone(photo.file.data)
        self.assertEqual(photo.file.provider, "drive")
        self.assertEqual(photo.file.drive_id, "private-drive-file-id")
        self.assertEqual(upload_mock.call_args.args[3]["kind"], "product")

    @override_settings(PRIVATE_MEDIA_PROVIDER="drive")
    @patch("inventory.drive.upload", side_effect=ValidationError("Drive hết quyền"))
    def test_drive_error_never_falls_back_to_database(self, _upload):
        with self.assertRaises(ValidationError):
            add_product_photo(
                self.p, self.admin, validate_upload(self.image(), photo=True)
            )
        self.assertFalse(StoredFile.objects.exists())

    def test_drive_settings_and_oauth_are_admin_only_and_reject_invalid_state(self):
        self.client.force_login(self.maker)
        self.assertEqual(self.client.get("/settings/drive/").status_code, 403)
        self.client.force_login(self.admin)
        self.assertEqual(self.client.get("/settings/drive/").status_code, 200)
        response = self.client.get(
            "/settings/drive/callback/", {"state": "forged", "code": "invalid"}
        )
        self.assertRedirects(response, "/settings/drive/")
        self.assertFalse(DriveConnection.objects.exists())

    @override_settings(
        GOOGLE_DRIVE_CLIENT_ID="client", GOOGLE_DRIVE_CLIENT_SECRET="secret"
    )
    @patch("inventory.drive.google_request")
    @patch("inventory.drive.exchange_token")
    def test_oauth_stores_encrypted_refresh_and_never_exposes_it_in_page(
        self, exchange, request_mock
    ):
        from .drive import SCOPE, token_cipher

        exchange.return_value = {
            "access_token": "access-secret",
            "refresh_token": "refresh-secret",
            "scope": SCOPE,
        }
        request_mock.return_value = {"user": {"emailAddress": "owner@example.test"}}
        self.client.force_login(self.admin)
        self.client.post("/settings/drive/connect/")
        state = self.client.session["drive_oauth"]["state"]
        self.client.get(
            "/settings/drive/callback/", {"state": state, "code": "one-time-code"}
        )
        connection = DriveConnection.objects.get()
        self.assertNotIn("refresh-secret", connection.encrypted_refresh_token)
        self.assertEqual(
            token_cipher().decrypt(connection.encrypted_refresh_token.encode()),
            b"refresh-secret",
        )
        self.assertNotContains(self.client.get("/settings/drive/"), "refresh-secret")

    @override_settings(
        GOOGLE_DRIVE_CLIENT_ID="client", GOOGLE_DRIVE_CLIENT_SECRET="secret"
    )
    @patch("inventory.drive.google_request")
    @patch("inventory.drive.access_token", return_value="short-lived")
    def test_drive_selects_only_approved_private_folder(self, _token, google):
        from django.conf import settings
        from .drive import choose_folder

        DriveConnection.objects.create(
            account_email="owner@example.test",
            encrypted_refresh_token="encrypted",
            connected_by=self.admin,
        )
        with self.assertRaises(ValidationError):
            choose_folder("unapproved-folder")
        google.assert_not_called()
        google.return_value = {
            "id": settings.GOOGLE_DRIVE_EXPECTED_FOLDER_ID,
            "name": "Hồ sơ công ty",
            "mimeType": "application/vnd.google-apps.folder",
            "ownedByMe": True,
            "capabilities": {"canAddChildren": True},
        }
        choose_folder(settings.GOOGLE_DRIVE_EXPECTED_FOLDER_ID)
        self.assertEqual(
            DriveConnection.objects.get().folder_id,
            settings.GOOGLE_DRIVE_EXPECTED_FOLDER_ID,
        )

    @patch("inventory.drive.folder", side_effect=["products-folder", "sku-folder"])
    @patch("inventory.drive.access_token", return_value="short-lived")
    @patch("inventory.drive.google_request")
    def test_drive_upload_creates_path_and_metadata_without_public_sharing(
        self, google, _token, folders
    ):
        from .drive import upload

        DriveConnection.objects.create(
            account_email="owner@example.test",
            encrypted_refresh_token="encrypted",
            connected_by=self.admin,
            folder_id="approved-root",
        )
        google.side_effect = [
            {"files": []},
            {"id": "created-private-file", "size": "3"},
        ]
        file_id = upload(
            b"pdf",
            "application/pdf",
            "a" * 64,
            {"kind": "product", "key": str(self.p.qr_token), "name": self.p.sku},
            "sample.pdf",
        )
        self.assertEqual(file_id, "created-private-file")
        self.assertEqual(folders.call_args_list[0].args[1], "approved-root")
        self.assertEqual(folders.call_args_list[1].args[1], "products-folder")
        self.assertIn(b'"parents": ["sku-folder"]', google.call_args.kwargs["payload"])
        self.assertNotIn(b"permissions", google.call_args.kwargs["payload"])

    @patch("inventory.drive.access_token", return_value="short-lived")
    @patch("inventory.drive.google_request", return_value=b"tampered")
    def test_drive_content_change_is_detected(self, _request, _token):
        from .drive import download

        file = StoredFile.objects.create(
            sha256="0" * 64,
            context_key="receipt:test",
            provider="drive",
            drive_id="id",
            content_type="application/pdf",
            size=8,
        )
        with self.assertRaises(ValidationError):
            download(file)

    @override_settings(DEBUG=False, PRIVATE_MEDIA_PROVIDER="database")
    def test_production_never_silently_uses_database_for_media(self):
        with self.assertRaises(ValidationError):
            add_product_photo(
                self.p, self.admin, validate_upload(self.image(), photo=True)
            )
        self.assertFalse(StoredFile.objects.exists())

    def test_voided_invoice_can_be_corrected_without_losing_original(self):
        doc = self.receipt()
        file = self.pdf()
        validated = validate_upload(file)
        old = add_receipt_attachment(
            doc, self.maker, validated, file.name, invoice_number="Nhập sai số"
        )
        self.client.force_login(self.maker)
        self.client.post(
            f"/attachments/{old.pk}/void/", {"reason": "Sửa nhãn hóa đơn, giữ tệp gốc"}
        )
        corrected = add_receipt_attachment(
            doc, self.maker, validated, file.name, invoice_number="Số đúng"
        )
        self.assertNotEqual(old.pk, corrected.pk)
        self.assertEqual(old.file_id, corrected.file_id)
        old.refresh_from_db()
        self.assertEqual(old.voided_by_id, self.maker.pk)
        self.assertEqual(
            list(
                doc.events.filter(action__startswith="FILE").values_list(
                    "action", flat=True
                )
            ),
            ["FILE_ADD", "FILE_VOID", "FILE_ADD"],
        )
        self.assertEqual(Balance.objects.get().quantity, 3)

    def test_ceo_grant_and_revocation_are_logged_without_password(self):
        from .services import can_approve_adjustments
        from django.contrib.admin.models import LogEntry

        self.client.force_login(self.admin)
        data = {
            "username": self.manager.username,
            "first_name": "Người duyệt",
            "is_active": "on",
            "approve_adjustments": "on",
            "password": "private-example-password",
        }
        self.client.post(f"/team/{self.manager.pk}/edit/", data)
        self.assertTrue(can_approve_adjustments(self.manager))
        self.assertNotIn(
            "private-example-password", LogEntry.objects.latest("id").change_message
        )
        data.pop("approve_adjustments")
        data["password"] = ""
        self.client.post(f"/team/{self.manager.pk}/edit/", data)
        self.assertFalse(can_approve_adjustments(self.manager))
        self.assertEqual(
            LogEntry.objects.filter(object_id=str(self.manager.pk)).count(), 2
        )
