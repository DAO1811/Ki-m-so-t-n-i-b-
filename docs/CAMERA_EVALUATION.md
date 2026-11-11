# Camera riêng của KSNB — bản đánh giá 11/11/2026

Phân hệ `camera_identity` thực hiện ghi nhận mẫu và so khớp 1:1 ở máy chủ bằng YuNet/SFace. Đây không phải Apple Face ID. Kết quả nhận diện **không tạo phiên đăng nhập**, kể cả khi khớp; mật khẩu và các chức năng cũ giữ đường truy cập hiện có. Chưa phát hành hoặc bật chức năng trên bản chính.

## Đã thực hiện

- Xác nhận mật khẩu và đồng ý xử lý sinh trắc học trước khi đăng ký cho chính tài khoản đang sử dụng.
- Ba ảnh theo hướng dẫn; kiểm tra một khuôn mặt, chất lượng và tư thế ở máy chủ. Không tin kết quả so khớp do trình duyệt cung cấp.
- Mẫu 128 chiều được mã hóa Fernet, gắn với user/model/consent; không lưu ảnh gốc hoặc tải lên Drive. Thiếu RAM, không khớp, lỗi camera hoặc thay đổi mật khẩu không tự xóa mẫu. Không có nút/API xóa mẫu; đăng ký lại thành công mới cập nhật mẫu, theo yêu cầu chủ phần mềm ngày 12/11/2026.
- Yêu cầu theo phiên, hết hạn 120 giây, dùng một lần, giới hạn tần suất. Mỗi tài khoản chỉ quản lý mẫu của mình; mẫu của tài khoản khác không được dùng thay.
- Camera chỉ mở khi người dùng bấm và cấp quyền; tắt khi hoàn tất, hủy, lỗi hoặc rời trang.
- Engine chạy tiến trình riêng, thư viện và trọng số tùy chọn; không thêm OpenCV vào dependencies chính. Mô hình được kiểm tra giấy phép và SHA-256. Docker đóng gói môi trường engine riêng nhưng mặc định tắt camera; chỉ bật trong bản thử bằng biến môi trường.
- Một tác vụ inference đồng thời qua khóa liên tiến trình; tối đa 20 giây, ưu tiên CPU thấp. Kiểm tra RAM theo cgroup/host: cần 300 MiB trước khi bắt đầu; dừng tiến trình inference nếu phần còn lại dưới 64 MiB hoặc không đo được. Chỉ dừng tiến trình inference của phân hệ mới.

## Kiểm chứng và hạn chế

Toàn bộ 552 kiểm thử ứng dụng đạt trên PostgreSQL thử riêng (208,7 giây), gồm kiểm tra bảo vệ API, ràng buộc tài khoản, không xóa mẫu khi lỗi, khóa mã hóa và giới hạn tài nguyên. Các kiểm thử bảo vệ API giả lập đầu ra mô hình; phép thử engine thật được chạy riêng với ảnh ví dụ được cấp phép Apache-2.0. Bảy kiểm tra trình duyệt Chromium đạt, dùng camera ảo từ ảnh được cấp phép; không phải kiểm tra iPhone thật.

Sau đợt đầy đủ này đã bổ sung kiểm tra che mật khẩu/ảnh trong biến cục bộ của traceback JSON API khi lỗi bất ngờ; toàn bộ 39 kiểm tra camera riêng đã đạt. CI chạy lại cả bộ trên đúng commit cuối, kèm job engine thật độc lập. Không dùng số kiểm thử chức năng để khẳng định độ chính xác sinh trắc học hoặc chống giả mạo.

Engine thật đã tạo descriptor, từ chối ảnh trống và nhiều khuôn mặt. API thật đã mã hóa mẫu và trả kết quả khớp. Đồng thời, ảnh được biến dạng/mirror cũng vượt qua được kiểm tra chuyển động: đây là **bằng chứng chưa chống giả mạo**, không phải bằng chứng người thật. Kết quả khớp vẫn trả `login_permitted=false` và không đăng nhập.

Đã thử riêng Intel Open Model Zoo `anti-spoof-mn3` ONNX chính thức, kiểm tra SHA-384 và MIT license. Ba khung ảnh biến dạng nêu trên vẫn được mô hình chấm xác suất người thật khoảng 96–98%. Đây là phép chèn ảnh số tổng hợp, không phải phép thử in ảnh/camera/người thật được kiểm định; không đủ căn cứ để mở đăng nhập. Mô hình PAD này không được tích hợp vào đường xác thực.

