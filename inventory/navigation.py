from django.urls import reverse


def navigation(request, access):
    route = request.resolver_match.url_name if request.resolver_match else ""
    kind = (
        request.resolver_match.kwargs.get("kind", "") if request.resolver_match else ""
    ).upper()
    sections = []

    def group(label, items):
        visible = [item for item in items if item]
        if visible:
            sections.append({"label": label, "items": visible})

    def item(key, label, icon, target, names=(), args=(), query=""):
        if not access.get(key):
            return None
        return {
            "label": label,
            "icon": icon,
            "url": reverse(target, args=args) + query,
            "active": route in (names or (target,)),
        }

    def operation(module, code, label, icon):
        if not access.get(module + "_view"):
            return None
        creating = access.get(module + "_create")
        return {
            "label": label,
            "icon": icon,
            "url": reverse("operation_new", args=[code.lower()])
            if creating
            else reverse("documents") + "?kind=" + code,
            "active": (route == "operation_new" and kind == code)
            or (route == "documents" and request.GET.get("kind") == code)
            or (code == "IN" and route == "receipt_import")
            or (code == "OUT" and route == "issue_import"),
        }

    group("I. TỔNG QUAN", [item("dashboard_view", "Tổng quan", "chart", "dashboard")])
    group(
        "II. KHAI BÁO",
        [
            item(
                "products_view",
                "Danh mục hàng hóa",
                "box",
                "products",
                (
                    "products",
                    "product_detail",
                    "product_new",
                    "product_edit",
                    "product_import",
                ),
            ),
            item(
                "warehouses_view",
                "Kho hàng",
                "warehouse",
                "warehouse_list",
                ("warehouse_list", "warehouse_new", "warehouse_edit"),
            ),
        ],
    )
    group(
        "III. NGHIỆP VỤ",
        [
            operation("receipts", "IN", "Nhập kho", "in"),
            operation("issues", "OUT", "Xuất kho", "out"),
            operation("transfers", "TRANSFER", "Chuyển kho", "transfer"),
            item(
                "loans_view",
                "Mượn & trả",
                "loan",
                "loans",
                ("loans", "loan_return", "loan_return_edit"),
            ),
            item(
                "returns_view",
                "Phiếu trả hàng",
                "loan",
                "documents",
                query="?kind=RETURN",
            )
            if not access.get("loans_view")
            else None,
            item(
                "stocktakes_view",
                "Kiểm kê kho",
                "count",
                "stocktakes",
                (
                    "stocktakes",
                    "stocktake_detail",
                    "stocktake_report",
                    "stocktake_paper",
                ),
            ),
            operation("adjustments", "ADJUST", "Điều chỉnh tồn", "count"),
            item(
                "any_approve",
                "Duyệt & xử lý phiếu" if access["admin"] else "Phiếu chờ duyệt",
                "shield",
                "approvals",
            ),
            item("documents_view", "Quản lý phiếu", "file", "documents"),
            item("stock_view", "Tồn kho", "grid", "stock"),
        ],
    )
    group(
        "IV. BÁO CÁO",
        [
            item("reports_view", "Báo cáo", "chart", "reports"),
            item("ledger_view", "Thẻ kho & lịch sử", "history", "ledger"),
        ],
    )
    group(
        "V. TIỆN ÍCH",
        [
            item("tools_qr", "In tem QR", "box", "product_labels"),
        ],
    )
    group(
        "VI. CẤU HÌNH KHO",
        [
            item(
                "custom_fields_manage", "Thông tin tự thêm", "settings", "custom_fields"
            )
        ],
    )
    group(
        "QUẢN TRỊ HỆ THỐNG",
        [
            {
                "label": "Đổi mật khẩu",
                "icon": "lock",
                "url": reverse("password_change"),
                "active": route == "password_change",
            },
            item(
                "team_view",
                "Tài khoản & phân quyền" if access["admin"] else "Nhân viên",
                "users",
                "team",
                ("team", "employee_new", "employee_edit"),
            ),
            item("admin", "Lưu trữ Google Drive", "file", "drive_settings"),
            item("admin", "Dung lượng & báo cáo", "grid", "storage_settings"),
        ],
    )
    return sections


def module_navigation(sections, route, access=None):
    """Group existing, permission-filtered links without granting new access."""
    warehouse = [s for s in sections if s["label"] != "QUẢN TRỊ HỆ THỐNG"]
    administration = [s for s in sections if s["label"] == "QUẢN TRỊ HỆ THỐNG"]
    from deviations.navigation import sections as deviation_sections

    deviations = deviation_sections(route, access or {})
    modules = []
    for key, label, icon, groups in [
        ("warehouse", "Quản lý kho", "warehouse", warehouse),
        ("deviations", "Xử lý sai lệch", "alert", deviations),
        ("processes", "Quy trình", "file", []),
        ("human_resources", "Quản lý nhân sự", "users", []),
        ("administration", "Quản trị hệ thống", "settings", administration),
    ]:
        if key in ("warehouse", "administration") and not groups:
            continue
        active = any(i["active"] for g in groups for i in g["items"])
        modules.append(
            {
                "key": key,
                "label": label,
                "icon": icon,
                "sections": groups,
                "active": active or route == key,
                "url": reverse(key) if not groups else "",
            }
        )
    if not any(module["active"] for module in modules):
        for module in modules:
            if module["key"] == "warehouse":
                module["active"] = True
                break
    return modules
