# Kiểm tra kết nối Drive — 19/10/2026

Thay đổi không có migration và không đổi tồn kho, phiếu, tài khoản hay khóa mã hóa.

- 149/149 kiểm thử PostgreSQL đạt, không bỏ qua. Bảy bài mới kiểm tra: callback theo hostname hiện tại, trang không lộ refresh token/client secret, làm mới token khi chẩn đoán, đối chiếu email/thư mục/quyền, chặn thư mục sai trước khi gọi Google, admin/POST/CSRF, không dùng cache khi đổi cấu hình và xóa lựa chọn thư mục khi đổi tài khoản chưa có hồ sơ.
- Sau sửa câu thông báo, chạy lại 7/7 bài Drive đạt.
- `makemigrations --check --dry-run`: không có thay đổi. `collectstatic --noinput`: thành công. `git diff --check`: đạt; kiểm tra import/undefined names trên các tệp Python thay đổi: đạt.
- Chromium với tài khoản minh họa: trang cấu hình HTTP 200, không lỗi JavaScript; cấu hình thiếu khóa nút kết nối; không tràn ngang ở chiều rộng 390px.
- Nút kiểm tra chỉ đọc metadata, thử refresh authorization và xác minh quyền thêm tệp. Không tạo/xóa tệp hoặc tuyên bố upload đã thành công.
- Cần chủ Drive cấu hình OAuth/Picker trên Google Cloud và cấp quyền thật. Chưa kiểm chứng upload/download thật vào tài khoản của chủ dự án. Xem [hướng dẫn thực hiện](GOOGLE_DRIVE_CONNECTION.md).

## Sửa chính sách referrer cho Google Picker

Sau khi chủ dự án cấp OAuth thành công, Google Picker báo `The API developer key is invalid` dù ảnh cấu hình cho thấy key đã giới hạn đúng API/website. Kiểm tra HTTP website đang chạy xác nhận `Referrer-Policy: same-origin`. Chính sách mặc định này không gửi Referer sang Google, làm mất tín hiệu website cần cho key giới hạn HTTP referrer.

Trang admin `/settings/drive/` nay dùng `strict-origin-when-cross-origin`: yêu cầu khác origin chỉ gửi origin, không gửi đường dẫn/query, không gửi referrer khi hạ cấp HTTPS. Giữ chính sách mặc định ở mọi trang khác, nhất là callback OAuth có authorization code. Không bỏ giới hạn API key hoặc mở thêm scope Google.

- 8/8 kiểm thử PostgreSQL Drive đạt; bài mới kiểm tra policy trang Picker và giữ policy của login/callback.
- Chromium với website thử thật: trước sửa, Referer của yêu cầu khác origin là null; sau sửa, chỉ có origin, không có query minh họa. Trang hàng hóa vẫn không gửi referrer ra ngoài.
- Kiểm tra import/undefined names và `git diff --check` đạt. Không có migration hoặc thay đổi dữ liệu.
- Đây là xác nhận sửa chính sách website, chưa phải bằng chứng Google chấp nhận API key hiện tại hoặc đã lưu tệp Drive thật. Cần chủ tài khoản thử Picker và upload/download lại.

Tham chiếu: https://docs.djangoproject.com/en/5.2/ref/middleware/#referrer-policy
