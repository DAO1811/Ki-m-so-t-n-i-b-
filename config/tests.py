"""Staging identity and isolation; production presentation must stay unchanged."""

import os
import subprocess
import sys
from pathlib import Path
from unittest.mock import patch

from django.contrib.auth import get_user_model
from django.core import mail
from django.core.exceptions import ValidationError
from django.test import SimpleTestCase, TestCase, override_settings

from config import environment
from config.mail import StagingBlockedEmailBackend

ROOT = Path(__file__).resolve().parent.parent
STAGING = {"APP_ENVIRONMENT": "staging", "APP_VERSION": "v121-thu"}
BANNER = "BẢN THỬ – v121-thu – không nhập dữ liệu thật"


def settings_in_subprocess(env, expression):
    """Import settings with a clean, explicit environment and print one value."""
    clean = {
        key: value
        for key, value in os.environ.items()
        if key
        not in {
            "DEBUG",
            "SECRET_KEY",
            "DATABASE_URL",
            "RENDER_EXTERNAL_HOSTNAME",
            "APP_ENVIRONMENT",
            "APP_VERSION",
            "PRIVATE_MEDIA_PROVIDER",
            "GOOGLE_DRIVE_CLIENT_ID",
            "GOOGLE_DRIVE_CLIENT_SECRET",
        }
    }
    clean.update(env, DJANGO_SETTINGS_MODULE="config.settings")
    return subprocess.run(
        [
            sys.executable,
            "-c",
            "import django; from django.conf import settings as s; "
            f"print({expression})",
        ],
        cwd=ROOT,
        env=clean,
        capture_output=True,
        text=True,
        timeout=60,
    )


class EnvironmentParsingTests(SimpleTestCase):
    def test_defaults_to_production_and_unknown_version(self):
        with patch.dict(os.environ, {}, clear=True):
            self.assertEqual(environment.app_environment(), "production")
            self.assertFalse(environment.is_staging())
            self.assertEqual(environment.app_version(), "unknown")

    def test_staging_and_version_are_read(self):
        with patch.dict(
            os.environ,
            {"APP_ENVIRONMENT": " Staging ", "APP_VERSION": "v121-thu2"},
            clear=True,
        ):
            self.assertTrue(environment.is_staging())
            self.assertEqual(environment.app_version(), "v121-thu2")

    def test_unknown_environment_fails_closed(self):
        with patch.dict(os.environ, {"APP_ENVIRONMENT": "prod"}, clear=True):
            with self.assertRaises(RuntimeError):
                environment.app_environment()


class StagingSettingsTests(SimpleTestCase):
    def test_staging_discards_drive_credentials_and_stores_files_locally(self):
        result = settings_in_subprocess(
            {
                "DEBUG": "1",
                "APP_ENVIRONMENT": "staging",
                "PRIVATE_MEDIA_PROVIDER": "drive",
                "GOOGLE_DRIVE_CLIENT_ID": "leaked-client-id",
                "GOOGLE_DRIVE_CLIENT_SECRET": "leaked-secret",
            },
            "s.PRIVATE_MEDIA_PROVIDER, repr(s.GOOGLE_DRIVE_CLIENT_ID), "
            "repr(s.GOOGLE_DRIVE_CLIENT_SECRET), s.EMAIL_BACKEND",
        )
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(
            result.stdout.split(),
            ["database", "''", "''", "config.mail.StagingBlockedEmailBackend"],
        )

    def test_production_keeps_configured_provider_and_credentials(self):
        result = settings_in_subprocess(
            {
                "DEBUG": "1",
                "PRIVATE_MEDIA_PROVIDER": "drive",
                "GOOGLE_DRIVE_CLIENT_ID": "configured-id",
            },
            "s.APP_ENVIRONMENT, s.PRIVATE_MEDIA_PROVIDER, s.GOOGLE_DRIVE_CLIENT_ID",
        )
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(
            result.stdout.split(), ["production", "drive", "configured-id"]
        )


class DebugDefaultTests(SimpleTestCase):
    """Missing DEBUG must never turn on debug mode (Docker outside Render)."""

    def test_missing_debug_requires_secret_key(self):
        result = settings_in_subprocess({}, "s.DEBUG")
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("Set a secure SECRET_KEY", result.stderr)

    def test_missing_debug_requires_postgresql(self):
        result = settings_in_subprocess({"SECRET_KEY": "x" * 50}, "s.DEBUG")
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("PostgreSQL DATABASE_URL", result.stderr)

    def test_missing_debug_defaults_to_false(self):
        result = settings_in_subprocess(
            {
                "SECRET_KEY": "x" * 50,
                "DATABASE_URL": "postgresql://u:p@127.0.0.1:1/db",
            },
            "s.DEBUG",
        )
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(result.stdout.strip(), "False")

    def test_explicit_debug_one_still_enables_development(self):
        result = settings_in_subprocess({"DEBUG": "1"}, "s.DEBUG")
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(result.stdout.strip(), "True")

    def test_render_configuration_is_unchanged(self):
        result = settings_in_subprocess(
            {
                "DEBUG": "0",
                "RENDER_EXTERNAL_HOSTNAME": "example.onrender.com",
                "SECRET_KEY": "x" * 50,
                "DATABASE_URL": "postgresql://u:p@127.0.0.1:1/db",
            },
            "s.DEBUG, s.SECURE_SSL_REDIRECT, 'example.onrender.com' in s.ALLOWED_HOSTS",
        )
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(result.stdout.split(), ["False", "True", "True"])


class ProductionPresentationTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.admin = get_user_model().objects.create_superuser("env-admin")

    def test_production_pages_have_no_staging_marks(self):
        login = self.client.get("/login/")
        self.assertNotContains(login, "BẢN THỬ")
        self.assertNotContains(login, "staging.css")
        self.assertNotContains(login, "[THỬ]")
        self.assertContains(login, '<body class="auth-page">', html=False)
        self.client.force_login(self.admin)
        page = self.client.get("/")
        self.assertEqual(page.status_code, 200)
        self.assertNotContains(page, "BẢN THỬ")
        self.assertNotContains(page, "staging.css")
        self.assertNotContains(page, "[THỬ]")
        self.assertContains(page, "  <body>\n", html=False)

    def test_groq_panel_reminds_not_to_paste_sensitive_data(self):
        self.client.force_login(self.admin)
        self.assertContains(
            self.client.get("/"),
            "không dán dữ liệu khách hàng, giá vốn hay mật khẩu",
        )

    @override_settings(APP_VERSION="v121")
    def test_every_page_footer_and_login_show_the_version(self):
        mark = "<span data-app-version>Phiên bản v121</span>"
        self.assertContains(self.client.get("/login/"), mark, html=False)
        self.client.force_login(self.admin)
        for url in ("/", "/stock/", "/products/"):
            with self.subTest(url=url):
                self.assertContains(self.client.get(url), mark, html=False)

    @override_settings(APP_VERSION="v120")
    def test_admin_footer_shows_version(self):
        self.client.force_login(self.admin)
        page = self.client.get("/admin/")
        self.assertContains(page, "<span data-app-version>v120</span>", html=False)
        self.assertNotContains(page, "BẢN THỬ")

    @override_settings(APP_VERSION="v120")
    def test_health_reports_environment_and_version(self):
        with patch.dict(os.environ, {"RENDER_GIT_COMMIT": ""}):
            data = self.client.get("/healthz/").json()
        self.assertEqual(data["environment"], "production")
        self.assertEqual(data["version"], "v120")
        self.assertEqual(data["release"], "unknown")
        with patch.dict(os.environ, {"RENDER_GIT_COMMIT": "abc123"}):
            self.assertEqual(self.client.get("/healthz/").json()["release"], "abc123")


@override_settings(**STAGING)
class StagingPresentationTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.admin = get_user_model().objects.create_superuser("staging-admin")

    def test_banner_and_tab_title_on_login_workspace_admin_and_print(self):
        login = self.client.get("/login/")
        self.assertContains(login, BANNER)
        self.assertContains(login, "<title>[THỬ] Đăng nhập", html=False)
        self.assertContains(login, "staging.css")
        self.client.force_login(self.admin)
        for url in ("/", "/products/", "/chat/", "/admin/"):
            with self.subTest(url=url):
                page = self.client.get(url)
                self.assertEqual(page.status_code, 200)
                self.assertContains(page, BANNER)
                self.assertContains(page, "[THỬ]")

    def test_health_reports_staging(self):
        data = self.client.get("/healthz/").json()
        self.assertEqual(
            (data["environment"], data["version"]), ("staging", "v121-thu")
        )

    def test_drive_requests_are_blocked_before_any_network_call(self):
        from inventory import drive

        with patch("inventory.drive.urllib.request.urlopen") as urlopen:
            with self.assertRaisesMessage(
                ValidationError, environment.STAGING_BLOCKED_MESSAGE
            ):
                drive.google_request(
                    "https://www.googleapis.com/drive/v3/about", token="t"
                )
        urlopen.assert_not_called()

    @override_settings(
        GOOGLE_DRIVE_CLIENT_ID="leaked", GOOGLE_DRIVE_CLIENT_SECRET="leaked"
    )
    def test_drive_connect_never_redirects_to_google(self):
        self.client.force_login(self.admin)
        response = self.client.post("/settings/drive/connect/", follow=True)
        self.assertNotIn("accounts.google.com", response.redirect_chain[0][0])
        self.assertContains(response, environment.STAGING_BLOCKED_MESSAGE)

    def test_groq_is_disabled_even_with_a_key(self):
        from ai_assistant import cloud_config

        env = {"GROQ_API_KEY": "gsk_" + "a" * 40, "GROQ_FREE_ZDR_CONFIRMED": "1"}
        with patch.dict(os.environ, env):
            self.assertFalse(cloud_config.configuration().ready)
            self.assertFalse(cloud_config.is_enabled())
            self.client.force_login(self.admin)
            status = self.client.get("/assistant/api/cloud/status/").json()
        self.assertTrue(status["staging_blocked"])
        self.assertFalse(status["configured"])

    def test_email_backend_drops_messages(self):
        message = mail.EmailMessage(
            "s", "b", "a@example.invalid", ["b@example.invalid"]
        )
        with self.assertLogs("config.mail", "WARNING"):
            self.assertEqual(StagingBlockedEmailBackend().send_messages([message]), 0)


class GroqProductionUnchangedTests(SimpleTestCase):
    def test_production_still_reads_configured_key(self):
        from ai_assistant import cloud_config

        env = {"GROQ_API_KEY": "gsk_" + "a" * 40, "GROQ_FREE_ZDR_CONFIRMED": "1"}
        with patch.dict(os.environ, env):
            self.assertTrue(cloud_config.configuration().ready)
