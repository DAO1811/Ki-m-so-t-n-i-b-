from hashlib import sha256
from io import BytesIO
from unittest.mock import patch

from django.core.exceptions import PermissionDenied, ValidationError
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import override_settings
from django.urls import reverse
from PIL import Image
from pypdf import PdfWriter

from deviations import storage
from deviations.models import (
    Attachment,
    Case,
    Event,
    PolicyEvent,
)
from inventory.models import StoredFile

from .support import DeviationTestCase


def image_file():
    output = BytesIO()
    Image.new("RGB", (8, 8), "gold").save(output, format="PNG")
    return SimpleUploadedFile("bang-chung.png", output.getvalue(), "image/png")


class HttpTests(DeviationTestCase):
    def test_all_staff_can_read_all_cases_without_warehouse_access(self):
        case = self.create()
        self.assertEqual(self.client.get(reverse("deviations")).status_code, 302)
        self.client.force_login(self.reader)
        for name, args in [
            ("deviations", []),
            ("deviation_list", []),
            ("deviation_detail", [case.pk]),
            ("deviation_reports", []),
            ("deviation_print", [case.pk]),
        ]:
            with self.subTest(name=name):
                response = self.client.get(reverse(name, args=args))
                self.assertEqual(response.status_code, 200)
                self.assertNotContains(response, 'id="global-warehouse"')
        self.assertEqual(self.client.get(reverse("products")).status_code, 403)
        self.assertEqual(self.client.post(reverse("deviations")).status_code, 403)

    def test_new_grants_do_not_implicitly_grant_legacy_permissions(self):
        self.client.force_login(self.maker)
        response = self.client.get(reverse("deviation_new"))
        self.assertContains(response, "Ghi nhận sai lệch")
        for name in (
            "products",
            "documents",
            "stocktakes",
            "team",
            "deviation_settings",
        ):
            self.assertEqual(self.client.get(reverse(name)).status_code, 403)
        self.client.force_login(self.reader)
        self.assertEqual(self.client.get(reverse("deviation_new")).status_code, 403)

    def test_http_create_submit_edit_and_wrong_source_form_are_validated(self):
        self.client.force_login(self.maker)
        data = dict(
            title="Ghi nhận qua giao diện",
            category=self.category.pk,
            department="Vận hành",
            actual="Thiếu biên bản",
            detected_at="2026-01-01T09:00",
            reported_at="2026-01-01T09:01",
            reporter_job_title="Nhân viên",
            discoverer_name="Người phát hiện giả lập",
            discoverer_job_title="Nhân viên",
            location="Văn phòng",
            what_changed="Thiếu hồ sơ",
            detection_method="Đối chiếu",
            expected="Đủ hồ sơ",
            gap_analysis="Thiếu một biên bản",
            immediate_response="Đã báo cáo TBP",
            department_reviewer=self.admin.pk,
            control_reviewer=self.admin.pk,
        )
        response = self.client.post(reverse("deviation_new"), data)
        self.assertEqual(response.status_code, 302)
        case = Case.objects.get(title=data["title"])
        self.assertEqual(case.status, "DRAFT")
        response = self.client.post(
            reverse("deviation_transition", args=[case.pk]),
            dict(revision=case.revision, command="submit"),
        )
        self.assertEqual(response.status_code, 302)
        case.refresh_from_db()
        self.assertEqual(case.status, "REPORTED")
        self.assertEqual(
            self.client.get(reverse("deviation_edit", args=[case.pk])).status_code, 403
        )
        data["source_product"] = 987654
        response = self.client.post(reverse("deviation_new"), data)
        self.assertEqual(response.status_code, 200)
        self.assertTrue(response.context["form"].errors)
        self.assertEqual(Case.objects.count(), 1)

    def test_filter_search_pagination_and_escaping(self):
        self.client.force_login(self.reader)
        case = self.create()
        case.title = "<script>alert(1)</script>"
        case.save(update_fields=["title"])
        response = self.client.get(reverse("deviation_list"), dict(q=case.code))
        self.assertContains(response, case.code)
        self.assertContains(response, "&lt;script&gt;alert(1)&lt;/script&gt;")
        self.assertNotContains(response, "<script>alert(1)</script>")
        for title in range(26):
            Case.objects.create(
                title=str(title),
                actual="Giả lập",
                category=self.category,
                department="Kho",
                created_by=self.maker,
            )
        response = self.client.get(reverse("deviation_list"), {"page": 2})
        self.assertEqual(response.context["page_obj"].number, 2)
        self.assertEqual(len(response.context["cases"]), 2)
        self.assertEqual(
            self.client.get(reverse("deviation_list"), {"q": "9" * 100}).status_code,
            200,
        )

    def test_get_on_mutations_cannot_change_state_and_csrf_is_required(self):
        from django.test import Client

        case = self.create()
        self.client.force_login(self.admin)
        self.assertEqual(
            self.client.get(
                reverse("deviation_transition", args=[case.pk])
            ).status_code,
            405,
        )
        secure = Client(enforce_csrf_checks=True)
        secure.force_login(self.maker)
        self.assertEqual(
            secure.post(
                reverse("deviation_transition", args=[case.pk]),
                dict(revision=case.revision, command="submit"),
            ).status_code,
            403,
        )
        self.assertEqual(Case.objects.get(pk=case.pk).status, "DRAFT")

    def test_configuration_and_category_screens_are_admin_only(self):
        self.client.force_login(self.admin)
        response = self.client.get(reverse("deviation_settings"))
        self.assertContains(response, "Quy tắc xử lý")
        self.assertEqual(
            self.client.get(reverse("deviation_category")).status_code, 200
        )
        response = self.client.post(
            reverse("deviation_category"),
            dict(name="Nhóm giả lập mới", active="on", reason="Tạo để kiểm thử"),
        )
        self.assertEqual(response.status_code, 302)
        self.assertTrue(PolicyEvent.objects.filter(reason="Tạo để kiểm thử").exists())
        self.client.force_login(self.reader)
        self.assertEqual(
            self.client.get(reverse("deviation_category")).status_code, 403
        )
        self.assertEqual(
            self.client.get(reverse("deviation_settings")).status_code, 403
        )

    def test_new_forms_render_during_workflow_with_permissions(self):
        case, action = self.planned()
        self.client.force_login(self.manager)
        for name, args in [
            ("deviation_analysis", [case.pk]),
            ("deviation_action_new", [case.pk]),
            ("deviation_action_edit", [case.pk, action.pk]),
        ]:
            self.assertEqual(self.client.get(reverse(name, args=args)).status_code, 200)
        self.step(case, "approve_plan", self.reviewer)
        self.client.force_login(self.worker)
        for name in ("deviation_action_work", "deviation_extension"):
            self.assertEqual(
                self.client.get(reverse(name, args=[case.pk, action.pk])).status_code,
                200,
            )


