from django.core.management import call_command
from django.core.management.base import CommandError
from django.test import SimpleTestCase, override_settings

from .preview import validate_preview_environment


class PreviewSafetyTests(SimpleTestCase):
    def test_preview_refuses_production_urls_and_database_overrides(self):
        env = {
            "DHD_PREVIEW": "1",
            "DEBUG": "1",
            "DATABASE_URL": "postgresql://dhd_preview:fake@db/dhd_preview",
        }
        validate_preview_environment(env)
        for changes in [
            {"DHD_PREVIEW": "0"},
            {"DEBUG": "0"},
            {"RENDER_EXTERNAL_HOSTNAME": "kiemsoatnoibolemon.onrender.com"},
            {
                "DATABASE_URL": "postgresql://dhd_preview:fake@company.neon.tech/dhd_preview"
            },
            {"DATABASE_URL": "postgresql://dhd_preview:fake@localhost/production"},
            {"DATABASE_URL": "postgresql://company:fake@localhost/dhd_preview"},
            {"DATABASE_URL": env["DATABASE_URL"] + "?host=company.neon.tech"},
            {"DATABASE_URL": "sqlite:///company.sqlite3"},
        ]:
            with self.subTest(changes=changes), self.assertRaises(RuntimeError):
                validate_preview_environment({**env, **changes})

    @override_settings(DHD_PREVIEW=False)
    def test_sample_setup_is_refused_before_any_database_query_outside_preview(self):
        with self.assertRaises(CommandError):
            call_command("setup_preview")

    @override_settings(DHD_PREVIEW=True)
    def test_preview_is_labeled_on_login(self):
        self.assertContains(self.client.get("/login/"), "BẢN CHẠY THỬ")

    @override_settings(DHD_PREVIEW=False)
    def test_production_login_has_no_preview_banner(self):
        self.assertNotContains(self.client.get("/login/"), "BẢN CHẠY THỬ")
