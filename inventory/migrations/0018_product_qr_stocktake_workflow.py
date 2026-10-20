import django.db.models.deletion
from django.conf import settings
from django.db import migrations, models

import inventory.product_codes


def preserve_qr_identity(apps, schema_editor):
    Product = apps.get_model("inventory", "Product")
    pending = []
    for product in (
        Product.objects.using(schema_editor.connection.alias)
        .only("pk", "qr_token", "qr_code")
        .iterator(chunk_size=500)
    ):
        product.qr_code = f"DHD:ITEM:{product.qr_token}"
        pending.append(product)
        if len(pending) == 500:
            Product.objects.using(schema_editor.connection.alias).bulk_update(
                pending, ["qr_code"], batch_size=500
            )
            pending.clear()
    if pending:
        Product.objects.using(schema_editor.connection.alias).bulk_update(
            pending, ["qr_code"], batch_size=500
        )


def preserve_count_history(apps, schema_editor):
    Session = apps.get_model("inventory", "StocktakeSession")
    Session.objects.using(schema_editor.connection.alias).filter(
        started_at__isnull=True
    ).update(started_at=models.F("created_at"), counted_by_id=models.F("created_by_id"))


class Migration(migrations.Migration):
    dependencies = [("inventory", "0017_approval_hierarchy")]
    operations = [
        migrations.AddField(
            model_name="stocktakesession",
            name="counted_by",
            field=models.ForeignKey(
                to=settings.AUTH_USER_MODEL,
                on_delete=django.db.models.deletion.PROTECT,
                null=True,
                blank=True,
                related_name="counted_stocktakes",
            ),
        ),
        migrations.AddField(
            model_name="product",
            name="qr_auto",
            field=models.BooleanField(
                "Tự động tạo mã QR", default=True, db_default=True
            ),
        ),
        # Nullable permits old workers to finish inserts during the rolling
        # switch. New creation requires QR; legacy UUID lookup remains valid.
        migrations.AddField(
            model_name="product",
            name="qr_code",
            field=models.CharField("Mã QR", max_length=120, unique=True, null=True),
        ),
        migrations.RunPython(preserve_qr_identity, migrations.RunPython.noop),
        migrations.AlterField(
            model_name="product",
            name="qr_code",
            field=models.CharField(
                "Mã QR",
                max_length=120,
                unique=True,
                null=True,
                default=inventory.product_codes.new_qr_code,
            ),
        ),
        migrations.AddField(
            model_name="stocktakesession",
            name="started_at",
            field=models.DateTimeField(null=True, blank=True),
        ),
        migrations.AddField(
            model_name="stocktakesession",
            name="method",
            field=models.CharField(
                "Cách kiểm kê",
                max_length=8,
                default="QR",
                db_default="QR",
                choices=[("QR", "Quét QR"), ("PAPER", "Kiểm bằng giấy")],
            ),
        ),
        migrations.AddField(
            model_name="stocktakesession",
            name="locks_inventory",
            field=models.BooleanField(default=False, db_default=False),
        ),
        migrations.AlterField(
            model_name="stocktakesession",
            name="status",
            field=models.CharField(
                max_length=12,
                default="OPEN",
                choices=[
                    ("READY", "Đã chốt tồn, chờ kiểm kê"),
                    ("OPEN", "Đang đếm"),
                    ("SUBMITTED", "Đã lập phiếu điều chỉnh"),
                    ("COMPLETED", "Hoàn tất, không chênh lệch"),
                    ("CANCELLED", "Đã hủy phiên"),
                ],
            ),
        ),
        migrations.AlterField(
            model_name="stocktakeevent",
            name="action",
            field=models.CharField(
                max_length=12,
                choices=[
                    ("FREEZE", "Chốt tồn và khóa kho"),
                    ("BEGIN", "Bắt đầu kiểm đếm"),
                    ("START", "Mở phiên"),
                    ("SET", "Ghi số đếm"),
                    ("ADD", "Quét cộng 1"),
                    ("SUBMIT", "Gửi duyệt"),
                    ("CANCEL", "Hủy phiên"),
                ],
            ),
        ),
        migrations.AddConstraint(
            model_name="stocktakesession",
            constraint=models.UniqueConstraint(
                fields=("warehouse",),
                condition=models.Q(locks_inventory=True, status__in=["READY", "OPEN"]),
                name="one_locked_count_per_warehouse",
            ),
        ),
        migrations.RunPython(preserve_count_history, migrations.RunPython.noop),
    ]
