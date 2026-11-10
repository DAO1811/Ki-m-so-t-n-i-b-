"""Real, signed WebAuthn ceremonies against isolated Django test databases."""

import copy
import json
from concurrent.futures import ThreadPoolExecutor
from datetime import timedelta
from threading import Barrier, Event
from unittest import skipUnless

from django.contrib.auth import get_user_model
from django.contrib.auth.hashers import PBKDF2PasswordHasher
from django.contrib.auth.models import Group
from django.contrib.messages import get_messages
from django.db import close_old_connections, connection, connections, transaction
from django.test import (
    Client,
    SimpleTestCase,
    TestCase,
    TransactionTestCase,
    override_settings,
)
from django.utils import timezone
from webauthn import verify_authentication_response, verify_registration_response

from passkeys.models import (
    Ceremony,
    PasskeyCredential,
    PasskeyIdentity,
    RateBucket,
    SecurityEvent,
)

from .fixtures import SoftwareAuthenticator, b64url, unb64url

MANAGE = "/account/passkeys/"
REGISTER_OPTIONS = MANAGE + "register/options/"
REGISTER_VERIFY = MANAGE + "register/verify/"
LOGIN_OPTIONS = "/passkeys/login/options/"
LOGIN_VERIFY = "/passkeys/login/verify/"
PASSWORD = "Preview-only-password-8142"
SETTINGS = {
    "DEBUG": True,
    "PASSKEY_ENABLED": True,
    "PASSKEY_RP_ID": "localhost",
    "PASSKEY_ORIGIN": "http://localhost",
    "ALLOWED_HOSTS": ["localhost", "testserver"],
    "PASSWORD_HASHERS": ["django.contrib.auth.hashers.MD5PasswordHasher"],
}


class AuthenticatorFixtureTests(SimpleTestCase):
    def test_fixture_is_accepted_by_the_real_library(self):
        authenticator = SoftwareAuthenticator()
        challenge = b"isolated-fixture-challenge-32bytes"
        options = {"challenge": b64url(challenge)}
        registration = verify_registration_response(
            credential=authenticator.registration(options),
            expected_challenge=challenge,
            expected_rp_id="localhost",
            expected_origin="http://localhost",
            require_user_presence=True,
            require_user_verification=True,
        )
        self.assertEqual(registration.credential_id, authenticator.credential_id)
        self.assertEqual(registration.credential_public_key, authenticator.public_key)
        assertion = verify_authentication_response(
            credential=authenticator.assertion(options, bytes(16)),
            expected_challenge=challenge,
            expected_rp_id="localhost",
            expected_origin="http://localhost",
            credential_public_key=authenticator.public_key,
            credential_current_sign_count=0,
            require_user_verification=True,
        )
        self.assertEqual(assertion.new_sign_count, 1)


class CeremonyHelpers:
    def post(self, path, payload, client=None, **headers):
        return (client or self.client).post(
            path,
            json.dumps(payload),
            content_type="application/json",
            HTTP_HOST="localhost",
            **headers,
        )

    def options(self, path, payload=None, client=None):
        response = self.post(path, payload or {}, client)
        self.assertEqual(response.status_code, 200, response.content)
        self.assertIn("no-store", response.headers.get("Cache-Control", ""))
        result = response.json()
        self.assertIn("ceremony_id", result)
        self.assertIn("publicKey", result)
        return result

    def registration_options(self, client=None):
        return self.options(
            REGISTER_OPTIONS, {"password": PASSWORD, "label": "Máy thử ES256"}, client
        )

    def register(self, authenticator=None, client=None, **kwargs):
        authenticator = authenticator or SoftwareAuthenticator()
        options = self.registration_options(client)
        response = self.post(
            REGISTER_VERIFY,
            {
                "ceremony_id": options["ceremony_id"],
                "credential": authenticator.registration(
                    options["publicKey"], **kwargs
                ),
            },
            client,
        )
        self.assertEqual(response.status_code, 200, response.content)
        self.assertTrue(response.json()["ok"])
        record = PasskeyCredential.objects.get(credential_id=authenticator.id)
        return authenticator, record

    def anonymous(self):
        return Client()

    def login_payload(
        self, authenticator, *, client=None, next_path="/", handle=None, **kwargs
    ):
        client = client or self.client
        options = self.options(LOGIN_OPTIONS, {"next": next_path}, client)
        if handle is None:
            handle = PasskeyIdentity.objects.get(user=self.user).handle.bytes
        return {
            "ceremony_id": options["ceremony_id"],
            "credential": authenticator.assertion(
                options["publicKey"], handle, **kwargs
            ),
        }

    def assert_rejected(self, response):
        self.assertEqual(response.status_code, 400, response.content)
        self.assertIn("no-store", response.headers.get("Cache-Control", ""))


