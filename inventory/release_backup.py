"""Consistent, private PostgreSQL data snapshot before this schema upgrade.

The snapshot lives in the same database. It is a migration recovery copy, not
an off-site backup. No production data is sent to logs or the application host.
"""

from contextlib import contextmanager
import os

import psycopg
from psycopg import sql
from psycopg.types.json import Jsonb
from django.db import connection

SNAPSHOT_SCHEMA = "dhd_backup_inventory_0017"
MANIFEST_TABLE = "_dhd_snapshot_manifest"
# Stable across versions so old/new deployments cannot migrate concurrently.
DEPLOY_LOCK = 1811000016


def direct_connection():
    """Use the configured DB, including the test DB; bypass Neon transaction pooling."""
    config = connection.settings_dict
    params = {
        key: config[name]
        for key, name in [
            ("dbname", "NAME"),
            ("user", "USER"),
            ("password", "PASSWORD"),
            ("host", "HOST"),
            ("port", "PORT"),
        ]
        if config.get(name)
    }
    params.update(config.get("OPTIONS", {}))
    host = str(params.get("host", ""))
    if host.endswith(".neon.tech"):
        endpoint, domain = host.split(".", 1)
        if endpoint.endswith("-pooler"):
            params["host"] = endpoint.removesuffix("-pooler") + "." + domain
    params.setdefault("connect_timeout", 15)
    return psycopg.connect(**params, autocommit=True)


@contextmanager
def deploy_connection():
    # A dedicated session is necessary: session locks are unsafe through a
    # transaction pool. Keep this connection alive through the migration.
    with direct_connection() as db:
        locked = db.execute(
            "SELECT pg_try_advisory_lock(%s)", (DEPLOY_LOCK,)
        ).fetchone()[0]
        if not locked:
            raise RuntimeError("Another deployment is already running")
        try:
            db.execute("SET lock_timeout = '10s'")
            db.execute("SET statement_timeout = '120s'")
            yield db
        finally:
            db.execute("SELECT pg_advisory_unlock(%s)", (DEPLOY_LOCK,))


def _qualified(table):
    return sql.Identifier(SNAPSHOT_SCHEMA, table)


def _manifest(db):
    if not db.execute(
        "SELECT EXISTS(SELECT 1 FROM pg_namespace WHERE nspname=%s)",
        (SNAPSHOT_SCHEMA,),
    ).fetchone()[0]:
        return None
    row = db.execute(
        sql.SQL("SELECT details FROM {} WHERE id=1").format(_qualified(MANIFEST_TABLE))
    ).fetchone()
    if row is None:
        raise RuntimeError("Incomplete release snapshot")
    return row[0]


def _verify(db, manifest):
    if (
        not manifest
        or manifest.get("format") != 1
        or not isinstance(manifest.get("tables"), list)
    ):
        raise RuntimeError("Invalid release snapshot")
    for table in manifest["tables"]:
        count = db.execute(
            sql.SQL("SELECT count(*) FROM {}").format(_qualified(table["name"]))
        ).fetchone()[0]
        if count != table["rows"]:
            raise RuntimeError("Release snapshot row count mismatch")


def _copy_table(db, table):
    source = sql.Identifier("public", table)
    db.execute(sql.SQL("CREATE TABLE {} AS TABLE {}").format(_qualified(table), source))
    count = db.execute(sql.SQL("SELECT count(*) FROM {}").format(source)).fetchone()[0]
    columns = db.execute(
        """SELECT a.attname, format_type(a.atttypid,a.atttypmod),
                  a.attnotnull, pg_get_expr(d.adbin,d.adrelid)
           FROM pg_attribute a
           LEFT JOIN pg_attrdef d ON d.adrelid=a.attrelid AND d.adnum=a.attnum
           WHERE a.attrelid=%s::regclass AND a.attnum>0 AND NOT a.attisdropped
           ORDER BY a.attnum""",
        (sql.Identifier("public", table).as_string(db),),
    ).fetchall()
    constraints = db.execute(
        "SELECT conname, pg_get_constraintdef(oid) FROM pg_constraint WHERE conrelid=%s::regclass",
        (sql.Identifier("public", table).as_string(db),),
    ).fetchall()
    return {
        "name": table,
        "rows": count,
        "columns": columns,
        "constraints": constraints,
    }


