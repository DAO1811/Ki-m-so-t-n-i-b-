from zoneinfo import ZoneInfo
from django.db import migrations


def preserve_dates(apps, schema_editor):
    Document = apps.get_model("inventory", "Document")
    batch = []
    for doc in (
        Document.objects.using(schema_editor.connection.alias)
        .all()
        .iterator(chunk_size=1000)
    ):
        timestamp = doc.dispatched_at or doc.posted_at or doc.created_at
        doc.business_date = timestamp.astimezone(ZoneInfo("Asia/Ho_Chi_Minh")).date()
        batch.append(doc)
        if len(batch) == 1000:
            Document.objects.using(schema_editor.connection.alias).bulk_update(
                batch, ["business_date"]
            )
            batch = []
    if batch:
        Document.objects.using(schema_editor.connection.alias).bulk_update(
            batch, ["business_date"]
        )


class Migration(migrations.Migration):
    dependencies = [("inventory", "0010_stocktake_and_revision_guards")]
    operations = [migrations.RunPython(preserve_dates, migrations.RunPython.noop)]
