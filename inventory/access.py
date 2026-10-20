"""Admin has all functions; other accounts need the admin's explicit function grants."""

from django.core.exceptions import PermissionDenied, ValidationError

KIND_MODULES = {
    "IN": "receipts",
    "OUT": "issues",
    "TRANSFER": "transfers",
    "LOAN": "loans",
    "RETURN": "returns",
    "COUNT": "stocktakes",
    "ADJUST": "adjustments",
}
FUNCTION_ROWS = [
    ("dashboard", "Tổng quan", [("view", "Xem tổng quan và số liệu tổng hợp")]),
    (
        "products",
        "Danh mục hàng hóa",
        [
            ("view", "Xem danh mục và ảnh"),
            ("create", "Thêm hàng hóa"),
            ("edit", "Sửa thông tin / ảnh"),
        ],
    ),
    (
        "warehouses",
        "Kho hàng",
        [
            ("view", "Xem kho được phân công"),
            ("create", "Thêm kho"),
            ("edit", "Sửa thông tin kho"),
        ],
    ),
    (
        "receipts",
        "Nhập kho",
        [
            ("view", "Xem phiếu nhập"),
            ("create", "Lập / sửa phiếu của mình"),
            ("approve", "Duyệt nhập tại kho được phân công"),
        ],
    ),
    (
        "issues",
        "Xuất kho",
        [
            ("view", "Xem phiếu xuất"),
            ("create", "Lập / sửa phiếu của mình"),
            ("approve", "Duyệt xuất tại kho được phân công"),
        ],
    ),
    (
        "transfers",
        "Chuyển kho",
        [
            ("view", "Xem phiếu chuyển"),
            ("create", "Lập / sửa phiếu của mình"),
            ("approve", "Duyệt chuyển đi"),
            ("receive", "Xác nhận nhận hàng"),
        ],
    ),
    (
        "loans",
        "Cho mượn",
        [
            ("view", "Xem lệnh và tồn mượn"),
            ("create", "Lập / sửa lệnh của mình"),
            ("approve", "Duyệt cho mượn"),
            ("receive", "Xác nhận nhận mượn"),
        ],
    ),
    (
        "returns",
        "Trả hàng mượn",
        [
            ("view", "Xem phiếu trả"),
            ("create", "Lập / sửa phiếu của mình"),
            ("approve", "Duyệt trả"),
            ("receive", "Xác nhận nhận trả"),
        ],
    ),
    (
        "stocktakes",
        "Kiểm kê",
        [
            ("view", "Xem phiên / biên bản"),
            ("create", "Mở phiên, đếm QR / ghi số, chốt"),
        ],
    ),
    (
        "adjustments",
        "Điều chỉnh tồn",
        [
            ("view", "Xem phiếu điều chỉnh"),
            ("create", "Lập / sửa phiếu điều chỉnh"),
            ("approve", "Duyệt kiểm kê / điều chỉnh (Tổng giám đốc)"),
        ],
    ),
    ("documents", "Quản lý phiếu", [("view", "Tra cứu các loại phiếu được phép xem")]),
    ("stock", "Tồn kho", [("view", "Xem số lượng và giá trị tồn")]),
    ("ledger", "Thẻ kho và lịch sử", [("view", "Xem giao dịch chi tiết")]),
    ("reports", "Báo cáo", [("view", "Xem báo cáo trong phạm vi được cấp")]),
    (
        "files",
        "Hóa đơn và hồ sơ nhập",
        [
            ("view", "Xem / tải hồ sơ"),
            ("upload", "Bổ sung hồ sơ phiếu nhập"),
            ("void", "Đánh dấu hồ sơ không sử dụng"),
        ],
    ),
    (
        "tools",
        "Tiện ích",
        [
            ("import", "Lập phiếu nhập kho từ Excel"),
            ("export", "Xuất CSV"),
            ("qr", "Xem / in tem QR"),
        ],
    ),
    ("custom_fields", "Trường bổ sung", [("manage", "Quản lý trường hàng hóa")]),
    ("team", "Nhân viên", [("view", "Xem danh sách nhân viên")]),
]
FUNCTION_CHOICES = [
    (f"{module}_{action}", f"{title}: {label}")
    for module, title, actions in FUNCTION_ROWS
    for action, label in actions
]
FUNCTION_KEYS = frozenset(code for code, _ in FUNCTION_CHOICES)
CREATE_KEYS = frozenset(f"{module}_create" for module in KIND_MODULES.values())
APPROVE_KEYS = frozenset(
    f"{module}_{action}"
    for module in set(KIND_MODULES.values())
    for action in ["approve", "receive"]
    if f"{module}_{action}" in FUNCTION_KEYS
)


