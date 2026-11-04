# DHD Connect — nhắn tin nội bộ

Phạm vi chủ phần mềm duyệt ngày 03/11/2026: chat cá nhân và nhóm, chữ/ảnh/PDF, nhiều emoji/sticker, gọi thoại/video cá nhân và nhóm tối đa 6 người. Chủ phần mềm yêu cầu hoàn thiện, kiểm thử và phát hành lên bản chính; không được ảnh hưởng chức năng khác.

## Quyền và riêng tư

- `chat_use`: nhắn tin, xem nội dung và ảnh/PDF của hội thoại mình tham gia.
- `chat_groups`: tạo nhóm, quản lý nhóm mình làm trưởng nhóm; bao gồm quyền dùng chat.
- `chat_call`: gọi hoặc nhận cuộc gọi trong hội thoại tham gia; bao gồm quyền dùng chat.
- Admin quản lý các quyền trên ở Tài khoản & phân quyền. Không tự cấp quyền cho tài khoản cũ. Admin không đọc/nhắn/tải tệp/tham gia gọi trong hội thoại mà mình không là thành viên. App không đăng ký model vào Django Admin.
- Nhóm tối đa 30 thành viên; chỉ trưởng nhóm đổi tên, thêm/mời rời hoặc chuyển trưởng nhóm. Muốn rời vai trò trưởng nhóm phải chuyển cho thành viên đã được cấp quyền tạo/quản lý nhóm.
- Thành viên mới chỉ xem tin từ lúc tham gia; trích dẫn và tệp cũ không được chia sẻ theo. Rời nhóm hoặc bị mời rời sẽ mất truy cập API, ảnh/PDF và cuộc gọi; thêm lại không mở toàn bộ lịch sử cũ.
- Việc kiểm tra quyền áp dụng tại máy chủ cho từng request, kể cả Admin và URL tệp trực tiếp. Không tuyên bố đây là ứng dụng mã hóa đầu cuối: dữ liệu tin nhắn nằm trong PostgreSQL; người quản trị hạ tầng/database và chủ Drive có quyền kỹ thuật trên dữ liệu lưu trữ. Không hỗ trợ xóa dấu vết từ ảnh chụp hoặc bản sao người nhận đã tải.

## Sử dụng

Vào Nhắn tin → biểu tượng tạo mới → chọn đồng nghiệp. Bật Tạo nhóm để chọn nhiều người và đặt tên. Thêm ảnh/PDF bằng dấu cộng; mỗi tin tối đa 3 tệp, tổng 8 MB. Ảnh được xác minh, bỏ metadata và chuẩn hóa JPEG; PDF phải hợp lệ, không khóa mật khẩu, tối đa 200 trang. Tệp online lưu trong `NhanTinNoiBo/năm/HoiThoai-UUID` dưới thư mục Drive đã kết nối; không tạo chia sẻ công khai và không lưu binary vào database production.

Tin chữ tối đa 4.000 ký tự. Enter gửi, Shift+Enter xuống dòng; nút Gửi vẫn dùng được trên điện thoại. Có trả lời, biểu cảm, tìm trong hội thoại, ảnh/PDF riêng, trạng thái đã xem theo mốc đã tải và công bố đang soạn. Bộ chọn có 3.781 emoji Unicode, 36 sticker hình gốc và 72 biến thể lời nhắn tiếng Việt. Tìm kiếm/chủ đề/gần đây được tải khi mở, không gọi website bên ngoài để hiển thị.

Bản nháp không được tự lưu lâu dài lên thiết bị. Khi gửi lỗi, giữ nguyên nội dung/tệp đang soạn và dùng mã gửi để chống nhân đôi khi bấm lại; thay nội dung sẽ tạo lần gửi khác. Trang hỏi trước khi rời nếu đang có nội dung chưa gửi. Bộ chọn gần đây chỉ lưu mã biểu cảm theo từng tài khoản, không lưu nội dung hội thoại vào localStorage.

## Gọi thoại và video

Bấm biểu tượng điện thoại/camera trong hội thoại. Trình duyệt hỏi quyền micro/camera; bên nhận mở lời mời và bấm Tham gia. Tối đa 6 người cùng lúc; có tắt/mở micro và camera, từ chối, rời/kết thúc, lịch sử và hết hạn khi không có người nghe. Không tự bật camera và không ghi âm/ghi hình cuộc gọi.

Mỗi tài khoản chỉ tham gia một cuộc gọi tại một thời điểm; thiết bị/cửa sổ thứ hai không chiếm phiên đang gọi. Rời nhóm hoặc mất quyền gọi dừng request và đóng media trên client ở lần kiểm tra tiếp theo. Thông tin SDP/ICE chỉ đi giữa các bên đang tham gia, có giới hạn dung lượng/tần suất và hết hạn; kết thúc xóa tín hiệu tạm.

