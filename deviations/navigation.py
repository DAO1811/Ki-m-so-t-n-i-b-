"""Only new-module navigation; existing warehouse menus are left intact."""

from django.urls import reverse

LABELS = {
    "deviations": "Tổng quan sai lệch",
    "deviation_list": "Hồ sơ sai lệch",
    "deviation_new": "Ghi nhận sai lệch",
    "deviation_detail": "Chi tiết hồ sơ",
    "deviation_edit": "Thông tin sự việc",
    "deviation_analysis": "Xác minh & nguyên nhân",
    "deviation_action_new": "Thêm hành động",
    "deviation_action_edit": "Kế hoạch hành động",
    "deviation_action_work": "Cập nhật thực hiện",
    "deviation_extension": "Đề nghị gia hạn",
    "deviation_extension_decide": "Xem xét gia hạn",
    "deviation_reports": "Báo cáo sai lệch",
    "deviation_settings": "Danh mục & cấu hình",
    "deviation_category": "Nhóm sai lệch",
    "deviation_category_edit": "Nhóm sai lệch",
}


def sections(route, access):
    active = (
        route
        if route in {"deviations", "deviation_reports", "deviation_settings"}
        else "deviation_list"
    )
    if route in {"deviation_category", "deviation_category_edit"}:
        active = "deviation_settings"
    links = [
        ("deviations", "Tổng quan", "chart"),
        ("deviation_list", "Hồ sơ sai lệch", "file"),
        ("deviation_reports", "Báo cáo", "grid"),
    ]
    if access.get("admin"):
        links.append(("deviation_settings", "Danh mục & cấu hình", "settings"))
    return [
        {
            "label": "XỬ LÝ SAI LỆCH",
            "items": [
                {
                    "url": reverse(name),
                    "label": label,
                    "icon": icon,
                    "active": route.startswith("deviation") and active == name,
                }
                for name, label, icon in links
            ],
        }
    ]