@override_settings(
    DEBUG=True,
    PRIVATE_MEDIA_PROVIDER="database",
    PRIVATE_MEDIA_LIMIT_BYTES=8 * 1024 * 1024,
)
class AttachmentTests(DeviationTestCase):
    def attach(self, case, user=None):
        return storage.add_attachment(
            case.pk,
            user or self.maker,
            case.revision,
            storage.validated_evidence(image_file()),
            "../bang-chung.png",
            "Tình trạng khi phát hiện",
        )

    def test_evidence_dedup_private_download_and_void_retains_original(self):
        case = self.create()
        item = self.attach(case)
        case.refresh_from_db()
        self.assertEqual(self.attach(case).pk, item.pk)
        self.assertEqual(Attachment.objects.count(), 1)
        self.assertEqual(item.filename, "bang-chung.png")
        self.client.force_login(self.reader)
        response = self.client.get(reverse("deviation_file", args=[item.pk]))
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response["Cache-Control"], "private, no-store")
        self.assertEqual(response["X-Content-Type-Options"], "nosniff")
        self.assertEqual(
            sha256(b"".join(response.streaming_content)).hexdigest(), item.file.sha256
        )
        storage.void_attachment(
            case.pk, self.admin, case.revision, item.pk, "Ảnh chụp nhầm thời điểm"
        )
        self.assertTrue(Attachment.objects.get(pk=item.pk).voided_at)
        self.assertTrue(StoredFile.objects.filter(pk=item.file_id).exists())
        self.assertTrue(
            Event.objects.filter(case=case, reason="Ảnh chụp nhầm thời điểm").exists()
        )

    def test_reader_and_unassigned_worker_cannot_upload(self):
        case = self.create()
        for user in (self.reader, self.worker, self.manager):
            with self.subTest(user=user.username), self.assertRaises(PermissionDenied):
                self.attach(case, user)
        self.assertFalse(StoredFile.objects.exists())

    def test_pdf_is_accepted_executable_svg_corrupt_or_large_uploads_are_rejected(self):
        output = BytesIO()
        writer = PdfWriter()
        writer.add_blank_page(width=100, height=100)
        writer.write(output)
        self.assertEqual(
            storage.validated_evidence(
                SimpleUploadedFile("hoso.pdf", output.getvalue())
            )[1],
            "application/pdf",
        )
        for name, content in [
            ("file.exe", b"MZ"),
            ("file.svg", b"<svg/>"),
            ("file.xml", b"<xml/>"),
            ("file.pdf", b"broken"),
            ("file.png", b"broken"),
            ("big.pdf", b"x" * (8 * 1024 * 1024 + 1)),
        ]:
            with self.subTest(name=name), self.assertRaises(ValidationError):
                storage.validated_evidence(SimpleUploadedFile(name, content))

    def test_corrupt_bytes_fail_integrity_check(self):
        case = self.create()
        item = self.attach(case)
        StoredFile.objects.filter(pk=item.file_id).update(data=b"changed")
        self.client.force_login(self.reader)
        response = self.client.get(reverse("deviation_file", args=[item.pk]))
        self.assertEqual(response.status_code, 503)

    @override_settings(DEBUG=False, PRIVATE_MEDIA_PROVIDER="drive")
    def test_drive_error_does_not_fallback_to_database_or_create_false_event(self):
        case = self.create()
        before = case.events.count()
        with (
            patch(
                "inventory.drive.upload",
                side_effect=ValidationError("Chưa chọn thư mục Drive"),
            ),
            self.assertRaises(ValidationError),
        ):
            self.attach(case)
        self.assertFalse(StoredFile.objects.exists())
        self.assertFalse(Attachment.objects.exists())
        self.assertEqual(case.events.count(), before)

    def test_closed_case_cannot_add_or_void_evidence(self):
        case = self.create()
        item = self.attach(case)
        case.refresh_from_db()
        case.status = "CLOSED"
        case.save(update_fields=["status"])
        with self.assertRaises(PermissionDenied):
            self.attach(case, self.admin)
        with self.assertRaises(ValidationError):
            storage.void_attachment(
                case.pk, self.admin, case.revision, item.pk, "Thử sửa hồ sơ đóng"
            )

    def test_http_upload_and_void_keep_foreign_case_files_inaccessible_to_write(self):
        case = self.create()
        self.client.force_login(self.maker)
        response = self.client.post(
            reverse("deviation_upload", args=[case.pk]),
            dict(
                revision=case.revision, file=image_file(), description="Ảnh bằng chứng"
            ),
        )
        self.assertEqual(response.status_code, 302)
        self.assertEqual(Attachment.objects.count(), 1)
        item = Attachment.objects.get()
        other = self.create()
        self.client.force_login(self.admin)
        # An attachment from another case must never be affected.
        response = self.client.post(
            reverse("deviation_void_file", args=[other.pk, item.pk]),
            dict(revision=other.revision, reason="Không hợp lệ"),
        )
        self.assertIn(response.status_code, (404, 302))
        self.assertIsNone(Attachment.objects.get().voided_at)


