"""Reviewed answers to real screens, not an unverified dump of project documents.

Each entry records its implementation evidence for future workflow changes. Matching
is conservative: an unrelated question must not receive arbitrary inventory rows.
"""

from dataclasses import dataclass

from .text import any_phrase, plain


@dataclass(frozen=True)
class Article:
    key: str
    topic: str
    title: str
    phrases: tuple
    answer: str
    evidence: tuple


ARTICLES = (
    Article(
        "return_loan",
        "loans",
        "Trả hàng đã mượn",
        ("tra hang", "tra muon", "muon hang muon tra", "tra lai hang", "tra mot phan"),
        "Để trả hàng đã mượn:\n1. Vào Mượn & trả, mở đúng lệnh mượn gốc đã nhận hàng hoàn tất.\n2. Chọn Trả hàng theo lệnh, nhập số thực trả của từng mã; có thể trả một phần.\n3. Kiểm tra kho trả, kho nhận và diễn giải rồi lưu phiếu.\n4. Người được phân công duyệt chuyển trả; kho cho mượn xác nhận nhận lại thì tồn mới được cộng về kho đó.\nKhông lập một phiếu nhập độc lập để thay việc trả. Nếu không có nút trả, kiểm tra quyền Trả hàng mượn, quyền xem lệnh gốc, kho đang mượn và số còn được trả; phiếu trả nháp cũng giữ chỗ số lượng.",
        ("inventory/loan_returns.py", "inventory/views/document_detail.py"),
    ),
    Article(
        "receipt_excel",
        "receipts",
        "Nhập kho bằng Excel",
        (
            "nhap kho excel",
            "nhap kho hang loat",
            "nhap hang vao kho",
            "1000 dong",
            "1.000 dong",
            "500 dong",
            "mau nhap kho",
            "file nhap kho",
        ),
        "Vào Nhập kho → Nhập từ Excel và tải mẫu ngay tại màn hình này.\n1. Điền ma_hang, so_luong, don_gia, sl_chung_tu, sl_khong_nhan, ly_do, ma_kho. Mã hàng phải có trong danh mục; tra mã kho trong trang Danh sach kho của mẫu.\n2. Dùng .xlsx tối đa 5 MB / 1.000 dòng ở mẫu mới; mẫu cũ 3 hoặc 6 cột tối đa 50 mã. Không dùng công thức Excel.\n3. Tải lên và đối chiếu từng kho, số dòng, số lượng cùng lỗi hiển thị trước khi xác nhận.\n4. Hệ thống chia phiếu nháp theo kho, mỗi phiếu tối đa 50 mã. Duyệt từng phiếu xong mới cộng tồn; import thành công chưa có nghĩa là đã nhập kho.\nSố thực nhận mới vào tồn; phần thiếu/không nhận cần ghi riêng và có lý do.",
        ("inventory/excel.py", "inventory/views/imports.py"),
    ),
    Article(
        "catalog_excel",
        "products",
        "Import danh mục khác nhập tồn",
        (
            "danh muc excel",
            "danh muc hang loat",
            "tao hang hoa hang loat",
            "them hang hoa hang loat",
            "nhap tu excel dung de",
            "import san pham",
        ),
        "Có hai file dùng cho hai công việc khác nhau:\n• Danh mục hàng hóa → Nhập Excel: tạo mã hàng mới cùng tên, đơn vị, QR và thông tin mô tả; tối đa 500 mã / 5 MB. Có thể điền thêm kho, số lượng và đơn giá để tạo riêng phiếu nhập nháp theo kho nếu tài khoản có quyền.\n• Nhập kho → Nhập từ Excel: nhập số lượng của mã đã có; mẫu mới tối đa 1.000 dòng / 5 MB, tự tách phiếu theo kho.\nCả hai cách đều phải kiểm tra bản xem trước. Tồn không tăng khi mới tạo danh mục hoặc lưu phiếu nháp; cần duyệt phiếu nhập.",
        (
            "inventory/product_import.py",
            "inventory/product_allocation.py",
            "inventory/excel.py",
        ),
    ),
    Article(
        "issue_excel",
        "issues",
        "Xuất kho hàng loạt",
        (
            "xuat kho excel",
            "xuat hang loat",
            "xuat kho hang loat",
            "mau xuat kho",
            "file xuat kho",
        ),
        "Vào Xuất kho → Nhập từ Excel, tải đúng mẫu xuất có ma_hang, so_luong, ghi_chu. Chọn kho xuất được cấp quyền, nhập lý do và tải file .xlsx; mỗi phiếu tối đa 50 mã. Kiểm tra bản xem trước rồi xác nhận tạo phiếu nháp. Người đủ quyền và phân công duyệt thì mới trừ tồn. File nhập kho 7 cột không dùng thay cho mẫu xuất kho.",
        ("inventory/issue_import_views.py", "inventory/forms.py"),
    ),
    Article(
        "product_qr",
        "products",
        "QR gắn cố định với hàng hóa",
        ("ma qr", "tao qr", "qr tu dong", "qr tu nhap", "doi qr", "tem qr"),
        "Trong Danh mục hàng hóa → Thêm hàng hóa:\n1. Khai báo mã, tên, đơn vị tính.\n2. Giữ chọn QR tự động để phần mềm tạo mã; bỏ chọn để nhập nội dung mã đã có trên tem hoặc mã tự đặt duy nhất.\n3. Lưu hàng hóa. QR gắn cố định với mã đó, không sửa sau khi đã lưu. Người có quyền xem/in tem QR có thể in tem từ danh mục.\nNếu sản phẩm có tem sẵn, nhập đúng nội dung mà máy quét đọc được, không nhập đường dẫn ảnh QR. Tạo QR không làm tăng tồn kho.",
        ("inventory/forms.py", "inventory/models.py", "inventory/records_views.py"),
    ),
    Article(
        "product_photo",
        "products",
        "Ảnh hàng hóa",
        (
            "hinh anh",
            "anh san pham",
            "anh hang hoa",
            "tai anh",
            "them anh",
            "cap nhat anh",
        ),
        "Vào Danh mục hàng hóa, mở đúng mã hàng rồi bổ sung ảnh và chú thích. Có thể thêm ảnh ngay khi tạo hoặc cập nhật sau nếu có quyền Thêm/Sửa hàng hóa tương ứng. Ảnh nhận diện dùng chung cho mã hàng; hóa đơn của từng lần mua cần lưu ở hồ sơ phiếu nhập, không trộn vào ảnh sản phẩm. Nếu báo chưa chọn thư mục Drive, Admin cần hoàn tất kết nối và chọn thư mục tại Google Drive trước.",
        (
            "inventory/views/catalog.py",
            "inventory/records_views.py",
            "inventory/media.py",
        ),
    ),
    Article(
        "invoice_history",
        "receipts",
        "Hóa đơn theo từng lần nhập",
        ("hoa don", "scan", "file pdf", "chung tu nguon"),
        "Mỗi lần nhập lưu hồ sơ tại chính phiếu nhập đó: số/ngày hóa đơn hoặc chứng từ nguồn và tệp scan/PDF liên quan. Mở phiếu nhập → bổ sung hồ sơ nếu được cấp quyền Hóa đơn và hồ sơ nhập. Khi mở chi tiết mã hàng, lịch sử các lần nhập giúp quay về đúng phiếu/hóa đơn, tránh gộp hóa đơn khác đợt. Quyền xem tệp và quyền tải lên được cấp riêng; tệp đã ghi nhận không xóa thẳng, có thao tác đánh dấu không sử dụng theo quyền và lưu lý do.",
        ("inventory/records_views.py", "inventory/models.py"),
    ),
    Article(
        "receipt_fields",
        "receipts",
        "Thông tin phiếu nhập",
        (
            "truong nhap",
            "can dien",
            "thong tin nhap",
            "tao phieu nhap",
            "lap phieu nhap",
            "mua hang",
        ),
        "Để nhập hàng mua về:\n1. Nếu chưa có mã, tạo trong Danh mục hàng hóa trước.\n2. Vào Nhập kho, chọn kho nhập và ngày nghiệp vụ hôm nay; bổ sung diễn giải, nhà cung cấp/chứng từ nguồn theo thực tế.\n3. Thêm từng mã, số lượng thực nhận, đơn giá; đối chiếu số theo chứng từ, số không nhận và lý do. Ghi tình trạng/lý do ở từng dòng; bộ phận, người giao và người nhận là thông tin của phiếu. Bản hiện tại chưa có trường bảo hành/lô/serial riêng theo từng dòng nhập.\n4. Lưu nháp, kiểm tra lại, chuyển người có quyền và phân công tại kho duyệt. Chỉ sau khi ghi sổ tồn mới tăng.\nHóa đơn scan bổ sung trong hồ sơ phiếu nhập. Không tự suy ra rằng mọi đề xuất trường hoặc quy trình email đã được triển khai.",
        (
            "inventory/forms.py",
            "inventory/services.py",
            "inventory/views/document_editing.py",
        ),
    ),
    Article(
        "short_receipt",
        "receipts",
        "Hàng thiếu hoặc không nhận",
        (
            "thieu hang",
            "hang thieu",
            "khong nhan",
            "thuc nhan",
            "hang hong",
            "so chung tu",
        ),
        "Số lượng nhập phải là số thực nhận. Ghi riêng số theo chứng từ và số không nhận; nếu thiếu/không nhận cần nêu rõ lý do trên dòng hàng. Kiểm tra quan hệ giữa các số trước khi gửi duyệt. Phần thiếu, hỏng bị từ chối nhận không được cộng vào tồn như hàng đã nhận. Lưu hóa đơn và bằng chứng theo đúng phiếu nhập.",
        ("inventory/services.py", "inventory/forms.py"),
    ),
    Article(
        "business_date",
        "receipts",
        "Ngày nghiệp vụ của phiếu",
        (
            "ngay nhap",
            "ngay xuat",
            "ngay hom qua",
            "ngay cu",
            "lui ngay",
            "ngay nghiep vu",
            "qua ngay",
        ),
        "Phiếu nháp chỉ được lập và duyệt với ngày nghiệp vụ hôm nay. Nếu phiếu nháp từ hôm trước, người lập cần mở sửa, cập nhật ngày và kiểm tra lại hàng trước khi gửi. Ngày chứng từ nguồn là trường riêng, không được ở tương lai; có ngày chứng từ thì cần có số chứng từ. Không đổi ngày một phiếu đã ghi sổ để sửa lịch sử tồn.",
        ("inventory/services.py", "inventory/forms.py"),
    ),
    Article(
        "approval",
        "approvals",
        "Điều kiện duyệt phiếu kho",
        (
            "khong duyet duoc",
            "khong the duyet",
            "ai duyet",
            "quyen duyet",
            "cap duyet",
            "tu duyet",
            "khong thay nut duyet",
            "duyet phieu",
            "cho duyet",
        ),
        "Phiếu kho chỉ duyệt khi đủ cả trạng thái, cấp, quyền chức năng và phân công kho:\n• Nhân viên → Leader → Trưởng phòng → Admin tổng. Người duyệt phải cao hơn người lập và không tự duyệt; chức danh nhập bằng chữ không thay thế cấp duyệt.\n• Nhập kho: phân công người quản lý kho nhận. Xuất/chuyển đi: phân công duyệt tại kho xuất. Nhận hàng đang chuyển: người quản lý kho nhận.\n• Kiểm kê/điều chỉnh: cần quyền duyệt điều chỉnh được cấp riêng.\n• Admin tổng thấy toàn bộ và được ngoại lệ tự duyệt, nhưng phải xác nhận cảnh báo.\nMột người đủ điều kiện duyệt là đủ cho bước phiếu kho tương ứng; Xử lý sai lệch dùng chuỗi ký riêng. Gửi số phiếu để tôi kiểm tra trạng thái và lý do chặn của tài khoản đang đăng nhập.",
        ("inventory/services.py", "inventory/hierarchy.py"),
    ),
    Article(
        "posted_immutable",
        "documents",
        "Phiếu đã ghi sổ không sửa trực tiếp",
        (
            "sua phieu",
            "xoa phieu",
            "da duyet",
            "da ghi so",
            "huy phieu",
            "chinh sua phieu",
        ),
        "Phiếu đã ghi sổ không được sửa hoặc xóa trực tiếp. Phiếu nháp/yêu cầu sửa chỉ được chỉnh theo quyền và người lập; hủy hoặc yêu cầu sửa cần lý do và điều kiện tương ứng. Nếu sai sau khi ghi sổ, ghi nhận sai lệch và để người có thẩm quyền xử lý bằng nghiệp vụ có dấu vết; không xóa database để làm sạch lịch sử. Trợ lý không tự sửa, xóa hoặc duyệt phiếu thay bạn.",
        ("inventory/views/document_editing.py", "inventory/services.py"),
    ),
    Article(
        "transfer",
        "transfers",
        "Chuyển kho có hai bước",
        ("chuyen kho", "hang dang chuyen", "cho nhan", "nhan chuyen"),
        "Lập phiếu chuyển với hai kho khác nhau, mã hàng, số lượng và lý do. Người có quyền tại kho xuất duyệt chuyển đi: kho xuất giảm và hàng ở trạng thái đang chuyển. Người có quyền tại kho nhận kiểm tra rồi xác nhận thực nhận: kho nhận mới tăng tồn. Chưa xác nhận nhận thì không coi là tồn đã có tại kho nhận. Nếu không thấy nút, kiểm tra cấp duyệt, quyền theo chức năng và phân công kho.",
        ("inventory/services.py", "inventory/views/document_detail.py"),
    ),
    Article(
        "stocktake_qr",
        "stocktakes",
        "Kiểm kê bằng QR hoặc giấy",
        (
            "kiem ke",
            "kiem dem",
            "chot ton",
            "quet qr",
            "khoa kho",
            "mo kho",
            "chenh lech",
            "bien ban",
        ),
        "Luồng kiểm kê theo từng kho:\n1. Vào Kiểm kê · QR, chọn kho và chốt mốc tồn. Giao dịch làm đổi tồn kho đó bị khóa trong thời gian kiểm đếm.\n2. Mở phiên đã chốt, nhận kiểm và chọn Quét QR hoặc Kiểm bằng giấy.\n3. QR: mỗi lượt quét hợp lệ cộng một đơn vị; đưa tem ra ngoài trước lượt tiếp theo. Có thể ghi/sửa tổng thực đếm. Với giấy: in bảng, đếm thực tế rồi nhập kết quả lại đúng phiên.\n4. Xác nhận tất cả mã, kể cả số thực đếm 0; ghi kết luận/lý do rồi chốt. Ở bản hiện tại, nếu đã gửi phiếu điều chỉnh còn chờ duyệt thì kho vẫn khóa giao dịch; chỉ chốt biên bản chưa tự mở kho trong trường hợp này.\n5. Có chênh lệch thì lập phiếu điều chỉnh, chờ người được phân quyền Tổng giám đốc duyệt mới thay tồn. Nếu kho đã biến động không khớp mốc, hệ thống yêu cầu kiểm tra/kiểm đếm lại.\nChưa quét không có nghĩa là số đếm bằng 0. Không cộng hàng mượn tạm vào tồn sở hữu.",
        (
            "inventory/stocktakes.py",
            "inventory/models.py",
            "templates/stocktake_detail.html",
        ),
    ),
    Article(
        "stocktake_delete",
        "stocktakes",
        "Hủy phiên và yêu cầu sửa điều chỉnh",
        (
            "xoa kiem ke",
            "xoa phieu kiem ke",
            "khong duyet dieu chinh",
            "tu choi dieu chinh",
            "huy kiem ke",
        ),
        "Bản phần mềm hiện có thao tác Hủy phiên có lý do khi phiên còn ở trạng thái cho phép; người lập/người nhận kiểm hoặc Admin cần đủ quyền tương ứng. Hủy phiên đang kiểm kết thúc khóa kiểm đếm theo phiên đó. Phiếu điều chỉnh đã gửi được xử lý riêng theo trạng thái và quyền duyệt; yêu cầu sửa không đồng nghĩa đã điều chỉnh tồn. Hiện chưa có thao tác xóa hẳn phiếu kiểm kê trong giao diện này. Tôi không hướng dẫn một nút xóa chưa được triển khai.",
        (
            "inventory/stocktakes.py",
            "inventory/stocktake_views.py",
            "inventory/urls.py",
        ),
    ),
    Article(
        "permissions",
        "team",
        "Tài khoản, cấp duyệt và phân quyền",
        (
            "phan quyen",
            "tai khoan",
            "chuc vu",
            "chuc danh",
            "leader",
            "truong phong",
            "admin",
            "nhan vien",
        ),
        "Admin vào Tài khoản & phân quyền để tạo/sửa tài khoản:\n1. Đặt tên đăng nhập, thông tin nhân viên, chức danh và cấp duyệt Nhân viên/Leader/Trưởng phòng.\n2. Cấp từng chức năng: xem, tạo, duyệt, nhận hoặc thao tác liên quan.\n3. Phân công kho được xem, quản lý kho nhận, duyệt tại kho xuất.\nAdmin tổng có toàn quyền chức năng. Tài khoản khác không được duyệt chỉ vì có chức danh cao: cần đủ quyền, cấp cao hơn người lập và phân công kho. Người dùng đổi mật khẩu tại mục đổi mật khẩu của tài khoản; không gửi mật khẩu trong khung trợ lý.",
        (
            "core/views.py",
            "inventory/forms.py",
            "inventory/access.py",
            "inventory/hierarchy.py",
        ),
    ),
    Article(
        "deviation_approval",
        "deviations",
        "Chuỗi duyệt hồ sơ sai lệch",
        ("sai lech", "capa", "dieu tra", "riv", "ket thuc ho so", "danh gia hieu qua"),
        "Với biểu mẫu sai lệch phiên bản mới:\n1. Báo cáo: người lập → Trưởng bộ phận → KSNB.\n2. Điều tra: người thực hiện → TBP chuyên môn → KSNB.\n3. Kế hoạch CAPA: người soạn → bộ phận liên quan → KSNB → Tổng giám đốc.\n4. Thực hiện hành động, cập nhật kết quả/bằng chứng. KSNB được phân quyền đánh giá hiệu quả rồi kết thúc theo điều kiện hồ sơ.\nRIV được tính từ khả năng xảy ra × hậu quả; người duyệt chọn loại sai lệch theo căn cứ. Các bước phụ thuộc phiên bản và cấu hình đã chụp của hồ sơ; không đổi thứ tự ký của hồ sơ cũ theo quy tắc mới. Trợ lý không ký hoặc chuyển bước thay người dùng.",
        ("deviations/template_forms.py", "deviations/services", "deviations/models.py"),
    ),
    Article(
        "drive",
        "drive",
        "Kết nối Google Drive và chọn thư mục",
        (
            "google",
            "drive",
            "thu muc",
            "developer key",
            "invalid_client",
            "access_denied",
        ),
        "Admin mở Google Drive trong phần cài đặt:\n1. Kết nối đúng tài khoản Google và đồng ý quyền của ứng dụng.\n2. Chọn đúng thư mục lưu trữ qua bộ chọn Google; đăng nhập thành công chưa có nghĩa là đã chọn thư mục.\n3. Kiểm tra quyền truy cập, sau đó thử tải ảnh tại hàng hóa và PDF tại phiếu nhập rồi mở lại để kiểm tra.\nNếu báo API developer key is invalid: kiểm tra khóa Google Picker, dự án và giới hạn website khớp địa chỉ phần mềm. Nếu invalid_client: kiểm tra Client ID và Client secret là hai giá trị riêng. Nếu access_denied khi đang thử nghiệm: thêm đúng tài khoản vào người kiểm thử OAuth. Không gửi khóa, mật khẩu hoặc token trong khung này.",
        ("inventory/drive_views.py", "inventory/drive.py"),
    ),
    Article(
        "storage",
        "storage",
        "Dung lượng database và tệp",
        ("dung luong", "database", "neon", "luu tru", "trang tinh", "sheet"),
        "Admin mở Lưu trữ để kiểm tra dung lượng mới nhất. Số dung lượng PostgreSQL đo trong phần mềm khác với Storage/History của Neon; không tự dùng một con số thay cho cả hai. Hạn mức tổng phải đối chiếu đúng gói của tài khoản Neon, không suy ra chỉ từ số MB đã dùng. Ảnh/PDF dùng Drive theo kết nối; dữ liệu nghiệp vụ cần giao dịch và phân quyền vẫn ở database. Trợ lý không xóa dữ liệu hoặc tự chuyển sổ kho sang trang tính.",
        ("inventory/storage_views.py", "inventory/storage_reports.py"),
    ),
    Article(
        "chat",
        "chat",
        "Nhắn tin, nhóm và gọi nội bộ",
        (
            "nhan tin",
            "messenger",
            "zalo",
            "chat",
            "sticker",
            "goi video",
            "goi thoai",
            "tao nhom",
            "danh ba",
        ),
        "Mở Nhắn tin nội bộ, dùng Danh bạ/tìm người để bắt đầu trò chuyện. Tạo nhóm cần quyền tạo nhóm; nhóm tối đa 30 thành viên. Có thể gửi chữ, ảnh, PDF, emoji/sticker; mỗi lượt tối đa 3 tệp, tổng 8 MB. Gọi thoại/video cần quyền gọi và quyền micro/camera; cuộc gọi tối đa 6 người, chất lượng còn phụ thuộc mạng và cấu hình kết nối. Chỉ thành viên được xem hội thoại; Admin không đọc hội thoại riêng mình không tham gia. Trợ lý không đọc hoặc tìm nội dung chat của nhân viên.",
        ("chat/services.py", "chat/calls.py", "chat/directory.py"),
    ),
    Article(
        "custom_fields",
        "products",
        "Trường bổ sung và bảo hành",
        ("truong bo sung", "bao hanh", "serial", "so lo", "han bao hanh"),
        "Trường bổ sung dùng để khai báo thêm thông tin của mã hàng, ví dụ xuất xứ, vị trí trên kệ hoặc thời hạn bảo hành dạng nội dung. Người có quyền quản lý trường tạo ô tại Trường bổ sung; người có quyền tạo/sửa hàng nhập nội dung trong hồ sơ mã hàng. Không dùng trường của mã hàng để thay lịch sử riêng từng lần mua. Bản hiện tại chưa có bộ đếm/cảnh báo hết bảo hành theo từng đợt nhập; tôi không tự suy ra số ngày còn lại từ ô văn bản chưa được chuẩn hóa.",
        ("inventory/forms.py", "templates/custom_fields.html", "inventory/models.py"),
    ),
    Article(
        "not_implemented",
        "general",
        "Phân hệ đang chuẩn bị",
        (
            "nhan su",
            "tien luong",
            "cham cong",
            "tuyen dung",
            "xuat huy",
            "kho huy",
            "quy trinh email",
        ),
        "Tôi chưa có căn cứ trong phiên bản hiện tại để hướng dẫn nghiệp vụ này như một chức năng hoàn chỉnh. Nhân sự và Quy trình đang là phân hệ chuẩn bị; các quy trình xuất hủy/email riêng chưa được xác nhận là đã triển khai. Không dùng xuất kho thông thường để giả lập một quy trình phê duyệt chưa có. Bạn có thể hỏi rõ thao tác hiện tại hoặc gửi yêu cầu để Admin xác nhận phạm vi.",
        ("people/views.py", "workflows/views.py", "inventory/urls.py"),
    ),
)

