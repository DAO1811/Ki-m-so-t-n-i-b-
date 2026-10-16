# Tách bản đang dùng và bản đang sửa

Theo yêu cầu của chủ dự án, website phải tiếp tục hoạt động khi phát triển bản mới.

- Nhánh production: `main`, commit nền đã triển khai `702f516`.
- Nhánh đang phát triển: `feature/modern-warehouse-workspace`.
- Không đẩy nhánh phát triển vào `main`, không bấm Manual Deploy cho production, không đổi Environment của Render trong lúc review.
- Không dùng DATABASE_URL của Neon production để kiểm thử hoặc tạo dữ liệu mẫu.
- Preview dùng `/workspace/scratch/modern-warehouse/preview.sqlite3`. PostgreSQL kiểm thử riêng chạy trong container `khoviet-ux-postgres` tại loopback 55433. Mật khẩu thử được tạo ngẫu nhiên ngoài kho mã, không đưa vào Git.
- Ảnh bản xem trước có dữ liệu minh họa; chúng không thể hiện trạng thái kho thực tế.
- Lệnh `manage.py test` tạo DB test riêng. Cần chạy trên PostgreSQL để thực hiện kiểm thử cập nhật tồn đồng thời.

## Khi chủ dự án yêu cầu phát hành

1. Kiểm tra lại thay đổi nhánh main từ lần chuẩn bị bản này; giữ các thay đổi mới của người dùng.
2. Xác nhận test nghiệp vụ và trình duyệt, kiểm tra nội dung diff, không có bí mật hoặc DB thử.
3. Sao lưu cơ sở dữ liệu bằng phương thức đã thống nhất với chủ dự án; không xóa dữ liệu cũ.
4. Hợp nhất nhánh cải tiến và cập nhật main; lúc đó Render mới nhận mã mới theo cấu hình triển khai của nó.
5. Kiểm tra triển khai thành công, đăng nhập thật, một luồng nhân viên/quản lý và số dư. Không tuyên bố hoàn tất chỉ từ HTTP 200 của trang đăng nhập.
6. Giữ commit trước để có thể quay lại mã khi cần. Nếu phát sinh thay đổi schema trong tương lai, phải đánh giá riêng khả năng quay lại trước khi chạy migration.

Bản giao diện này không cần thêm hoặc đổi cột trong DB. Kiểm tra `makemigrations --check --dry-run` phải báo không có thay đổi. Tài khoản, mật khẩu băm, phiếu và tồn hiện có vẫn dùng cấu trúc cũ.
