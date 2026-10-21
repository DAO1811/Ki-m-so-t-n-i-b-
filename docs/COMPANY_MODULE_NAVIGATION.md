# Điều hướng phần mềm công ty

Menu gồm bốn phần ngang cấp:

- Quản lý kho: các danh mục, nghiệp vụ, kiểm kê, phiếu, tồn kho, báo cáo, QR và trường bổ sung của kho.
- Quy trình: trang thông báo chưa triển khai.
- Quản lý nhân sự: trang thông báo chưa triển khai.
- Quản trị hệ thống: tài khoản/phân quyền, Google Drive và đổi mật khẩu.

Các phần chứa chức năng được mở/thu gọn; chỉ một phần mở tại một thời điểm. Danh sách kho có vùng cuộn riêng để bốn phần luôn dễ tìm. Trang đang dùng tự mở đúng phần, đánh dấu liên kết và đưa mục đang chọn vào vùng nhìn thấy. Điện thoại dùng menu trượt hiện có.

Liên kết và quyền nghiệp vụ hiện có được giữ nguyên. Hai trang chuẩn bị chỉ cho tài khoản đăng nhập đọc thông báo; không cấp quyền nghiệp vụ nhân sự/quy trình và không ghi dữ liệu. Khi xây dựng nghiệp vụ mới phải bổ sung quyền riêng và kiểm soát tại máy chủ.

Không thay đổi mô hình dữ liệu, quy trình duyệt, tồn kho hoặc dữ liệu công ty. Cấu hình trường bổ sung thuộc Quản lý kho vì hiện áp dụng cho dữ liệu kho. Không thêm các chức năng nhật ký/cấu hình chung chưa có sẵn.

Kiểm tra: bộ kiểm thử PostgreSQL, kiểm tra quyền và tách nhóm menu, trình duyệt ở 320/390/768/1024/1440px, mở/thu gọn và hai trang chuẩn bị. Báo cáo kiểm tra trình duyệt lưu ngoài repository tại `/workspace/scratch/company-modules/browser-report.json`.
