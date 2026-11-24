# Nhật ký phiên bản

Mỗi lần phát hành ghi: phiên bản, ngày, nội dung thay đổi bằng tiếng Việt dễ hiểu và nhãn bản thử đã được chủ phần mềm duyệt. Quy trình ở [docs/RELEASE_PROCESS.md](docs/RELEASE_PROCESS.md).

## v124 – 24/11/2026

Theo yêu cầu của chủ phần mềm ngày 24/11/2026: "thoát ra khỏi phần mềm thì bắt đăng nhập lại, không cho lưu mật khẩu như các ngân hàng", "làm giống ACB". Áp dụng chỉ đạo ngày 23/11/2026 (hoàn thiện đăng nhập Face ID và cập nhật bản chính, toàn quyền, không cần hỏi lại).

### Đăng nhập và phiên làm việc kiểu app ngân hàng (giống ACB)
- Màn hình đăng nhập mới: thiết bị đã dùng hiện "Xin chào, <họ tên>", chỉ hỏi mật khẩu; nút Face ID nằm cạnh nút Đăng nhập và tự hiện Face ID nếu thiết bị đã bật; có "Đăng nhập tài khoản khác" và "Quên mật khẩu? Liên hệ quản trị viên." Thiết bị chỉ nhớ tên tài khoản, không nhớ mật khẩu.
- Áp dụng cho **mọi tài khoản** (trước đây chỉ phiên Face ID): đóng trình duyệt/app là hết phiên; rời phần mềm quá 1 phút hoặc không thao tác 5 phút thì phải đăng nhập lại bằng Face ID hoặc mật khẩu; nội dung đang nhập dở vẫn giữ. Đang gọi nội bộ thì không khóa.
- Ô mật khẩu không mời trình duyệt lưu hay tự điền (`autocomplete="off"`).
- Sai mật khẩu khi đăng nhập lại tính chung luật 5 lần: nhân viên bị khóa tới khi Admin mở.
- Bật Face ID một chạm ngay trong lời mời sau khi đăng nhập bằng mật khẩu; hướng dẫn iPhone viết lại ("Lưu mã khóa?" → Tiếp tục, không cần vào Cài đặt).
- Thời gian khóa chỉnh được bằng biến môi trường `APP_LOCK_AWAY_SECONDS`, `APP_LOCK_IDLE_SECONDS`; tắt khẩn cấp bằng `APP_LOCK_ENABLED=0`.

### Sửa lỗi
- Màn hình khóa trong trang (có từ v123): nhập sai mật khẩu một lần thì nút gửi bị vô hiệu hóa luôn; nay nhập lại được.
- Mở khóa bằng Face ID không còn bị tính vào hạn mức 5 lần xác nhận mật khẩu mỗi phút; nhiều tab không cùng lúc hỏi Face ID.

## v123 – 23/11/2026

Phát hành theo chỉ đạo của chủ phần mềm ngày 23/11/2026: hoàn thiện phần đang dở và cập nhật bản chính, toàn quyền, không cần hỏi lại; ưu tiên đăng nhập Face ID. Đã lên bản chính (commit `37d9b0a`, 18:59 giờ Việt Nam 23/11/2026) sau khi chạy trên bản thử không lỗi. Nhánh khôi phục Neon: `khoi-phuc-truoc-v123-20261123`. Bản thử từ nay mang nhãn `v124-thu`.

### Đăng nhập bằng Face ID kiểu app ngân hàng
- Trang đăng nhập có "Đăng nhập bằng Face ID"; Face ID không được thì nhập mật khẩu; "Quên mật khẩu? Liên hệ quản trị viên."
- Sau khi đăng nhập bằng mật khẩu, iPhone được mời "Bật Face ID" — bật ngay, không phải nhập lại mật khẩu (trong 10 phút).
- Thiết bị đã bật Face ID: mở phần mềm là Face ID tự hiện ("Xin chào, …"), nhận diện xong vào thẳng; iPhone còn gợi ý tài khoản trên bàn phím.
- Phiên đăng nhập bằng Face ID tự khóa khi rời phần mềm hoặc không dùng quá 5 phút; mở lại bằng Face ID hoặc mật khẩu, nội dung đang nhập dở vẫn giữ. Phiên đăng nhập bằng mật khẩu không bị ảnh hưởng.
- Thêm được phần mềm vào Màn hình chính iPhone như một app (biểu tượng KSNB).


