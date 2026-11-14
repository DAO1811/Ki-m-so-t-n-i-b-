# Đặc tả Trợ lý AI v2 (dự kiến phiên bản v122)

Trạng thái: **đã triển khai trên nhánh `claude/ai-v2`, chờ bản thử `v122-thu`**. Chủ phần mềm chọn làm song song với phát hành `v121`.

## Quyết định của chủ phần mềm (14/11/2026)

- Trò chuyện nhiều lượt như trợ lý thông thường, **miễn phí**, dùng **Groq Free**. Không dùng API trả phí, không có phương án trả phí dự phòng.
- **Đồng ý gửi dữ liệu theo quyền của người hỏi sang Groq** để AI trả lời về số liệu trong phần mềm.
- Gỡ phần AI chạy trong trình duyệt (Qwen, khoảng 786 MB); giữ "Tra cứu nội bộ" không cần mạng ngoài.

## Cách hoạt động

1. Người dùng hỏi trong khung Trợ lý tại đúng màn hình đang dùng (không cần mở ứng dụng khác).
2. Phần mềm gửi câu hỏi và lịch sử trò chuyện gần đây sang Groq, kèm danh sách **công cụ tra cứu chỉ đọc**.
3. Khi cần số liệu, mô hình yêu cầu một công cụ. Phần mềm chạy công cụ đó **bằng đúng quyền và phạm vi kho của người hỏi**, rút gọn kết quả rồi gửi lại cho mô hình.
4. Mô hình trả lời bằng tiếng Việt, kèm đường dẫn tới màn hình nguồn để người dùng đối chiếu.
5. Tối đa 3 vòng và 4 lần gọi công cụ cho một câu hỏi; mỗi kết quả tối đa 30 dòng / 3.000 byte; cả lượt tối đa 40 giây. Hết giới hạn thì trả lời theo phần đã có và hướng dẫn mở màn hình nguồn.

## Công cụ tra cứu (chỉ đọc, theo quyền)

| Công cụ | Quyền cần có | Nội dung trả về |
|---|---|---|
| Tìm hàng hóa | `products_view` | Mã, tên, đơn vị, nhóm, định mức |
| Tồn kho | `stock_view` | Số tồn, giá trị tồn theo kho được cấp |
| Thẻ kho | `ledger_view` | Nhập/xuất của một mã hàng trong khoảng thời gian |
| Tìm phiếu, chi tiết phiếu | quyền xem loại phiếu tương ứng | Số phiếu, loại, trạng thái, kho, dòng hàng |
| Việc chờ tôi duyệt | quyền duyệt tương ứng | Danh sách phiếu đang chờ người hỏi |
| Kiểm kê | `stocktakes_view` | Phiên, trạng thái, chênh lệch |
| Mượn – trả | `loans_view` / `returns_view` | Lệnh mượn, số còn phải trả |
| Hồ sơ sai lệch | quy tắc xem của phân hệ sai lệch | Mã hồ sơ, trạng thái, người phụ trách, hạn |
| Hướng dẫn sử dụng | `assistant_use` | Bài hướng dẫn trong phần mềm |

**Không bao giờ gửi:** tin nhắn chat nội bộ, mật khẩu, khóa bí mật, mã passkey, tệp đính kèm (ảnh, hóa đơn PDF), nhật ký bảo mật, dữ liệu ngoài quyền của người hỏi.

**Không bao giờ thực hiện:** tạo, sửa, xóa, duyệt, hủy hay bất kỳ thao tác ghi nào. Câu hỏi yêu cầu thao tác chỉ nhận hướng dẫn cách tự làm.

## An toàn và kiểm soát

- Người dùng phải đánh dấu đồng ý gửi nội dung sang Groq trước lần hỏi đầu (giữ luồng đồng ý hiện có, cập nhật lời giải thích rằng số liệu theo quyền cũng được gửi).
- Admin bật Zero Data Retention trong tài khoản Groq và giữ gói Free (`GROQ_FREE_ZDR_CONFIRMED=1`).
- Quyền `assistant_chat` vẫn do Admin cấp từng người.
- Ghi nhật ký: ai hỏi, lúc nào, công cụ nào được gọi, số dòng trả về. Không ghi nội dung câu trả lời của mô hình.
- Giữ hạn mức số lượt/người/ngày và hạn mức chung; đối chiếu lại với hạn mức thật của gói Groq Free trên Groq Console trước khi phát hành. Gọi công cụ làm tốn thêm token, nên số câu hỏi mỗi ngày có thể ít hơn hiện nay.
- Chất lượng câu trả lời phụ thuộc mô hình miễn phí; không cam kết ngang Claude hay ChatGPT. Số liệu luôn kèm đường dẫn nguồn để đối chiếu.

## Bản thử

Bản thử đang chặn cứng Groq. Để thử Trợ lý v2 cần chủ phần mềm đồng ý:

- Thêm công tắc riêng `STAGING_ALLOW_GROQ=1`, chỉ có tác dụng trên bản thử, mặc định tắt.
- Dùng **khóa Groq riêng cho bản thử**, không dùng chung khóa với bản chính. Bản thử chỉ có dữ liệu thử nên không gửi dữ liệu công ty.

## Nghiệm thu dự kiến

- Có quyền: hỏi "Tồn THU-001 ở kho Hà Nội" → số đúng như màn hình Tồn kho, có đường dẫn nguồn.
- Không quyền: `thu_chixem` hỏi số tồn → bị từ chối, không lộ số.
- Hỏi tiếp nhiều lượt ("còn kho kia thì sao?") → hiểu ngữ cảnh.
- Yêu cầu "duyệt phiếu PK-000005" → không duyệt, chỉ hướng dẫn.
- Hỏi nội dung tin nhắn chat của người khác → từ chối.
- Phần Qwen đã gỡ; trang không còn nút tải mô hình.
- Hồi quy Phần B đầy đủ.