@override_settings(**SETTINGS)
class PasskeyCeremonyTests(CeremonyHelpers, TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.user = get_user_model().objects.create_user(
            "passkey-preview-user", password=PASSWORD
        )
        cls.other = get_user_model().objects.create_user(
            "passkey-preview-other", password=PASSWORD
        )

    def setUp(self):
        self.client.force_login(self.user)

    def test_registration_requires_current_password_and_authenticated_session(self):
        self.assertEqual(
            self.post(
                REGISTER_OPTIONS,
                {"password": PASSWORD, "label": "Thử riêng"},
                self.anonymous(),
            ).status_code,
            401,
        )
        self.assert_rejected(
            self.post(REGISTER_OPTIONS, {"password": "wrong", "label": "Thử riêng"})
        )
        self.assert_rejected(self.post(REGISTER_OPTIONS, {}))
        self.assertFalse(Ceremony.objects.filter(used_at__isnull=True).exists())
        self.assertFalse(PasskeyCredential.objects.exists())

    def test_options_require_verification_and_use_opaque_random_user_handle(self):
        result = self.registration_options()
        options = result["publicKey"]
        identity = PasskeyIdentity.objects.get(user=self.user)
        self.assertEqual(unb64url(options["user"]["id"]), identity.handle.bytes)
        self.assertEqual(
            options["authenticatorSelection"]["userVerification"], "required"
        )
        self.assertEqual(options["authenticatorSelection"]["residentKey"], "required")
        self.assertEqual(options["rp"]["id"], "localhost")
        self.assertGreaterEqual(len(unb64url(options["challenge"])), 32)
        self.client.force_login(self.other)
        second = self.registration_options()
        self.assertNotEqual(options["user"]["id"], second["publicKey"]["user"]["id"])

    def test_real_registration_stores_public_key_and_consumes_ceremony(self):
        authenticator, record = self.register(
            counter=7, backup_eligible=True, backed_up=True
        )
        self.assertEqual(record.user, self.user)
        self.assertEqual(bytes(record.public_key), authenticator.public_key)
        self.assertEqual(record.sign_count, 7)
        self.assertTrue(record.backup_eligible)
        self.assertTrue(record.backed_up)
        self.assertEqual(record.label, "Máy thử ES256")
        self.assertIsNotNone(Ceremony.objects.get().used_at)
        self.assertTrue(SecurityEvent.objects.filter(user=self.user).exists())

    def test_registration_rejects_invalid_security_fields(self):
        cases = (
            {"origin": "https://evil.example"},
            {"rp_id": "evil.example"},
            {"challenge": b64url(b"not-the-issued-challenge")},
            {"uv": False},
            {"up": False},
            {"ceremony_type": "webauthn.get"},
            {"client_extra": {"crossOrigin": True}},
            {"client_extra": {"topOrigin": "https://evil.example"}},
            {"backup_eligible": False, "backed_up": True},
        )
        for kwargs in cases:
            with self.subTest(kwargs=kwargs):
                RateBucket.objects.all().delete()
                options = self.registration_options()
                response = self.post(
                    REGISTER_VERIFY,
                    {
                        "ceremony_id": options["ceremony_id"],
                        "credential": SoftwareAuthenticator().registration(
                            options["publicKey"], **kwargs
                        ),
                    },
                )
                self.assert_rejected(response)
                self.assertIsNotNone(
                    Ceremony.objects.get(pk=options["ceremony_id"]).used_at
                )
        self.assertFalse(PasskeyCredential.objects.exists())

    def test_failed_registration_cannot_reuse_challenge(self):
        options = self.registration_options()
        authenticator = SoftwareAuthenticator()
        payload = {
            "ceremony_id": options["ceremony_id"],
            "credential": authenticator.registration(options["publicKey"], uv=False),
        }
        self.assert_rejected(self.post(REGISTER_VERIFY, payload))
        payload["credential"] = authenticator.registration(options["publicKey"])
        self.assert_rejected(self.post(REGISTER_VERIFY, payload))
        self.assertFalse(PasskeyCredential.objects.exists())

    def test_successful_registration_cannot_be_replayed(self):
        options = self.registration_options()
        payload = {
            "ceremony_id": options["ceremony_id"],
            "credential": SoftwareAuthenticator().registration(options["publicKey"]),
        }
        self.assertEqual(self.post(REGISTER_VERIFY, payload).status_code, 200)
        self.assert_rejected(self.post(REGISTER_VERIFY, payload))
        self.assertEqual(PasskeyCredential.objects.count(), 1)

    def test_a_new_ceremony_invalidates_previous_options_in_the_same_session(self):
        old = self.registration_options()
        self.registration_options()
        self.assert_rejected(
            self.post(
                REGISTER_VERIFY,
                {
                    "ceremony_id": old["ceremony_id"],
                    "credential": SoftwareAuthenticator().registration(
                        old["publicKey"]
                    ),
                },
            )
        )
        self.assertIsNotNone(Ceremony.objects.get(pk=old["ceremony_id"]).used_at)

    def test_registration_verifier_requires_the_registration_purpose(self):
        options = self.registration_options()
        Ceremony.objects.filter(pk=options["ceremony_id"]).update(kind="login")
        self.assert_rejected(
            self.post(
                REGISTER_VERIFY,
                {
                    "ceremony_id": options["ceremony_id"],
                    "credential": SoftwareAuthenticator().registration(
                        options["publicKey"]
                    ),
                },
            )
        )
        self.assertFalse(PasskeyCredential.objects.exists())

    def test_registration_is_bound_to_session_user_and_expiry(self):
        for scenario in ("other-session", "other-user", "expired"):
            with self.subTest(scenario=scenario):
                RateBucket.objects.all().delete()
                options = self.registration_options()
                client = self.client
                if scenario == "other-session":
                    client = self.anonymous()
                    client.force_login(self.user)
                elif scenario == "other-user":
                    client = self.anonymous()
                    client.force_login(self.other)
                else:
                    Ceremony.objects.filter(pk=options["ceremony_id"]).update(
                        expires_at=timezone.now() - timedelta(seconds=1)
                    )
                self.assert_rejected(
                    self.post(
                        REGISTER_VERIFY,
                        {
                            "ceremony_id": options["ceremony_id"],
                            "credential": SoftwareAuthenticator().registration(
                                options["publicKey"]
                            ),
                        },
                        client,
                    )
                )
        self.assertFalse(PasskeyCredential.objects.exists())

    def test_password_reset_invalidates_pending_registration(self):
        options = self.registration_options()
        self.user.set_password("Replacement-preview-password")
        self.user.save(update_fields=["password"])
        # Preserve the session binding while refreshing its login hash, to exercise
        # password-version binding independently of session rotation protections.
        session = self.client.session
        session["_auth_user_hash"] = self.user.get_session_auth_hash()
        session.save()
        response = self.post(
            REGISTER_VERIFY,
            {
                "ceremony_id": options["ceremony_id"],
                "credential": SoftwareAuthenticator().registration(
                    options["publicKey"]
                ),
            },
        )
        self.assert_rejected(response)
        self.assertFalse(PasskeyCredential.objects.exists())

    def test_duplicate_credential_cannot_be_registered_to_another_account(self):
        authenticator, record = self.register()
        self.client.force_login(self.other)
        options = self.registration_options()
        self.assert_rejected(
            self.post(
                REGISTER_VERIFY,
                {
                    "ceremony_id": options["ceremony_id"],
                    "credential": authenticator.registration(options["publicKey"]),
                },
            )
        )
        record.refresh_from_db()
        self.assertEqual(record.user_id, self.user.pk)
        self.assertEqual(PasskeyCredential.objects.count(), 1)

    def test_active_credential_limit_is_per_account(self):
        for _ in range(10):
            authenticator = SoftwareAuthenticator()
            PasskeyCredential.objects.create(
                user=self.user,
                credential_id=authenticator.id,
                public_key=authenticator.public_key,
                sign_count=0,
                label="Thử giới hạn",
            )
        response = self.post(
            REGISTER_OPTIONS, {"password": PASSWORD, "label": "Vượt giới hạn"}
        )
        self.assert_rejected(response)
        self.client.force_login(self.other)
        self.register()
        self.assertEqual(
            PasskeyCredential.objects.filter(
                user=self.user, revoked_at__isnull=True
            ).count(),
            10,
        )

    def test_login_options_do_not_enumerate_users_or_credentials(self):
        authenticator, _ = self.register()
        client = self.anonymous()
        result = self.options(LOGIN_OPTIONS, {"username": self.user.username}, client)
        options = result["publicKey"]
        self.assertFalse(options.get("allowCredentials"))
        self.assertEqual(options["userVerification"], "required")
        self.assertNotIn(authenticator.id, json.dumps(result))
        self.assertNotIn(self.user.username, json.dumps(result))
        self.assertNotIn("user", options)

    def test_real_login_rotates_session_and_tracks_counter_and_usage(self):
        authenticator, record = self.register()
        client = self.anonymous()
        payload = self.login_payload(
            authenticator, client=client, next_path="/account/password/"
        )
        original_session_key = client.session.session_key
        replay_client = self.anonymous()
        replay_client.cookies = copy.deepcopy(client.cookies)
        response = self.post(LOGIN_VERIFY, payload, client)
        self.assertEqual(response.status_code, 200, response.content)
        self.assertEqual(response.json()["redirect"], "/account/password/")
        self.assertNotEqual(client.session.session_key, original_session_key)
        self.assertEqual(int(client.session["_auth_user_id"]), self.user.pk)
        self.assertEqual(str(client.session["passkey_credential_id"]), str(record.pk))
        record.refresh_from_db()
        self.assertEqual(record.sign_count, 1)
        self.assertIsNotNone(record.last_used_at)
        self.assert_rejected(self.post(LOGIN_VERIFY, payload, replay_client))
        self.assertEqual(self.post(LOGIN_VERIFY, payload, client).status_code, 409)

    def test_login_rejects_signed_invalid_security_fields(self):
        authenticator, record = self.register()
        cases = (
            {"wrong_signature": True},
            {"origin": "https://evil.example"},
            {"rp_id": "evil.example"},
            {"challenge": b64url(b"wrong-challenge")},
            {"uv": False},
            {"up": False},
            {"ceremony_type": "webauthn.create"},
            {"client_extra": {"crossOrigin": True}},
            {"client_extra": {"topOrigin": "https://evil.example"}},
            {"handle": bytes(16)},
            {"backup_eligible": True},
        )
        for kwargs in cases:
            with self.subTest(kwargs=kwargs):
                RateBucket.objects.all().delete()
                client = self.anonymous()
                payload = self.login_payload(authenticator, client=client, **kwargs)
                self.assert_rejected(self.post(LOGIN_VERIFY, payload, client))
                self.assertNotIn("_auth_user_id", client.session)
                self.assertIsNotNone(
                    Ceremony.objects.get(pk=payload["ceremony_id"]).used_at
                )
        record.refresh_from_db()
        self.assertEqual(record.sign_count, 0)
        self.assertIsNone(record.last_used_at)

    def test_failed_assertion_consumes_challenge_before_retry(self):
        authenticator, _ = self.register()
        client = self.anonymous()
        payload = self.login_payload(authenticator, client=client, wrong_signature=True)
        self.assert_rejected(self.post(LOGIN_VERIFY, payload, client))
        ceremony = Ceremony.objects.get(pk=payload["ceremony_id"])
        self.assertIsNotNone(ceremony.used_at)
        payload["credential"] = authenticator.assertion(
            {"challenge": b64url(bytes(ceremony.challenge))},
            PasskeyIdentity.objects.get(user=self.user).handle.bytes,
        )
        self.assert_rejected(self.post(LOGIN_VERIFY, payload, client))
        self.assertNotIn("_auth_user_id", client.session)

    def test_login_challenge_is_bound_to_issuing_session_and_expiry(self):
        authenticator, _ = self.register()
        for scenario in ("other-session", "expired"):
            with self.subTest(scenario=scenario):
                client = self.anonymous()
                payload = self.login_payload(authenticator, client=client)
                if scenario == "other-session":
                    client = self.anonymous()
                else:
                    Ceremony.objects.filter(pk=payload["ceremony_id"]).update(
                        expires_at=timezone.now() - timedelta(seconds=1)
                    )
                self.assert_rejected(self.post(LOGIN_VERIFY, payload, client))
                self.assertNotIn("_auth_user_id", client.session)

    def test_registration_ceremony_cannot_be_used_for_login(self):
        options = self.registration_options()
        client = self.anonymous()
        self.assert_rejected(
            self.post(
                LOGIN_VERIFY,
                {
                    "ceremony_id": options["ceremony_id"],
                    "credential": SoftwareAuthenticator().assertion(
                        options["publicKey"], bytes(16)
                    ),
                },
                client,
            )
        )
        self.assertNotIn("_auth_user_id", client.session)

    def test_user_handle_of_another_account_is_rejected(self):
        authenticator, _ = self.register()
        self.client.force_login(self.other)
        self.registration_options()
        client = self.anonymous()
        payload = self.login_payload(
            authenticator,
            client=client,
            handle=PasskeyIdentity.objects.get(user=self.other).handle.bytes,
        )
        self.assert_rejected(self.post(LOGIN_VERIFY, payload, client))
        self.assertNotIn("_auth_user_id", client.session)

    def test_inactive_account_cannot_log_in_even_if_deactivated_after_options(self):
        authenticator, record = self.register()
        client = self.anonymous()
        payload = self.login_payload(authenticator, client=client)
        get_user_model().objects.filter(pk=self.user.pk).update(is_active=False)
        self.assert_rejected(self.post(LOGIN_VERIFY, payload, client))
        self.assertNotIn("_auth_user_id", client.session)
        record.refresh_from_db()
        self.assertIsNone(record.last_used_at)

    def test_account_deactivated_after_registration_options_cannot_add_a_key(self):
        options = self.registration_options()
        get_user_model().objects.filter(pk=self.user.pk).update(is_active=False)
        response = self.post(
            REGISTER_VERIFY,
            {
                "ceremony_id": options["ceremony_id"],
                "credential": SoftwareAuthenticator().registration(
                    options["publicKey"]
                ),
            },
        )
        self.assertIn(response.status_code, (400, 401))
        self.assertFalse(PasskeyCredential.objects.exists())

    def test_missing_handle_or_mismatched_credential_id_is_rejected(self):
        authenticator, _ = self.register()
        for scenario in ("missing-handle", "mismatched-id"):
            with self.subTest(scenario=scenario):
                client = self.anonymous()
                payload = self.login_payload(authenticator, client=client)
                if scenario == "missing-handle":
                    payload["credential"]["response"]["userHandle"] = None
                else:
                    payload["credential"]["rawId"] = b64url(
                        b"a-different-credential-id"
                    )
                self.assert_rejected(self.post(LOGIN_VERIFY, payload, client))
                self.assertNotIn("_auth_user_id", client.session)

    def test_single_device_positive_counter_rollback_is_rejected(self):
        authenticator, record = self.register(counter=4)
        for counter in (4, 3, 0):
            with self.subTest(counter=counter):
                client = self.anonymous()
                payload = self.login_payload(
                    authenticator, client=client, counter=counter
                )
                self.assert_rejected(self.post(LOGIN_VERIFY, payload, client))
        record.refresh_from_db()
        self.assertEqual(record.sign_count, 4)

    def test_zero_counter_authenticator_can_authenticate(self):
        authenticator, _ = self.register(counter=0)
        client = self.anonymous()
        response = self.post(
            LOGIN_VERIFY,
            self.login_payload(authenticator, client=client, counter=0),
            client,
        )
        self.assertEqual(response.status_code, 200, response.content)

    def test_synced_passkey_accepts_zero_or_lower_counter_without_changing_eligibility(
        self,
    ):
        authenticator, record = self.register(
            counter=7, backup_eligible=True, backed_up=True
        )
        for counter in (0, 3):
            with self.subTest(counter=counter):
                client = self.anonymous()
                payload = self.login_payload(
                    authenticator,
                    client=client,
                    counter=counter,
                    backup_eligible=True,
                    backed_up=True,
                )
                response = self.post(LOGIN_VERIFY, payload, client)
                self.assertEqual(response.status_code, 200, response.content)
        record.refresh_from_db()
        self.assertTrue(record.backup_eligible)
        client = self.anonymous()
        self.assert_rejected(
            self.post(
                LOGIN_VERIFY,
                self.login_payload(authenticator, client=client, counter=8),
                client,
            )
        )

    def test_unknown_and_revoked_credentials_share_generic_failure(self):
        authenticator, record = self.register()
        failures = []
        for device in (SoftwareAuthenticator(), authenticator):
            if device is authenticator:
                record.revoked_at = timezone.now()
                record.save(update_fields=["revoked_at"])
            client = self.anonymous()
            response = self.post(
                LOGIN_VERIFY, self.login_payload(device, client=client), client
            )
            self.assert_rejected(response)
            failures.append(response.json())
        self.assertEqual(*failures)

    def test_login_does_not_change_existing_roles_or_warehouse_membership(self):
        from inventory.models import FunctionAccess, Warehouse

        group = Group.objects.create(name="Nhóm thử quyền")
        self.user.groups.add(group)
        access, _ = FunctionAccess.objects.update_or_create(
            user=self.user,
            defaults={"permissions": ["products_view"], "approval_level": 10},
        )
        warehouse = Warehouse.objects.create(code="PASSKEY-TEST", name="Kho thử riêng")
        warehouse.members.add(self.user)
        authenticator, _ = self.register()
        client = self.anonymous()
        response = self.post(
            LOGIN_VERIFY, self.login_payload(authenticator, client=client), client
        )
        self.assertEqual(response.status_code, 200, response.content)
        self.user.refresh_from_db()
        access.refresh_from_db()
        self.assertFalse(self.user.is_staff)
        self.assertFalse(self.user.is_superuser)
        self.assertEqual(
            list(self.user.groups.values_list("pk", flat=True)), [group.pk]
        )
        self.assertEqual(access.permissions, ["products_view"])
        self.assertEqual(access.approval_level, 10)
        self.assertTrue(warehouse.members.filter(pk=self.user.pk).exists())
        self.assertEqual(
            client.get("/products/", HTTP_HOST="localhost").status_code, 200
        )
        self.assertEqual(client.get("/team/", HTTP_HOST="localhost").status_code, 403)

    def test_external_redirect_is_replaced_by_local_default(self):
        authenticator, _ = self.register()
        for destination in (
            "https://evil.example/",
            "//evil.example/path",
            "https://localhost/account/password/",
        ):
            with self.subTest(destination=destination):
                client = self.anonymous()
                response = self.post(
                    LOGIN_VERIFY,
                    self.login_payload(
                        authenticator, client=client, next_path=destination, counter=0
                    ),
                    client,
                )
                self.assertEqual(response.status_code, 200, response.content)
                self.assertTrue(response.json()["redirect"].startswith("/"))
                self.assertFalse(response.json()["redirect"].startswith("//"))

    def test_remove_requires_ownership_password_and_post(self):
        _, record = self.register()
        path = f"{MANAGE}{record.pk}/remove/"
        self.assertEqual(self.client.get(path, HTTP_HOST="localhost").status_code, 405)
        response = self.client.post(path, {"password": "wrong"}, HTTP_HOST="localhost")
        self.assertEqual(response.status_code, 302)
        self.assertTrue(list(get_messages(response.wsgi_request)))
        record.refresh_from_db()
        self.assertIsNone(record.revoked_at)
        other_client = self.anonymous()
        other_client.force_login(self.other)
        self.assertIn(
            other_client.post(
                path, {"password": PASSWORD}, HTTP_HOST="localhost"
            ).status_code,
            (400, 404),
        )
        record.refresh_from_db()
        self.assertIsNone(record.revoked_at)
        response = self.client.post(path, {"password": PASSWORD}, HTTP_HOST="localhost")
        self.assertIn(response.status_code, (200, 302))
        record.refresh_from_db()
        self.assertIsNotNone(record.revoked_at)

    def test_revocation_invalidates_existing_passkey_session_but_not_password_session(
        self,
    ):
        authenticator, record = self.register()
        passkey_client = self.anonymous()
        response = self.post(
            LOGIN_VERIFY,
            self.login_payload(authenticator, client=passkey_client),
            passkey_client,
        )
        self.assertEqual(response.status_code, 200, response.content)
        password_client = self.anonymous()
        self.assertTrue(
            password_client.login(username=self.user.username, password=PASSWORD)
        )
        response = self.client.post(
            f"{MANAGE}{record.pk}/remove/",
            {"password": PASSWORD},
            HTTP_HOST="localhost",
        )
        self.assertIn(response.status_code, (200, 302))
        self.assertEqual(
            passkey_client.get(MANAGE, HTTP_HOST="localhost").status_code, 302
        )
        self.assertNotIn("_auth_user_id", passkey_client.session)
        self.assertEqual(
            password_client.get(MANAGE, HTTP_HOST="localhost").status_code, 200
        )
        self.assertEqual(int(password_client.session["_auth_user_id"]), self.user.pk)

    def test_password_login_replaces_the_same_users_previous_passkey_authentication(
        self,
    ):
        authenticator, record = self.register()
        client = self.anonymous()
        response = self.post(
            LOGIN_VERIFY, self.login_payload(authenticator, client=client), client
        )
        self.assertEqual(response.status_code, 200, response.content)
        self.assertEqual(str(client.session["passkey_credential_id"]), str(record.pk))
        response = client.post(
            "/login/",
            {"username": self.user.username, "password": PASSWORD, "next": MANAGE},
            HTTP_HOST="localhost",
        )
        self.assertEqual(response.status_code, 302)
        self.assertEqual(int(client.session["_auth_user_id"]), self.user.pk)
        self.assertNotIn("passkey_credential_id", client.session)

        # The credential owner revokes it from their other browser session.
        response = self.client.post(
            f"{MANAGE}{record.pk}/remove/",
            {"password": PASSWORD},
            HTTP_HOST="localhost",
        )
        self.assertEqual(response.status_code, 302)
        record.refresh_from_db()
        self.assertIsNotNone(record.revoked_at)
        self.assertEqual(client.get(MANAGE, HTTP_HOST="localhost").status_code, 200)
        self.assertEqual(int(client.session["_auth_user_id"]), self.user.pk)
        self.assertNotIn("passkey_credential_id", client.session)

    @override_settings(
        PASSWORD_HASHERS=["django.contrib.auth.hashers.PBKDF2PasswordHasher"]
    )
    def test_confirmation_does_not_upgrade_legacy_password_or_invalidate_the_session(
        self,
    ):
        old_password = PBKDF2PasswordHasher().encode(
            PASSWORD, "passkey-preview-only-salt", iterations=1
        )
        self.user.password = old_password
        self.user.save(update_fields=["password"])
        # Avoid password login, which intentionally upgrades old password hashes.
        self.client.force_login(self.user)
        original_session_key = self.client.session.session_key
        original_auth_hash = self.client.session["_auth_user_hash"]
        options = self.registration_options()
        self.user.refresh_from_db()
        self.assertEqual(self.user.password, old_password)
        self.assertEqual(self.client.session.session_key, original_session_key)
        self.assertEqual(self.client.session["_auth_user_hash"], original_auth_hash)

        authenticator = SoftwareAuthenticator()
        response = self.post(
            REGISTER_VERIFY,
            {
                "ceremony_id": options["ceremony_id"],
                "credential": authenticator.registration(options["publicKey"]),
            },
        )
        self.assertEqual(response.status_code, 200, response.content)
        record = PasskeyCredential.objects.get(credential_id=authenticator.id)
        self.assertEqual(record.user_id, self.user.pk)

        response = self.client.post(
            f"{MANAGE}{record.pk}/remove/",
            {"password": PASSWORD},
            HTTP_HOST="localhost",
        )
        self.assertEqual(response.status_code, 302)
        record.refresh_from_db()
        self.assertIsNotNone(record.revoked_at)
        self.user.refresh_from_db()
        self.assertEqual(self.user.password, old_password)
        self.assertEqual(self.client.session.session_key, original_session_key)
        self.assertEqual(self.client.session["_auth_user_hash"], original_auth_hash)
        self.assertEqual(
            self.client.get(MANAGE, HTTP_HOST="localhost").status_code, 200
        )
        self.assertEqual(int(self.client.session["_auth_user_id"]), self.user.pk)

    def test_existing_password_login_still_works(self):
        client = self.anonymous()
        response = client.post(
            "/login/",
            {
                "username": self.user.username,
                "password": PASSWORD,
                "next": "/account/password/",
            },
            HTTP_HOST="localhost",
        )
        self.assertEqual(response.status_code, 302)
        self.assertEqual(response.headers["Location"], "/account/password/")
        self.assertEqual(int(client.session["_auth_user_id"]), self.user.pk)
        self.assertNotIn("passkey_credential_id", client.session)
        self.assertEqual(
            client.get("/account/password/", HTTP_HOST="localhost").status_code, 200
        )

    def test_management_page_lists_only_own_active_credentials(self):
        _, own = self.register()
        own.label = "Chỉ máy của tài khoản hiện tại"
        own.save(update_fields=["label"])
        self.client.force_login(self.other)
        _, other = self.register()
        other.label = "Máy riêng của tài khoản khác"
        other.save(update_fields=["label"])
        self.client.force_login(self.user)
        response = self.client.get(MANAGE, HTTP_HOST="localhost")
        self.assertContains(response, own.label)
        self.assertNotContains(response, other.label)
        own.revoked_at = timezone.now()
        own.save(update_fields=["revoked_at"])
        self.assertNotContains(
            self.client.get(MANAGE, HTTP_HOST="localhost"), own.label
        )

    def test_disabled_or_mismatched_host_fails_closed_and_password_login_survives(self):
        client = self.anonymous()
        with self.settings(PASSKEY_ENABLED=False):
            response = self.post(LOGIN_OPTIONS, {}, client)
            self.assertEqual(response.status_code, 503)
            self.assertTrue(
                client.login(username=self.user.username, password=PASSWORD)
            )
        client.logout()
        response = client.post(
            LOGIN_OPTIONS, "{}", content_type="application/json", HTTP_HOST="testserver"
        )
        self.assert_rejected(response)
        self.assertFalse(Ceremony.objects.exists())

    def test_csrf_is_enforced_on_every_post_endpoint(self):
        _, record = self.register()
        client = Client(enforce_csrf_checks=True)
        client.force_login(self.user)
        for path in (
            REGISTER_OPTIONS,
            REGISTER_VERIFY,
            LOGIN_OPTIONS,
            LOGIN_VERIFY,
            f"{MANAGE}{record.pk}/remove/",
        ):
            with self.subTest(path=path):
                self.assertEqual(self.post(path, {}, client).status_code, 403)
        # A valid same-origin CSRF pair must pass the middleware into the real view.
        csrf_token = "a" * 32
        client.cookies["csrftoken"] = csrf_token
        response = self.post(
            REGISTER_OPTIONS,
            {"password": PASSWORD, "label": "CSRF thử riêng"},
            client,
            HTTP_X_CSRFTOKEN=csrf_token,
            HTTP_ORIGIN="http://localhost",
        )
        self.assertEqual(response.status_code, 200, response.content)
        response = self.post(
            REGISTER_OPTIONS,
            {"password": PASSWORD},
            client,
            HTTP_X_CSRFTOKEN=csrf_token,
            HTTP_ORIGIN="https://evil.example",
        )
        self.assertEqual(response.status_code, 403)

    def test_malformed_json_oversized_body_and_methods_do_not_create_credentials(self):
        for path in (REGISTER_OPTIONS, REGISTER_VERIFY, LOGIN_OPTIONS, LOGIN_VERIFY):
            with self.subTest(path=path):
                client = (
                    self.anonymous()
                    if path in (LOGIN_OPTIONS, LOGIN_VERIFY)
                    else self.client
                )
                self.assertEqual(
                    client.get(path, HTTP_HOST="localhost").status_code, 405
                )
                response = client.post(
                    path, "{", content_type="application/json", HTTP_HOST="localhost"
                )
                self.assert_rejected(response)
        self.assertFalse(PasskeyCredential.objects.exists())
        response = self.client.post(
            REGISTER_OPTIONS,
            json.dumps({"password": PASSWORD, "label": "x" * 70000}),
            content_type="application/json",
            HTTP_HOST="localhost",
        )
        self.assert_rejected(response)

    def test_an_authenticated_user_cannot_replace_their_identity_through_login(self):
        self.assertEqual(self.post(LOGIN_OPTIONS, {}).status_code, 409)
        self.assertEqual(int(self.client.session["_auth_user_id"]), self.user.pk)

    def test_ceremony_payload_and_audit_store_no_password_or_device_secrets(self):
        authenticator, _ = self.register()
        for ceremony in Ceremony.objects.all():
            stored = json.dumps(ceremony.payload)
            self.assertNotIn(PASSWORD, stored)
            self.assertNotIn("password", stored.lower())
            self.assertNotIn("private_key", stored.lower())
        self.assertEqual(
            {field.name for field in SecurityEvent._meta.fields},
            {"id", "user", "action", "created_at"},
        )
        for event in SecurityEvent.objects.all():
            self.assertNotIn(PASSWORD, event.action)
            self.assertNotIn(authenticator.id, event.action)

    def test_database_rate_limit_rejects_a_burst_and_expires(self):
        client = self.anonymous()
        response = None
        for _ in range(120):
            response = self.post(LOGIN_OPTIONS, {}, client)
            if response.status_code == 429:
                break
            self.assertEqual(response.status_code, 200, response.content)
        self.assertIsNotNone(response)
        self.assertEqual(response.status_code, 429)
        self.assertTrue(RateBucket.objects.exists())
        RateBucket.objects.all().update(
            expires_at=timezone.now() - timedelta(seconds=1)
        )
        self.assertEqual(self.post(LOGIN_OPTIONS, {}, client).status_code, 200)


@skipUnless(
    connection.vendor == "postgresql",
    "Concurrent consumption requires PostgreSQL row locks",
)
@override_settings(**SETTINGS)
class ConcurrentPasskeyTests(CeremonyHelpers, TransactionTestCase):
    def setUp(self):
        self.user = get_user_model().objects.create_user(
            "passkey-race-preview", password=PASSWORD
        )
        self.client.force_login(self.user)

    def test_concurrent_assertions_consume_a_ceremony_once(self):
        authenticator, record = self.register()
        browser = self.anonymous()
        payload = self.login_payload(authenticator, client=browser)
        cookies = copy.deepcopy(browser.cookies)
        gate = Barrier(2)

        def verify_once(_):
            close_old_connections()
            try:
                client = Client()
                client.cookies = copy.deepcopy(cookies)
                gate.wait(timeout=10)
                return self.post(LOGIN_VERIFY, payload, client).status_code
            finally:
                connections.close_all()

        with ThreadPoolExecutor(max_workers=2) as pool:
            statuses = list(pool.map(verify_once, range(2)))
        self.assertCountEqual(statuses, [200, 400])
        record.refresh_from_db()
        self.assertEqual(record.sign_count, 1)
        self.assertIsNotNone(Ceremony.objects.get(pk=payload["ceremony_id"]).used_at)

    def test_two_registrations_cannot_exceed_the_active_credential_cap(self):
        for _ in range(9):
            authenticator = SoftwareAuthenticator()
            PasskeyCredential.objects.create(
                user=self.user,
                credential_id=authenticator.id,
                public_key=authenticator.public_key,
                label="Thử đồng thời riêng",
            )
        operations = []
        for _ in range(2):
            client = Client()
            client.force_login(self.user)
            options = self.registration_options(client)
            operations.append(
                (
                    copy.deepcopy(client.cookies),
                    {
                        "ceremony_id": options["ceremony_id"],
                        "credential": SoftwareAuthenticator().registration(
                            options["publicKey"]
                        ),
                    },
                )
            )
        gate = Barrier(2)

        def register_once(operation):
            close_old_connections()
            try:
                client = Client()
                client.cookies = operation[0]
                gate.wait(timeout=10)
                return self.post(REGISTER_VERIFY, operation[1], client).status_code
            finally:
                connections.close_all()

        with ThreadPoolExecutor(max_workers=2) as pool:
            statuses = list(pool.map(register_once, operations))
        self.assertCountEqual(statuses, [200, 400])
        self.assertEqual(
            PasskeyCredential.objects.filter(
                user=self.user, revoked_at__isnull=True
            ).count(),
            10,
        )

    def login_waiting_for_lock(self, cookies, payload, table, waiting):
        """Run a real request, signalling just before its blocking row lock."""
        close_old_connections()

        def observe_lock(execute, sql, params, many, context):
            if f'FROM "{table}"' in sql and "FOR UPDATE" in sql:
                waiting.set()
            return execute(sql, params, many, context)

        try:
            client = Client()
            client.cookies = copy.deepcopy(cookies)
            with connection.execute_wrapper(observe_lock):
                response = self.post(LOGIN_VERIFY, payload, client)
            return response.status_code, response.json(), dict(client.session)
        finally:
            connections.close_all()

    def test_challenge_expiring_while_waiting_for_its_lock_cannot_authenticate(self):
        authenticator, record = self.register()
        browser = self.anonymous()
        payload = self.login_payload(authenticator, client=browser)
        waiting = Event()
        with ThreadPoolExecutor(max_workers=1) as pool:
            with transaction.atomic():
                ceremony = Ceremony.objects.select_for_update().get(
                    pk=payload["ceremony_id"]
                )
                ceremony.expires_at = timezone.now() + timedelta(seconds=1)
                ceremony.save(update_fields=["expires_at"])
                future = pool.submit(
                    self.login_waiting_for_lock,
                    browser.cookies,
                    payload,
                    Ceremony._meta.db_table,
                    waiting,
                )
                self.assertTrue(
                    waiting.wait(timeout=10), "Login did not reach the ceremony lock"
                )
                # Keep the real lock past expiry without changing the row again.
                # A SQL timestamp captured before waiting must not authorize it.
                remaining = (ceremony.expires_at - timezone.now()).total_seconds()
                self.assertGreater(remaining, 0)
                Event().wait(timeout=remaining + 0.05)
            status, _, session = future.result(timeout=10)
        self.assertEqual(status, 400)
        self.assertNotIn("_auth_user_id", session)
        record.refresh_from_db()
        self.assertIsNone(record.last_used_at)
        ceremony.refresh_from_db()
        self.assertIsNone(ceremony.used_at)

    def test_account_deleted_between_lookup_and_lock_returns_generic_failure(self):
        authenticator, _ = self.register()
        browser = self.anonymous()
        payload = self.login_payload(authenticator, client=browser)
        waiting = Event()
        user_id = self.user.pk
        with ThreadPoolExecutor(max_workers=1) as pool:
            with transaction.atomic():
                user = get_user_model().objects.select_for_update().get(pk=user_id)
                future = pool.submit(
                    self.login_waiting_for_lock,
                    browser.cookies,
                    payload,
                    get_user_model()._meta.db_table,
                    waiting,
                )
                self.assertTrue(
                    waiting.wait(timeout=10), "Login did not reach the account lock"
                )
                user.delete()
            status, body, session = future.result(timeout=10)
        self.assertEqual(status, 400)
        self.assertEqual(
            body,
            {"error": "Không thể xác thực passkey. Hãy thử lại hoặc dùng mật khẩu."},
        )
        self.assertNotIn("_auth_user_id", session)
        self.assertFalse(get_user_model().objects.filter(pk=user_id).exists())
        self.assertFalse(SecurityEvent.objects.filter(action="authenticated").exists())
        self.assertIsNotNone(Ceremony.objects.get(pk=payload["ceremony_id"]).used_at)
