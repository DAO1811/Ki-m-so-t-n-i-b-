"""Bank-app style lock for sessions that signed in with Face ID (23/11/2026)."""

import json

from django.contrib.auth import get_user_model
from django.test import Client, TestCase, override_settings

from passkeys import services
from passkeys.models import PasskeyIdentity

from .test_ceremonies import PASSWORD, SETTINGS, CeremonyHelpers

HOST = {"HTTP_HOST": "localhost"}


@override_settings(**SETTINGS)
class AppLockTests(CeremonyHelpers, TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.user = get_user_model().objects.create_user(
            "faceid-lock", password=PASSWORD
        )
        cls.other = get_user_model().objects.create_user(
            "faceid-other", password=PASSWORD
        )

    def setUp(self):
        self.client.force_login(self.user)
        self.authenticator, self.record = self.register()
        self.client.logout()

    def face_id_login(self):
        phone = Client()
        response = self.post(
            "/passkeys/login/verify/",
            self.login_payload(self.authenticator, client=phone),
            phone,
        )
        self.assertEqual(response.status_code, 200, response.content)
        self.assertEqual(response.json()["name"], self.user.username)
        return phone

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
        self.age(phone, services.APP_LOCK_AFTER + 5)
        response = phone.get("/account/password/", **HOST)
        self.assertEqual(response.status_code, 302)
        self.assertTrue(
            response["Location"].startswith("/unlock/?next=/account/password/")
        )
        page = phone.get(response["Location"], **HOST)
        self.assertContains(page, "Mở khóa bằng Face ID")
        self.assertContains(page, "Quên mật khẩu")
        # API calls are refused with JSON while locked.
        api = phone.get("/chat/api/summary/", HTTP_ACCEPT="application/json", **HOST)
        self.assertEqual(api.status_code, 423)
        self.assertTrue(api.json()["locked"])
        result = self.unlock_with_face_id(phone)
        self.assertEqual(result.status_code, 200, result.content)
        self.assertEqual(result.json()["redirect"], "/account/password/")
        self.assertEqual(phone.get("/account/password/", **HOST).status_code, 200)

    def test_password_also_unlocks_and_wrong_password_does_not(self):
        phone = self.face_id_login()
        phone.get("/unlock/", **HOST)  # opening the lock screen locks the session
        self.assertEqual(phone.get("/account/password/", **HOST).status_code, 302)
        wrong = self.post("/unlock/password/", {"password": "sai"}, phone)
        self.assertEqual(wrong.status_code, 400)
        self.assertIn("Quên mật khẩu", wrong.json()["error"])
        self.assertEqual(phone.get("/account/password/", **HOST).status_code, 302)
        right = self.post(
            "/unlock/password/", {"password": PASSWORD, "next": "/"}, phone
        )
        self.assertEqual(right.status_code, 200, right.content)
        self.assertEqual(phone.get("/account/password/", **HOST).status_code, 200)

    def test_another_accounts_face_id_cannot_unlock(self):
        phone = self.face_id_login()
        phone.get("/unlock/", **HOST)
        stranger = Client()
        stranger.force_login(self.other)
        other_authenticator, _ = self.register(client=stranger)
        result = self.unlock_with_face_id(phone, authenticator=other_authenticator)
        self.assertEqual(result.status_code, 400)
        self.assertEqual(phone.get("/account/password/", **HOST).status_code, 302)

    def test_password_sessions_are_never_locked(self):
        laptop = Client()
        self.assertEqual(
            laptop.post(
                "/login/",
                {"username": self.user.username, "password": PASSWORD},
                **HOST,
            ).status_code,
            302,
        )
        self.age(laptop, 10 * services.APP_LOCK_AFTER)
        page = laptop.get("/account/password/", **HOST)
        self.assertEqual(page.status_code, 200)
        self.assertNotContains(page, 'id="app-lock"')
        self.assertEqual(laptop.get("/unlock/", **HOST).status_code, 302)

    def test_in_use_ping_keeps_unlocked_and_lock_endpoint_locks(self):
        phone = self.face_id_login()
        page = phone.get("/account/password/", **HOST)
        self.assertContains(page, 'id="app-lock"')
        self.assertContains(page, "app-lock.js")
        self.age(phone, services.APP_LOCK_AFTER - 10)
        self.assertEqual(self.post("/unlock/ping/", {}, phone).json(), {"ok": True})
        self.assertEqual(phone.get("/account/password/", **HOST).status_code, 200)
        self.post("/unlock/lock/", {}, phone)
        self.assertEqual(self.post("/unlock/ping/", {}, phone).json(), {"locked": True})
        self.assertEqual(phone.get("/account/password/", **HOST).status_code, 302)

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

    def test_manifest_and_home_screen_icon_are_linked(self):
        page = Client().get("/login/", **HOST)
        self.assertContains(page, 'rel="manifest"')
        self.assertContains(page, 'rel="apple-touch-icon"')
        self.assertContains(page, 'name="apple-mobile-web-app-capable" content="yes"')
        self.assertContains(page, "data-fid-quick")
        manifest = json.loads(open("static/manifest.json", encoding="utf-8").read())
        self.assertEqual(manifest["display"], "standalone")
        self.assertEqual(manifest["start_url"], "/")
