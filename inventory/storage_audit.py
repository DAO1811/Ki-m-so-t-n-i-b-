"""Read-only storage measurements; never infer a cloud plan from database size."""

import hashlib
from collections import defaultdict

from django.conf import settings
from django.core.cache import caches
from django.db import connection, transaction
from django.db.models import Count, Sum
from django.utils import timezone

from .models import StoredFile

cache = caches["storage"]


def cache_key():
    identity = repr(
        tuple(
            connection.settings_dict.get(k) for k in ("ENGINE", "HOST", "PORT", "NAME")
        )
    )
    return "storage-audit-v1:" + hashlib.sha256(identity.encode()).hexdigest()


def measure_storage():
    """Return sizes and counts, without credentials, filenames, or business rows."""
    with transaction.atomic():
        tables = []
        total = None
        if connection.vendor == "postgresql":
            with connection.cursor() as cursor:
                # Use transaction-local settings so a pool never inherits them.
                cursor.execute("SET LOCAL statement_timeout = '8s'")
                cursor.execute("SELECT pg_database_size(current_database())")
                total = cursor.fetchone()[0]
                cursor.execute("""
                    SELECT n.nspname, c.relname, pg_total_relation_size(c.oid),
                           pg_indexes_size(c.oid), GREATEST(c.reltuples,0)::bigint
                    FROM pg_class c JOIN pg_namespace n ON n.oid=c.relnamespace
                    WHERE c.relkind='r' AND n.nspname NOT LIKE 'pg_%'
                      AND n.nspname <> 'information_schema'
                    ORDER BY pg_total_relation_size(c.oid) DESC, n.nspname,c.relname
                """)
                tables = [
                    dict(
                        zip(
                            (
                                "schema",
                                "table",
                                "bytes",
                                "index_bytes",
                                "estimated_rows",
                            ),
                            row,
                        )
                    )
                    for row in cursor.fetchall()
                ]
                cursor.execute(
                    "SELECT count(*), COALESCE(sum(octet_length(data)),0) FROM inventory_storedfile WHERE data IS NOT NULL"
                )
                blob_count, blob_bytes = cursor.fetchone()
        else:
            # Do not present a local SQLite file as a production PostgreSQL measurement.
            blob_count = StoredFile.objects.filter(data__isnull=False).count()
            blob_bytes = sum(
                len(value)
                for value in StoredFile.objects.filter(data__isnull=False).values_list(
                    "data", flat=True
                )
            )
        files = list(
            StoredFile.objects.values("provider")
            .annotate(count=Count("id"), bytes=Sum("size"))
            .order_by("provider")
        )
    schemas = defaultdict(int)
    for table in tables:
        schemas[table["schema"]] += table["bytes"]
    snapshot_bytes = sum(
        size
        for name, size in schemas.items()
        if name.startswith("dhd_backup_inventory_")
    )
    configured_mb = getattr(settings, "DATABASE_STORAGE_LIMIT_MB", None)
    limit = int(configured_mb) * 1024 * 1024 if configured_mb else None
    result = {
        "measured_at": timezone.now().isoformat(),
        "engine": connection.vendor,
        "database_bytes": total,
        "configured_limit_bytes": limit,
        "remaining_bytes": max(limit - total, 0)
        if limit is not None and total is not None
        else None,
        "percent": min(round(total * 100 / limit, 1), 100)
        if total is not None and limit
        else None,
        "snapshot_bytes": snapshot_bytes,
        "blob_count": blob_count,
        "blob_bytes": blob_bytes,
        "files": files,
        "schemas": [
            {"name": name, "bytes": size}
            for name, size in sorted(schemas.items(), key=lambda item: -item[1])
        ],
        "tables": tables[:50],
        "tables_count": len(tables),
    }
    cache.set(cache_key(), result, 600)
    return result
