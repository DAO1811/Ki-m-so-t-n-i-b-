import json
import os
import subprocess
import sys
from io import StringIO
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest.mock import patch

from django.contrib.auth import get_user_model
from django.contrib.auth.models import Group, Permission
from django.core.management import call_command
from django.core.management.base import CommandError
from django.db import connection
from django.test import SimpleTestCase, TransactionTestCase
from psycopg import sql

from . import release_backup as backup
from .models import Balance, Product, Warehouse


class RuntimePreparationOrderTests(SimpleTestCase):
    stages = ("safe_migrate", "setup_roles", "bootstrap_admin")

    def test_preparation_keeps_order_and_forwards_command_output(self):
        output, errors = StringIO(), StringIO()
        executed = []

        def stage(name, **options):
            executed.append(name)
            options["stdout"].write(f"output:{name}")
            options["stderr"].write(f"error-stream:{name}")

        with patch(
            "inventory.management.commands.prepare_runtime.call_command",
            side_effect=stage,
        ):
            call_command("prepare_runtime", stdout=output, stderr=errors)

        self.assertEqual(executed, list(self.stages))
        for name in self.stages:
            self.assertIn(f"output:{name}", output.getvalue())
            self.assertIn(f"error-stream:{name}", errors.getvalue())

    def test_failure_at_any_stage_prevents_remaining_stages(self):
        for failed_index, failed_name in enumerate(self.stages):
            with self.subTest(stage=failed_name):
                executed = []
                failure = CommandError("isolated startup failure")

                def stage(name, **options):
                    executed.append(name)
                    if name == failed_name:
                        raise failure

                with patch(
                    "inventory.management.commands.prepare_runtime.call_command",
                    side_effect=stage,
                ):
                    with self.assertRaises(CommandError) as caught:
                        call_command(
                            "prepare_runtime", stdout=StringIO(), stderr=StringIO()
                        )

                self.assertIs(caught.exception, failure)
                self.assertEqual(executed, list(self.stages[: failed_index + 1]))


