# Quy tắc chủ phần mềm đã xác nhận ngày 03/11/2026

- Khi thêm hoặc sửa một chức năng, tuyệt đối không được làm ảnh hưởng đến chức năng khác. Khoanh phạm vi thay đổi; giữ nguyên dữ liệu, phân quyền, luồng nghiệp vụ và hành vi của các chức năng không thuộc yêu cầu.
- Tách phân hệ mới thành mã nguồn và bảng dữ liệu riêng khi phù hợp. Các điểm tích hợp dùng chung phải nhỏ, có mục đích rõ ràng và có kiểm thử hồi quy bảo vệ chức năng cũ.
- Kiểm tra toàn bộ kiểm thử hiện có cùng kiểm thử cho thay đổi mới; rà soát diff ngoài phạm vi trước khi đề nghị phát hành. Không tuyên bố không ảnh hưởng nếu chưa có bằng chứng kiểm tra.

## Quy tắc xem thử và phát hành, xác nhận ngày 04/11/2026

- Từ lần thay đổi tiếp theo, phải cho chủ phần mềm xem bản chạy thử thật trước khi cập nhật chính thức; chỉ phát hành khi chủ phần mềm đồng ý đúng phiên bản đã xem. Quy tắc này thay thế các chỉ thị tự động cập nhật trước đây.
- Bản chạy thử phải chạy đúng mã nguồn của thay đổi cần duyệt, dùng database/tài khoản/tệp thử riêng. Không ghi thử vào database công ty, không nối Drive hoặc email thật để minh họa.
- Ảnh hoặc video gửi trong chat phải được chụp từ bản đang chạy, ghi rõ phiên bản và dữ liệu thử. Không dùng giao diện mô phỏng, ảnh thiết kế hoặc dữ liệu giả để tuyên bố đã kiểm chứng hệ thống thật.
- Nếu không có công cụ xem tương tác ngay trong ChatGPT, phải nói rõ giới hạn đó; phân biệt ảnh/video xem trong chat với đường dẫn bản thử có thể thao tác. Không hứa đã nhúng ứng dụng hoặc đã cấp đường dẫn thử khi chưa kiểm tra người dùng truy cập được.
- Không merge vào main, đổi nhánh triển khai hoặc gọi lệnh triển khai bản chính chỉ vì kiểm thử đã đạt. Sau khi chủ phần mềm duyệt, phát hành đúng commit đã xem; thay đổi đáng kể sau lần xem phải đưa xem lại.

## Yêu cầu Trợ lý AI, xác nhận ngày 04/11/2026

- Chủ phần mềm chọn cả hỗ trợ hướng dẫn/soạn nội dung và tra cứu dữ liệu kho/sai lệch theo quyền, nhưng yêu cầu không phát sinh phí API. Không tự gọi API trả phí hoặc dùng API trả phí làm fallback.
- Máy người dùng cung cấp là Windows, RAM 8 GB. Phương án mô hình nội bộ mới đang ở bước đề xuất/kiểm chứng, chưa được kết nối. Không gọi mô hình của bên khác là ChatGPT/OpenAI, không hứa chất lượng/tốc độ khi chưa thử.

- Làm rõ cùng ngày: Trợ lý phải mở ngay trong phần mềm tại mục người dùng đang sử dụng. Không yêu cầu người dùng mở/cài ứng dụng AI riêng; bản thử hiện chọn CPU/WebAssembly trong trình duyệt. Chưa phát hành khi chủ phần mềm chưa xem và duyệt.
