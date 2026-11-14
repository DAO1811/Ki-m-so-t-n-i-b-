from datetime import timedelta
from io import StringIO
from unittest.mock import patch

from django.contrib.auth import get_user_model
from django.core.management import call_command
from django.test import RequestFactory, TestCase, override_settings
from django.utils import timezone

from . import services
from .models import LoginThrottle

PASSWORD = "dung-mat-khau-thu"
WRONG = "sai-mat-khau"
LOCKED = "Đăng nhập tạm khóa"


class LoginLockoutTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.user = get_user_model().objects.create_user("nv_thu", password=PASSWORD)

    def setUp(self):
        patcher = patch("login_guard.services.logger")
        self.logger = patcher.start()
        self.addCleanup(patcher.stop)

    def login(self, username="nv_thu", password=WRONG, ip="203.0.113.5"):
        return self.client.post(
            "/login/",
            {"username": username, "password": password},
            REMOTE_ADDR=ip,
        )

    def test_correct_login_still_works_and_clears_account_counter(self):
        for _ in range(3):
            self.assertContains(self.login(), "auth-error")
        response = self.login(password=PASSWORD)
        self.assertEqual(response.status_code, 302)
        self.assertFalse(
            LoginThrottle.objects.filter(scope="user", key="nv_thu").exists()
        )

    def test_account_locks_at_threshold_even_with_correct_password(self):
        for attempt in range(1, 5):
            response = self.login(ip=f"203.0.113.{attempt}")
            self.assertNotContains(response, LOCKED)
        self.assertContains(self.login(ip="203.0.113.9"), LOCKED)
        # Locked: the correct password is refused and authentication is skipped.
        with patch("django.contrib.auth.forms.authenticate") as authenticate:
            response = self.login(password=PASSWORD, ip="198.51.100.7")
        authenticate.assert_not_called()
        self.assertContains(response, LOCKED)
        self.assertNotIn("_auth_user_id", self.client.session)

    def test_unknown_account_gets_identical_messages(self):
        for name in ("nv_thu", "khong_ton_tai"):
            for _ in range(4):
                first = self.login(username=name)
            locked = self.login(username=name)
            with self.subTest(name=name):
                self.assertContains(first, "auth-error")
                self.assertContains(locked, LOCKED)
        self.assertEqual(LoginThrottle.objects.filter(scope="user").count(), 2)

    def test_username_case_and_spaces_share_one_counter(self):
        for name in ("NV_THU", " nv_thu", "Nv_Thu ", "nv_thu"):
            self.login(username=name)
        self.assertContains(self.login(username="NV_thu"), LOCKED)

    def test_lock_expires(self):
        for _ in range(5):
            self.login()
        LoginThrottle.objects.update(locked_until=timezone.now() - timedelta(seconds=1))
        self.assertEqual(self.login(password=PASSWORD).status_code, 302)

    def test_old_failures_outside_window_reset(self):
        for _ in range(4):
            self.login()
        LoginThrottle.objects.update(
            window_started_at=timezone.now() - timedelta(minutes=16)
        )
        self.assertNotContains(self.login(), LOCKED)
        self.assertEqual(
            LoginThrottle.objects.get(scope="user", key="nv_thu").failures, 1
        )

    @override_settings(LOGIN_IP_MAX_FAILURES=3)
    def test_ip_limit_blocks_spraying_many_accounts(self):
        for index in range(3):
            self.login(username=f"spray{index}", ip="192.0.2.50")
        self.assertContains(self.login(username="spray9", ip="192.0.2.50"), LOCKED)
        # Another IP is unaffected.
        self.assertEqual(
            self.login(password=PASSWORD, ip="192.0.2.51").status_code, 302
        )

    def test_existing_sessions_are_not_logged_out(self):
        other = self.client_class()
        other.force_login(self.user)
        for _ in range(6):
            self.login()
        self.assertEqual(other.get("/").status_code, 200)

    def test_password_is_never_stored(self):
        for _ in range(5):
            self.login(password="bi-mat-khong-luu")
        for row in LoginThrottle.objects.values():
            self.assertNotIn("bi-mat-khong-luu", str(row))
        self.logger.warning.assert_called_once()
        self.assertNotIn("bi-mat-khong-luu", str(self.logger.warning.call_args))

    def test_passkey_login_options_still_available_when_password_locked(self):
        for _ in range(5):
            self.login()
        response = self.client.post(
            "/passkeys/login/options/", REMOTE_ADDR="203.0.113.5"
        )
        self.assertNotEqual(response.status_code, 404)
        self.assertNotIn(LOCKED, response.content.decode())

    def test_cleanup_command_keeps_active_locks(self):
        for _ in range(5):
            self.login()
        self.login(username="cu", ip="198.51.100.1")
        LoginThrottle.objects.update(updated_at=timezone.now() - timedelta(days=2))
        call_command("cleanup_login_throttle", stdout=StringIO())
        self.assertEqual(
            sorted(LoginThrottle.objects.values_list("key", flat=True)),
            ["nv_thu"],  # unlocked IP counter and old "cu" counters are gone
        )


class ClientIpTests(TestCase):
    def request(self, remote="10.0.0.1", xff=None):
        meta = {"REMOTE_ADDR": remote}
        if xff is not None:
            meta["HTTP_X_FORWARDED_FOR"] = xff
        return RequestFactory().post("/login/", **meta)

    @override_settings(LOGIN_TRUSTED_PROXY_HOPS=0)
    def test_without_proxy_ignores_forwarded_header(self):
        ip = services.client_ip(self.request(xff="1.2.3.4"))
        self.assertEqual(ip, "10.0.0.1")

    @override_settings(LOGIN_TRUSTED_PROXY_HOPS=1)
    def test_one_trusted_proxy_uses_the_address_it_appended(self):
        spoofed = self.request(xff="6.6.6.6, 198.51.100.20")
        self.assertEqual(services.client_ip(spoofed), "198.51.100.20")
        self.assertEqual(
            services.client_ip(self.request(xff="198.51.100.21")), "198.51.100.21"
        )

    @override_settings(LOGIN_TRUSTED_PROXY_HOPS=1)
    def test_invalid_or_missing_header_falls_back_to_remote_addr(self):
        self.assertEqual(services.client_ip(self.request(xff="not-an-ip")), "10.0.0.1")
        self.assertEqual(services.client_ip(self.request()), "10.0.0.1")
