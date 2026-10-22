from django.contrib.auth import get_user_model
from django.db import connection
from django.db.migrations.executor import MigrationExecutor
from django.test import TransactionTestCase
from psycopg import sql

from . import release_backup as backup
from .models import Balance, Product, StocktakeSession
from .stocktakes import product_from_scan


class StocktakeUpgradeTests(TransactionTestCase):
    def test_schema_17_qr_labels_open_sessions_and_rolling_inserts_survive(self):
        old = [("inventory", "0017_approval_hierarchy")]
        latest = sorted(
            MigrationExecutor(connection).loader.graph.leaf_nodes(),
            key=lambda node: node[0] != "inventory",
        )
        try:
            executor = MigrationExecutor(connection)
            executor.migrate(old)
            apps = executor.loader.project_state(old).apps
            OldProduct = apps.get_model("inventory", "Product")
            OldUser = apps.get_model("auth", "User")
            OldWarehouse = apps.get_model("inventory", "Warehouse")
            OldSession = apps.get_model("inventory", "StocktakeSession")
            OldBalance = apps.get_model("inventory", "Balance")
            owner = OldUser.objects.create(
                username="upgrade-owner", password="preserve-hash"
            )
            warehouse = OldWarehouse.objects.create(code="UPGRADE", name="Kho cũ")
            product = OldProduct.objects.create(
                sku="OLD-QR", name="Hàng cũ", unit="Cái"
            )
            token = product.qr_token
            session = OldSession.objects.create(warehouse=warehouse, created_by=owner)
            OldBalance.objects.create(
                warehouse=warehouse, product=product, quantity=7, value=700
            )
            if connection.vendor == "postgresql":
                with backup.deploy_connection() as db:
                    manifest = backup.ensure_snapshot(db)
                    self.assertIn(
                        ["inventory", "0017_approval_hierarchy"],
                        [list(row) for row in manifest["migrations"]],
                    )
            MigrationExecutor(connection).migrate(latest)
            current = Product.objects.get(pk=product.pk)
            self.assertEqual(
                StocktakeSession.objects.get(pk=session.pk).counter_id, owner.pk
            )
            self.assertEqual(
                StocktakeSession.objects.get(pk=session.pk).started_at,
                session.created_at,
            )
            self.assertEqual(current.qr_token, token)
            self.assertEqual(current.qr_code, f"DHD:ITEM:{token}")
            self.assertEqual(
                product_from_scan(f"https://old.example/q/items/{token}/").pk,
                product.pk,
            )
            self.assertFalse(
                StocktakeSession.objects.get(pk=session.pk).locks_inventory
            )
            self.assertEqual(Balance.objects.get(product=current).quantity, 7)
            self.assertEqual(Balance.objects.get(product=current).value, 700)
            self.assertEqual(
                get_user_model().objects.get(pk=owner.pk).password, "preserve-hash"
            )
            # An old worker can finish an insert while the new schema is live.
            transitional = OldProduct.objects.create(
                sku="ROLLING-QR", name="Giao dịch đang hoàn tất", unit="Bộ"
            )
            live = Product.objects.get(pk=transitional.pk)
            self.assertTrue(live.qr_auto)
            self.assertIsNone(live.qr_code)
            self.assertEqual(product_from_scan(f"/q/items/{live.qr_token}/"), live)
            live.name = "Đổi tên không đổi QR"
            live.save()
            self.assertEqual(live.qr_code, f"DHD:ITEM:{live.qr_token}")
        finally:
            MigrationExecutor(connection).migrate(latest)
            if connection.vendor == "postgresql":
                with backup.direct_connection() as db:
                    db.execute(
                        sql.SQL("DROP SCHEMA IF EXISTS {} CASCADE").format(
                            sql.Identifier(backup.SNAPSHOT_SCHEMA)
                        )
                    )
