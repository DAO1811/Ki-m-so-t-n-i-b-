# Kiểm tra bản cải tiến chưa phát hành

Ngày 16/10/2026. Tất cả thao tác ghi và dữ liệu thử chạy trong môi trường phát triển tách riêng, không kết nối Neon production.

## PostgreSQL

60 kiểm thử chạy trên PostgreSQL 17: **60 đạt, 0 thất bại, 0 bỏ qua**. Gồm 37 kiểm thử nền và 23 kiểm thử bổ sung về phạm vi kho, hàng chờ duyệt, tạo/sửa phiếu, chống gửi trùng, xóa dòng, giá trị báo cáo, thiếu tồn từ bước lập phiếu, trả theo lệnh gốc, quản lý nhân viên, mật khẩu tự chọn, ngăn tự cấp quyền và bộ lọc lỗi. Có kiểm thử hai luồng cùng xuất hàng không thể làm âm tồn.

Các kiểm tra nền của Django, migration chưa tạo, Ruff F và Git whitespace đạt. Không phát sinh thay đổi schema.

## Chromium

- Quản trị viên tạo nhân viên, chọn vai trò và kho trên một màn hình; dùng mật khẩu ban đầu ngắn theo quy tắc của chủ dự án.
- Nhân viên đổi mật khẩu, phiên đăng nhập được giữ và tên đăng nhập không đổi.
- Lập phiếu nhập có một dòng ban đầu, tự chọn kho khi chỉ có một kho, tìm hàng không dấu, tính tạm tiền, thêm/xóa dòng rồi lưu.
- Tài khoản khác duyệt qua hàng chờ; tồn thực trong DB preview tăng đúng số lượng. Người lập không có nút tự duyệt.
- Hủy hộp xác nhận duyệt vẫn dùng được nút; chấp nhận sau đó mới ghi sổ.
- Trả hàng từ lệnh mượn tự điền hàng, kho đi và kho về, khóa chiều trả ở cả client và server.
- Xuất kho, chuyển hai bước, cho mượn và trả từng phần, kiểm kê số thực đếm, điều chỉnh giảm và nhập Excel đều được chạy trọn quy trình trên trình duyệt; kiểm tra lại số tồn từ DB preview sau từng bước.
- Các trang danh mục, kho, nhân viên, báo cáo, tồn, thẻ, mượn trả, Excel, trường bổ sung và đổi mật khẩu tải thành công.
- Giao diện 1600 px và 390 px; menu điện thoại, bộ lọc kho chung, sáng/tối, không tràn ngang toàn trang. Không có lỗi JavaScript hoặc HTTP 500 trong các luồng đã chạy.

## Lỗi đã xử lý trong đợt này

- Phiếu nhập thiếu giá và xuất thiếu tồn được báo ngay trước khi tạo phiếu chờ duyệt; khi ghi sổ vẫn kiểm tra lại.
- Tạo/sửa phiếu dùng chung kiểm tra dòng, chống trùng mã và số lượng không hợp lệ.
- Thêm khóa phiên gửi để tránh tạo trùng khi gửi lại form.
- Hàng mượn giữ riêng; phía trả không tự đổi chiều kho và không dùng nhầm tồn thường.
- Bộ lọc kho trái phép hoặc sai định dạng trả trang 404 an toàn, không gây lỗi lồng trong trang lỗi.
- CSV được mã hóa một lần để không chèn BOM vào từng dòng.
- Kiểm tra giới hạn số lượng/giá trị trước khi ghi sổ để trả lỗi nghiệp vụ thay vì lỗi DB.
- Hủy hộp xác nhận không vô hiệu hóa nút duyệt.

Đây là bằng chứng cho các tình huống đã kiểm tra, không phải cam kết không thể phát sinh lỗi khác. Chưa cập nhật Render production hoặc nghiệm thu đăng nhập người dùng thật cho bản mới.

## Giữ website hiện tại

Đã xác minh remote main vẫn là commit `702f516`. Trang đăng nhập production trả HTTP 200 và vẫn phục vụ CSS bản cũ. Không đẩy main, không thao tác Environment hoặc Deploy của Render, không ghi vào Neon production.
