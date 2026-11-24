# Passkey: Face ID / Windows Hello

## Đăng nhập kiểu app ngân hàng – giống ACB (cập nhật 24/11/2026, bản v124)

Chủ phần mềm yêu cầu (23–24/11/2026): đăng nhập bằng Face ID như app ngân hàng; Face ID không được thì nhập mật khẩu; quên mật khẩu thì liên hệ quản trị viên; **thoát khỏi phần mềm thì phải đăng nhập lại, không cho lưu mật khẩu**, "làm giống ACB". Giao diện dùng chữ "Face ID" (Windows Hello / vân tay trên máy khác), không bắt người dùng hiểu "passkey".

1. **Màn hình đăng nhập:** thiết bị đã đăng nhập trước đây hiện "Xin chào, <họ tên>" (vòng tròn chữ cái đầu của tên), chỉ còn ô mật khẩu, nút **Đăng nhập** và nút biểu tượng **Face ID** cạnh nhau, "Đăng nhập tài khoản khác", "Quên mật khẩu? Liên hệ quản trị viên." Thiết bị chỉ nhớ tên tài khoản (`localStorage` `dhd-last-user`), **không bao giờ nhớ mật khẩu**. Thiết bị đã bật Face ID cho tài khoản đó thì Face ID tự hiện ngay khi mở. Thiết bị mới hoặc sau "Đăng nhập tài khoản khác" thì hiện đủ ô tên đăng nhập và mật khẩu.
2. **Bật Face ID:** sau khi đăng nhập (hoặc đăng nhập lại) bằng mật khẩu, lời mời "Đăng nhập nhanh bằng Face ID?" có nút **Bật Face ID** bật ngay tại chỗ (iPhone hỏi "Lưu mã khóa?" → Tiếp tục), không phải nhập lại mật khẩu trong 10 phút (`RECENT_PASSWORD_LOGIN`). Trang Tài khoản → Face ID vẫn dùng được như trước.
3. **Phiên làm việc (mọi tài khoản, không chỉ Face ID):**
   - Đóng trình duyệt / đóng app là hết phiên (`SESSION_EXPIRE_AT_BROWSER_CLOSE=True`); máy chủ giữ phiên tối đa 12 giờ (`SESSION_COOKIE_AGE`).
   - Rời phần mềm (chuyển app khác, khóa màn hình điện thoại, không tab nào của phần mềm đang hiện) quá **60 giây** → quay lại phải đăng nhập lại.
   - Không chạm / gõ / cuộn quá **5 phút** → "Phiên đăng nhập đã hết hạn do không thao tác trong 5 phút".
   - Máy chủ không nhận yêu cầu nào quá **120 giây** (app bị đóng, máy tắt) → máy chủ tự khóa phiên.
   - Màn hình "đăng nhập lại" phủ lên trang hiện tại, nên **nội dung đang nhập dở vẫn giữ**; đăng nhập lại bằng Face ID (nếu thiết bị đã bật) hoặc mật khẩu. Các tab khác của phần mềm khóa/mở theo cùng lúc. Đang trong cuộc gọi nội bộ thì không khóa.
   - Khi đang khóa, máy chủ trả trang `/unlock/` cho trang thường và mã 423 cho lời gọi dữ liệu (chat, trợ lý tự thử lại sau khi đăng nhập lại).
   - Sai mật khẩu ở màn hình đăng nhập lại **tính chung luật 5 lần** của trang đăng nhập (`login_guard`): nhân viên sai 5 lần bị khóa tới khi Admin mở; tài khoản Admin tự mở sau 15 phút.
4. **Không lưu / không tự điền mật khẩu:** mọi ô mật khẩu đăng nhập, đăng nhập lại và trang Face ID đặt `autocomplete="off"`. Giới hạn: Safari/Chrome vẫn có thể tự hỏi "Lưu mật khẩu?" (trình duyệt quyết định, trang web không chặn tuyệt đối được); hãy bấm **"Không bao giờ cho trang web này"**. Dùng Face ID thì không cần gõ mật khẩu.
5. **Cài như app:** Safari → Chia sẻ → **Thêm vào Màn hình chính** (biểu tượng KSNB, `static/manifest.json`, `static/icons/`). Mở từ biểu tượng chạy toàn màn hình như app.

| Biến môi trường | Mặc định | Ý nghĩa |
| --- | --- | --- |
| `APP_LOCK_ENABLED` | `1` | `0` tắt hẳn việc khóa phiên (khẩn cấp). Đóng trình duyệt vẫn hết phiên. |
| `APP_LOCK_AWAY_SECONDS` | `60` | Rời phần mềm bao lâu thì phải đăng nhập lại (tối thiểu 15). |
| `APP_LOCK_IDLE_SECONDS` | `300` | Không thao tác bao lâu thì hết phiên (tối thiểu 60). |
| `APP_LOCK_SERVER_GAP_SECONDS` | `120` | Máy chủ không nhận yêu cầu bao lâu thì tự khóa (tối thiểu 90, không nhỏ hơn thời gian rời phần mềm). |

Face ID do iPhone tự xác minh; phần mềm không mở camera, không lưu ảnh khuôn mặt. Mỗi thiết bị bật riêng. Mã: `passkeys/services.py` (`app_lock_applies`, `lock_timing`, `unlock_with_password`), `passkeys/middleware.py` (`AppLockMiddleware`), `static/app-lock.js`, `static/login.js`, `static/passkeys.js`, `templates/passkeys/includes/unlock_card.html`. Kiểm thử: `passkeys/tests/test_app_lock.py`, `passkeys/tests/test_faceid_flow.py`; đã chạy trọn vòng bằng Chromium mô phỏng iPhone 13 có Face ID giả lập (lần đầu → bật Face ID một chạm → rời app 90 giây → đăng nhập lại bằng Face ID, giữ chữ đang gõ → đóng app mở lại hiện "Xin chào" → nhân viên không Face ID để yên 5 phút → sai/đúng mật khẩu).


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
