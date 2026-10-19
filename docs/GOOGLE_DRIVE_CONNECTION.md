# Kết nối Drive trên website Lemon

Website: https://kiemsoatnoibolemon.onrender.com
Trang dành cho admin: https://kiemsoatnoibolemon.onrender.com/settings/drive/

Link thư mục chủ dự án cung cấp không phải thông tin xác thực API. Cần cấu hình ứng dụng Google và chủ Drive đăng nhập cấp quyền một lần. Kết nối ChatGPT với Drive cũng không tự kết nối website này.

## Thứ tự thực hiện

1. Trong Google Cloud Console, tạo/chọn cùng một project cho Drive API, Picker API, OAuth Web application và Picker API key. Bật cả hai API.
2. Trong Google Auth Platform cấu hình Branding/Audience, dùng External cho Gmail cá nhân; thêm tài khoản chủ Drive vào Test users nếu ứng dụng còn Testing. Google quy định refresh token của External Testing cho Drive hết hạn sau 7 ngày; chuyển sang Production để sử dụng lâu dài và thực hiện yêu cầu của Google nếu có. Production không có nghĩa là quyền sẽ không bao giờ bị thu hồi.
3. OAuth Web application có JavaScript origin `https://kiemsoatnoibolemon.onrender.com` và redirect URI `https://kiemsoatnoibolemon.onrender.com/settings/drive/callback/`. Địa chỉ phải khớp từng ký tự. Nếu dùng client cũ, thêm địa chỉ mới thay vì tạo client khác khi chưa cần thiết.
4. API key giới hạn Website referrer `https://kiemsoatnoibolemon.onrender.com/*`, API restriction Google Picker API. Project number là dãy số của chính project này.
5. Tại Render **dịch vụ kiemsoatnoibolemon**, không phải dịch vụ cũ đã tạm dừng: Environment → thêm `GOOGLE_DRIVE_CLIENT_ID`, `GOOGLE_DRIVE_CLIENT_SECRET`, `GOOGLE_PICKER_API_KEY`, `GOOGLE_CLOUD_PROJECT_NUMBER`. Nhập trực tiếp tại Render, không gửi bí mật vào chat. Giữ nguyên SECRET_KEY và DATABASE_URL. Lưu và triển khai lại.
6. Đăng nhập admin → Google Drive → Kết nối tài khoản Google. Chọn tài khoản sở hữu thư mục và gói Google One. Đồng ý quyền drive.file. Sau đó chọn thư mục qua Google Picker: `1ZR6b7rB5KJOh9LjSkoVIcFqEKHp5o0Mp`.
7. Bấm **Kiểm tra quyền truy cập Drive**. Máy chủ thử lấy access token mới từ refresh token, đối chiếu email, thư mục gốc, quyền sở hữu và quyền thêm tệp. Đây là kiểm tra quyền qua API chỉ đọc, chưa phải thử upload.
8. Thêm một ảnh trong hồ sơ hàng hóa và một PDF vào phiếu nhập có thật, rồi mở lại cả hai và kiểm tra thư mục trên Drive. Phần mềm chỉ báo lưu thành công sau khi nhận xác nhận Google; khi đọc lại sẽ kiểm tra kích thước/SHA-256. Không dùng dữ liệu giả hoặc tạo phiếu kho giả trên production để thử.

## Khi gặp lỗi

- Nút kết nối bị khóa: trang hiển thị tên biến còn thiếu. Điền ở Render của dịch vụ mới, không phải phần môi trường Codex.
- `redirect_uri_mismatch`: kiểm tra redirect URI ở bước 3, bao gồm https, hostname và dấu `/` cuối.
- Google chặn tài khoản thử: kiểm tra Audience/Test users và trạng thái ứng dụng.
- Bộ chọn không mở: kiểm tra Picker API đã bật, key/referrer, project number và OAuth cùng project; trình duyệt phải tải được apis.google.com.
- Đã lưu tài khoản nhưng kiểm tra thất bại: quyền có thể hết hạn/bị thu hồi, client đã đổi, thư mục bị chuyển vào thùng rác hoặc mất quyền sở hữu. Kết nối lại đúng tài khoản, chọn lại thư mục. Không tự thay SECRET_KEY để thử.
- Drive hết dung lượng hoặc Google từ chối: tải tệp thất bại, không tự chuyển sang ổ đĩa Render hay database.

Không chia sẻ công khai thư mục, không dùng tài khoản dịch vụ cho dung lượng Drive cá nhân, không đổi tài khoản khi đã có hồ sơ nếu chưa lập kế hoạch chuyển dữ liệu. Ảnh chia theo mã hàng; hóa đơn theo năm/đợt nhập. Database nghiệp vụ vẫn nằm ở PostgreSQL, không nằm trong Drive.

## Nguồn chính thức đã đối chiếu

- https://developers.google.com/workspace/drive/api/guides/api-specific-auth
- https://developers.google.com/workspace/drive/picker/guides/overview
- https://developers.google.com/identity/protocols/oauth2/web-server
- https://developers.google.com/identity/protocols/oauth2#expiration

## Giới hạn xác nhận ngày 19/10/2026

Kiểm thử tự động dùng Google API giả lập, không cấp quyền thay chủ tài khoản. Chưa có bằng chứng OAuth và lưu/đọc tệp thật trên Drive của chủ dự án; chỉ hoàn tất khi các bước 6–8 được thực hiện. Trang hiển thị email kết nối không đủ chứng minh quyền hiện tại vẫn hoạt động.
