# Kiểm tra kết nối Drive — 19/10/2026

Thay đổi không có migration và không đổi tồn kho, phiếu, tài khoản hay khóa mã hóa.

- 149/149 kiểm thử PostgreSQL đạt, không bỏ qua. Bảy bài mới kiểm tra: callback theo hostname hiện tại, trang không lộ refresh token/client secret, làm mới token khi chẩn đoán, đối chiếu email/thư mục/quyền, chặn thư mục sai trước khi gọi Google, admin/POST/CSRF, không dùng cache khi đổi cấu hình và xóa lựa chọn thư mục khi đổi tài khoản chưa có hồ sơ.
- Sau sửa câu thông báo, chạy lại 7/7 bài Drive đạt.
- `makemigrations --check --dry-run`: không có thay đổi. `collectstatic --noinput`: thành công. `git diff --check`: đạt; kiểm tra import/undefined names trên các tệp Python thay đổi: đạt.
- Chromium với tài khoản minh họa: trang cấu hình HTTP 200, không lỗi JavaScript; cấu hình thiếu khóa nút kết nối; không tràn ngang ở chiều rộng 390px.
- Nút kiểm tra chỉ đọc metadata, thử refresh authorization và xác minh quyền thêm tệp. Không tạo/xóa tệp hoặc tuyên bố upload đã thành công.
- Cần chủ Drive cấu hình OAuth/Picker trên Google Cloud và cấp quyền thật. Chưa kiểm chứng upload/download thật vào tài khoản của chủ dự án. Xem [hướng dẫn thực hiện](GOOGLE_DRIVE_CONNECTION.md).
