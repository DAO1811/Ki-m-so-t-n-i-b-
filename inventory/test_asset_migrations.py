from datetime import datetime
from decimal import Decimal
from zoneinfo import ZoneInfo

from django.db import connection
from django.db.migrations.executor import MigrationExecutor
from django.test import TransactionTestCase


class AssetMigrationTests(TransactionTestCase):
    def test_existing_stock_values_users_and_historical_dates_survive_upgrade(self):
        old = [("inventory", "0007_balance_nonnegative_stock_value")]
        latest = [("inventory", "0014_stocktake_catalog_snapshot")]
        executor = MigrationExecutor(connection)
        try:
            executor.migrate(old)
            apps = executor.loader.project_state(old).apps
            User = apps.get_model("auth", "User")
            Warehouse = apps.get_model("inventory", "Warehouse")
            Product = apps.get_model("inventory", "Product")
            Document = apps.get_model("inventory", "Document")
            Balance = apps.get_model("inventory", "Balance")
            Line = apps.get_model("inventory", "Line")
            user = User.objects.create(
                username="historical_user", password="preserve-hash-marker"
            )
            warehouse = Warehouse.objects.create(code="OLD", name="Kho cũ")
            product = Product.objects.create(sku="OLD", name="Hàng cũ", unit="Cái")
            second_product = Product.objects.create(
                sku="OLD2", name="Hàng cũ 2", unit="Cái"
            )
            balance = Balance.objects.create(
                warehouse=warehouse, product=product, quantity=5, value=1250
            )
            posted = datetime(2026, 9, 1, 18, 30, tzinfo=ZoneInfo("UTC"))
            doc = Document.objects.create(
                kind="IN",
                destination=warehouse,
                created_by=user,
                status="POSTED",
                posted_by=user,
                posted_at=posted,
            )
            Line.objects.create(
                document=doc, product=product, quantity=5, unit_price=250
            )
            executor = MigrationExecutor(connection)
            executor.migrate(latest)
            apps = executor.loader.project_state(latest).apps
            upgraded = apps.get_model("inventory", "Document").objects.get(pk=doc.pk)
            products = apps.get_model("inventory", "Product")
            self.assertNotEqual(
                products.objects.get(pk=product.pk).qr_token,
                products.objects.get(pk=second_product.pk).qr_token,
            )
            upgraded_balance = apps.get_model("inventory", "Balance").objects.get(
                pk=balance.pk
            )
            self.assertEqual(str(upgraded.business_date), "2026-09-02")
            self.assertEqual(upgraded.posted_at, posted)
            self.assertEqual(upgraded_balance.quantity, Decimal(5))
            self.assertEqual(upgraded_balance.value, Decimal(1250))
            self.assertEqual(
                apps.get_model("auth", "User").objects.get(pk=user.pk).password,
                "preserve-hash-marker",
            )
            self.assertEqual(
                apps.get_model("inventory", "DocumentEvent").objects.count(), 0
            )
        finally:
            MigrationExecutor(connection).migrate(latest)
