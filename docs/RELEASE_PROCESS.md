# Tách bản đang dùng và bản đang sửa

Theo yêu cầu của chủ dự án, website phải tiếp tục hoạt động khi phát triển bản mới.

- Nhánh production: `main`, commit đã triển khai `f0a38e7` (bản giao diện được chủ dự án yêu cầu phát hành 16/10/2026), schema inventory 0007.
- Nhánh đang phát triển: `feature/qr-stocktake-product-records`, kế thừa `feature/asset-control-details`. Chưa hợp nhất vào `main`.
- Không đẩy nhánh phát triển vào `main`, không bấm Manual Deploy cho production, không đổi Environment của Render trong lúc review.
- Không dùng DATABASE_URL của Neon production để kiểm thử hoặc tạo dữ liệu mẫu.
- Preview QR dùng `/workspace/scratch/qr-records/preview.sqlite3`. PostgreSQL kiểm thử riêng chạy trong container `khoviet-ux-postgres` tại loopback 55433. Mật khẩu thử được tạo ngẫu nhiên ngoài kho mã, không đưa vào Git.
- Ảnh bản xem trước có dữ liệu minh họa; chúng không thể hiện trạng thái kho thực tế.
- Lệnh `manage.py test` tạo DB test riêng. Cần chạy trên PostgreSQL để thực hiện kiểm thử cập nhật tồn đồng thời.

## Khi chủ dự án yêu cầu phát hành

1. Kiểm tra lại thay đổi nhánh main từ lần chuẩn bị bản này; giữ các thay đổi mới của người dùng.
2. Xác nhận test nghiệp vụ và trình duyệt, kiểm tra nội dung diff, không có bí mật hoặc DB thử.
3. Sao lưu cơ sở dữ liệu bằng phương thức đã thống nhất với chủ dự án; không xóa dữ liệu cũ. Khôi phục bản sao vào DB thử, chạy migration 0008–0014 và đối chiếu số dư, phiếu, ngày, mật khẩu; thử kế hoạch quay lại. Không coi rollback code là rollback schema.
4. Chuẩn bị cấu hình OAuth/Drive ở bản thử, kiểm tra lưu/tải thật và quyền truy cập. Lên lịch khoảng chuyển đổi có kiểm soát vì có migration; không hứa hai bản ghi đồng thời an toàn. Khi được yêu cầu phát hành, hợp nhất nhánh cải tiến và cập nhật main; lúc đó Render mới nhận mã mới theo cấu hình triển khai của nó.
5. Kiểm tra triển khai thành công, đăng nhập thật, một luồng nhân viên/quản lý và số dư. Không tuyên bố hoàn tất chỉ từ HTTP 200 của trang đăng nhập.
6. Quản trị viên tạo/chọn tài khoản Tổng giám đốc và cấp quyền duyệt kiểm kê/điều chỉnh riêng. Migration không tự cấp; khi chưa có người duyệt, phiếu nằm chờ. Kiểm tra máy quét/điện thoại thật trước khi in tem hàng loạt.
7. Giữ commit và backup trước nâng cấp để có thể phục hồi theo kế hoạch. Giữ nguyên `SECRET_KEY` để đọc được kết nối Drive đã mã hóa; thay khóa cần quy trình chuyển khóa hoặc kết nối lại có kiểm soát.

Bản giao diện đã phát hành trước đây không có migration; bản đang phát triển này **có** migration 0008–0014. `makemigrations --check --dry-run` phải báo không có thay đổi vì các migration cần thiết đã được ghi đầy đủ. Xem [kiểm tra nâng cấp](QR_VALIDATION.md) và [cấu hình Drive](QR_STOCKTAKE_AND_DRIVE.md).
