# Phát hành riêng Xử lý sai lệch — 22/10/2026

Chủ phần mềm đã đồng ý cập nhật bản chính và chọn rõ: **chỉ thêm Xử lý sai lệch, giữ nguyên chức năng cũ**. Bản phát hành được tách từ main `340b2da351b782a23a8d7b27b51744603505821d`; không phát hành toàn bộ nhánh `preview/shared-review`.

## Phạm vi

- Thêm app `deviations`, bảng `deviations_*`, màn hình, quyền ghi, ảnh/PDF, hành động, đánh giá và lịch sử đã được xem trên bản thử.
- Chỉ thêm các điểm tích hợp app/URL, menu, quyền, loại lưu trữ Drive và stylesheet riêng. Template và CSS nguồn của màn hình cũ giữ nguyên.
- Không có migration inventory 0019, không thêm StocktakeDeletion, không sửa models/services/stocktakes/views/URL nghiệp vụ kho hoặc các màn hình phiếu kho.
- Giữ nguyên cơ chế khóa kho/duyệt/xóa kiểm kê đang chạy, không đưa thay đổi kiểm kê còn chờ trong PR bản thử vào đây.
- Liên kết kiểm kê trong app mới tương thích với schema inventory 0018 hiện tại; không bắt buộc nâng cấp phần kiểm kê.

## Nâng cấp và bảo vệ dữ liệu

Migration app mới phụ thuộc inventory 0018 và chỉ tạo dữ liệu/bảng của app sai lệch. Tài khoản, mật khẩu, quyền đã cấp, số dư, chứng từ và khóa kiểm kê cũ không được viết lại.

Bước `safe_migrate` hiện có dùng một tên snapshot mới `dhd_backup_deviations_0001` để chụp nhất quán dữ liệu trước khi thêm app. Cơ chế khóa/sao chép cũ không đổi; không xóa hoặc ghi đè snapshot trước. Snapshot nằm cùng database, không thay backup độc lập.

Health giữ điều kiện inventory 0018 và thêm điều kiện migration app sai lệch 0003. Chỉ báo phát hành thành công khi `/healthz/` trả đúng commit đang chạy và snapshot sẵn sàng.

Rollback code về `340b2da` có thể bỏ qua các bảng sai lệch mới; không tự đảo migration/xóa dữ liệu hoặc khôi phục snapshot. Giữ mọi hồ sơ phát sinh để đối soát trước khi quyết định phục hồi.

## Kiểm tra ứng viên

- Toàn bộ 343 kiểm thử trên PostgreSQL 17 thử riêng đã đạt; gồm bộ hồi quy cũ và kiểm thử app sai lệch.
- Kiểm thử nâng cấp riêng: từ inventory 0018 có tài khoản, hàng, tồn và khóa kiểm kê giả lập sang app mới. Đối chiếu mật khẩu, cấu trúc bảng StocktakeSession, số dư và khóa còn nguyên; không có bảng xóa kiểm kê.
- Ba bài diễn tập migration cũ cập nhật đích khôi phục thành mọi migration lá, để giữ app mới trong môi trường test; không đổi kiểm tra nghiệp vụ kho.
- `safe_migrate` đã chạy với dữ liệu giả lập, tạo snapshot mới và chỉ áp dụng deviations 0001–0003; inventory vẫn ở 0018.
- Trình duyệt Chromium: đăng nhập, tạo/gửi, ảnh và tải riêng tư, phân công, xác minh, kế hoạch, cảnh báo Admin tự duyệt, thực hiện, đánh giá/kết thúc, PDF, sáng/tối và màn hình 390 px.
- Sau thử, quy tắc giả lập được tắt lại. Không có dữ liệu mẫu được đưa vào migration hoặc production.
- Ruff, Django check, migration check, CSS bundle và collectstatic phải đạt trước khi merge; GitHub Actions chạy lại trên đúng nhánh phát hành.

## Giới hạn giữ nguyên như bản đã xem

Mặc định mở ghi nhận hồ sơ; các bước xử lý chờ Admin cấu hình quy tắc công ty đã chốt. Chưa tự áp SLA, email hay chế tài. Mọi tài khoản nhân viên hoạt động được xem hồ sơ theo quyết định của chủ phần mềm; quyền ghi được cấp riêng. Drive thật dùng cấu hình hiện có, chưa xác minh bằng một lần tải tệp mới trên production; test mạng dùng giả lập.

Không tự tạo thêm Nhân sự/Quy trình hoặc dịch vụ trả phí. Xem `deviations/README.md` để bảo trì app mới.