class RuntimeEntrypointTests(SimpleTestCase):
    repo = Path(__file__).resolve().parent.parent

    def run_entrypoint(self, name, *, failure=0, overrides=None):
        with TemporaryDirectory(prefix="dhd-runtime-entrypoint-") as directory:
            root = Path(directory)
            log = root / "commands.jsonl"
            script = (
                f"#!{sys.executable}\n"
                "import json, os, sys\n"
                "from pathlib import Path\n"
                "program = Path(sys.argv[0]).name\n"
                "with open(os.environ['RUNTIME_COMMAND_LOG'], 'a') as output:\n"
                "    output.write(json.dumps({'program': program, "
                "'args': sys.argv[1:]}) + '\\n')\n"
                "raise SystemExit(int(os.environ['RUNTIME_PREPARE_EXIT']) "
                "if program == 'python' else 0)\n"
            )
            for program in ("python", "gunicorn"):
                executable = root / program
                executable.write_text(script)
                executable.chmod(0o700)
            # No production configuration or credentials reach either stub.
            environment = {
                "PATH": str(root) + os.pathsep + os.defpath,
                "RUNTIME_COMMAND_LOG": str(log),
                "RUNTIME_PREPARE_EXIT": str(failure),
                **(overrides or {}),
            }
            if name == "native":
                command = ["/bin/bash", str(self.repo / "start.sh")]
            else:
                docker_cmd = next(
                    line.removeprefix("CMD ")
                    for line in (self.repo / "Dockerfile").read_text().splitlines()
                    if line.startswith("CMD ")
                )
                command = json.loads(docker_cmd)
            result = subprocess.run(
                command,
                cwd=self.repo,
                env=environment,
                capture_output=True,
                text=True,
                timeout=10,
                check=False,
            )
            commands = (
                [json.loads(line) for line in log.read_text().splitlines()]
                if log.exists()
                else []
            )
            return result, commands

    def web_arguments(self, result, commands):
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(
            commands[0],
            {"program": "python", "args": ["manage.py", "prepare_runtime"]},
        )
        self.assertEqual([c["program"] for c in commands], ["python", "gunicorn"])
        arguments = commands[1]["args"]
        self.assertEqual(arguments[0], "config.wsgi:application")
        self.assertEqual(
            arguments[arguments.index("--access-logformat") + 1],
            "%(h)s %(t)s %(m)s %(U)s %(s)s %(L)s",
        )
        return arguments

    def test_preparation_failure_prevents_web_server_for_both_entrypoints(self):
        for name in ("native", "docker"):
            with self.subTest(entrypoint=name):
                result, commands = self.run_entrypoint(name, failure=23)
                self.assertEqual(result.returncode, 23)
                self.assertEqual(
                    commands,
                    [{"program": "python", "args": ["manage.py", "prepare_runtime"]}],
                )

    def test_native_entrypoint_preserves_configurable_port_and_workers(self):
        result, commands = self.run_entrypoint(
            "native", overrides={"PORT": "8791", "WEB_CONCURRENCY": "3"}
        )
        arguments = self.web_arguments(result, commands)
        self.assertEqual(arguments[arguments.index("--bind") + 1], "0.0.0.0:8791")
        self.assertEqual(arguments[arguments.index("--workers") + 1], "3")
        self.assertNotIn("--timeout", arguments)

    def test_native_entrypoint_preserves_default_port_and_workers(self):
        result, commands = self.run_entrypoint("native")
        arguments = self.web_arguments(result, commands)
        self.assertEqual(arguments[arguments.index("--bind") + 1], "0.0.0.0:8000")
        self.assertEqual(arguments[arguments.index("--workers") + 1], "2")

    def test_docker_entrypoint_preserves_port_workers_and_timeout(self):
        result, commands = self.run_entrypoint("docker", overrides={"PORT": "8792"})
        arguments = self.web_arguments(result, commands)
        self.assertEqual(arguments[arguments.index("--bind") + 1], "0.0.0.0:8792")
        self.assertEqual(arguments[arguments.index("--workers") + 1], "2")
        self.assertEqual(arguments[arguments.index("--timeout") + 1], "120")