### Trợ lý AI v2
- Trò chuyện AI qua Groq Free tự tra cứu dữ liệu trong phần mềm theo đúng quyền của người hỏi: hàng hóa, tồn kho, thẻ kho, phiếu, việc chờ duyệt, kiểm kê, hàng cho mượn, sai lệch, hướng dẫn. Chỉ đọc; không tạo, sửa hay duyệt.
- Câu trả lời có số liệu kèm đường dẫn tới màn hình nguồn; khi đang tra cứu hiện "Đang tra cứu: …".
- Ghi nhật ký mỗi lần AI tra cứu (người hỏi, thời điểm, công cụ, số dòng); Admin xem trong Quản trị.
- Gỡ phần AI chạy trong trình duyệt (Qwen, khoảng 800 MB tải về), kho mã nhẹ đi khoảng 22 MB.
- Mỗi câu hỏi giữ dưới hạn mức 8.000 token/phút của Groq Free (ngừng tra cứu thêm khi đã dùng nhiều token). Cần Admin dán khóa `GROQ_API_KEY` trên Render thì trò chuyện AI mới chạy.

### Thiết bị đang đăng nhập (mục 4.3)
- Mỗi người xem các thiết bị đang đăng nhập tài khoản mình, đăng xuất từ xa từng thiết bị hoặc tất cả thiết bị khác.
- Admin đăng xuất một nhân viên khỏi mọi thiết bị ngay trong trang sửa nhân viên (khi nghỉ việc, mất máy).

### Quy trình và Nhân sự
- Hai mục chưa có nghiệp vụ chỉ hiện với Admin; nhân viên không còn thấy (câu 12).

## v122 – 15/11/2026

Đã phát hành lên bản chính (commit `ddf4b76`). Chủ phần mềm báo **"Đạt v122-thu, phát hành"** ngày 15/11/2026. Nhánh khôi phục Neon: `khoi-phuc-truoc-v122-20261115`.

- Bản chính hiện số phiên bản đang dùng ở 3 chỗ: dưới tên tài khoản ở menu trái, chân trang mọi màn hình, và trong khung đăng nhập (kể cả trên điện thoại).
- Bản thử hiện số của bản chính cộng 1 kèm "-thu" (quy tắc chủ phần mềm chốt ngày 15/11/2026).

## v121 – 15/11/2026

Đã phát hành lên bản chính (commit `2de2acb`). Chủ phần mềm báo **"Đạt v121-thu2"** ngày 14/11/2026 sau khi thử trên bản thử. Trước khi phát hành đã tạo nhánh khôi phục Neon `khoi-phuc-truoc-v121-20261115`. Bản trước đó (commit `7eb1e8d`) được gọi là `v120`.

### Bản thử và đánh số phiên bản (Đợt 0)

- Thêm biến `APP_ENVIRONMENT` và `APP_VERSION`. Bản thử hiện dải "BẢN THỬ" trên mọi trang, thêm "[THỬ]" vào tiêu đề tab.
- Bản thử chặn cứng Google Drive, email và Groq, kể cả khi lỡ khai báo khóa.
- `/healthz/` trả thêm môi trường và phiên bản; chân trang Admin hiện số phiên bản.
- Lệnh `seed_staging` nạp dữ liệu và tài khoản thử, chỉ chạy được trên bản thử.

### Sửa lỗi và rủi ro an toàn (Đợt 1)

- Đăng nhập bằng mật khẩu: nhân viên sai 5 lần trong 15 phút thì bị khóa đến khi Admin mở khóa (tài khoản Admin tự mở sau 15 phút); sai 20 lần từ cùng một địa chỉ IP thì tạm khóa IP đó 15 phút. Thông báo giống nhau dù tài khoản có tồn tại hay không. Đăng nhập đúng xóa bộ đếm. Admin thấy biểu tượng ổ khóa kèm số tài khoản chờ mở và mở khóa ngay trong trang Quản trị. Passkey và phiên đang đăng nhập không bị ảnh hưởng. Lệnh dọn: `cleanup_login_throttle`.
- Không khai báo `DEBUG` thì mặc định tắt chế độ gỡ lỗi (trước đây ngoài Render sẽ tự bật). Dockerfile đặt `DEBUG=0` và khởi động bằng `start.sh` như Render.
- Gunicorn trên Render chờ tối đa 120 giây mỗi yêu cầu (trước là 30 giây), để nhập Excel lớn và xuất báo cáo không bị cắt.
- Mật khẩu Admin đầu tiên tạo bằng `bootstrap_admin` cần ít nhất 12 ký tự và không trùng tên tài khoản. Chính sách mật khẩu của nhân viên giữ nguyên.
- `/healthz/` trả `unknown` khi thiếu mã commit thay cho nhãn cũ.
- Khung trò chuyện Groq có dòng nhắc không dán dữ liệu khách hàng, giá vốn hay mật khẩu.
- Sửa bài kiểm thử chập chờn của Trợ lý AI; 2 bài chỉ chạy được trên PostgreSQL được đánh dấu rõ khi chạy SQLite.

## Các phiên bản trước

`v120` là commit `7eb1e8d` (đăng nhập passkey), bản chính trước ngày 15/11/2026. Lịch sử chi tiết các bản trước sẽ được viết lại ở Đợt 2.
