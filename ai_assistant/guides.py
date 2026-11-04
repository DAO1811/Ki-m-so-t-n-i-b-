"""Reviewed help for implemented features, not proposed business workflows."""

GUIDES = {
    "products": (
        "Danh mục hàng hóa",
        "Tạo danh mục hàng hóa chỉ khai báo mã, tên, đơn vị và QR; chưa làm tăng tồn kho. QR gắn với mã hàng suốt vòng đời. Có thể thêm ảnh khi tạo hoặc cập nhật sau theo quyền được cấp. Để tăng tồn cần lập phiếu nhập và được duyệt.",
        "products",
    ),
    "receipts": (
        "Nhập kho",
        "Chọn kho nhập, hàng hóa, số lượng thực nhận và đơn giá. Số theo chứng từ, số không nhận và lý do cần đối chiếu trước khi gửi. Lưu phiếu nháp chưa tăng tồn; người có quyền và phân công phù hợp duyệt mới ghi sổ. Phiếu đã ghi sổ không sửa hoặc xóa trực tiếp. Nhập Excel cần dùng đúng file mẫu từ màn hình nhập kho, kiểm tra kết quả trước khi xác nhận.",
        "documents",
    ),
    "issues": (
        "Xuất kho",
        "Chọn kho xuất được cấp quyền, hàng hóa, số lượng và lý do. Kiểm tra tồn khả dụng trước khi gửi. Phiếu được duyệt mới ghi sổ; hệ thống không cho âm tồn. Người duyệt phải đáp ứng quyền, cấp duyệt và phân công. Admin tự duyệt cần xác nhận cảnh báo.",
        "documents",
    ),
    "transfers": (
        "Chuyển kho",
        "Chọn hai kho khác nhau, hàng hóa và số lượng. Duyệt chuyển đi trừ tồn kho xuất và treo hàng đang chuyển. Kho nhận xác nhận thực nhận thì cộng tồn kho nhận. Không xem hàng đang chuyển là đã nhận.",
        "documents",
    ),
    "loans": (
        "Mượn và trả",
        "Lệnh cho mượn và phiếu trả là hai bước riêng. Muốn trả, mở đúng lệnh mượn gốc rồi chọn trả hàng theo lệnh, có thể trả từng phần. Không trả quá số còn nợ; hàng đang trả cũng được tính để tránh trả trùng. Hai phía xác nhận theo quyền được giao.",
        "loans",
    ),
    "stocktakes": (
        "Kiểm kê",
        "Chọn kho, mở phiên kiểm kê và chốt mốc tồn theo luồng hiện có. Có thể đếm bằng giấy hoặc QR; một lượt quét hợp lệ cộng một đơn vị. Kiểm tra số đếm, ghi nguyên nhân chênh lệch rồi chốt. Chênh lệch không tự thay tồn; phải qua phiếu điều chỉnh và người được phân quyền duyệt.",
        "stocktakes",
    ),
    "stock": (
        "Tồn kho",
        "Số tồn phải đọc từ dữ liệu ghi sổ của kho được cấp quyền. Phiếu nháp, hàng đang chuyển và hàng mượn có trạng thái riêng. Khi tra cứu ghi rõ mã hàng và kho; không cộng các loại tồn khác nhau thành tồn khả dụng.",
        "stock",
    ),
    "deviations": (
        "Xử lý sai lệch",
        "Hồ sơ đi qua ghi nhận, điều tra, kế hoạch khắc phục/phòng ngừa, thực hiện và đánh giá hiệu quả. Thực hiện đúng thứ tự ký theo phiên bản luồng đã chốt. RIV là khả năng xảy ra nhân hậu quả; người duyệt chọn loại sai lệch theo căn cứ. KSNB có quyền phù hợp kiểm tra hiệu quả và kết thúc. AI chỉ gợi ý nội dung, không ký hoặc chuyển trạng thái hồ sơ.",
        "deviations",
    ),
    "general": (
        "Hỗ trợ công việc",
        "Nêu rõ thao tác, mã hàng hoặc số phiếu bạn cần hỏi. Trợ lý chỉ đọc dữ liệu được cấp quyền; không tạo, sửa, xóa hoặc duyệt phiếu thay bạn. Có thể hỗ trợ soạn nội dung khi bật AI trên thiết bị. Phân hệ Quy trình và Nhân sự mới là phần chuẩn bị; không khẳng định đã có nghiệp vụ chưa triển khai.",
        "dashboard",
    ),
}


def topic_for(route, kind=""):
    if route.startswith("deviation"):
        return "deviations"
    if route.startswith(("product", "qr_")):
        return "products"
    if route.startswith("stocktake"):
        return "stocktakes"
    if route in {"stock", "ledger", "reports"}:
        return "stock"
    if route.startswith(("loan", "return")):
        return "loans"
    if route.startswith("receipt"):
        return "receipts"
    if route.startswith("issue"):
        return "issues"
    return {
        "IN": "receipts",
        "OUT": "issues",
        "TRANSFER": "transfers",
        "LOAN": "loans",
        "RETURN": "loans",
        "COUNT": "stocktakes",
        "ADJUST": "stocktakes",
    }.get(kind, "general")
