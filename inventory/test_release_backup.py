from io import StringIO
from unittest import skipUnless
from unittest.mock import patch

from django.contrib.auth import get_user_model
from django.core.management import call_command
from django.core.management.base import CommandError
from django.db import connection
from django.test import TransactionTestCase, override_settings
from psycopg import sql

from . import release_backup as backup
from .models import Balance, Product, Warehouse


@skipUnless(connection.vendor == "postgresql", "PostgreSQL release snapshots")
class ReleaseBackupTests(TransactionTestCase):
    def setUp(self):
        self.assertTrue(str(connection.settings_dict["NAME"]).startswith("test_"))
        self.drop_snapshot()
        self.user = get_user_model().objects.create_user("snapshot_user", password="1")
        self.product = Product.objects.create(sku="BACKUP", name="Before upgrade")
        self.warehouse = Warehouse.objects.create(
            code="BACKUP", name="Backup warehouse"
        )
        self.balance = Balance.objects.create(
            product=self.product, warehouse=self.warehouse, quantity=5, value=1250
        )

    def drop_snapshot(self):
        with backup.direct_connection() as db:
            db.execute(
                sql.SQL("DROP SCHEMA IF EXISTS {} CASCADE").format(
                    sql.Identifier(backup.SNAPSHOT_SCHEMA)
                )
            )

    def tearDown(self):
        self.drop_snapshot()
        super().tearDown()

    def test_snapshot_retains_rows_types_credentials_and_private_access(self):
        with backup.deploy_connection() as db:
            manifest = backup.ensure_snapshot(db)
            self.assertIn("inventory_balance", [t["name"] for t in manifest["tables"]])
            self.assertEqual(
                db.execute(
                    sql.SQL("SELECT quantity,value FROM {} WHERE id=%s").format(
                        sql.Identifier(backup.SNAPSHOT_SCHEMA, "inventory_balance")
                    ),
                    (self.balance.pk,),
                ).fetchone(),
                (5, 1250),
            )
            self.assertEqual(
                db.execute(
                    sql.SQL("SELECT password FROM {} WHERE id=%s").format(
                        sql.Identifier(backup.SNAPSHOT_SCHEMA, "auth_user")
                    ),
                    (self.user.pk,),
                ).fetchone()[0],
                self.user.password,
            )
            self.assertTrue(manifest["sequences"])
            self.assertFalse(
                db.execute(
                    "SELECT EXISTS(SELECT 1 FROM pg_namespace n,aclexplode(n.nspacl) a WHERE n.nspname=%s AND a.grantee=0)",
                    (backup.SNAPSHOT_SCHEMA,),
                ).fetchone()[0]
            )
        # Public health metadata must not return the manifest, rows or passwords.
        with override_settings(DEBUG=False):
            response = self.client.get("/healthz/", secure=True)
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["pre_upgrade_snapshot"]["status"], "ready")
        self.assertNotIn(self.user.password.encode(), response.content)
        self.assertNotIn(backup.SNAPSHOT_SCHEMA.encode(), response.content)

    def test_restart_keeps_original_snapshot_instead_of_overwriting_it(self):
        with backup.deploy_connection() as db:
            first = backup.ensure_snapshot(db)
        Balance.objects.filter(pk=self.balance.pk).update(quantity=3)
        with backup.deploy_connection() as db:
            again = backup.ensure_snapshot(db)
            self.assertEqual(again["created_at"], first["created_at"])
            self.assertEqual(
                db.execute(
                    sql.SQL("SELECT quantity FROM {} WHERE id=%s").format(
                        sql.Identifier(backup.SNAPSHOT_SCHEMA, "inventory_balance")
                    ),
                    (self.balance.pk,),
                ).fetchone()[0],
                5,
            )
        self.balance.refresh_from_db()
        self.assertEqual(self.balance.quantity, 3)

    def test_copy_failure_leaves_no_partial_snapshot_or_public_changes(self):
        original = backup._copy_table
        calls = 0

        def interrupted(db, table):
            nonlocal calls
            calls += 1
            if calls == 2:
                raise RuntimeError("simulated interruption")
            return original(db, table)

        with backup.deploy_connection() as db:
            with patch.object(backup, "_copy_table", side_effect=interrupted):
                with self.assertRaises(RuntimeError):
                    backup.ensure_snapshot(db)
            self.assertFalse(
                db.execute(
                    "SELECT EXISTS(SELECT 1 FROM pg_namespace WHERE nspname=%s)",
                    (backup.SNAPSHOT_SCHEMA,),
                ).fetchone()[0]
            )
        self.balance.refresh_from_db()
        self.assertEqual(self.balance.quantity, 5)

    def test_snapshot_is_consistent_when_application_writes_during_copy(self):
        original = backup._copy_table
        changed = False

        def update_during_copy(db, table):
            nonlocal changed
            if not changed:
                changed = True
                # A separate, committed application connection changes two tables
                # after the snapshot transaction has acquired its MVCC snapshot.
                Product.objects.filter(pk=self.product.pk).update(name="After snapshot")
                Balance.objects.filter(pk=self.balance.pk).update(quantity=2)
            return original(db, table)

        with backup.deploy_connection() as db:
            with patch.object(backup, "_copy_table", side_effect=update_during_copy):
                backup.ensure_snapshot(db)
            self.assertEqual(
                db.execute(
                    sql.SQL("SELECT name FROM {} WHERE id=%s").format(
                        sql.Identifier(backup.SNAPSHOT_SCHEMA, "inventory_product")
                    ),
                    (self.product.pk,),
                ).fetchone()[0],
                "Before upgrade",
            )
            self.assertEqual(
                db.execute(
                    sql.SQL("SELECT quantity FROM {} WHERE id=%s").format(
                        sql.Identifier(backup.SNAPSHOT_SCHEMA, "inventory_balance")
                    ),
                    (self.balance.pk,),
                ).fetchone()[0],
                5,
            )
        self.balance.refresh_from_db()
        self.assertEqual(self.balance.quantity, 2)

    def test_failed_or_corrupted_snapshot_prevents_migration(self):
        with patch(
            "inventory.management.commands.safe_migrate.ensure_snapshot",
            side_effect=RuntimeError("private credential marker"),
        ):
            with patch(
                "inventory.management.commands.safe_migrate.call_command"
            ) as migrate:
                with self.assertRaises(CommandError) as error:
                    call_command("safe_migrate", stdout=StringIO())
                self.assertNotIn("private credential marker", str(error.exception))
                migrate.assert_not_called()
        with backup.deploy_connection() as db:
            backup.ensure_snapshot(db)
            db.execute(
                sql.SQL("DELETE FROM {}").format(
                    sql.Identifier(backup.SNAPSHOT_SCHEMA, "inventory_balance")
                )
            )
        with patch(
            "inventory.management.commands.safe_migrate.call_command"
        ) as migrate:
            with self.assertRaises(CommandError):
                call_command("safe_migrate", stdout=StringIO())
            migrate.assert_not_called()

    def test_overlapping_deployment_is_rejected_before_migration(self):
        with backup.deploy_connection():
            with patch(
                "inventory.management.commands.safe_migrate.call_command"
            ) as migrate:
                with self.assertRaises(CommandError):
                    call_command("safe_migrate", stdout=StringIO())
                migrate.assert_not_called()

    def test_neon_pooler_is_bypassed_for_deployment_session_lock(self):
        config = {
            **connection.settings_dict,
            "HOST": "ep-example-pooler.ap-southeast-1.aws.neon.tech",
        }
        with patch.object(connection, "settings_dict", config):
            with patch("inventory.release_backup.psycopg.connect") as connect:
                backup.direct_connection()
        self.assertEqual(
            connect.call_args.kwargs["host"], "ep-example.ap-southeast-1.aws.neon.tech"
        )
