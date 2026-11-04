**Bổ sung ngày 04/11/2026:** chủ phần mềm đã đồng ý Groq Free cho trò chuyện nhiều lượt và yêu cầu cập nhật bản chính. Xem [cấu hình, quota và dữ liệu](GROQ_FREE_CHAT.md). Phần tra cứu trực tiếp bên dưới giữ nguyên; mô hình Qwen trên thiết bị vẫn là lựa chọn riêng.

# Trợ lý trong màn hình làm việc

## Bản sửa tốc độ và kiến thức ngày 04/11/2026 — chờ xem thử

Chủ phần mềm phản ánh mô hình xử lý chậm và câu trả lời chưa bám đủ công việc. Bản này ưu tiên **câu trả lời có căn cứ trước**, không đợi mô hình xử lý và không mở thêm quyền đọc dữ liệu.

### Hỏi và tra cứu

- Khung trợ lý mở ngay tại trang làm việc, không khóa biểu mẫu hoặc đọc ô chưa lưu. Nút ở thanh công cụ, không che nút lưu phiếu.
- `knowledge.py` giữ các hướng dẫn theo tác vụ có bằng chứng mã nguồn kèm theo: trả mượn, ba loại import Excel, QR cố định, ảnh, hóa đơn từng lần nhập, ngày nghiệp vụ, duyệt, phiếu đã ghi sổ, kiểm kê, tài khoản, sai lệch, Drive, lưu trữ và chat. `guides.py` giữ hướng dẫn trang. Không lấy quy trình chỉ mới đề xuất làm hướng dẫn chức năng đã có.
- Câu hỏi về chức năng khác trang đang mở vẫn tìm theo tác vụ. Câu chưa đủ rõ được hỏi lại; không dùng vài dòng tồn bất kỳ để thay câu trả lời.
- Câu hỏi số liệu dùng `data.py`: mã/tên hàng, tồn, tổng giá trị, số lượng tách theo đơn vị, mức thấp/hết tồn, phiếu theo loại/trạng thái/ngày/kho, lý do tài khoản chưa đủ điều kiện duyệt một phiếu, mã/trạng thái sai lệch, phiên kiểm kê và kho được phép xem. Kết quả tổng được tính trong SQL trên toàn bộ bộ lọc, không lấy tổng của 8 dòng hiển thị. Hàng không có dòng Balance chưa được tự tính là tồn 0; lịch sử tồn phải đối chiếu Thẻ kho.
- Tồn sở hữu không gộp hàng mượn tạm hoặc đang chuyển. Không cộng số lượng khác đơn vị. Tra cứu lịch sử chưa hỗ trợ trong khung thì nói rõ, không thay bằng tồn hiện tại.
- Ngày phiếu hỗ trợ hôm nay, hôm qua, tháng này, ngày `dd/mm/yyyy` hoặc khoảng tối đa 366 ngày. Ngày này là ngày nghiệp vụ, không phải ngày hóa đơn. Số phiếu chính xác ưu tiên hơn ngữ cảnh trang.
- Hỏi tiếp về kết quả dùng token ngữ cảnh có chữ ký, hạn 15 phút, gắn với tài khoản/trang/kho; không phải quyền truy cập. Mỗi lần hỏi đọc lại quyền và dữ liệu hiện hành. Token chỉ giữ bộ lọc, không giữ câu trả lời/số liệu, không đưa toàn bộ hội thoại vào mô hình. Đổi kho/trang, hết hạn hoặc token sai thì không sử dụng tiếp ngữ cảnh cũ.
- Mẫu nhắc bổ sung chứng từ, kiểm tra mã/số lượng/đơn giá, duyệt và kiểm kê có sẵn, ghi rõ là mẫu tham khảo chưa gửi. Không giả làm văn bản đã gửi hoặc đã được duyệt.

Đây là tra cứu và hướng dẫn có cấu trúc, không phải một mô hình hiểu mọi câu hỏi như dịch vụ ChatGPT. Phạm vi trả lời được mở rộng theo các bộ đọc dữ liệu và hướng dẫn đã kiểm chứng; chưa có quyền đọc tùy ý database, đọc tệp, chat riêng, nhân sự hoặc toàn bộ nội dung điều tra. Không tuyên bố đã "học toàn bộ database".

### Phản hồi và tốc độ

Ngay khi gửi, giao diện hiện trạng thái đang đối chiếu. Kết quả máy chủ được hiển thị trực tiếp, không chờ tải mô hình, không chờ mô hình diễn đạt lại, kể cả khi mô hình đã bật. Sau 3 giây chưa có kết quả, báo máy chủ chậm/khởi động; không dựng câu trả lời hoặc dùng số liệu cũ. Hủy/đứt mạng/403 vẫn giữ câu hỏi và cho thử lại.

