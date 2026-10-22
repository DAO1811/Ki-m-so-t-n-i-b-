"""Stable data codes; Vietnamese display text can change without rewriting records."""

from django.db import models


class CaseStatus(models.TextChoices):
    DRAFT = "DRAFT", "Bản nháp"
    REPORTED = "REPORTED", "Đã ghi nhận"
    NEEDS_INFO = "NEEDS_INFO", "Cần bổ sung thông tin"
    INVESTIGATING = "INVESTIGATING", "Đang xác minh"
    PLANNING = "PLANNING", "Đang lập kế hoạch"
    EXECUTING = "EXECUTING", "Đang thực hiện"
    VERIFYING = "VERIFYING", "Chờ đánh giá hiệu quả"
    CLOSED = "CLOSED", "Đã kết thúc"
    NOT_ACCEPTED = "NOT_ACCEPTED", "Không tiếp nhận"
    DUPLICATE = "DUPLICATE", "Hồ sơ trùng"
    CANCELLED = "CANCELLED", "Đã hủy"


class ActionStatus(models.TextChoices):
    OPEN = "OPEN", "Chưa thực hiện"
    IN_PROGRESS = "IN_PROGRESS", "Đang thực hiện"
    DONE = "DONE", "Đã thực hiện"


class ActionKind(models.TextChoices):
    IMMEDIATE = "IMMEDIATE", "Xử lý tức thời"
    CORRECTIVE = "CORRECTIVE", "Khắc phục nguyên nhân"
    PREVENTIVE = "PREVENTIVE", "Phòng ngừa tái diễn"


SEVERITIES = [
    ("", "Chưa đánh giá"),
    ("MINOR", "Nhỏ"),
    ("MAJOR", "Lớn"),
    ("CRITICAL", "Nghiêm trọng"),
]
TERMINAL = {
    CaseStatus.CLOSED,
    CaseStatus.NOT_ACCEPTED,
    CaseStatus.DUPLICATE,
    CaseStatus.CANCELLED,
}
DEFAULT_CATEGORIES = [
    "Kho & hàng hóa",
    "Tài sản & thiết bị",
    "Nhân sự",
    "Quy trình & tuân thủ",
    "Tài chính & chứng từ",
    "Hoạt động khác",
]
# New screens/actions are registered here, then interpreted by access.py.
READ_ROUTES = {
    "deviations",
    "deviation_list",
    "deviation_detail",
    "deviation_reports",
    "deviation_print",
    "deviation_file",
}
ROUTE_PERMISSIONS = {
    "deviation_new": "deviations_create",
    "deviation_edit": "deviations_create",
    "deviation_analysis": "deviations_manage",
    "deviation_assign": "deviations_manage",
    "deviation_action_new": "deviations_manage",
    "deviation_action_edit": "deviations_manage",
    "deviation_action_work": "deviations_work",
    "deviation_extension": "deviations_work",
    "deviation_extension_decide": "deviations_review",
    "deviation_settings": "admin",
    "deviation_category": "admin",
    "deviation_category_edit": "admin",
    "deviation_transition": "authenticated",
    "deviation_upload": "authenticated",
    "deviation_void_file": "admin",
    "deviation_evaluate": "deviations_review",
}
