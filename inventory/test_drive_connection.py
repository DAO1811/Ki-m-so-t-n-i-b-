from unittest.mock import patch

from django.conf import settings
from django.contrib.auth import get_user_model
from django.core.cache import cache
from django.core.exceptions import ValidationError
from django.test import Client, TestCase, override_settings

from . import drive
from .models import DriveConnection


@override_settings(
    GOOGLE_DRIVE_CLIENT_ID="review-client",
    GOOGLE_DRIVE_CLIENT_SECRET="review-secret",
    GOOGLE_PICKER_API_KEY="review-picker",
    GOOGLE_CLOUD_PROJECT_NUMBER="123456",
)
class DriveConnectionTests(TestCase):
    def setUp(self):
        cache.clear()
        self.addCleanup(cache.clear)
        self.admin = get_user_model().objects.create_superuser(
            "drive-admin", "admin@example.test", "1"
        )
        self.connection = DriveConnection.objects.create(
            account_email="owner@example.test",
            encrypted_refresh_token=drive.token_cipher()
            .encrypt(b"review-refresh")
            .decode(),
            connected_by=self.admin,
            folder_id=settings.GOOGLE_DRIVE_EXPECTED_FOLDER_ID,
            folder_name="Company records",
        )
        self.client.force_login(self.admin)

    def metadata(self, **changes):
        return {
            "id": settings.GOOGLE_DRIVE_EXPECTED_FOLDER_ID,
            "mimeType": "application/vnd.google-apps.folder",
            "ownedByMe": True,
            "capabilities": {"canAddChildren": True},
            **changes,
        }

    def test_setup_shows_current_host_even_when_fully_configured(self):
        response = self.client.get("/settings/drive/", secure=True)
        self.assertContains(response, "https://testserver/settings/drive/callback/")
        self.assertContains(response, "https://testserver/*")
        self.assertNotContains(response, "review-secret")
        self.assertNotContains(response, "review-refresh")

    def test_picker_can_send_origin_without_relaxing_other_pages(self):
        response = self.client.get("/settings/drive/", secure=True)
        self.assertEqual(
            response.headers["Referrer-Policy"], "strict-origin-when-cross-origin"
        )
        for path in ["/login/", "/settings/drive/callback/?code=private-review-code"]:
            self.assertEqual(
                self.client.get(path, secure=True).headers["Referrer-Policy"],
                "same-origin",
            )

    @patch("inventory.drive.google_request")
    @patch("inventory.drive.exchange_token")
    def test_check_refreshes_cached_token_and_only_reads_metadata(
        self, exchange, google
    ):
        exchange.return_value = {"access_token": "cached-review"}
        drive.access_token(self.connection)
        exchange.return_value = {"access_token": "renewed-review"}
        google.side_effect = [
            {"user": {"emailAddress": self.connection.account_email}},
            self.metadata(),
        ]
        response = self.client.post("/settings/drive/check/", follow=True)
        self.assertContains(response, "Google đã xác nhận tài khoản và quyền thêm tệp")
        self.assertEqual(exchange.call_count, 2)
        for call in google.call_args_list:
            self.assertEqual(call.kwargs.get("method", "GET"), "GET")
            self.assertEqual(call.kwargs["token"], "renewed-review")
        self.assertNotContains(response, "renewed-review")

    @patch("inventory.drive.access_token", return_value="review-access")
    @patch("inventory.drive.google_request")
    def test_check_rejects_wrong_account_and_lost_folder_permissions(
        self, google, _token
    ):
        google.return_value = {"user": {"emailAddress": "different@example.test"}}
        with self.assertRaisesMessage(ValidationError, "không khớp"):
            drive.check_connection()
        for metadata in [
            self.metadata(trashed=True),
            self.metadata(ownedByMe=False),
            self.metadata(capabilities={"canAddChildren": False}),
        ]:
            google.side_effect = [
                {"user": {"emailAddress": self.connection.account_email}},
                metadata,
            ]
            with self.assertRaises(ValidationError):
                drive.check_connection()

    @patch("inventory.drive.access_token")
    def test_wrong_root_rejected_without_google_call(self, token):
        self.connection.folder_id = "wrong-root"
        self.connection.save()
        with self.assertRaisesMessage(ValidationError, "khác thư mục"):
            drive.check_connection()
        token.assert_not_called()

    @patch("inventory.drive.check_connection")
    def test_check_requires_admin_post_and_csrf(self, check):
        self.assertEqual(self.client.get("/settings/drive/check/").status_code, 405)
        csrf_client = Client(enforce_csrf_checks=True)
        csrf_client.force_login(self.admin)
        self.assertEqual(csrf_client.post("/settings/drive/check/").status_code, 403)
        employee = get_user_model().objects.create_user("drive-employee", password="1")
        self.client.force_login(employee)
        self.assertEqual(self.client.post("/settings/drive/check/").status_code, 403)
        check.assert_not_called()

    @patch("inventory.drive.exchange_token")
    def test_changing_credentials_cannot_reuse_previous_cached_token(self, exchange):
        exchange.return_value = {"access_token": "first-review"}
        self.assertEqual(drive.access_token(self.connection), "first-review")
        exchange.return_value = {"access_token": "second-review"}
        with override_settings(GOOGLE_DRIVE_CLIENT_SECRET="changed-review"):
            self.assertEqual(drive.access_token(self.connection), "second-review")
        self.assertEqual(exchange.call_count, 2)

    @patch("inventory.drive.google_request")
    @patch("inventory.drive.exchange_token")
    def test_account_change_without_files_requires_selecting_folder_again(
        self, exchange, google
    ):
        exchange.return_value = {
            "access_token": "review-access",
            "refresh_token": "new-review-refresh",
            "scope": drive.SCOPE,
        }
        google.return_value = {"user": {"emailAddress": "new-owner@example.test"}}
        self.client.post("/settings/drive/connect/")
        state = self.client.session["drive_oauth"]["state"]
        self.client.get(
            "/settings/drive/callback/", {"state": state, "code": "review-code"}
        )
        self.connection.refresh_from_db()
        self.assertEqual(self.connection.account_email, "new-owner@example.test")
        self.assertEqual(self.connection.folder_id, "")
        self.assertEqual(self.connection.folder_name, "")
