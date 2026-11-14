# Nhật ký phiên bản

Mỗi lần phát hành ghi: phiên bản, ngày, nội dung thay đổi bằng tiếng Việt dễ hiểu và nhãn bản thử đã được chủ phần mềm duyệt. Quy trình ở [docs/RELEASE_PROCESS.md](docs/RELEASE_PROCESS.md).

## Chưa phát hành

Đang chờ chủ phần mềm thử trên bản thử và báo Đạt.

### Bản thử và đánh số phiên bản (Đợt 0)

- Thêm biến `APP_ENVIRONMENT` và `APP_VERSION`. Bản thử hiện dải "BẢN THỬ" trên mọi trang, thêm "[THỬ]" vào tiêu đề tab.
- Bản thử chặn cứng Google Drive, email và Groq, kể cả khi lỡ khai báo khóa.
- `/healthz/` trả thêm môi trường và phiên bản; chân trang Admin hiện số phiên bản.
- Lệnh `seed_staging` nạp dữ liệu và tài khoản thử, chỉ chạy được trên bản thử.

### Sửa lỗi và rủi ro an toàn (Đợt 1)

- Đăng nhập bằng mật khẩu: sai 5 lần trong 15 phút với cùng tài khoản thì tạm khóa tài khoản đó 15 phút; sai 20 lần từ cùng một địa chỉ IP thì tạm khóa IP đó. Thông báo giống nhau dù tài khoản có tồn tại hay không. Đăng nhập đúng xóa bộ đếm. Passkey và phiên đang đăng nhập không bị ảnh hưởng. Admin xem và mở khóa tại Quản trị → "Khóa tạm đăng nhập". Lệnh dọn: `cleanup_login_throttle`.
- Không khai báo `DEBUG` thì mặc định tắt chế độ gỡ lỗi (trước đây ngoài Render sẽ tự bật). Dockerfile đặt `DEBUG=0` và khởi động bằng `start.sh` như Render.
- Gunicorn trên Render chờ tối đa 120 giây mỗi yêu cầu (trước là 30 giây), để nhập Excel lớn và xuất báo cáo không bị cắt.
- Mật khẩu Admin đầu tiên tạo bằng `bootstrap_admin` cần ít nhất 12 ký tự và không trùng tên tài khoản. Chính sách mật khẩu của nhân viên giữ nguyên.
- `/healthz/` trả `unknown` khi thiếu mã commit thay cho nhãn cũ.
- Khung trò chuyện Groq có dòng nhắc không dán dữ liệu khách hàng, giá vốn hay mật khẩu.
- Sửa bài kiểm thử chập chờn của Trợ lý AI; 2 bài chỉ chạy được trên PostgreSQL được đánh dấu rõ khi chạy SQLite.

## Các phiên bản trước

Chưa gắn số phiên bản. Bản chính hiện chạy commit `7eb1e8d` (đăng nhập passkey). Số phiên bản khởi điểm chờ chủ phần mềm chốt; lịch sử chi tiết sẽ được viết lại ở Đợt 2.