def is_admin(user):
    return bool(user and user.is_authenticated and user.is_active and user.is_superuser)


def function_codes(user):
    if not user.is_authenticated or not user.is_active:
        return set()
    if is_admin(user):
        return set(FUNCTION_KEYS)
    from .models import FunctionAccess

    return (
        set(
            FunctionAccess.objects.filter(user_id=user.pk)
            .values_list("permissions", flat=True)
            .first()
            or []
        )
        & FUNCTION_KEYS
    )


def has_function(user, code):
    return code in function_codes(user)


def require_function(user, code):
    if not has_function(user, code):
        raise PermissionDenied("Bạn chưa được admin cấp quyền cho chức năng này.")


def normalize_permissions(codes):
    result = set(codes)
    if result - FUNCTION_KEYS:
        raise ValidationError(
            "Có quyền không hợp lệ. Tải lại bảng phân quyền trước khi lưu."
        )
    # An action requires its view, but never implies another action.
    while True:
        before = set(result)
        for code in list(result):
            module, action = code.rsplit("_", 1)
            if action != "view" and f"{module}_view" in FUNCTION_KEYS:
                result.add(f"{module}_view")
        if result & CREATE_KEYS:
            result.add("products_view")
        if "tools_import" in result:
            result.add("receipts_create")
        if "tools_qr" in result:
            result.add("products_view")
        if result & {"files_view", "files_upload", "files_void"}:
            result.add("receipts_view")
        if "returns_create" in result:
            result.add("loans_view")
        if "stocktakes_view" in result:
            result.add("products_view")
        if "stocktakes_create" in result:
            result.add("adjustments_view")
        if "adjustments_approve" in result:
            result.add("stocktakes_view")
        if result == before:
            return sorted(result)


def can_view_kind(user, kind):
    return has_function(user, KIND_MODULES.get(kind, "") + "_view")


def can_create_kind(user, kind):
    return has_function(user, KIND_MODULES.get(kind, "") + "_create")


def approval_key(doc):
    if doc.kind in ["COUNT", "ADJUST"]:
        return "adjustments_approve"
    return KIND_MODULES.get(doc.kind, "") + (
        "_receive" if doc.status == "TRANSIT" else "_approve"
    )


def may_attach(doc, user, *, void=False):
    return bool(
        has_function(user, "files_void" if void else "files_upload")
        and can_view_kind(user, "IN")
        and doc.kind == "IN"
        and doc.status != "CANCELLED"
        and (
            is_admin(user)
            or doc.created_by_id == user.pk
            or doc.destination.managers.filter(pk=user.pk).exists()
        )
    )


def access_context(user):
    codes = function_codes(user)
    return {
        **{key: key in codes for key in FUNCTION_KEYS},
        "admin": is_admin(user),
        "any_create": bool(codes & CREATE_KEYS),
        "any_approve": bool(codes & APPROVE_KEYS),
        "loans_section": bool(codes & {"loans_view", "returns_view"}),
        "warehouse_scope": bool(codes - {"team_view", "custom_fields_manage"}),
    }
