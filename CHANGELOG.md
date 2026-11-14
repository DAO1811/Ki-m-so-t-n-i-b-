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

- Mục này được cập nhật khi hoàn tất Đợt 1.

## Các phiên bản trước

Chưa gắn số phiên bản. Bản chính hiện chạy commit `7eb1e8d` (đăng nhập passkey). Số phiên bản khởi điểm chờ chủ phần mềm chốt; lịch sử chi tiết sẽ được viết lại ở Đợt 2.
