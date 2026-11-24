# Bảng nghiệm thu – Đăng nhập giống app ngân hàng ACB (v124-thu)

**Phiên bản thử:** `v124-thu` (bản chính trước đó `v123`) · **Commit:** xem `/healthz/` (`release`) · **Bản thử:** https://kiemsoatnoibo-thu.onrender.com · **Tài khoản thử:** `thu_admin`, `thu_nguoilap`, `thu_nguoiduyet`, `thu_chixem` (mật khẩu bản thử) · **Ngày:** 24/11/2026

Yêu cầu của chủ phần mềm ngày 24/11/2026: "thoát ra khỏi phần mềm thì bắt đăng nhập lại, không cho lưu mật khẩu như các ngân hàng", "làm giống ACB".

## Phần A – Chức năng mới

| STT | Chức năng / thao tác | Cách thử (bấm gì, nhập gì) | Kết quả mong đợi | Kết quả (Đạt / Không đạt) | Ghi chú |
|---|---|---|---|---|---|
| A1 | Lần đầu trên thiết bị | iPhone mở bằng Safari trang đăng nhập | Ô tên đăng nhập + mật khẩu, nút Đăng nhập và biểu tượng Face ID cạnh nhau, "Quên mật khẩu? Liên hệ quản trị viên." | | |
| A2 | Bật Face ID một chạm | Đăng nhập `thu_admin` bằng mật khẩu → lời mời "Đăng nhập nhanh bằng Face ID?" → **Bật Face ID** → iPhone hỏi "Lưu mã khóa?" → Tiếp tục, nhìn màn hình | Báo "Đã bật Face ID cho thiết bị này"; không phải nhập lại mật khẩu | | |
| A3 | Rời phần mềm | Chuyển sang app khác hơn 1 phút rồi quay lại | Màn hình "Xin chào, Admin (thử)" + "Bạn vừa rời khỏi phần mềm…", Face ID tự hiện; nhận diện xong quay lại đúng trang, chữ đang gõ dở còn nguyên | | |
| A4 | Rời nhanh | Chuyển app khác dưới 1 phút rồi quay lại | Vẫn dùng tiếp, không hỏi đăng nhập | | |
| A5 | Để yên 5 phút | Mở một trang, không chạm 5 phút | "Phiên đăng nhập đã hết hạn do không thao tác trong 5 phút…" | | |
| A6 | Đóng app mở lại | Vuốt tắt Safari/app KSNB, mở lại | Trang đăng nhập "Xin chào, …" chỉ còn ô mật khẩu + Face ID; Face ID tự hiện | | |
| A7 | Face ID không được | Bấm Hủy ở Face ID | Nhập mật khẩu ngay ô bên dưới, đăng nhập bình thường | | |
| A8 | Tài khoản không có Face ID | `thu_nguoilap` (chưa bật Face ID) để yên 5 phút | Màn hình đăng nhập lại chỉ có ô mật khẩu, không có biểu tượng Face ID | | |
| A9 | Sai mật khẩu khi đăng nhập lại | Nhập sai 1 lần rồi nhập đúng | Báo "Mật khẩu chưa đúng…"; lần sau đúng thì vào lại được (nút không bị đứng) | | |
| A10 | Sai 5 lần | `thu_nguoilap` nhập sai 5 lần ở màn hình đăng nhập lại | Báo khóa, liên hệ quản trị viên; Admin thấy ổ khóa và mở được | | |
| A11 | Đăng nhập tài khoản khác | Ở màn hình "Xin chào" bấm **Đăng nhập tài khoản khác** | Hiện lại ô tên đăng nhập trống; thiết bị quên tên cũ | | |
| A12 | Không lưu mật khẩu | Đăng nhập bằng mật khẩu | Phần mềm không tự điền mật khẩu. Nếu Safari vẫn hỏi "Lưu mật khẩu?" bấm "Không bao giờ cho trang web này" | | |
| A13 | Nhiều tab | Máy tính mở 2 tab phần mềm, dùng qua lại | Chuyển tab không bị hỏi đăng nhập; khi đã khóa thì đăng nhập lại ở 1 tab là tab kia cũng mở | | |
| A14 | Đang gọi | Gọi nội bộ, để yên hơn 5 phút | Không bị khóa giữa cuộc gọi | | |

## Phần B – Hồi quy

| STT | Chức năng / thao tác | Cách thử | Kết quả mong đợi | Kết quả | Ghi chú |
|---|---|---|---|---|---|
| B1 | Lập phiếu, duyệt phiếu, tồn kho | Làm một phiếu nhập và duyệt | Như trước | | |
| B2 | Chat, thông báo | Gửi tin nhắn giữa 2 tài khoản | Như trước; khi đang khóa thì sau khi đăng nhập lại chat chạy tiếp | | |
| B3 | Trợ lý AI | Hỏi một câu tra cứu | Như trước | | |
| B4 | Khóa đăng nhập ở trang đăng nhập (v121) | Sai mật khẩu 5 lần ở trang đăng nhập | Bị khóa, Admin mở được | | |
| B5 | Thiết bị đang đăng nhập (v123) | Xem và đăng xuất từ xa | Như trước | | |
| B6 | Dải BẢN THỬ, phiên bản | Mở vài trang, `/healthz/` | "BẢN THỬ – v124-thu"; `version` = `v124-thu` | | |

## Bằng chứng phía phát triển

- Kiểm thử tự động PostgreSQL toàn bộ: 616/616 đạt, gồm bài mới: phiên mật khẩu cũng khóa và mở bằng mật khẩu, sai 5 lần khi đăng nhập lại bị khóa chờ Admin, cookie phiên hết khi đóng trình duyệt, ô mật khẩu `autocomplete="off"`, tắt được bằng `APP_LOCK_ENABLED=0`, thời gian khóa có mức tối thiểu, mở bằng Face ID không bị tính như xác nhận mật khẩu.
- Chạy thử trên máy với database thử riêng (`dhd_staging_local`, tài khoản `thu_admin`, `thu_nguoilap`), Chromium mô phỏng iPhone 13 có Face ID giả lập: 11 ảnh từ lần đầu đăng nhập tới đăng nhập lại sau 90 giây và sau 5 phút để yên.
- Giới hạn: Face ID thật, "Lưu mật khẩu?" của Safari và việc iPhone tự hỏi Face ID khi vừa mở chỉ kiểm được trên iPhone thật.