TOPIC_WORDS = (
    ("deviations", ("sai lech", "capa", "ho so sl")),
    ("stocktakes", ("kiem ke", "kiem dem", "chot ton", "quet qr")),
    ("loans", ("tra hang", "tra muon", "muon", "cho muon")),
    ("transfers", ("chuyen kho", "luan chuyen")),
    ("receipts", ("nhap kho", "phieu nhap", "hoa don", "hang mua")),
    ("issues", ("xuat kho", "phieu xuat")),
    (
        "products",
        ("danh muc", "tao san pham", "them hang hoa", "ma qr", "anh san pham"),
    ),
    ("approvals", ("duyet phieu", "quyen duyet", "tu duyet")),
    ("team", ("phan quyen", "tai khoan", "chuc vu", "chuc danh")),
    ("drive", ("drive", "google", "thu muc")),
    ("storage", ("database", "neon", "dung luong", "luu tru")),
    ("chat", ("chat", "nhan tin", "sticker", "danh ba", "tao nhom", "goi video")),
    ("stock", ("ton kho", "ton", "con bao nhieu", "sap het", "het hang", "ton thap")),
)


def explicit_topic(norm):
    return next(
        (topic for topic, words in TOPIC_WORDS if any_phrase(norm, words)), None
    )


def find_article(question, topic):
    norm = plain(question)
    ranked = []
    for index, article in enumerate(ARTICLES):
        matches = [p for p in article.phrases if any_phrase(norm, (p,))]
        if matches:
            # Specific task phrases beat a generic word such as "nhân viên".
            score = max(len(p.split()) for p in matches) * 10
            score += 3 if article.topic == topic else 0
            ranked.append((score, -index, article))
    return max(ranked, default=(0, 0, None), key=lambda item: item[:2])[2]


