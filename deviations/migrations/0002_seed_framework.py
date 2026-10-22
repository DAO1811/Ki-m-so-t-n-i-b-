from django.db import migrations


def seed(apps, schema_editor):
    Category = apps.get_model("deviations", "Category")
    Policy = apps.get_model("deviations", "WorkflowPolicy")
    for name in [
        "Kho & hàng hóa",
        "Tài sản & thiết bị",
        "Nhân sự",
        "Quy trình & tuân thủ",
        "Tài chính & chứng từ",
        "Hoạt động khác",
    ]:
        Category.objects.using(schema_editor.connection.alias).get_or_create(name=name)
    Policy.objects.using(schema_editor.connection.alias).get_or_create(
        pk=1, defaults={"enabled": False}
    )


class Migration(migrations.Migration):
    dependencies = [("deviations", "0001_initial")]
    operations = [migrations.RunPython(seed, migrations.RunPython.noop)]
