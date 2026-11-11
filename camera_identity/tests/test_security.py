"""Camera API security only: model results are mocked, not biometric evidence."""

import base64
import io
import json
from datetime import timedelta
from unittest.mock import patch

from cryptography.fernet import Fernet
from django.contrib.auth import get_user_model
from django.test import Client, TestCase, override_settings
from django.utils import timezone
from PIL import Image

from camera_identity.models import FaceChallenge, FaceProfile

MANAGE = "/account/camera/"
ENROLL = MANAGE + "enroll/options/"
SAVE = MANAGE + "enroll/verify/"
START = "/camera/verify/options/"
COMPARE = "/camera/verify/finish/"
PASSWORD = "Camera-security-preview-only"
KEY = Fernet.generate_key().decode()


def jpeg_fixture():
    stream = io.BytesIO()
    Image.new("RGB", (640, 480), (120, 120, 120)).save(stream, format="JPEG")
    return base64.b64encode(stream.getvalue()).decode()


@override_settings(
    CAMERA_IDENTITY_ENABLED=True,
    CAMERA_IDENTITY_TEMPLATE_KEY=KEY,
    ALLOWED_HOSTS=["localhost", "testserver"],
    PASSWORD_HASHERS=["django.contrib.auth.hashers.MD5PasswordHasher"],
)
class CameraSecurityTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.owner = get_user_model().objects.create_user(
            "camera-preview-owner", password=PASSWORD
        )
        cls.other = get_user_model().objects.create_user(
            "camera-preview-other", password=PASSWORD
        )
        cls.admin = get_user_model().objects.create_superuser(
            "camera-preview-admin", password=PASSWORD
        )
        cls.frame = jpeg_fixture()

    def setUp(self):
        self.client.force_login(self.owner)
        self.steps = ["CENTER", "LEFT", "RIGHT"]
        self.engine = patch("camera_identity.engine.analyse", self.analyse)
        self.engine.start()
        self.addCleanup(self.engine.stop)

    def analyse(self, frames):
        self.assertEqual(len(frames), 3)
        return {
            "model_id": "isolated-security-model-v1",
            "descriptors": [[1.0] + [0.0] * 127 for _ in frames],
            "poses": [
                {
                    "label": step,
                    "yaw": {"CENTER": 0.0, "LEFT": -0.3, "RIGHT": 0.3}[step],
                }
                for step in self.steps
            ],
            "quality": [{"ok": True} for _ in frames],
        }

    def post(self, path, data, client=None):
        return (client or self.client).post(
            path,
            json.dumps(data),
            content_type="application/json",
            HTTP_HOST="localhost",
        )

    def options(self, path=ENROLL, client=None, **data):
        payload = (
            {"password": PASSWORD, "consent": True}
            if path == ENROLL
            else {"username": self.owner.username}
        )
        payload.update(data)
        response = self.post(path, payload, client)
        self.assertEqual(response.status_code, 200, response.content)
        result = response.json()
        self.assertEqual(result["mode"], "evaluation")
        self.assertIs(result["login_permitted"], False)
        self.steps = result["steps"]
        self.assertEqual(sorted(self.steps), ["CENTER", "LEFT", "RIGHT"])
        return result

    def finish(self, options, path=SAVE, client=None, **extra):
        payload = {"challenge_id": options["challenge_id"], "frames": [self.frame] * 3}
        payload.update(extra)
        return self.post(path, payload, client)

    def enroll(self):
        response = self.finish(self.options())
        self.assertEqual(response.status_code, 200, response.content)
        self.assertIs(response.json()["ok"], True)
        return FaceProfile.objects.get(user=self.owner)

    def test_enrollment_requires_existing_login_password_and_explicit_consent(self):
        anonymous = Client()
        self.assertIn(
            self.post(
                ENROLL, {"password": PASSWORD, "consent": True}, anonymous
            ).status_code,
            (401, 403),
        )
        for data in (
            {"password": "wrong", "consent": True},
            {"password": PASSWORD, "consent": False},
            {"password": PASSWORD},
        ):
            with self.subTest(data=list(data)):
                self.assertIn(self.post(ENROLL, data).status_code, (400, 403))
        self.assertFalse(FaceProfile.objects.exists())

    def test_template_is_encrypted_and_plaintext_never_returned(self):
        profile = self.enroll()
        encrypted = bytes(profile.encrypted_template)
        self.assertNotIn(b"isolated-security-model-v1", encrypted)
        decoded = Fernet(KEY.encode()).decrypt(encrypted)
        payload = json.loads(decoded)
        self.assertEqual(len(payload["descriptor"]), 128)
        self.assertEqual(payload["user_id"], self.owner.pk)
        response = self.client.get(MANAGE, HTTP_HOST="localhost")
        self.assertEqual(response.status_code, 200)
        self.assertNotIn(encrypted, response.content)
        self.assertNotIn(decoded, response.content)
        self.assertTrue(profile.consent_version)

    def test_enrollment_challenge_is_bound_to_browser_and_single_use(self):
        options = self.options()
        foreign = Client()
        foreign.force_login(self.owner)
        self.assertIn(self.finish(options, client=foreign).status_code, (400, 403))
        self.assertEqual(self.finish(options).status_code, 200)
        self.assertIn(self.finish(options).status_code, (400, 403))

    def test_expired_challenge_cannot_create_template(self):
        options = self.options()
        FaceChallenge.objects.filter(pk=options["challenge_id"]).update(
            expires_at=timezone.now() - timedelta(seconds=1)
        )
        self.assertIn(self.finish(options).status_code, (400, 403))
        self.assertFalse(FaceProfile.objects.exists())

    def test_password_change_invalidates_pending_enrollment(self):
        options = self.options()
        session_key = self.client.session.session_key
        self.owner.set_password("changed-camera-preview-only")
        self.owner.save(update_fields=["password"])
        session = self.client.session
        session["_auth_user_hash"] = self.owner.get_session_auth_hash()
        session.save()
        self.assertEqual(self.client.session.session_key, session_key)
        self.assertIn(self.finish(options).status_code, (400, 403))
        self.assertFalse(FaceProfile.objects.exists())

    def test_evaluation_match_never_creates_login_session_or_grants_permissions(self):
        self.enroll()
        anonymous = Client()
        options = self.options(START, anonymous)
        response = self.finish(options, COMPARE, anonymous)
        self.assertEqual(response.status_code, 200, response.content)
        result = response.json()
        self.assertIs(result["matched"], True)
        self.assertIs(result["login_permitted"], False)
        self.assertEqual(result["mode"], "evaluation")
        self.assertNotIn("_auth_user_id", anonymous.session)
        self.owner.refresh_from_db()
        self.assertFalse(self.owner.is_staff)
        self.assertFalse(self.owner.is_superuser)
        self.assertFalse(self.owner.user_permissions.exists())

    def test_browser_claim_of_match_cannot_override_server_decision(self):
        self.enroll()
        anonymous = Client()
        options = self.options(START, anonymous)
        with patch("camera_identity.engine.analyse") as mocked:
            data = self.analyse([self.frame] * 3)
            data["descriptors"] = [[0.0, 1.0] + [0.0] * 126 for _ in range(3)]
            mocked.return_value = data
            response = self.finish(
                options,
                COMPARE,
                anonymous,
                faceMatched=True,
                matched=True,
                login_permitted=True,
            )
        self.assertEqual(response.status_code, 200, response.content)
        self.assertIs(response.json()["matched"], False)
        self.assertIs(response.json()["login_permitted"], False)
        self.assertNotIn("_auth_user_id", anonymous.session)

    def test_unknown_and_inactive_accounts_do_not_authenticate(self):
        self.enroll()
        self.owner.is_active = False
        self.owner.save(update_fields=["is_active"])
        for username in ("not-a-camera-account", self.owner.username):
            with self.subTest(username=username):
                anonymous = Client()
                options = self.options(START, anonymous, username=username)
                response = self.finish(options, COMPARE, anonymous)
                self.assertEqual(response.status_code, 200, response.content)
                self.assertIs(response.json()["matched"], False)
                self.assertIs(response.json()["login_permitted"], False)
                self.assertNotIn("_auth_user_id", anonymous.session)

    def test_account_disabled_after_options_cannot_match(self):
        self.enroll()
        anonymous = Client()
        options = self.options(START, anonymous)
        get_user_model().objects.filter(pk=self.owner.pk).update(is_active=False)
        response = self.finish(options, COMPARE, anonymous)
        self.assertEqual(response.status_code, 200, response.content)
        self.assertIs(response.json()["matched"], False)
        self.assertNotIn("_auth_user_id", anonymous.session)

    def test_admin_cannot_read_or_remove_another_users_biometric_profile(self):
        profile = self.enroll()
        admin_client = Client()
        admin_client.force_login(self.admin)
        response = admin_client.get(
            MANAGE, {"user_id": self.owner.pk}, HTTP_HOST="localhost"
        )
        self.assertEqual(response.status_code, 200)
        self.assertIsNone(response.context["profile"])
        self.assertNotIn(bytes(profile.encrypted_template), response.content)
        response = admin_client.post(
            MANAGE + "remove/",
            {"password": PASSWORD, "user_id": self.owner.pk},
            HTTP_HOST="localhost",
        )
        self.assertIn(response.status_code, (200, 302))
        self.assertTrue(FaceProfile.objects.filter(pk=profile.pk).exists())

    def test_engine_failure_does_not_store_template_or_create_session(self):
        options = self.options()
        with patch(
            "camera_identity.engine.analyse",
            side_effect=RuntimeError("synthetic engine failure"),
        ):
            response = self.finish(options)
        self.assertEqual(response.status_code, 503)
        self.assertFalse(FaceProfile.objects.exists())
        self.assertEqual(int(self.client.session["_auth_user_id"]), self.owner.pk)
        anonymous = Client()
        options = self.options(START, anonymous)
        with patch(
            "camera_identity.engine.analyse",
            side_effect=RuntimeError("synthetic engine failure"),
        ):
            response = self.finish(options, COMPARE, anonymous)
        self.assertEqual(response.status_code, 503)
        self.assertNotIn("_auth_user_id", anonymous.session)

    def test_encrypted_template_cannot_be_swapped_between_accounts(self):
        owner_profile = self.enroll()
        other_client = Client()
        other_client.force_login(self.other)
        response = self.finish(self.options(client=other_client), client=other_client)
        self.assertEqual(response.status_code, 200, response.content)
        FaceProfile.objects.filter(user=self.other).update(
            encrypted_template=owner_profile.encrypted_template
        )
        anonymous = Client()
        options = self.options(START, anonymous, username=self.other.username)
        response = self.finish(options, COMPARE, anonymous)
        self.assertEqual(response.status_code, 503)
        self.assertNotIn("_auth_user_id", anonymous.session)

    def test_frame_count_and_malformed_result_fail_closed(self):
        options = self.options()
        self.assertIn(self.finish(options, frames=[self.frame]).status_code, (400, 403))
        self.assertFalse(FaceProfile.objects.exists())
        options = self.options()
        with patch(
            "camera_identity.engine.analyse",
            return_value={
                "model_id": "fake",
                "descriptors": [[float("nan")] * 128] * 3,
                "poses": [],
                "quality": [],
            },
        ):
            response = self.finish(options)
        self.assertIn(response.status_code, (400, 503))
        self.assertFalse(FaceProfile.objects.exists())

    def test_csrf_is_required_for_enrollment_and_anonymous_comparison(self):
        strict = Client(enforce_csrf_checks=True)
        strict.force_login(self.owner)
        self.assertEqual(
            self.post(
                ENROLL, {"password": PASSWORD, "consent": True}, strict
            ).status_code,
            403,
        )
        self.assertEqual(
            self.post(
                START,
                {"username": self.owner.username},
                Client(enforce_csrf_checks=True),
            ).status_code,
            403,
        )

    def test_deletion_requires_own_password_and_retains_password_session(self):
        profile = self.enroll()
        wrong = self.client.post(
            MANAGE + "remove/", {"password": "wrong"}, HTTP_HOST="localhost"
        )
        self.assertIn(wrong.status_code, (302, 400, 403))
        self.assertTrue(FaceProfile.objects.filter(pk=profile.pk).exists())
        response = self.client.post(
            MANAGE + "remove/", {"password": PASSWORD}, HTTP_HOST="localhost"
        )
        self.assertIn(response.status_code, (200, 302))
        self.assertFalse(FaceProfile.objects.filter(user=self.owner).exists())
        self.assertEqual(int(self.client.session["_auth_user_id"]), self.owner.pk)

    @override_settings(CAMERA_IDENTITY_ENABLED=False)
    def test_disabled_feature_does_not_change_existing_password_login(self):
        self.assertIn(
            self.client.get(MANAGE, HTTP_HOST="localhost").status_code, (404, 503)
        )
        self.assertIn(
            self.post(START, {"username": self.owner.username}).status_code, (404, 503)
        )
        client = Client()
        response = client.post(
            "/login/",
            {"username": self.owner.username, "password": PASSWORD},
            HTTP_HOST="localhost",
        )
        self.assertEqual(response.status_code, 302)
        self.assertEqual(int(client.session["_auth_user_id"]), self.owner.pk)

    @override_settings(CAMERA_IDENTITY_TEMPLATE_KEY="")
    def test_missing_encryption_key_fails_closed(self):
        self.assertEqual(
            self.post(ENROLL, {"password": PASSWORD, "consent": True}).status_code, 503
        )
        self.assertFalse(FaceProfile.objects.exists())
