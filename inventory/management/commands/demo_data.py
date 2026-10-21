from django.contrib.auth import get_user_model
from django.core.management.base import BaseCommand, CommandError
from django.db import transaction

from inventory.models import Document, Line, Product, Warehouse
from inventory.services import post_document


class Command(BaseCommand):
    help = "Tạo dữ liệu minh họa trong kho trống; không tạo hoặc đổi mật khẩu."

    @transaction.atomic
    def handle(self, *args, **kwargs):
        if (
            Warehouse.objects.exists()
            or Product.objects.exists()
            or Document.objects.exists()
        ):
            raise CommandError(
                "Chỉ chạy trên dữ liệu trống để tránh trộn dữ liệu minh họa và dữ liệu thật."
            )
        user = (
            get_user_model().objects.filter(is_superuser=True, is_active=True).first()
        )
        if not user:
            raise CommandError("Hãy tạo quản trị viên bằng createsuperuser trước.")
        maker = get_user_model().objects.create(username="demo_author", is_active=False)
        maker.set_unusable_password()
        maker.save()
        a = Warehouse.objects.create(code="HN", name="Kho Hà Nội", address="Hà Nội")
        Warehouse.objects.create(
            code="HCM", name="Kho Hồ Chí Minh", address="TP. Hồ Chí Minh"
        )
        for sku, name, unit, qty, minimum in [
            ("VT-001", "Giấy in A4", "Ram", 120, 30),
            ("VT-002", "Mực máy in", "Hộp", 8, 10),
            ("VT-003", "Băng keo đóng hàng", "Cuộn", 200, 50),
        ]:
            p = Product.objects.create(sku=sku, name=name, unit=unit, minimum=minimum)
            d = Document.objects.create(
                kind="IN",
                destination=a,
                created_by=maker,
                note="Dữ liệu minh họa — không phải số liệu thực tế",
            )
            Line.objects.create(document=d, product=p, quantity=qty, unit_price=50000)
            post_document(d.pk, user)
        self.stdout.write(
            self.style.SUCCESS("Đã tạo 2 kho, 3 mã hàng và 3 phiếu nhập minh họa.")
        )
