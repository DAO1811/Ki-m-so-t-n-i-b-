"""Load sample warehouses, products, documents and role-based test accounts.

Runs only on staging (APP_ENVIRONMENT=staging) against an empty database. It
never copies company data, not even anonymised.
"""

import os
import secrets

from django.conf import settings
from django.contrib.auth import get_user_model
from django.core.management.base import BaseCommand, CommandError
from django.db import transaction

from config.environment import STAGING
from inventory.models import Document, FunctionAccess, Line, Product, Warehouse
from inventory.services import close_document, post_document

NOTE = "Dữ liệu thử — không phải số liệu thật"
COMMON = [
    "dashboard_view",
    "chat_use",
    "assistant_use",
    "products_view",
    "warehouses_view",
    "documents_view",
]
KINDS = ["receipts", "issues", "transfers", "loans", "returns"]
ACCOUNTS = [
    # username, full name, level, extra functions
    (
        "thu_nguoilap",
        "Người lập (thử)",
        10,
        [f"{k}_view" for k in KINDS]
        + [f"{k}_create" for k in KINDS]
        + [
            "stock_view",
            "ledger_view",
            "stocktakes_view",
            "stocktakes_create",
            "tools_import",
            "deviations_create",
            "deviations_work",
        ],
    ),
    (
        "thu_nguoiduyet",
        "Người duyệt (thử)",
        20,
        [f"{k}_view" for k in KINDS]
        + [f"{k}_approve" for k in KINDS]
        + ["transfers_receive", "loans_receive", "returns_receive"]
        + [
            "stock_view",
            "ledger_view",
            "reports_view",
            "stocktakes_view",
            "adjustments_view",
            "deviations_create",
            "deviations_manage",
            "deviations_review",
            "deviations_department_approve",
        ],
    ),
    (
        "thu_chixem",
        "Nhân viên chỉ xem (thử)",
        10,
        ["receipts_view", "issues_view"],
    ),
]
PRODUCTS = [
    ("THU-001", "Giấy in A4 (thử)", "Ram", 120, 30, 55000),
    ("THU-002", "Mực máy in (thử)", "Hộp", 8, 10, 420000),
    ("THU-003", "Băng keo đóng hàng (thử)", "Cuộn", 200, 50, 12000),
    ("THU-004", "Găng tay bảo hộ (thử)", "Đôi", 60, 20, 18000),
]


class Command(BaseCommand):
    help = (
        "Nạp dữ liệu thử cho bản thử (staging): kho, hàng hóa, phiếu và tài khoản "
        "theo cấp quyền. Chỉ chạy khi APP_ENVIRONMENT=staging và database trống."
    )

    def add_arguments(self, parser):
        parser.add_argument(
            "--password-env",
            default="STAGING_SEED_PASSWORD",
            help="Tên biến môi trường chứa mật khẩu chung cho tài khoản thử. "
            "Không có thì tạo ngẫu nhiên và in ra một lần.",
        )

    def handle(self, *args, password_env, **kwargs):
        if settings.APP_ENVIRONMENT != STAGING:
            raise CommandError(
                "Lệnh chỉ chạy trên bản thử (APP_ENVIRONMENT=staging). "
                "Đã dừng, không ghi gì vào database."
            )
        password = os.environ.get(password_env, "") or secrets.token_urlsafe(12)
        with transaction.atomic():
            self.seed(password)
        self.stdout.write(self.style.SUCCESS("Đã nạp dữ liệu thử."))
        self.stdout.write(
            "Tài khoản thử: thu_admin, " + ", ".join(a[0] for a in ACCOUNTS)
        )
        if not os.environ.get(password_env):
            self.stdout.write("Mật khẩu chung (chỉ hiện lần này): " + password)

    def seed(self, password):
        User = get_user_model()
        if (
            Warehouse.objects.exists()
            or Product.objects.exists()
            or Document.objects.exists()
            or User.objects.filter(username__startswith="thu_").exists()
        ):
            raise CommandError(
                "Database thử đã có dữ liệu. Chỉ nạp vào database trống để không trộn dữ liệu."
            )
        admin = User.objects.create_superuser(
            "thu_admin", password=password, first_name="Admin (thử)"
        )
        users = {}
        for username, full_name, level, functions in ACCOUNTS:
            user = User.objects.create_user(
                username, password=password, first_name=full_name
            )
            FunctionAccess.objects.create(
                user=user,
                approval_level=level,
                job_title=full_name,
                permissions=sorted(set(COMMON + functions)),
                updated_by=admin,
            )
            users[username] = user
        maker, approver, viewer = (
            users["thu_nguoilap"],
            users["thu_nguoiduyet"],
            users["thu_chixem"],
        )
        hn = Warehouse.objects.create(
            code="THU-HN", name="Kho thử Hà Nội", address="Địa chỉ thử"
        )
        hcm = Warehouse.objects.create(
            code="THU-HCM", name="Kho thử Hồ Chí Minh", address="Địa chỉ thử"
        )
        for warehouse in (hn, hcm):
            warehouse.members.add(maker, approver, viewer)
            warehouse.managers.add(approver)
            warehouse.issue_approvers.add(approver)

        products = []
        for sku, name, unit, qty, minimum, price in PRODUCTS:
            product = Product.objects.create(
                sku=sku, name=name, unit=unit, minimum=minimum
            )
            products.append(product)
            # Opening balance: posted receipt, approved by a higher level.
            receipt = self.document("IN", maker, destination=hn)
            Line.objects.create(
                document=receipt, product=product, quantity=qty, unit_price=price
            )
            post_document(receipt.pk, approver)

        # A receipt waiting for approval.
        pending = self.document("IN", maker, destination=hn)
        Line.objects.create(
            document=pending, product=products[0], quantity=10, unit_price=55000
        )
        Line.objects.create(
            document=pending, product=products[2], quantity=20, unit_price=12000
        )
        # An issue waiting for approval.
        issue = self.document("OUT", maker, source=hn, counterparty="Bộ phận thử")
        Line.objects.create(document=issue, product=products[0], quantity=5)
        # An issue sent back for correction.
        rejected = self.document("OUT", maker, source=hn, counterparty="Bộ phận thử")
        Line.objects.create(document=rejected, product=products[3], quantity=2)
        close_document(rejected.pk, approver, "REJECT", "Thử: ghi rõ bộ phận nhận")
        # A transfer dispatched and waiting for the receiving warehouse.
        transfer = self.document("TRANSFER", maker, source=hn, destination=hcm)
        Line.objects.create(document=transfer, product=products[2], quantity=30)
        post_document(transfer.pk, approver)

    @staticmethod
    def document(kind, maker, **fields):
        return Document.objects.create(kind=kind, created_by=maker, note=NOTE, **fields)