**Giới hạn cần hiểu đúng:** đây là web app; cần mở trang và còn phiên đăng nhập để nhận lời mời, chưa phải ứng dụng nền/điện thoại native. Máy phải có micro/camera và dùng HTTPS (localhost được phép khi thử). Kết nối trực tiếp có thể không qua được NAT/tường lửa của một số mạng. Triển khai ổn định giữa nhiều mạng cần TURN, không thể bảo đảm bằng STUN công khai.

Ứng dụng hỗ trợ coturn REST credentials qua `CHAT_TURN_URLS` (danh sách `turn:`/`turns:` phân cách dấu phẩy) và `CHAT_TURN_SECRET`. Máy chủ cấp credential ngắn hạn, không gửi secret cho trình duyệt. Không tự đăng ký dịch vụ tính phí; không dùng relay công cộng có mật khẩu chia sẻ làm hạ tầng công ty. Khi chưa có TURN, giao diện gọi có thể hoạt động trên các mạng nối trực tiếp được và báo rõ khi không kết nối được. Không ghi vào tài liệu rằng đã kiểm chứng hai mạng thực tế khi mới thử nhiều trình duyệt cùng máy.

## Bảo trì và kiểm tra

`chat/` chứa model/quyền, dịch vụ ghi, selector đọc, signaling, API và kiểm thử; `static/chat*.js`, `assets/styles/chat.css`, `templates/chat/` chứa giao diện. Không có ghi sổ, thay tồn hoặc sửa hồ sơ sai lệch. Tích hợp hiện có chỉ thêm grant, namespace URL/middleware, menu/badge, nhánh thư mục Drive, CSS và readiness/snapshot của bản phát hành.

Mỗi room được khóa khi ghi, có sequence và version; POST gửi, call và signal dùng nonce chống lặp. Nội dung cũ phân trang, tệp có cursor kể cả nhiều tệp cùng tin. Poll có backoff và bản tóm tắt nhẹ, không tải lại lịch sử khi version không đổi. Tạm ngừng cập nhật khi trang ẩn 5 phút hoặc không tương tác 15 phút (ngoại trừ đang gọi), tự tiếp tục khi trở lại; đây không phải nhận push nền. Media WebRTC đi giữa các thiết bị; Render không chuyển tiếp video.

Migration chỉ tạo bảng `chat_*`. Namespace snapshot phát hành là `dhd_backup_chat_0002`, readiness thêm chat 0002 và giữ inventory 0018/deviations 0005. Rollback code không tự xóa bảng hoặc tin đã có. Không chạy fixture, tài khoản demo hay kiểm thử vào database thật.

Chạy `ruff`, kiểm tra JS/CSS, Django check, migration check, collectstatic, toàn bộ test PostgreSQL và thử nhiều tài khoản/trình duyệt trước phát hành. Xác minh `/healthz/` đúng merge commit và snapshot ready sau deploy. Xem `CHAT_RESEARCH.md` về nguồn tham khảo và giới hạn kết luận.

## Bằng chứng trước phát hành

- Bộ kiểm thử đầy đủ đã đạt 390 bài trên PostgreSQL 17, gồm hồi quy và diễn tập giữ nguyên password/quyền/danh mục/tồn. Bộ chat 25 bài đã chạy riêng và đóng sạch các kết nối thử đồng thời. CI phải chạy lại toàn bộ trên đúng commit cuối.
- Chromium với tài khoản giả lập riêng: chữ/trả lời, emoji/sticker, ảnh/PDF và tải lại, mất mạng/giữ draft/thử gửi lại không nhân đôi, thoại, video hai người và video nhóm ba người, tắt micro/camera, kết thúc các bên, bề rộng 390px và giao diện tối.
- Môi trường thử chặn đường WebRTC trực tiếp. Dùng coturn TCP chỉ lắng nghe localhost và REST credentials ngắn hạn để thử media thực giữa các trình duyệt; không dùng dịch vụ relay công cộng hoặc secret thật. Giới hạn 6 người được kiểm thử phía server. Chưa thử hai mạng/thiết bị vật lý độc lập và chưa cấu hình TURN thật cho production.
- Đã kiểm tra lời mời gọi không modal, không cướp focus và không chặn soạn biểu mẫu hàng hóa; biểu mẫu không được lưu trong thử nghiệm.
- Diff nghiệp vụ kho, schema inventory, dịch vụ kho, đăng nhập và toàn bộ app sai lệch giữ nguyên. Chỉ một kỳ vọng danh sách menu cập nhật để có thêm phân hệ Nhắn tin; các kiểm tra tách quyền/menu cũ vẫn được giữ.
- Không đưa tài khoản, hội thoại, ảnh hoặc PDF DEMO vào migration/production. Sau phát hành chỉ thăm dò health, login, static và route bảo vệ nếu không có tài khoản công ty được cấp để kiểm tra.