def ensure_snapshot(db):
    # The first completed snapshot is retained across deploy retries/restarts.
    # DDL and data copies roll back together if any table fails to copy.
    with db.transaction():
        db.execute("SET TRANSACTION ISOLATION LEVEL REPEATABLE READ")
        if db.execute("SELECT current_schema()").fetchone()[0] != "public":
            raise RuntimeError("Unsupported application schema")
        manifest = _manifest(db)
        if manifest is not None:
            _verify(db, manifest)
            return manifest
        tables = db.execute(
            """SELECT c.relname, c.relkind FROM pg_class c
               JOIN pg_namespace n ON n.oid=c.relnamespace
               WHERE n.nspname='public' AND c.relkind IN ('r','p') ORDER BY c.relname"""
        ).fetchall()
        if any(kind != "r" or name == MANIFEST_TABLE for name, kind in tables):
            raise RuntimeError("Unsupported source table layout")
        db.execute(sql.SQL("CREATE SCHEMA {}").format(sql.Identifier(SNAPSHOT_SCHEMA)))
        db.execute(
            sql.SQL("REVOKE ALL ON SCHEMA {} FROM PUBLIC").format(
                sql.Identifier(SNAPSHOT_SCHEMA)
            )
        )
        copied = [_copy_table(db, name) for name, _ in tables]
        sequences = []
        for (name,) in db.execute(
            """SELECT c.relname FROM pg_class c JOIN pg_namespace n ON n.oid=c.relnamespace
               WHERE n.nspname='public' AND c.relkind='S' ORDER BY c.relname"""
        ).fetchall():
            last, called = db.execute(
                sql.SQL("SELECT last_value,is_called FROM {}").format(
                    sql.Identifier("public", name)
                )
            ).fetchone()
            sequences.append({"name": name, "last_value": last, "is_called": called})
        names = {name for name, _ in tables}
        migrations = (
            db.execute(
                "SELECT app,name FROM public.django_migrations ORDER BY app,name"
            ).fetchall()
            if "django_migrations" in names
            else []
        )
        manifest = {
            "format": 1,
            "source_schema": "public",
            "tables": copied,
            "sequences": sequences,
            "migrations": migrations,
            "release": os.environ.get(
                "RENDER_GIT_COMMIT", "admin-function-permissions"
            ),
            "created_at": db.execute("SELECT current_timestamp")
            .fetchone()[0]
            .isoformat(),
        }
        db.execute(
            sql.SQL(
                "CREATE TABLE {} (id integer PRIMARY KEY CHECK(id=1), details jsonb NOT NULL)"
            ).format(_qualified(MANIFEST_TABLE))
        )
        db.execute(
            sql.SQL("INSERT INTO {} VALUES (1,%s)").format(_qualified(MANIFEST_TABLE)),
            (Jsonb(manifest),),
        )
        db.execute(
            sql.SQL("REVOKE ALL ON ALL TABLES IN SCHEMA {} FROM PUBLIC").format(
                sql.Identifier(SNAPSHOT_SCHEMA)
            )
        )
        _verify(db, manifest)
        return manifest


def snapshot_status():
    """Only non-sensitive readiness metadata may be returned by the health route."""
    if connection.vendor != "postgresql":
        return {"status": "not_applicable"}
    with connection.cursor() as cursor:
        cursor.execute(
            "SELECT to_regclass(%s)", [f"{SNAPSHOT_SCHEMA}.{MANIFEST_TABLE}"]
        )
        if cursor.fetchone()[0] is None:
            return {"status": "missing"}
        cursor.execute(
            sql.SQL(
                "SELECT details->>'created_at', details->'migrations' FROM {} WHERE id=1"
            ).format(_qualified(MANIFEST_TABLE))
        )
        row = cursor.fetchone()
    if row is None:
        return {"status": "missing"}
    import json

    migrations = json.loads(row[1]) if isinstance(row[1], str) else row[1]
    return {
        "status": "ready",
        "created_at": row[0],
        "from_inventory_migration": max(
            (name for app, name in migrations if app == "inventory"), default="empty"
        ),
    }
