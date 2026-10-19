> Đợt 19/10/2026: quy tắc cấp duyệt, ngoại lệ admin tự duyệt kèm xác nhận và migration 0017 ở [APPROVAL_HIERARCHY.md](APPROVAL_HIERARCHY.md). Website chính là https://kiemsoatnoibolemon.onrender.com; snapshot mới giữ trạng thái trước migration 0017, không dùng lại snapshot 0016.

# Tách bản đang dùng và bản đang sửa

Theo yêu cầu của chủ dự án, website phải tiếp tục hoạt động khi phát triển bản mới.

- Trước đợt nâng cấp 17/10/2026, production `main` ở commit `f0a38e7`, schema inventory 0007. Bản mới nâng đến inventory 0016, dùng snapshot trước migration.
- Các nhánh đã kiểm tra: `feature/admin-function-permissions`, kế thừa `feature/qr-stocktake-product-records` và `feature/asset-control-details`; đưa lên main theo yêu cầu tự cập nhật ngày 17/10/2026. Mã thực tế đang chạy xem `/healthz/`, không suy ra từ tên nhánh.
- Không đẩy nhánh phát triển vào `main`, không bấm Manual Deploy cho production, không đổi Environment của Render trong lúc review.
- Không dùng DATABASE_URL của Neon production để kiểm thử hoặc tạo dữ liệu mẫu.
- Preview QR dùng `/workspace/scratch/qr-records/preview.sqlite3`. PostgreSQL kiểm thử riêng chạy trong container `khoviet-ux-postgres` tại loopback 55433. Mật khẩu thử được tạo ngẫu nhiên ngoài kho mã, không đưa vào Git.
- Ảnh bản xem trước có dữ liệu minh họa; chúng không thể hiện trạng thái kho thực tế.
- Lệnh `manage.py test` tạo DB test riêng. Cần chạy trên PostgreSQL để thực hiện kiểm thử cập nhật tồn đồng thời.

## Khi chủ dự án yêu cầu phát hành

1. Kiểm tra lại thay đổi nhánh main từ lần chuẩn bị bản này; giữ các thay đổi mới của người dùng.
2. Xác nhận test nghiệp vụ và trình duyệt, kiểm tra nội dung diff, không có bí mật hoặc DB thử.
3. Giữ dữ liệu trước nâng cấp, không xóa dữ liệu cũ. Đợt 17/10 dùng `safe_migrate` giữ snapshot nhất quán trong Neon trước migration 0008–0016; đã diễn tập phục hồi schema/dữ liệu thử và đối chiếu số dư, phiếu, ngày, mật khẩu. Xem [giới hạn cùng database và quy trình phục hồi](AUTOMATED_RELEASE_SNAPSHOT.md). Không coi rollback code là rollback schema; backup độc lập vẫn cần cho mất toàn database.
4. Chuẩn bị cấu hình OAuth/Drive ở bản thử, kiểm tra lưu/tải thật và quyền truy cập. Lên lịch khoảng chuyển đổi có kiểm soát vì có migration; không hứa hai bản ghi đồng thời an toàn. Khi được yêu cầu phát hành, hợp nhất nhánh cải tiến và cập nhật main; lúc đó Render mới nhận mã mới theo cấu hình triển khai của nó.
5. Kiểm tra triển khai thành công, đăng nhập thật, một luồng nhân viên/quản lý và số dư. Không tuyên bố hoàn tất chỉ từ HTTP 200 của trang đăng nhập.
6. Admin có toàn quyền. Tài khoản khác cấp từng chức năng tại Nhân viên & quyền; có thể cấp quyền duyệt kiểm kê/điều chỉnh cho Tổng giám đốc. Rà lại bảng quyền kế thừa và phân công kho sau migration. Kiểm tra máy quét/điện thoại thật trước khi in tem hàng loạt.
7. Giữ commit và backup trước nâng cấp để có thể phục hồi theo kế hoạch. Giữ nguyên `SECRET_KEY` để đọc được kết nối Drive đã mã hóa; thay khóa cần quy trình chuyển khóa hoặc kết nối lại có kiểm soát.

Bản giao diện đã phát hành trước đây không có migration; bản đang phát triển này **có** migration 0008–0016. `makemigrations --check --dry-run` phải báo không có thay đổi vì các migration cần thiết đã được ghi đầy đủ. Xem [kiểm tra nâng cấp](QR_VALIDATION.md) và [cấu hình Drive](QR_STOCKTAKE_AND_DRIVE.md).

## Yêu cầu phát hành hiện tại

Chủ dự án đã yêu cầu đưa bản mới lên chính thức sau khi kiểm tra và sửa lỗi, không cần xin lại phép phát hành. Ngày 17/10/2026 chủ dự án yêu cầu tự cập nhật ngay. Môi trường phát triển không có DATABASE_URL/API Neon/Render; bổ sung `safe_migrate` để Render dùng kết nối sẵn có, giữ snapshot trước migration trong schema riêng của chính Neon rồi mới nâng cấp. Nếu snapshot không hoàn tất thì dừng bản mới. Đây là bản phục hồi dữ liệu cùng database, không phải backup độc lập. Xem [cơ chế, giới hạn và diễn tập phục hồi](AUTOMATED_RELEASE_SNAPSHOT.md). Không coi GitHub token hoặc HTTP 200 trang đăng nhập là quyền truy cập database hay bằng chứng backup.

Khi đã đủ điều kiện, kiểm tra lại remote main, hợp nhất/push theo quy trình hiện tại và xác nhận Render triển khai đúng commit. `/healthz/` kiểm tra kết nối DB, migration 0016, manifest snapshot và trả mã release/thời điểm/migration nguồn không chứa dữ liệu bí mật. Kiểm tra thêm trang đăng nhập và static; nếu chưa có tài khoản nghiệm thu thật thì ghi rõ giới hạn kiểm tra production, không giả lập đã chạy nghiệp vụ bằng dữ liệu công ty.