Docker thử với 512 MiB RAM, 0,1 CPU và hai Gunicorn worker lưu được mẫu bằng engine thật. Khi cố ý tạo áp lực RAM, API trả 503, mẫu mã hóa giữ nguyên và dịch vụ không OOM. Trong một lượt inference 19,5 giây, 60 GET trang đăng nhập chạy song song đều trả 200 (trung vị 0,05 giây, cao nhất 0,50 giây). Đây là máy thử bị giới hạn tài nguyên, không phải số đo Render hoặc bảo đảm mọi tải sản xuất. Tốc độ inference hiện chưa đạt trải nghiệm đăng nhập nhanh.

Một lượt lặp lại với cùng giới hạn và GET chạy song song đã trả 503 khi hết thời gian xử lý. Không coi lượt thành công đầu tiên là bằng chứng vận hành ổn định hoặc đủ điều kiện phát hành.

Chưa đo tỉ lệ nhận nhầm/từ chối nhầm với người dùng KSNB hoặc iPhone/Windows thật. Chưa có PAD/bảo vệ nguồn thu nhận đã kiểm chứng. Vì vậy chưa đủ điều kiện dùng so mặt để mở tài khoản công ty. Không phát hành một bản chỉ so khớp rồi gọi là đăng nhập đã hoàn thiện.

## Chạy bản thử riêng

Dùng database, tài khoản và nơi lưu tệp thử riêng. Cài dependencies web hiện có và `requirements-camera-evaluation.txt` trong môi trường engine riêng, tải models bằng `scripts/fetch_camera_models.py`. Xem [giấy phép và nguồn mô hình](CAMERA_MODEL_LICENSES.md).

Cấu hình `CAMERA_IDENTITY_ENABLED=1`, `CAMERA_IDENTITY_TEMPLATE_KEY` là khóa Fernet tạo riêng, `CAMERA_IDENTITY_ENGINE_PYTHON` là đường dẫn tuyệt đối tới Python engine, `CAMERA_IDENTITY_MODEL_DIR` là thư mục models đã xác minh. Không gửi khóa vào chat hoặc Git. Production mặc định tắt; thiếu cấu hình trả lỗi đóng, không bỏ qua xác thực. Môi trường Python nguyên bản chỉ cài engine trong `build.sh` khi bật cờ camera và cung cấp đường dẫn tuyệt đối.

Docker chuẩn bị sẵn interpreter `/opt/ksnb-camera/bin/python`, models và license trong `/opt/ksnb-camera-models`. Nó cho phép suy ra khóa mã hóa bằng HKDF-SHA256 có phân tách miền từ Django `SECRET_KEY` khi không cung cấp khóa riêng. Cấu hình này phải được bật rõ bằng `CAMERA_IDENTITY_DERIVE_TEMPLATE_KEY=1`; secret yếu/biết trước hoặc khóa riêng sai định dạng vẫn bị từ chối. **Đổi SECRET_KEY làm khóa suy ra thay đổi và không đọc được mẫu cũ**; không tự xóa hoặc tự thay mẫu khi lỗi giải mã. Nên đặt khóa Fernet riêng được quản lý an toàn trước khi triển khai có dữ liệu thật để tách vòng đời mã hóa khỏi khóa phiên Django.

Mở `/account/camera/` sau đăng nhập để đăng ký/cập nhật mẫu, `/camera/verify/` để thử so khớp. `/camera/health/` chỉ đọc trạng thái cấu hình, không ghi database hoặc chạy inference. Trang thử luôn nêu rõ kết quả chưa cho phép đăng nhập. Không được dùng ảnh demo hoặc camera ảo để tuyên bố đã kiểm chứng Face ID/người thật.

## Điều kiện còn thiếu trước khi phát hành đăng nhập mặt

Cần giải pháp chống trình diện ảnh/video và chèn dữ liệu đã đánh giá, bảo vệ nguồn thu nhận, kiểm thử sai nhận/sai từ chối trên thiết bị thật, phục hồi/xóa dữ liệu và tài nguyên xử lý riêng đã đo. Không thể coi chớp mắt hoặc quay đầu là PAD đã đạt. Bản camera chưa được chủ phần mềm xem và kiểm chứng trên thiết bị thật.
