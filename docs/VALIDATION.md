# Bằng chứng kiểm tra bản đầu

Ngày 16/10/2026; kiểm tra trong môi trường phát triển cloud, không phải triển khai lên Internet.

- Django 5.2.18, Python 3.12; dependency check không có gói bị xung đột.
- PostgreSQL 17 trong container thử nghiệm: **37 test chạy, 37 đạt, 0 bỏ qua**. Có test xuất đồng thời, không âm tồn, chỉ đúng quản lý kho được nhập, quyền xuất do admin gán, không tự duyệt, định giá bình quân, hàng mượn bị khóa, trả từng phần giữ giá trị và chống trả trùng khi đang đi đường, nhập Excel xem trước/ghi nháp không trùng, bootstrap admin không tự đổi mật khẩu hoặc nâng quyền tài khoản có sẵn.
- Chromium / Playwright: đăng nhập nhân viên → tải file Excel → xem trước → tạo phiếu nháp → đăng nhập tài khoản quản lý kho riêng → xác nhận nhập. Kết quả đúng, không có lỗi JavaScript hoặc HTTP 500.
- Chromium: kiểm tra các trang tổng quan, tồn, thẻ kho, mượn trả, hàng hóa và chứng từ; biểu mẫu thay đổi ô theo loại nghiệp vụ. Viewport desktop 1440 px và điện thoại 390 px, không tràn chiều ngang toàn trang.
- `manage.py check`, kiểm tra migration chưa tạo, `pip check`, Ruff F và `git diff --check` đạt.
- `start.sh` chạy với Python environment đã kích hoạt, DEBUG=0 và PostgreSQL: migrate, tạo vai trò, bootstrap quản trị, chạy Gunicorn 2 workers thành công. Request login và CSS qua proxy HTTPS giả lập trả HTTP 200. Lần chạy ban đầu chưa kích hoạt environment báo thiếu Django; đã sửa cách chạy bằng PATH đúng của venv.
- Dockerfile build thông thường không tải pip được do DNS trong mạng Docker của máy thử nghiệm. Đã tải cùng các wheel chính thức qua pip có TLS bình thường, dùng bản sao build context ngoài checkout và bước install offline; image build thành công, không tắt xác minh TLS hoặc thay checksum. Vì vậy chưa tuyên bố build mạng thông thường trên hosting đã được kiểm chứng.
- Không có thao tác push, đăng ký dịch vụ, thanh toán, tạo DB online hoặc đưa website lên Internet.
- Tài khoản/mật khẩu ngẫu nhiên và dữ liệu minh họa cục bộ phục vụ kiểm thử không phải tài khoản sản xuất. Không lưu mật khẩu vào Git.
- Đã lưu `install_script` và `start_skill` vào bản nháp cấu hình môi trường; chưa Publish hoặc kiểm chứng khôi phục trong task mới.

Ảnh giao diện có dữ liệu minh họa: `images/tong-quan.png`, `images/dien-thoai.png`.