Không có API suy luận bên ngoài trong đường tra cứu. Kiến thức là mã nguồn nạp sẵn trong tiến trình; dữ liệu nghiệp vụ được truy vấn mới mỗi lần, không dùng cache chung giữa người dùng. Kết quả API `private, no-store`. `elapsed_ms` đo thời gian xử lý bên trong view, không gồm thời gian mạng, middleware hoặc máy chủ khởi động. Tốc độ đo ở môi trường thử không phải cam kết tốc độ production: Render miễn phí có khởi động nguội, Neon/mạng có độ trễ.

### Soạn nâng cao, tùy chọn

Nút **Soạn nâng cao → Tải và bật AI** giữ lựa chọn Qwen2.5 0.5B q4 chạy một luồng CPU/WebAssembly trong worker. Lần đầu tải khoảng 800 MB; không cần GPU hoặc cài Ollama. Không có phí API và không có fallback trả phí.

Sau khi bật, mô hình **không tự xử lý mọi câu hỏi**. Chỉ khi bấm **Diễn đạt thêm bằng AI (tùy chọn)** dưới một hướng dẫn/mẫu đã trả, mới sinh thêm đoạn văn tách riêng. Câu trả lời gốc không bị thay thế. Số liệu trực tiếp không có nút diễn đạt lại. Gửi câu hỏi mới vẫn được; nếu đang sinh văn bản, dừng worker trước khi tra câu mới. Nút Dừng/Tắt AI giải phóng worker. Soạn thêm quá 20 giây thì dừng và giữ câu trả lời gốc.

Chất lượng mô hình nhỏ và tốc độ phụ thuộc thiết bị; chưa kiểm chứng trực tiếp trên máy Windows RAM 8 GB của chủ phần mềm. Không cam kết ngang ChatGPT. Câu hỏi gửi tới máy chủ phần mềm để tra cứu theo quyền; suy luận nâng cao ở thiết bị. Máy chủ tải mô hình công khai không nhận câu hỏi hoặc dữ liệu nghiệp vụ. Lịch sử chỉ ở bộ nhớ trang, không lưu database/localStorage. Cache API chỉ cache mô hình công khai.

## Phân quyền và giới hạn thay đổi

App riêng `ai_assistant/`, không có models/migrations/bảng mới. Quyền `assistant_use` giữ nguyên: Admin có toàn quyền chức năng, tài khoản khác phải được cấp rõ; quyền trợ lý không cấp quyền kho/danh mục/phiếu. Không đổi `inventory`, `chat`, `deviations`, dữ liệu, luồng duyệt hoặc phân quyền của chúng trong bản sửa này.

`/assistant/api/context/` chỉ POST có CSRF + đăng nhập hoạt động. Kho qua `warehouses_for`, phiếu qua `documents_for`, danh mục/tồn kiểm quyền riêng. Hồ sơ sai lệch giữ quy tắc nhân viên xem toàn công ty đã chốt; chỉ lấy mã/tiêu đề/trạng thái. Token cũ không làm sống lại quyền đã thu hồi. Không tự tạo/sửa/xóa/duyệt/gửi mail, không SQL từ mô hình hoặc URL bất kỳ. Nội dung dùng `textContent`; liên kết nguồn cùng origin do server tạo. Không đưa mật khẩu/khóa/tệp hoặc hội thoại nhân viên vào ngữ cảnh.

## Tài nguyên mô hình

Giữ nguyên SDK Transformers.js 3.8.1, ONNX Runtime Web, SHA256, revision Qwen và giấy phép tại `static/vendor/transformers-3.8.1/` và `assistant-models.json`. Không tải SDK/trọng số khi mở trợ lý hoặc hỏi tra cứu; chỉ sau lựa chọn tải nâng cao.

```sh
python scripts/build_assistant_sdk.py --check
python scripts/build_styles.py --check
```

Tái tạo SDK khi thực sự cần, bằng npm package chính thức đã pin, theo `scripts/build_assistant_sdk.py`; Node không phải dependency chạy production. Không tắt TLS để thử mô hình.

## Kiểm chứng và phát hành

Chạy toàn bộ suite hiện có cùng test trợ lý mới trên PostgreSQL riêng; kiểm tra lint/JS/CSS/Django/migrations/static. Test hồi quy gồm mã sai, kho ngoài quyền, thu hồi quyền sau lượt hỏi, ngữ cảnh đổi/hết hạn, số thập phân, tổng nhiều đơn vị, ngày, cấp duyệt, CSRF/chỉ đọc, tác vụ ở trang khác và không bịa chức năng chưa có.

Chạy giao diện thật với tài khoản/dữ liệu giả riêng, không database/Drive/mail công ty. Đo thời gian riêng cho phản hồi thật; trường hợp mạng trễ/403 giả lập phải ghi riêng, không trộn vào số đo. Kiểm tra form/con trỏ/nút lưu, mobile/sáng/tối, mô hình tùy chọn không chặn tra cứu. Ảnh kèm phải ghi bản nguồn và dữ liệu thử. Chỉ phát hành đúng commit đã cho chủ phần mềm xem và được đồng ý, theo AGENTS.md.
