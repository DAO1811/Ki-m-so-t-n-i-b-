# Giới hạn đăng nhập sai mật khẩu

Phân hệ `login_guard` (bảng riêng `login_guard_loginthrottle`) bảo vệ trang `/login/` khỏi dò mật khẩu. Chính sách mật khẩu tự do của nhân viên giữ nguyên.

| Ngưỡng | Mặc định | Biến cấu hình (trong `config/settings.py`) |
|---|---|---|
| Sai theo tài khoản nhân viên | 5 lần trong 15 phút → **khóa đến khi Admin mở** | `LOGIN_USER_MAX_FAILURES`, `LOGIN_WINDOW_SECONDS` |
| Sai theo tài khoản Admin | 5 lần trong 15 phút → khóa 15 phút rồi tự mở | `LOGIN_LOCK_SECONDS` |
| Sai theo địa chỉ IP | 20 lần trong 15 phút → khóa 15 phút | `LOGIN_IP_MAX_FAILURES` |

- Ngưỡng IP cao hơn vì nhiều nhân viên trong cùng văn phòng có thể dùng chung một IP công cộng.
- Bộ đếm lưu trong database nên đúng với cả 2 worker Gunicorn. Không lưu mật khẩu; chỉ lưu tên tài khoản đã nhập (chữ thường) hoặc IP.
- Chủ phần mềm chốt ngày 14/11/2026: nhân viên sai 5 lần phải liên hệ Admin. Tài khoản Admin tự mở sau 15 phút vì nếu mọi Admin đều bị khóa vĩnh viễn thì không còn ai mở được; Admin vẫn đăng nhập được bằng passkey.
- Mọi trường hợp khóa đều hiện cùng một thông báo: "Đăng nhập đã bị khóa do nhập sai mật khẩu nhiều lần. Vui lòng liên hệ quản trị viên để mở khóa." Tên không tồn tại cũng bị khóa y như tài khoản thật, nên không lộ tài khoản nào có thật hay là Admin. Khi đang khóa, phần mềm không kiểm tra mật khẩu, kể cả mật khẩu đúng.
- Admin thấy biểu tượng ổ khóa có số đếm trên thanh trên cùng khi có tài khoản chờ mở khóa.
- Đăng nhập đúng xóa bộ đếm của tài khoản. Passkey và các phiên đang đăng nhập không bị ảnh hưởng.
- Admin mở khóa: bấm biểu tượng ổ khóa (hoặc **Quản trị → Bảo vệ đăng nhập → Khóa tạm đăng nhập**), chọn dòng, chọn hành động **"Mở khóa các dòng đã chọn"**. Nếu nhân viên quên mật khẩu, đặt lại tại Quản lý nhân viên → Sửa.
- Lệnh dọn bộ đếm cũ: `python manage.py cleanup_login_throttle --days 1`. Lệnh giữ lại khóa của tài khoản có thật cho đến khi Admin mở; khóa của tên không tồn tại bị xóa.

## Địa chỉ IP sau proxy

`LOGIN_TRUSTED_PROXY_HOPS` (biến môi trường) là số proxy tin cậy đứng trước ứng dụng. Trên Render mặc định là `1`: lấy địa chỉ **cuối cùng** trong `X-Forwarded-For` (do proxy của Render thêm vào); các địa chỉ bên trái có thể do trình duyệt tự ghi nên không tin. Ngoài Render mặc định `0`: dùng `REMOTE_ADDR`.

Cần kiểm chứng trên bản thử: đăng nhập sai một lần từ 2 mạng khác nhau (Wi-Fi và 4G), mở Quản trị → Khóa tạm đăng nhập và xem 2 dòng IP khác nhau, đúng IP công cộng của từng mạng. Nếu mọi dòng cùng một IP lạ (IP nội bộ của Render), đổi `LOGIN_TRUSTED_PROXY_HOPS` trước khi phát hành.
