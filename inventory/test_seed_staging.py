from io import StringIO

from django.contrib.auth import get_user_model
from django.core.management import call_command
from django.core.management.base import CommandError
from django.test import TestCase, override_settings

from .models import Balance, Document, Product, Warehouse


class SeedStagingTests(TestCase):
    def test_refuses_on_production_without_writing(self):
        with self.assertRaisesMessage(CommandError, "APP_ENVIRONMENT=staging"):
            call_command("seed_staging", stdout=StringIO())
        self.assertFalse(Warehouse.objects.exists())
        self.assertFalse(get_user_model().objects.exists())

    @override_settings(APP_ENVIRONMENT="staging")
    def test_seeds_accounts_balances_and_document_states_once(self):
        out = StringIO()
        call_command("seed_staging", stdout=out)
        self.assertIn("Mật khẩu chung", out.getvalue())
        users = get_user_model().objects.filter(username__startswith="thu_")
        self.assertEqual(
            sorted(users.values_list("username", flat=True)),
            ["thu_admin", "thu_chixem", "thu_nguoiduyet", "thu_nguoilap"],
        )
        self.assertTrue(users.get(username="thu_admin").is_superuser)
        stock = Balance.objects.get(
            warehouse__code="THU-HN", product__sku="THU-001"
        ).quantity
        self.assertEqual(stock, 120)
        self.assertEqual(
            sorted(set(Document.objects.values_list("status", flat=True))),
            ["DRAFT", "POSTED", "REJECTED", "TRANSIT"],
        )
        self.assertTrue(all("thử" in p.name for p in Product.objects.all()))
        with self.assertRaisesMessage(CommandError, "đã có dữ liệu"):
            call_command("seed_staging", stdout=StringIO())

    @override_settings(APP_ENVIRONMENT="staging")
    def test_view_only_account_cannot_create_documents(self):
        call_command("seed_staging", stdout=StringIO())
        viewer = get_user_model().objects.get(username="thu_chixem")
        self.client.force_login(viewer)
        self.assertEqual(self.client.get("/documents/").status_code, 200)
        self.assertEqual(self.client.get("/stock/").status_code, 403)
        self.assertEqual(self.client.get("/documents/new/").status_code, 403)


class SeedStagingAutoTests(TestCase):
    """start.sh calls `seed_staging --auto` on staging at every boot."""

    def test_auto_refuses_on_production(self):
        with self.assertRaises(CommandError):
            call_command("seed_staging", "--auto", stdout=StringIO())
        self.assertFalse(Warehouse.objects.exists())

    @override_settings(APP_ENVIRONMENT="staging")
    def test_auto_skips_without_password_then_seeds_once_without_printing_it(self):
        from unittest.mock import patch

        with patch.dict("os.environ", {"STAGING_SEED_PASSWORD": ""}):
            out = StringIO()
            call_command("seed_staging", "--auto", stdout=out)
        self.assertIn("Bỏ qua", out.getvalue())
        self.assertFalse(Warehouse.objects.exists())
        with patch.dict("os.environ", {"STAGING_SEED_PASSWORD": "Mat-khau-thu-2026"}):
            out = StringIO()
            call_command("seed_staging", "--auto", stdout=out)
            self.assertNotIn("Mat-khau-thu-2026", out.getvalue())
            user = get_user_model().objects.get(username="thu_admin")
            self.assertTrue(user.check_password("Mat-khau-thu-2026"))
            again = StringIO()
            call_command("seed_staging", "--auto", stdout=again)
        self.assertIn("đã có dữ liệu", again.getvalue())
        self.assertEqual(Warehouse.objects.count(), 2)
