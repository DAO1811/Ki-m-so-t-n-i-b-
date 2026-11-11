"""Deployment safeguards, without loading a recognition model or real faces."""

import base64
import json
import os
import subprocess
import sys

from cryptography.fernet import Fernet, InvalidToken
from django.conf import settings
from django.test import Client, RequestFactory, SimpleTestCase, override_settings
from django.views.debug import SafeExceptionReporterFilter

from camera_identity import services
from camera_identity.views import api

STRONG_SECRET = "camera-deployment-test-key-8d7f3c42a91e6b05"
SECOND_SECRET = "camera-deployment-test-key-41c6e93b70a5d82f"
EXPLICIT_KEY = Fernet.generate_key().decode()


@override_settings(
    CAMERA_IDENTITY_ENABLED=True, CAMERA_IDENTITY_DERIVE_TEMPLATE_KEY=True
)
class CameraTemplateDeploymentTests(SimpleTestCase):
    @override_settings(CAMERA_IDENTITY_DERIVE_TEMPLATE_KEY=False)
    def test_no_implicit_derived_key_when_not_enabled(self):
        with override_settings(
            SECRET_KEY=STRONG_SECRET, CAMERA_IDENTITY_TEMPLATE_KEY=""
        ):
            with self.assertRaises(services.CameraError):
                services.cipher()

    @override_settings(SECRET_KEY=STRONG_SECRET, CAMERA_IDENTITY_TEMPLATE_KEY="")
    def test_derived_template_key_is_stable_and_domain_separated(self):
        token = services.cipher().encrypt(b"synthetic-encrypted-template")
        self.assertEqual(
            services.cipher().decrypt(token), b"synthetic-encrypted-template"
        )
        direct = Fernet(base64.urlsafe_b64encode(STRONG_SECRET.encode()[:32]))
        with self.assertRaises(InvalidToken):
            direct.decrypt(token)

    @override_settings(SECRET_KEY=STRONG_SECRET, CAMERA_IDENTITY_TEMPLATE_KEY="")
    def test_rotation_of_fallback_secret_cannot_silently_read_old_templates(self):
        token = services.cipher().encrypt(b"synthetic-encrypted-template")
        with override_settings(SECRET_KEY=SECOND_SECRET):
            with self.assertRaises(InvalidToken):
                services.cipher().decrypt(token)

    @override_settings(SECRET_KEY="weak", CAMERA_IDENTITY_TEMPLATE_KEY=EXPLICIT_KEY)
    def test_explicit_fernet_key_is_preferred_over_derived_fallback(self):
        token = services.cipher().encrypt(b"synthetic-encrypted-template")
        self.assertEqual(
            Fernet(EXPLICIT_KEY.encode()).decrypt(token),
            b"synthetic-encrypted-template",
        )
        with override_settings(SECRET_KEY=SECOND_SECRET):
            self.assertEqual(
                services.cipher().decrypt(token), b"synthetic-encrypted-template"
            )

    @override_settings(CAMERA_IDENTITY_TEMPLATE_KEY="")
    def test_weak_and_known_development_secrets_fail_closed(self):
        for secret in (
            "",
            "weak",
            "x" * 31,
            "local-development-only-change-before-deployment",
        ):
            with self.subTest(
                secret_kind="known-development"
                if secret.startswith("local-")
                else len(secret)
            ):
                with override_settings(SECRET_KEY=secret):
                    with self.assertRaises(services.CameraError) as caught:
                        services.cipher()
                    self.assertEqual(caught.exception.status, 503)

    @override_settings(
        SECRET_KEY=STRONG_SECRET, CAMERA_IDENTITY_TEMPLATE_KEY="not-a-key"
    )
    def test_invalid_explicit_key_is_not_hidden_by_fallback(self):
        with self.assertRaises(services.CameraError) as caught:
            services.cipher()
        self.assertEqual(caught.exception.status, 503)

    @override_settings(
        CAMERA_IDENTITY_ENABLED=False,
        SECRET_KEY=STRONG_SECRET,
        CAMERA_IDENTITY_TEMPLATE_KEY=EXPLICIT_KEY,
    )
    def test_disabled_feature_remains_disabled_even_with_valid_keys(self):
        with self.assertRaises(services.CameraError) as caught:
            services.cipher()
        self.assertEqual(caught.exception.status, 503)

    def test_source_configuration_is_disabled_without_explicit_environment(self):
        env = os.environ.copy()
        for name in list(env):
            if name.startswith(
                (
                    "CAMERA_IDENTITY_",
                    "DATABASE_",
                    "RENDER_",
                    "GOOGLE_",
                    "GROQ_",
                    "EMAIL_",
                    "SMTP_",
                    "INITIAL_ADMIN_",
                )
            ):
                env.pop(name)
        env.update(
            DEBUG="1", DATABASE_URL="sqlite:///:memory:", SECRET_KEY=STRONG_SECRET
        )
        result = subprocess.run(
            [
                sys.executable,
                "-c",
                "from config.settings import CAMERA_IDENTITY_ENABLED; print(CAMERA_IDENTITY_ENABLED)",
            ],
            cwd=settings.BASE_DIR,
            env=env,
            capture_output=True,
            text=True,
            timeout=10,
            check=False,
        )
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(result.stdout.strip(), "False")


@override_settings(
    CAMERA_IDENTITY_ENABLED=True,
    CAMERA_IDENTITY_TEMPLATE_KEY=EXPLICIT_KEY,
    ALLOWED_HOSTS=["localhost"],
)
class CameraReadinessTests(SimpleTestCase):
    @override_settings(DEBUG=False)
    def test_unexpected_json_api_error_redacts_password_and_frames_in_tracebacks(self):
        marker = "synthetic-camera-privacy-marker"

        @api()
        def synthetic_failure(request, data):
            raise RuntimeError("synthetic internal failure")

        request = RequestFactory().post(
            "/camera/verify/finish/",
            json.dumps({"password": marker, "frames": [marker]}),
            content_type="application/json",
        )
        try:
            synthetic_failure(request)
        except RuntimeError:
            trace = sys.exc_info()[2]
            filtered_frames = 0
            while trace:
                frame = trace.tb_frame
                if frame.f_code.co_name in {"view", "synthetic_failure"}:
                    filtered = (
                        SafeExceptionReporterFilter().get_traceback_frame_variables(
                            request, frame
                        )
                    )
                    self.assertNotIn(marker, repr(filtered))
                    filtered_frames += 1
                trace = trace.tb_next
            self.assertEqual(filtered_frames, 2)
        else:
            self.fail("The test must exercise an unexpected API exception")

    def test_readiness_does_not_query_database_or_expose_paths_and_secrets(self):
        from unittest.mock import patch

        with patch("camera_identity.engine.configuration_ready", return_value=True):
            response = Client().get("/camera/health/", HTTP_HOST="localhost")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(
            response.json(),
            {
                "enabled": True,
                "configured": True,
                "mode": "evaluation",
                "login_permitted": False,
            },
        )
        self.assertIn("no-store", response.headers["Cache-Control"])

    @override_settings(CAMERA_IDENTITY_ENABLED=False)
    def test_disabled_readiness_does_not_report_ready(self):
        response = Client().get("/camera/health/", HTTP_HOST="localhost")
        self.assertEqual(response.status_code, 503)
        self.assertFalse(response.json()["configured"])
