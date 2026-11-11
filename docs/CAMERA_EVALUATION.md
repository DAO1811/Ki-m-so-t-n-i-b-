# Camera riêng của KSNB — bản đánh giá 11/11/2026

Phân hệ `camera_identity` thực hiện ghi nhận mẫu và so khớp 1:1 ở máy chủ bằng YuNet/SFace. Đây không phải Apple Face ID. Kết quả nhận diện **không tạo phiên đăng nhập**, kể cả khi khớp; mật khẩu và các chức năng cũ giữ đường truy cập hiện có. Chưa phát hành hoặc bật chức năng trên bản chính.

## Đã thực hiện

- Xác nhận mật khẩu và đồng ý xử lý sinh trắc học trước khi đăng ký cho chính tài khoản đang sử dụng.
- Ba ảnh theo hướng dẫn; kiểm tra một khuôn mặt, chất lượng và tư thế ở máy chủ. Không tin kết quả so khớp do trình duyệt cung cấp.
- Mẫu 128 chiều được mã hóa Fernet bằng khóa cấu hình riêng, gắn với user/model/consent; không lưu ảnh gốc hoặc tải lên Drive.
- Yêu cầu theo phiên, hết hạn 120 giây, dùng một lần, giới hạn tần suất. Xóa mẫu cần mật khẩu. Mỗi tài khoản chỉ quản lý mẫu của mình.
- Camera chỉ mở khi người dùng bấm và cấp quyền; tắt khi hoàn tất, hủy, lỗi hoặc rời trang.
- Engine chạy tiến trình riêng, thư viện và trọng số tùy chọn; không thêm OpenCV vào dependencies chính. Mô hình được kiểm tra giấy phép và SHA-256.

## Kiểm chứng và hạn chế

Toàn bộ 531 kiểm thử ứng dụng đạt trên PostgreSQL thử riêng, gồm 17 trường hợp bảo vệ API camera. Các kiểm thử bảo vệ API giả lập đầu ra mô hình; phép thử engine thật được chạy riêng với ảnh ví dụ được cấp phép Apache-2.0.

Engine thật đã tạo descriptor, từ chối ảnh trống và nhiều khuôn mặt. API thật đã mã hóa mẫu và trả kết quả khớp. Đồng thời, ảnh được biến dạng/mirror cũng vượt qua được kiểm tra chuyển động: đây là **bằng chứng chưa chống giả mạo**, không phải bằng chứng người thật. Kết quả khớp vẫn trả `login_permitted=false` và không đăng nhập.

Chưa đo tỉ lệ nhận nhầm/từ chối nhầm với người dùng KSNB hoặc iPhone/Windows thật. Chưa có PAD đã đánh giá độc lập. Chưa đo tải trên Render Free; engine đo khoảng 223 MB RSS ở môi trường phát triển, không chứng minh vừa tài nguyên hoặc không ảnh hưởng ứng dụng chính. Vì vậy chưa đủ điều kiện dùng so mặt để mở tài khoản công ty.

## Chạy bản thử riêng

Dùng database, tài khoản và nơi lưu tệp thử riêng. Cài dependencies web hiện có và `requirements-camera-evaluation.txt` trong môi trường engine riêng, tải models bằng `scripts/fetch_camera_models.py`. Xem [giấy phép và nguồn mô hình](CAMERA_MODEL_LICENSES.md).

Cấu hình `CAMERA_IDENTITY_ENABLED=1`, `CAMERA_IDENTITY_TEMPLATE_KEY` là khóa Fernet tạo riêng, `CAMERA_IDENTITY_ENGINE_PYTHON` là đường dẫn tuyệt đối tới Python engine, `CAMERA_IDENTITY_MODEL_DIR` là thư mục models đã xác minh. Không gửi khóa vào chat hoặc Git. Production mặc định tắt; thiếu cấu hình trả lỗi đóng, không bỏ qua xác thực.

Mở `/account/camera/` sau đăng nhập để đăng ký/xóa mẫu, `/camera/verify/` để thử so khớp. Trang thử luôn nêu rõ kết quả chưa cho phép đăng nhập. Không được dùng ảnh demo hoặc camera ảo để tuyên bố đã kiểm chứng Face ID/người thật.

## Điều kiện còn thiếu trước khi phát hành đăng nhập mặt

Cần giải pháp chống trình diện ảnh/video và chèn dữ liệu đã đánh giá, bảo vệ nguồn thu nhận, kiểm thử sai nhận/sai từ chối trên thiết bị thật, phục hồi/xóa dữ liệu và tài nguyên xử lý riêng đã đo. Không thể coi chớp mắt hoặc quay đầu là PAD đã đạt. Bản camera chưa được chủ phần mềm xem và kiểm chứng trên thiết bị thật.
