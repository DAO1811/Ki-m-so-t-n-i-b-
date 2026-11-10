# Passkey: Face ID / Windows Hello

Passkey bổ sung cách đăng nhập cho tài khoản hiện có. Thiết bị/hệ điều hành quyết định dùng khuôn mặt, vân tay hoặc PIN; website không bắt buộc chỉ dùng khuôn mặt, không mở camera và không lưu ảnh khuôn mặt. Máy chủ lưu khóa công khai cùng thông tin quản lý passkey; khóa bí mật do thiết bị hoặc trình quản lý passkey giữ. Chức năng không gọi API AI hay API xác thực trả phí.

## Cấu hình và cài đặt

Cài `requirements.txt` và chạy migration theo quy trình hiện có. Phân hệ dùng bảng `passkeys_*` riêng. Chỉ phát hành đúng commit sau khi chủ phần mềm đã xem bản chạy thử và duyệt theo [quy trình phát hành](RELEASE_PROCESS.md).

| Biến môi trường | Ý nghĩa và giá trị mặc định |
| --- | --- |
| `PASSKEY_ENABLED` | `1` để bật; đặt `0` để ẩn điểm đăng nhập/đăng ký và ngừng các thao tác passkey. Đăng nhập bằng mật khẩu vẫn dùng được. |
| `PASSKEY_RP_ID` | Hostname tin cậy, không có giao thức, cổng hoặc đường dẫn. Mặc định lấy `RENDER_EXTERNAL_HOSTNAME`; khi phát triển không có hostname Render thì dùng `localhost`. Production ngoài Render cần khai báo rõ. |
| `PASSKEY_ORIGIN` | Origin chính xác gồm giao thức, hostname và cổng nếu có. Production mặc định `https://` + RP ID; phát triển mặc định `http://localhost`. Không thêm đường dẫn, query hoặc fragment. |

Render production dùng `DEBUG=0`; hostname mặc định lấy từ biến do môi trường triển khai cung cấp, không lấy từ HTTP Host do trình duyệt gửi. Với tên miền riêng, đặt đồng thời `PASSKEY_RP_ID=ksnb.example.com` và `PASSKEY_ORIGIN=https://ksnb.example.com`, rồi cấu hình `ALLOWED_HOSTS` và `CSRF_TRUSTED_ORIGINS` tương ứng. Không dùng wildcard cho RP ID. Hãy mở đúng hostname đã cấu hình; địa chỉ khác bị từ chối dù cũng trỏ về ứng dụng.

Passkey cần HTTPS và trình duyệt/thiết bị có WebAuthn, xác minh người dùng và passkey lưu được trên thiết bị. Ngoại lệ phát triển là `http://localhost` khi `DEBUG=1`. Nếu cấu hình không hợp lệ, trình duyệt không hỗ trợ hoặc người dùng hủy xác minh, tiếp tục dùng biểu mẫu mật khẩu hiện có.

## Chạy thử riêng trên localhost

Dùng database, tài khoản và tệp thử riêng; không kết nối database công ty, Drive hoặc email thật. Ví dụ cấu hình cho cổng 8000:

```bash
export DEBUG=1
export DATABASE_URL=sqlite:////tmp/ksnb-passkey-preview.sqlite3
export PRIVATE_MEDIA_PROVIDER=database
export PASSKEY_RP_ID=localhost
export PASSKEY_ORIGIN=http://localhost:8000
python manage.py migrate
python manage.py createsuperuser
python manage.py runserver 127.0.0.1:8000
```

Mở `http://localhost:8000/login/`, không đổi thành `127.0.0.1`. Đổi cổng chạy thử phải đổi `PASSKEY_ORIGIN` tương ứng; RP ID vẫn là `localhost`. Localhost chỉ dùng trên máy đang chạy server, không phải đường dẫn xem thử có thể gửi cho chủ phần mềm truy cập từ xa. Bản thử qua một hostname HTTPS riêng cần database riêng và cấu hình RP ID/origin đúng hostname đó.

## Đăng ký, đăng nhập và thu hồi

1. Đăng nhập bằng tài khoản hiện có, mở **Face ID / Windows Hello** trong nhóm quản trị hệ thống hoặc `/account/passkeys/`.
2. Đặt tên dễ nhận biết, nhập **mật khẩu hiện tại**, chọn **Thêm passkey** rồi làm theo hướng dẫn của hệ điều hành. Mỗi tài khoản có tối đa 10 passkey; người dùng chỉ quản lý passkey của chính mình.
3. Khi đăng xuất, chọn **Đăng nhập bằng passkey** trên trang đăng nhập và xác minh trên thiết bị. Quyền nghiệp vụ và phạm vi kho vẫn được kiểm tra sau đăng nhập như trước.
4. Để thu hồi, mở **Gỡ passkey** ở đúng mục và xác nhận bằng mật khẩu hiện tại. Passkey bị thu hồi không đăng nhập được nữa; phiên đã đăng nhập bằng passkey đó bị yêu cầu đăng nhập lại ở yêu cầu tiếp theo. Phiên đăng nhập bằng mật khẩu không bị thu hồi bởi thao tác này.

Nếu mất thiết bị hoặc không dùng được passkey, đăng nhập bằng mật khẩu từ thiết bị khác, gỡ passkey bị mất rồi đăng ký passkey mới. Nếu quên mật khẩu, liên hệ quản trị viên theo quy trình khôi phục tài khoản hiện có; không có cơ chế bỏ qua xác minh để lấy lại passkey. Đổi mật khẩu không thay cho việc gỡ passkey bị mất. Việc gỡ tại website không tự xóa mục đã lưu trong trình quản lý passkey của thiết bị.

Passkey gắn với RP ID của tên miền. Khi đổi hostname/RP ID, người dùng cần dùng mật khẩu để đăng ký lại trên tên miền mới; không coi passkey đã tạo cho localhost hoặc hostname xem thử là passkey của production. Việc đồng bộ passkey giữa thiết bị phụ thuộc hệ điều hành/trình quản lý passkey của người dùng.

## Vận hành và phạm vi kiểm chứng

`python manage.py cleanup_passkeys` dọn yêu cầu xác minh và bộ đếm giới hạn đã hết hạn; không xóa passkey đã đăng ký hoặc dữ liệu nghiệp vụ. Sao lưu/khôi phục database theo quy trình hiện có. Tắt `PASSKEY_ENABLED` không xóa passkey đã lưu.

Kiểm thử tự động dùng chữ ký WebAuthn và trình xác thực ảo; kiểm tra trình duyệt dùng trình xác thực WebAuthn ảo của Chrome. Các phép thử này kiểm tra luồng ứng dụng, không chứng minh Face ID hoặc Windows Hello đã hoạt động trên phần cứng thật. Chưa kiểm tra thiết bị Face ID/Windows Hello thật hoặc hiệu năng trên máy Windows RAM 8 GB. Trước khi xác nhận tương thích cho một thiết bị cụ thể, cần thử trên thiết bị đó; ảnh/video chỉ được ghi là bằng chứng từ bản đang chạy, kèm commit và dữ liệu thử.
