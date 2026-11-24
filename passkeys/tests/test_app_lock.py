"""Bank-app style session lock for every account (owner requests 23-24/11/2026,
"giống app ACB"): sessions end with the browser, time away asks to sign in
again with Face ID or the password, and wrong passwords count toward the same
5-attempt lockout as the login page."""

import json

from django.conf import settings
from django.contrib.auth import get_user_model
from django.test import Client, TestCase, override_settings

from login_guard.forms import LOCK_MESSAGE
from login_guard.models import LoginThrottle
from passkeys import services
from passkeys.models import PasskeyIdentity

from .test_ceremonies import PASSWORD, SETTINGS, CeremonyHelpers

HOST = {"HTTP_HOST": "localhost"}


@override_settings(**SETTINGS)
class AppLockTests(CeremonyHelpers, TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.user = get_user_model().objects.create_user(
            # The app keeps "Họ và tên" in first_name.
            "faceid-lock",
            password=PASSWORD,
            first_name="Đào Hữu Đạo",
        )
        cls.other = get_user_model().objects.create_user(
            "faceid-other", password=PASSWORD
        )
        cls.plain = get_user_model().objects.create_user(
            "password-only", password=PASSWORD
        )

    def setUp(self):
        self.client.force_login(self.user)
        self.authenticator, self.record = self.register()
        self.client.logout()

    @property
    def gap(self):
        return services.lock_timing()[2]

    def face_id_login(self):
        phone = Client()
        response = self.post(
            "/passkeys/login/verify/",
            self.login_payload(self.authenticator, client=phone),
            phone,
        )
        self.assertEqual(response.status_code, 200, response.content)
        self.assertEqual(response.json()["username"], self.user.username)
        return phone

    def password_login(self, user=None):
        laptop = Client()
        response = laptop.post(
            "/login/",
            {"username": (user or self.plain).username, "password": PASSWORD},
            **HOST,
        )
        self.assertEqual(response.status_code, 302)
        return laptop

    def age(self, client, seconds):
        session = client.session
        session["app_seen_at"] = services.now_seconds() - seconds
        session.save()

    def unlock_with_face_id(self, client, authenticator=None):
        options = self.options("/unlock/options/", {}, client)
        allowed = [c["id"] for c in options["publicKey"].get("allowCredentials", [])]
        self.assertEqual(allowed, [self.record.credential_id])
        handle = PasskeyIdentity.objects.get(user=self.user).handle.bytes
        return self.post(
            "/unlock/verify/",
            {
                "ceremony_id": options["ceremony_id"],
                # A real authenticator advances its counter after the sign-in.
                "credential": (authenticator or self.authenticator).assertion(
                    options["publicKey"], handle, counter=2
                ),
                "next": "/account/password/",
            },
            client,
        )

    def test_face_id_session_locks_after_time_away_and_face_id_unlocks(self):
        phone = self.face_id_login()
        self.assertEqual(phone.get("/account/password/", **HOST).status_code, 200)
        self.age(phone, self.gap + 5)
        response = phone.get("/account/password/", **HOST)
        self.assertEqual(response.status_code, 302)
        self.assertTrue(
            response["Location"].startswith("/unlock/?next=/account/password/")
        )
        page = phone.get(response["Location"], **HOST)
        self.assertContains(page, "Xin chào,")
        self.assertContains(page, "Đào Hữu Đạo")
        self.assertContains(page, 'data-pk-faceid="1"')
        self.assertContains(page, "Đăng nhập bằng Face ID")
        self.assertContains(page, "Đăng nhập tài khoản khác")
        self.assertContains(page, "Quên mật khẩu? <span>Liên hệ quản trị viên.</span>")
        # API calls are refused with JSON while locked.
        api = phone.get("/chat/api/summary/", HTTP_ACCEPT="application/json", **HOST)
        self.assertEqual(api.status_code, 423)
        self.assertTrue(api.json()["locked"])
        result = self.unlock_with_face_id(phone)
        self.assertEqual(result.status_code, 200, result.content)
        self.assertEqual(result.json()["redirect"], "/account/password/")
        self.assertEqual(phone.get("/account/password/", **HOST).status_code, 200)

    def test_password_sessions_lock_too_and_the_password_signs_back_in(self):
        laptop = self.password_login()
        page = laptop.get("/account/password/", **HOST)
        self.assertContains(page, 'id="app-lock"')
        self.assertContains(page, 'data-pk-faceid="0"')
        self.age(laptop, self.gap + 5)
        response = laptop.get("/account/password/", **HOST)
        self.assertEqual(response.status_code, 302)
        self.assertTrue(response["Location"].startswith("/unlock/"))
        lock_page = laptop.get(response["Location"], **HOST)
        self.assertContains(lock_page, 'data-pk-faceid="0"')
        self.assertContains(lock_page, 'type="password" autocomplete="off"')
        self.assertEqual(
            self.post("/unlock/options/", {}, laptop).status_code, 400
        )  # no Face ID on this account: password only
        wrong = self.post("/unlock/password/", {"password": "sai"}, laptop)
        self.assertEqual(wrong.status_code, 400)
        self.assertIn("Quên mật khẩu", wrong.json()["error"])
        self.assertEqual(laptop.get("/account/password/", **HOST).status_code, 302)
        right = self.post(
            "/unlock/password/", {"password": PASSWORD, "next": "/"}, laptop
        )
        self.assertEqual(right.status_code, 200, right.content)
        self.assertEqual(laptop.get("/account/password/", **HOST).status_code, 200)
        # The wrong attempt before the right one is forgotten, like the login page.
        self.assertFalse(
            LoginThrottle.objects.filter(scope="user", key="password-only").exists()
        )

    def test_wrong_passwords_on_the_lock_screen_lock_the_account_for_an_admin(self):
        laptop = self.password_login()
        laptop.get("/unlock/", **HOST)
        for _ in range(4):
            self.assertEqual(
                self.post("/unlock/password/", {"password": "sai"}, laptop).status_code,
                400,
            )
        fifth = self.post("/unlock/password/", {"password": "sai"}, laptop)
        self.assertEqual(fifth.status_code, 403)
        self.assertEqual(fifth.json()["error"], LOCK_MESSAGE)
        self.assertTrue(
            LoginThrottle.objects.get(
                scope="user", key="password-only"
            ).admin_unlock_required
        )
        # Even the right password is refused until an Admin unlocks the account.
        right = self.post("/unlock/password/", {"password": PASSWORD}, laptop)
        self.assertEqual(right.status_code, 403)
        self.assertEqual(laptop.get("/account/password/", **HOST).status_code, 302)
        login = Client().post(
            "/login/", {"username": "password-only", "password": PASSWORD}, **HOST
        )
        self.assertContains(login, "liên hệ quản trị viên để mở khóa")

    def test_another_accounts_face_id_cannot_unlock(self):
        phone = self.face_id_login()
        phone.get("/unlock/", **HOST)
        stranger = Client()
        stranger.force_login(self.other)
        other_authenticator, _ = self.register(client=stranger)
        result = self.unlock_with_face_id(phone, authenticator=other_authenticator)
        self.assertEqual(result.status_code, 400)
        self.assertEqual(phone.get("/account/password/", **HOST).status_code, 302)

    def test_face_id_unlock_is_not_counted_as_password_attempts(self):
        phone = self.face_id_login()
        phone.get("/unlock/", **HOST)
        # Several tries in a minute (cancelled prompts) stay allowed; only the
        # per-session and per-IP limits apply, not the 5 password confirmations.
        for _ in range(7):
            self.assertEqual(self.post("/unlock/options/", {}, phone).status_code, 200)

    def test_greeting_uses_the_given_name_initial(self):
        user = get_user_model()(username="dhdao", first_name="Đào Hữu Đạo")
        self.assertEqual(services.identity(user), ("Đào Hữu Đạo", "Đ"))
        user.first_name = "Admin (thử)"
        self.assertEqual(services.identity(user)[1], "A")
        user.first_name = ""
        self.assertEqual(services.identity(user), ("dhdao", "D"))

    def test_short_gaps_do_not_lock(self):
        laptop = self.password_login()
        self.age(laptop, self.gap - 10)
        self.assertEqual(laptop.get("/account/password/", **HOST).status_code, 200)

    def test_in_use_ping_keeps_unlocked_and_lock_endpoint_locks(self):
        phone = self.face_id_login()
        page = phone.get("/account/password/", **HOST)
        self.assertContains(page, 'id="app-lock"')
        self.assertContains(page, "app-lock.js")
        self.assertContains(page, 'data-lock-away="60"')
        self.assertContains(page, 'data-lock-idle="300"')
        self.assertContains(page, 'data-account="faceid-lock"')
        self.age(phone, self.gap - 10)
        self.assertEqual(self.post("/unlock/ping/", {}, phone).json(), {"ok": True})
        self.assertEqual(phone.get("/account/password/", **HOST).status_code, 200)
        self.post("/unlock/lock/", {}, phone)
        self.assertEqual(self.post("/unlock/ping/", {}, phone).json(), {"locked": True})
        self.assertEqual(phone.get("/account/password/", **HOST).status_code, 302)

    def test_password_unlock_then_offers_face_id_on_this_device(self):
        laptop = self.password_login(self.user)
        laptop.get("/unlock/", **HOST)
        session = laptop.session
        session.pop("password_login_at", None)
        session.save()
        self.post("/unlock/password/", {"password": PASSWORD}, laptop)
        page = laptop.get("/account/password/", **HOST)
        self.assertContains(page, 'id="pk-offer"')
        self.assertContains(page, "data-pk-offer-enable")

    def test_unlock_never_redirects_off_site_or_back_to_itself(self):
        phone = self.face_id_login()
        page = phone.get("/unlock/?next=https://evil.example/x", **HOST)
        self.assertContains(page, 'name="next" value="/"')
        page = phone.get("/unlock/?next=/unlock/", **HOST)
        self.assertContains(page, 'name="next" value="/"')
        result = self.post(
            "/unlock/password/", {"password": PASSWORD, "next": "//evil.example"}, phone
        )
        self.assertEqual(result.json()["redirect"], "/")

    def test_logout_and_static_stay_reachable_while_locked(self):
        phone = self.face_id_login()
        phone.get("/unlock/", **HOST)
        self.assertEqual(phone.get("/healthz/", **HOST).status_code in (200, 503), True)
        response = phone.post("/logout/", **HOST)
        self.assertEqual(response.status_code, 302)
        self.assertNotIn("_auth_user_id", phone.session)

    @override_settings(APP_LOCK_ENABLED=False)
    def test_the_lock_can_be_switched_off(self):
        laptop = self.password_login()
        self.age(laptop, 10 * self.gap)
        page = laptop.get("/account/password/", **HOST)
        self.assertEqual(page.status_code, 200)
        self.assertNotContains(page, 'id="app-lock"')
        self.assertEqual(laptop.get("/unlock/", **HOST).status_code, 302)

    @override_settings(
        APP_LOCK_AWAY_SECONDS=1, APP_LOCK_IDLE_SECONDS=1, APP_LOCK_SERVER_GAP_SECONDS=1
    )
    def test_lock_times_keep_safe_minimums(self):
        self.assertEqual(services.lock_timing(), (15, 60, 90))

    def test_sessions_end_when_the_browser_or_app_closes(self):
        self.assertTrue(settings.SESSION_EXPIRE_AT_BROWSER_CLOSE)
        response = Client().post(
            "/login/", {"username": "password-only", "password": PASSWORD}, **HOST
        )
        cookie = response.cookies[settings.SESSION_COOKIE_NAME]
        self.assertEqual(cookie["max-age"], "")
        self.assertEqual(cookie["expires"], "")
        self.assertLessEqual(settings.SESSION_COOKIE_AGE, 12 * 60 * 60)

    def test_password_fields_do_not_invite_saving_or_auto_fill(self):
        login = Client().get("/login/", **HOST)
        self.assertContains(
            login, '<form method="post" class="auth-form" autocomplete="off">'
        )
        self.assertContains(login, 'type="password" name="password" autocomplete="off"')
        self.assertNotContains(login, "current-password")
        laptop = self.password_login()
        page = laptop.get("/account/password/", **HOST)
        self.assertContains(page, 'name="password" type="password" autocomplete="off"')

    def test_manifest_and_home_screen_icon_are_linked(self):
        page = Client().get("/login/", **HOST)
        self.assertContains(page, 'rel="manifest"')
        self.assertContains(page, 'rel="apple-touch-icon"')
        self.assertContains(page, 'name="apple-mobile-web-app-capable" content="yes"')
        self.assertContains(page, "data-bank-login")
        manifest = json.loads(open("static/manifest.json", encoding="utf-8").read())
        self.assertEqual(manifest["display"], "standalone")
        self.assertEqual(manifest["start_url"], "/")