class RuntimePreparationDatabaseTests(TransactionTestCase):
    def setUp(self):
        # Snapshot DDL must only ever operate on the Django test database.
        if connection.vendor == "postgresql":
            self.assertTrue(str(connection.settings_dict["NAME"]).startswith("test_"))
            self.drop_snapshot()
            self.addCleanup(self.drop_snapshot)

    def drop_snapshot(self):
        self.assertTrue(str(connection.settings_dict["NAME"]).startswith("test_"))
        with backup.direct_connection() as db:
            db.execute(
                sql.SQL("DROP SCHEMA IF EXISTS {} CASCADE").format(
                    sql.Identifier(backup.SNAPSHOT_SCHEMA)
                )
            )

    def prepare(self):
        output, errors = StringIO(), StringIO()
        call_command("prepare_runtime", stdout=output, stderr=errors)
        return output.getvalue() + errors.getvalue()

    def test_restart_preserves_admin_custom_grants_and_stock(self):
        User = get_user_model()
        admin = User.objects.create_superuser(
            "runtime_admin", "admin@example.test", "original-local-password"
        )
        worker = User.objects.create_user("runtime_worker", password="worker-password")
        call_command("setup_roles", stdout=StringIO())
        employee_group = Group.objects.get(name="Nhân viên kho")
        custom_permission = Permission.objects.get(
            content_type__app_label="inventory", codename="view_warehouse"
        )
        employee_group.permissions.set([custom_permission])
        custom_group = Group.objects.create(name="Runtime custom role")
        custom_group.permissions.add(custom_permission)
        worker.groups.add(employee_group, custom_group)
        worker.user_permissions.add(custom_permission)
        product = Product.objects.create(sku="STARTUP", name="Startup test product")
        warehouse = Warehouse.objects.create(
            code="STARTUP", name="Startup test warehouse"
        )
        balance = Balance.objects.create(
            product=product, warehouse=warehouse, quantity=7, value=350
        )
        original_hash = admin.password
        original_worker_hash = worker.password
        group_count = Group.objects.count()

        with patch.dict(
            "os.environ",
            {
                "INITIAL_ADMIN_USERNAME": "runtime_admin",
                "INITIAL_ADMIN_PASSWORD": "replacement-not-to-be-applied",
                "INITIAL_ADMIN_EMAIL": "replacement@example.test",
            },
        ):
            output = self.prepare() + self.prepare()

        admin.refresh_from_db()
        worker.refresh_from_db()
        balance.refresh_from_db()
        self.assertEqual(admin.password, original_hash)
        self.assertEqual(admin.email, "admin@example.test")
        self.assertEqual(worker.password, original_worker_hash)
        self.assertFalse(worker.is_superuser)
        self.assertEqual(Group.objects.count(), group_count)
        self.assertEqual(
            set(employee_group.permissions.values_list("pk", flat=True)),
            {custom_permission.pk},
        )
        self.assertEqual(
            set(custom_group.permissions.values_list("pk", flat=True)),
            {custom_permission.pk},
        )
        self.assertEqual(
            set(worker.groups.values_list("pk", flat=True)),
            {employee_group.pk, custom_group.pk},
        )
        self.assertEqual(
            set(worker.user_permissions.values_list("pk", flat=True)),
            {custom_permission.pk},
        )
        self.assertEqual((balance.quantity, balance.value), (7, 350))
        self.assertEqual(Product.objects.count(), 1)
        self.assertEqual(Warehouse.objects.count(), 1)
        self.assertEqual(User.objects.count(), 2)
        self.assertNotIn("replacement-not-to-be-applied", output)
        self.assertNotIn(original_hash, output)

    def test_initial_preparation_creates_admin_once(self):
        password = "first-local-startup-password"
        with patch.dict(
            "os.environ",
            {
                "INITIAL_ADMIN_USERNAME": "runtime_first_admin",
                "INITIAL_ADMIN_PASSWORD": password,
                "INITIAL_ADMIN_EMAIL": "first@example.test",
            },
        ):
            output = self.prepare()
        admin = get_user_model().objects.get(username="runtime_first_admin")
        self.assertTrue(admin.is_superuser)
        self.assertTrue(admin.check_password(password))
        original_hash = admin.password

        with patch.dict(
            "os.environ",
            {
                "INITIAL_ADMIN_USERNAME": "runtime_first_admin",
                "INITIAL_ADMIN_PASSWORD": "second-password-not-to-be-applied",
            },
        ):
            output += self.prepare()

        admin.refresh_from_db()
        self.assertEqual(admin.password, original_hash)
        self.assertEqual(get_user_model().objects.filter(is_superuser=True).count(), 1)
        self.assertNotIn(password, output)
        self.assertNotIn("second-password-not-to-be-applied", output)

    def test_bootstrap_refusal_propagates_without_promoting_existing_user(self):
        user = get_user_model().objects.create_user(
            "runtime_existing_worker", password="original-worker-password"
        )
        original_hash = user.password
        with patch.dict(
            "os.environ",
            {
                "INITIAL_ADMIN_USERNAME": user.username,
                "INITIAL_ADMIN_PASSWORD": "not-an-admin-password",
            },
        ):
            with self.assertRaises(CommandError):
                self.prepare()

        user.refresh_from_db()
        self.assertFalse(user.is_superuser)
        self.assertFalse(user.is_staff)
        self.assertEqual(user.password, original_hash)
        self.assertFalse(get_user_model().objects.filter(is_superuser=True).exists())
