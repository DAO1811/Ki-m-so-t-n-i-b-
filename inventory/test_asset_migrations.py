from datetime import datetime
from decimal import Decimal
from io import StringIO
from zoneinfo import ZoneInfo

from django.core.management import call_command
from django.db import connection
from django.db.migrations.executor import MigrationExecutor
from django.test import TransactionTestCase
from psycopg import sql

from . import release_backup as backup


class AssetMigrationTests(TransactionTestCase):
    def test_existing_stock_values_users_and_historical_dates_survive_upgrade(self):
        old = [("inventory", "0007_balance_nonnegative_stock_value")]
        latest = sorted(
            MigrationExecutor(connection).loader.graph.leaf_nodes(),
            key=lambda node: node[0] != "inventory",
        )
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
            Group = apps.get_model("auth", "Group")
            Permission = apps.get_model("auth", "Permission")
            role = Group.objects.create(name="Historical assigned role")
            role.permissions.set(
                Permission.objects.filter(
                    content_type__app_label="inventory",
                    codename__in=["view_document", "add_document"],
                )
            )
            user.groups.add(role)
            # A permission with the same name from a different app must not
            # become an inventory grant during the one-time role conversion.
            other_user = User.objects.create(username="unassigned_inventory_user")
            other_type_id = (
                Permission.objects.filter(content_type__app_label="auth")
                .values_list("content_type_id", flat=True)
                .first()
            )
            self.assertIsNotNone(other_type_id)
            other_role = Group.objects.create(name="Unrelated application role")
            other_role.permissions.add(
                Permission.objects.create(
                    content_type_id=other_type_id,
                    codename="add_document",
                    name="Unrelated document creation",
                )
            )
            other_user.groups.add(other_role)
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
            manifest = None
            if connection.vendor == "postgresql":
                self.assertTrue(
                    str(connection.settings_dict["NAME"]).startswith("test_")
                )
                with backup.direct_connection() as db:
                    db.execute(
                        sql.SQL("DROP SCHEMA IF EXISTS {} CASCADE").format(
                            sql.Identifier(backup.SNAPSHOT_SCHEMA)
                        )
                    )
                call_command("safe_migrate", stdout=StringIO())
                with backup.direct_connection() as db:
                    manifest = backup._manifest(db)
                self.assertIn(["inventory", old[0][1]], manifest["migrations"])
                self.assertNotIn(["inventory", latest[0][1]], manifest["migrations"])
            else:
                MigrationExecutor(connection).migrate(latest)
            executor = MigrationExecutor(connection)
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
            grants = (
                apps.get_model("inventory", "FunctionAccess")
                .objects.get(user_id=user.pk)
                .permissions
            )
            self.assertIn("receipts_create", grants)
            self.assertIn("issues_create", grants)
            self.assertNotIn("adjustments_approve", grants)
            self.assertEqual(
                apps.get_model("inventory", "FunctionAccess")
                .objects.get(user_id=other_user.pk)
                .permissions,
                [],
            )
            if manifest is not None:
                # Rehearse a controlled rollback in the isolated test database:
                # restore the old schema first, then all old data and sequences.
                apps.get_model("inventory", "Balance").objects.filter(
                    pk=balance.pk
                ).update(quantity=0, value=0)
                apps.get_model("auth", "User").objects.filter(pk=user.pk).update(
                    password="changed-after-upgrade"
                )
                MigrationExecutor(connection).migrate(old)
                with backup.direct_connection() as db, db.transaction():
                    targets = sql.SQL(",").join(
                        sql.Identifier("public", t["name"]) for t in manifest["tables"]
                    )
                    db.execute(
                        sql.SQL("TRUNCATE {} RESTART IDENTITY CASCADE").format(targets)
                    )
                    db.execute("SET CONSTRAINTS ALL DEFERRED")
                    for table in manifest["tables"]:
                        columns = sql.SQL(",").join(
                            sql.Identifier(c[0]) for c in table["columns"]
                        )
                        db.execute(
                            sql.SQL(
                                "INSERT INTO {} ({}) OVERRIDING SYSTEM VALUE SELECT {} FROM {}"
                            ).format(
                                sql.Identifier("public", table["name"]),
                                columns,
                                columns,
                                sql.Identifier(backup.SNAPSHOT_SCHEMA, table["name"]),
                            )
                        )
                    for seq in manifest["sequences"]:
                        db.execute(
                            "SELECT setval(%s::regclass,%s,%s)",
                            (
                                sql.Identifier("public", seq["name"]).as_string(db),
                                seq["last_value"],
                                seq["is_called"],
                            ),
                        )
                self.assertEqual(
                    Balance.objects.get(pk=balance.pk).quantity, Decimal(5)
                )
                self.assertEqual(
                    Balance.objects.get(pk=balance.pk).value, Decimal(1250)
                )
                self.assertEqual(
                    User.objects.get(pk=user.pk).password, "preserve-hash-marker"
                )
                self.assertEqual(Document.objects.get(pk=doc.pk).posted_at, posted)
                recorder = MigrationExecutor(connection).recorder
                self.assertIn(old[0], recorder.applied_migrations())
                self.assertNotIn(latest[0], recorder.applied_migrations())
        finally:
            MigrationExecutor(connection).migrate(latest)
            if connection.vendor == "postgresql":
                with backup.direct_connection() as db:
                    db.execute(
                        sql.SQL("DROP SCHEMA IF EXISTS {} CASCADE").format(
                            sql.Identifier(backup.SNAPSHOT_SCHEMA)
                        )
                    )