class ConfigurationAndStorageIntegrationTests(DeviationTestCase):
    def test_category_concurrent_edit_cannot_overwrite_saved_version(self):
        self.client.force_login(self.admin)
        url = reverse("deviation_category_edit", args=[self.category.pk])
        old_revision = self.category.revision
        response = self.client.post(
            url,
            dict(
                name="Nhóm đã chỉnh",
                active="on",
                revision=old_revision,
                reason="Thống nhất nhóm",
            ),
        )
        self.assertEqual(response.status_code, 302)
        response = self.client.post(
            url,
            dict(
                name="Ghi đè bản cũ",
                active="on",
                revision=old_revision,
                reason="Màn hình chưa tải lại",
            ),
        )
        self.assertContains(response, "Nhóm vừa được cập nhật")
        self.category.refresh_from_db()
        self.assertEqual(self.category.name, "Nhóm đã chỉnh")
        self.assertEqual(PolicyEvent.objects.count(), 1)

    def test_drive_deviation_namespace_keeps_existing_product_and_receipt_paths(self):
        from inventory import drive
        from inventory.models import DriveConnection

        DriveConnection.objects.create(
            pk=1,
            folder_id="fake-authorized-root",
            account_email="fake@example.invalid",
            connected_by=self.admin,
            encrypted_refresh_token="not-a-real-token",
        )
        expectations = {
            "product": [("Hàng hóa", "products"), ("Mã giả lập", "product-token")],
            "receipt": [
                ("Hóa đơn", "receipts"),
                ("2026", "year-2026"),
                ("Mã giả lập", "receipt-token"),
            ],
            "deviation": [
                ("XuLySaiLech", "deviations"),
                ("2026", "deviation-year-2026"),
                ("Mã giả lập", "deviation-token"),
            ],
        }
        for kind, expected in expectations.items():
            with (
                self.subTest(kind=kind),
                patch("inventory.drive.access_token", return_value="fake-test-token"),
                patch(
                    "inventory.drive.folder", return_value="fake-subfolder"
                ) as folders,
                patch(
                    "inventory.drive.google_request",
                    return_value={"files": [{"id": "fake-file", "size": 3}]},
                ),
            ):
                result = drive.upload(
                    b"abc",
                    "image/png",
                    sha256(b"abc").hexdigest(),
                    dict(kind=kind, name="Mã giả lập", key="token", year="2026"),
                    "test.png",
                )
                self.assertEqual(result, "fake-file")
                self.assertEqual(
                    [(c.args[2], c.args[3]) for c in folders.call_args_list], expected
                )