DRAFTS = (
    (
        ("hoa don", "chung tu", "bien ban"),
        "Bạn vui lòng bổ sung hóa đơn/chứng từ và biên bản liên quan vào đúng hồ sơ trước khi gửi duyệt; nếu chưa có, ghi rõ lý do và thông tin còn thiếu để người phụ trách kiểm tra.",
    ),
    (
        ("duyet",),
        "Anh/chị vui lòng kiểm tra thông tin, số lượng và hồ sơ đính kèm của phiếu trước khi xem xét duyệt theo đúng quyền và phân công. Nếu có nội dung chưa phù hợp, đề nghị ghi rõ lý do để người lập bổ sung.",
    ),
    (
        ("kiem ke", "kiem dem"),
        "Anh/chị vui lòng kiểm đếm theo đúng kho và mốc tồn đã chốt, xác nhận số thực đếm của từng mã kể cả số 0, ghi rõ nguyên nhân chênh lệch và hoàn tất biên bản trước khi chuyển bước xem xét điều chỉnh.",
    ),
    (
        ("ma hang", "so luong", "don gia", "nhap kho"),
        "Bạn vui lòng đối chiếu mã hàng, số lượng thực nhận và đơn giá với chứng từ; bổ sung lý do thiếu/không nhận nếu có và kiểm tra đúng kho nhập trước khi gửi phiếu duyệt.",
    ),
)


def draft_answer(norm):
    if not any_phrase(norm, ("soan", "viet", "nhac", "mau noi dung")):
        return None
    for words, text in DRAFTS:
        if any_phrase(norm, words):
            return "Mẫu nội dung tham khảo (chưa gửi):\n" + text
    return None
