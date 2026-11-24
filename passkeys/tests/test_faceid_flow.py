"""Face ID sign-in on iPhone (owner request 23/11/2026): easy to turn on right
after a password sign-in, password stays the fallback, Admin resets passwords."""

from datetime import timedelta
from unittest.mock import patch

from django.contrib.auth import get_user_model
from django.test import Client, TestCase, override_settings
from django.utils import timezone

from passkeys.models import PasskeyCredential

from .fixtures import SoftwareAuthenticator
from .test_ceremonies import (
    MANAGE,
    PASSWORD,
    REGISTER_OPTIONS,
    REGISTER_VERIFY,
    SETTINGS,
    CeremonyHelpers,
)


@override_settings(**SETTINGS)
class FaceIdTurnOnTests(CeremonyHelpers, TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.user = get_user_model().objects.create_user(
            "faceid-user", password=PASSWORD
        )

    def password_login(self, client=None):
        client = client or Client()
        response = client.post(
            "/login/",
            {"username": self.user.username, "password": PASSWORD},
            HTTP_HOST="localhost",
        )
        self.assertEqual(response.status_code, 302)
        return client

    def turn_on(self, client, password=""):
        options = self.post(
            REGISTER_OPTIONS, {"password": password, "label": "iPhone"}, client
        )
        return options

    def test_right_after_password_login_no_password_is_needed(self):
        client = self.password_login()
        page = client.get(MANAGE + "?bat=1", HTTP_HOST="localhost")
        self.assertContains(page, "không cần nhập lại mật khẩu")
        self.assertContains(
            page, '<input id="passkey-password" name="password" type="hidden"'
        )
        options = self.turn_on(client)
        self.assertEqual(options.status_code, 200, options.content)
        authenticator = SoftwareAuthenticator()
        data = options.json()
        response = self.post(
            REGISTER_VERIFY,
            {
                "ceremony_id": data["ceremony_id"],
                "credential": authenticator.registration(data["publicKey"]),
            },
            client,
        )
        self.assertEqual(response.status_code, 200, response.content)
        self.assertEqual(
            PasskeyCredential.objects.get(credential_id=authenticator.id).label,
            "iPhone",
        )

    def test_after_ten_minutes_the_password_is_required_again(self):
        client = self.password_login()
        later = timezone.now() + timedelta(minutes=11)
        with patch("passkeys.services.timezone.now", return_value=later):
            self.assertEqual(self.turn_on(client).status_code, 400)
            self.assertEqual(self.turn_on(client, PASSWORD).status_code, 200)
        self.assertContains(
            Client().get("/login/", HTTP_HOST="localhost"), "Quên mật khẩu"
        )

    def test_wrong_password_is_still_rejected_even_right_after_login(self):
        client = self.password_login()
        self.assertEqual(self.turn_on(client, "sai-mat-khau").status_code, 400)
        self.assertFalse(PasskeyCredential.objects.exists())

    def test_session_without_a_fresh_password_login_needs_the_password(self):
        client = Client()
        client.force_login(self.user)
        self.assertEqual(self.turn_on(client).status_code, 400)
        self.assertContains(
            client.get(MANAGE, HTTP_HOST="localhost"),
            'name="password" type="password" autocomplete="off" required',
        )

    def test_turn_on_invitation_only_right_after_a_password_login(self):
        client = self.password_login()
        page = client.get("/account/password/", HTTP_HOST="localhost")
        self.assertContains(page, 'id="pk-offer"')
        self.assertContains(page, "passkeys-offer.js")
        # One tap turns Face ID on right here, like a banking app.
        self.assertContains(page, "data-pk-offer-enable")
        # Not repeated on the Face ID page itself.
        self.assertNotContains(
            client.get(MANAGE, HTTP_HOST="localhost"), 'id="pk-offer"'
        )
        later = timezone.now() + timedelta(minutes=11)
        with patch("passkeys.services.timezone.now", return_value=later):
            self.assertNotContains(
                client.get("/account/password/", HTTP_HOST="localhost"),
                'id="pk-offer"',
            )
        forced = Client()
        forced.force_login(self.user)
        self.assertNotContains(
            forced.get("/account/password/", HTTP_HOST="localhost"), 'id="pk-offer"'
        )

    def test_no_invitation_after_signing_in_with_face_id(self):
        authenticator, _record = self.register(client=self.password_login())
        phone = Client()
        response = self.post(
            "/passkeys/login/verify/",
            self.login_payload(authenticator, client=phone),
            phone,
        )
        self.assertEqual(response.status_code, 200, response.content)
        self.assertNotContains(
            phone.get("/account/password/", HTTP_HOST="localhost"), 'id="pk-offer"'
        )

    def test_login_page_offers_face_id_with_password_fallback(self):
        page = Client().get("/login/", HTTP_HOST="localhost")
        self.assertContains(page, 'aria-label="Đăng nhập bằng Face ID"')
        # Bank-app style: a remembered account can switch to another one.
        self.assertContains(page, "Đăng nhập tài khoản khác")
        self.assertContains(
            page, "Quên mật khẩu? <span>Liên hệ quản trị viên.</span>", html=False
        )
        self.assertContains(page, 'autocomplete="username webauthn"')

    @override_settings(PASSKEY_ENABLED=False)
    def test_without_face_id_the_login_page_is_password_only(self):
        page = Client().get("/login/", HTTP_HOST="localhost")
        self.assertNotContains(page, "Đăng nhập bằng Face ID")
        self.assertContains(page, "Quên mật khẩu")
        client = self.password_login()
        self.assertNotContains(
            client.get("/account/password/", HTTP_HOST="localhost"), 'id="pk-offer"'
        )
