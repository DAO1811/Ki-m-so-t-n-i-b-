# Kiểm chứng đăng nhập passkey — 10/11/2026

Bản thay đổi được tách từ `7430d1f` trên nhánh `feature/passkey-login-20261110`. Phạm vi chỉ gồm phân hệ passkey và các điểm nối đăng nhập, menu tài khoản, cấu hình và thư viện cần thiết. Không gộp các thay đổi giao diện, tối ưu khởi động hoặc phân hệ Anh Hiếu đang phát triển ở nơi khác.

## Kết quả

- Toàn bộ **514 kiểm thử** đạt trên PostgreSQL thử riêng, gồm **45 kiểm thử passkey**; thời gian 208,006 giây.
- Kiểm thử passkey dùng chữ ký ES256/CBOR thật: đăng ký, đăng nhập, ràng buộc origin/RP/session, xác minh người dùng, hết hạn, chặn phát lại, thu hồi và bảo toàn phân quyền.
- Kiểm tra đồng thời trên PostgreSQL dùng khóa hàng thật: dùng lại challenge, giới hạn số passkey, challenge hết hạn trong lúc đợi khóa, tài khoản bị xóa trong lúc đăng nhập.
- Hồi quy mật khẩu: đăng nhập mật khẩu sau passkey không giữ dấu vết phương thức cũ; xác nhận bằng mật khẩu định dạng cũ không tự đổi hash hoặc làm hỏng phiên đang đăng ký.
- Chromium với trình xác thực CTAP2 ảo đã thực hiện `navigator.credentials.create/get` tới backend thật. Đã kiểm tra mật khẩu xác nhận sai, đăng nhập theo quyền hạn chế, gỡ passkey, phiên bị thu hồi, mật khẩu dự phòng, CSRF, trình duyệt không hỗ trợ và bố cục 390px.
- Ruff, cú pháp JavaScript, kiểm tra bundle CSS, Django check, phát hiện migration thiếu, collectstatic và kiểm tra xung đột thư viện đều đạt.
- Docker dựng thành công. Bước cài thư viện trong bản dựng kiểm tra chỉ bổ sung mount CA của môi trường; vẫn xác minh TLS. Không sửa Dockerfile phát hành.

Database, tài khoản, mật khẩu và passkey trong các phép thử đều là dữ liệu thử riêng. Không nối database công ty, Drive, email hoặc API trả phí để thử nghiệm. Không tạo passkey thử trên bản chính.

## Giới hạn và phát hành

Chưa thử Face ID trên iPhone hoặc Windows Hello trên phần cứng thật. Trình xác thực ảo kiểm tra luồng ứng dụng và xác thực WebAuthn; không chứng minh tương thích phần cứng của từng người dùng. Hệ điều hành có thể dùng khuôn mặt, vân tay hoặc PIN. Giữ đăng nhập bằng mật khẩu để khôi phục khi cần.

Ảnh xem trước phải được chụp lại từ server chạy commit đã chốt, ghi rõ commit và dữ liệu thử. Chưa merge main hoặc triển khai production; chờ chủ phần mềm xem và đồng ý đúng phiên bản theo `AGENTS.md`.

Hướng dẫn cấu hình và vận hành: [passkeys.md](passkeys.md).
