"""The approved release adds deviations without upgrading warehouse behavior."""

from django.contrib.auth import get_user_model
from django.db import connection
from django.db.migrations.executor import MigrationExecutor
from django.test import TransactionTestCase

from deviations.forms import ReportForm
from deviations.services import cases
from inventory.models import Balance, Product, StocktakeSession, Warehouse

from .support import DeviationTestCase


class LegacySourceTests(DeviationTestCase):
    def test_linking_existing_stocktake_does_not_require_stocktake_upgrade(self):
        warehouse = Warehouse.objects.create(code="SL-LEGACY", name="Kho giả lập cũ")
        session = StocktakeSession.objects.create(
            warehouse=warehouse,
            created_by=self.admin,
            status="SUBMITTED",
            locks_inventory=True,
        )
        form = ReportForm(user=self.admin)
        self.assertTrue(
            form.fields["source_stocktake"].queryset.filter(pk=session.pk).exists()
        )
        data = self.payload()
        data["source_stocktake"] = session
        case = cases.create_case(self.admin, data)
        self.assertEqual(case.source_stocktake_id, session.pk)
        session.refresh_from_db()
        self.assertTrue(session.locks_inventory)
        self.assertEqual(session.status, "SUBMITTED")


class AdditiveUpgradeTests(TransactionTestCase):
    def test_deviation_migrations_preserve_warehouse_data_and_schema(self):
        latest = MigrationExecutor(connection).loader.graph.leaf_nodes()
        try:
            MigrationExecutor(connection).migrate([("deviations", None)])
            user = get_user_model().objects.create_user(
                "legacy-release-account", password="test-only-preserve-hash"
            )
            password_hash = user.password
            warehouse = Warehouse.objects.create(code="LEGACY-R", name="Kho cũ giả lập")
            product = Product.objects.create(
                sku="LEGACY-R", name="Hàng giả lập", unit="Cái"
            )
            balance = Balance.objects.create(
                warehouse=warehouse, product=product, quantity=7, value=700
            )
            session = StocktakeSession.objects.create(
                warehouse=warehouse,
                created_by=user,
                status="SUBMITTED",
                locks_inventory=True,
            )
            with connection.cursor() as cursor:
                before = connection.introspection.get_table_description(
                    cursor, StocktakeSession._meta.db_table
                )
            MigrationExecutor(connection).migrate(latest)
            with connection.cursor() as cursor:
                after = connection.introspection.get_table_description(
                    cursor, StocktakeSession._meta.db_table
                )
            self.assertEqual(before, after)
            self.assertEqual(
                get_user_model().objects.get(pk=user.pk).password, password_hash
            )
            self.assertEqual(Product.objects.get(pk=product.pk).sku, "LEGACY-R")
            balance.refresh_from_db()
            session.refresh_from_db()
            self.assertEqual((balance.quantity, balance.value), (7, 700))
            self.assertEqual(
                (session.status, session.locks_inventory), ("SUBMITTED", True)
            )
            self.assertNotIn(
                "inventory_stocktakedeletion", connection.introspection.table_names()
            )
        finally:
            MigrationExecutor(connection).migrate(latest)
