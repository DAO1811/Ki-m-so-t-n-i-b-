import os

from django.conf import settings
from django.db import DatabaseError, connection
from django.db.migrations.recorder import MigrationRecorder
from django.http import JsonResponse
from django.views.decorators.http import require_GET

from inventory.release_backup import snapshot_status


@require_GET
def health(request):
    ready = False
    snapshot = {"status": "unavailable"}
    try:
        with connection.cursor() as cursor:
            cursor.execute("SELECT 1")
            ready = cursor.fetchone()[0] == 1
        ready = (
            ready
            and MigrationRecorder.Migration.objects.filter(
                app="inventory", name="0018_product_qr_stocktake_workflow"
            ).exists()
            and MigrationRecorder.Migration.objects.filter(
                app="deviations", name="0005_reviewer_classification"
            ).exists()
        )
        snapshot = snapshot_status()
        if not settings.DEBUG and connection.vendor == "postgresql":
            ready = ready and snapshot["status"] == "ready"
    except DatabaseError:
        ready = False
    response = JsonResponse(
        {
            "status": "ok" if ready else "unavailable",
            "release": os.environ.get(
                "RENDER_GIT_COMMIT", "admin-function-permissions"
            ),
            "pre_upgrade_snapshot": snapshot,
        },
        status=200 if ready else 503,
    )
    response["Cache-Control"] = "no-store"
    return response
