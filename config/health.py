import os
from django.db import connection, DatabaseError
from django.db.migrations.recorder import MigrationRecorder
from django.http import JsonResponse
from django.views.decorators.http import require_GET


@require_GET
def health(request):
    ready = False
    try:
        with connection.cursor() as cursor:
            cursor.execute("SELECT 1")
            ready = cursor.fetchone()[0] == 1
        ready = (
            ready
            and MigrationRecorder.Migration.objects.filter(
                app="inventory", name="0016_preserve_assigned_function_access"
            ).exists()
        )
    except DatabaseError:
        ready = False
    response = JsonResponse(
        {
            "status": "ok" if ready else "unavailable",
            "release": os.environ.get(
                "RENDER_GIT_COMMIT", "admin-function-permissions"
            ),
        },
        status=200 if ready else 503,
    )
    response["Cache-Control"] = "no-store"
    return response
