# Nhật ký phiên bản

Mỗi lần phát hành ghi: phiên bản, ngày, nội dung thay đổi bằng tiếng Việt dễ hiểu và nhãn bản thử đã được chủ phần mềm duyệt. Quy trình ở [docs/RELEASE_PROCESS.md](docs/RELEASE_PROCESS.md).

## v122 – Trợ lý AI v2 (đang làm, chưa thử)

- Trò chuyện AI qua Groq Free tự tra cứu dữ liệu trong phần mềm theo đúng quyền của người hỏi: hàng hóa, tồn kho, thẻ kho, phiếu, việc chờ duyệt, kiểm kê, hàng cho mượn, sai lệch, hướng dẫn. Chỉ đọc; không tạo, sửa hay duyệt.
- Câu trả lời có số liệu kèm đường dẫn tới màn hình nguồn; khi đang tra cứu hiện "Đang tra cứu: …".
- Ghi nhật ký mỗi lần AI tra cứu (người hỏi, thời điểm, công cụ, số dòng).
- Chân trang mọi màn hình và trang đăng nhập hiện số phiên bản đang dùng (ví dụ "Phiên bản v122").
- Gỡ phần AI chạy trong trình duyệt (Qwen, khoảng 800 MB tải về), kho mã nhẹ đi khoảng 22 MB.

## v121 – 15/11/2026

Đã phát hành lên bản chính (commit `2de2acb`). Chủ phần mềm báo **"Đạt v121-thu2"** ngày 14/11/2026 sau khi thử trên bản thử. Trước khi phát hành đã tạo nhánh khôi phục Neon `khoi-phuc-truoc-v121-20261115`. Bản trước đó (commit `7eb1e8d`) được gọi là `v120`.

### Bản thử và đánh số phiên bản (Đợt 0)

- Thêm biến `APP_ENVIRONMENT` và `APP_VERSION`. Bản thử hiện dải "BẢN THỬ" trên mọi trang, thêm "[THỬ]" vào tiêu đề tab.
- Bản thử chặn cứng Google Drive, email và Groq, kể cả khi lỡ khai báo khóa.
- `/healthz/` trả thêm môi trường và phiên bản; chân trang Admin hiện số phiên bản.
- Lệnh `seed_staging` nạp dữ liệu và tài khoản thử, chỉ chạy được trên bản thử.

### Sửa lỗi và rủi ro an toàn (Đợt 1)

- Đăng nhập bằng mật khẩu: nhân viên sai 5 lần trong 15 phút thì bị khóa đến khi Admin mở khóa (tài khoản Admin tự mở sau 15 phút); sai 20 lần từ cùng một địa chỉ IP thì tạm khóa IP đó 15 phút. Thông báo giống nhau dù tài khoản có tồn tại hay không. Đăng nhập đúng xóa bộ đếm. Admin thấy biểu tượng ổ khóa kèm số tài khoản chờ mở và mở khóa ngay trong trang Quản trị. Passkey và phiên đang đăng nhập không bị ảnh hưởng. Lệnh dọn: `cleanup_login_throttle`.
- Không khai báo `DEBUG` thì mặc định tắt chế độ gỡ lỗi (trước đây ngoài Render sẽ tự bật). Dockerfile đặt `DEBUG=0` và khởi động bằng `start.sh` như Render.
- Gunicorn trên Render chờ tối đa 120 giây mỗi yêu cầu (trước là 30 giây), để nhập Excel lớn và xuất báo cáo không bị cắt.
- Mật khẩu Admin đầu tiên tạo bằng `bootstrap_admin` cần ít nhất 12 ký tự và không trùng tên tài khoản. Chính sách mật khẩu của nhân viên giữ nguyên.
- `/healthz/` trả `unknown` khi thiếu mã commit thay cho nhãn cũ.
- Khung trò chuyện Groq có dòng nhắc không dán dữ liệu khách hàng, giá vốn hay mật khẩu.
- Sửa bài kiểm thử chập chờn của Trợ lý AI; 2 bài chỉ chạy được trên PostgreSQL được đánh dấu rõ khi chạy SQLite.

## Các phiên bản trước

`v120` là commit `7eb1e8d` (đăng nhập passkey), bản chính trước ngày 15/11/2026. Lịch sử chi tiết các bản trước sẽ được viết lại ở Đợt 2.
