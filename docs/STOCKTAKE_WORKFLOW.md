# Hàng hóa và kiểm kê kho — 20/10/2026

## QR và ảnh hàng hóa

Khi thêm hàng hóa, **Tự động tạo mã QR** được chọn sẵn. Nếu hàng có QR trên nhãn hoặc muốn tự đặt mã, bỏ chọn và nhập nội dung mã đó. Mỗi mã QR gắn với một mã hàng và giữ cố định suốt vòng đời; sửa tên, thông tin hoặc ảnh không đổi QR. Mã QR thủ công phải là chuỗi duy nhất, tối đa 120 ký tự, không chứa khoảng trắng/ký tự điều khiển hoặc giả dạng đường dẫn tem UUID cũ. Tránh dùng mã của hàng khác làm QR.

Mẫu Excel hàng hóa có thêm **QR tự động** và **Mã QR**. Để trống/Có là tự động; Không yêu cầu mã riêng. Các cột cũ vẫn dùng được và mặc định QR tự động. Định dạng mã QR là Text để giữ số 0 đầu mã. File có QR trùng hoặc mâu thuẫn với mã hàng bị chặn toàn bộ; không ghi dở một phần.

QR đã cấp trước nâng cấp giữ UUID và vẫn được nhận diện khi quét trong phần mềm, kể cả tem có tên miền cũ. Mã tự nhập được tạo hình QR đúng nội dung đó; hệ thống không mở website bên ngoài từ nội dung quét.

Ảnh không bắt buộc. Có thể tải ảnh khi tạo hàng hoặc bấm **Cập nhật ảnh** ngay ở danh sách Hàng hóa để bổ sung sau. Hiển thị ảnh thu nhỏ trong danh sách và các ảnh đã có ở màn hình sửa. Giữ quy tắc lưu tệp riêng tư trên Drive ở bản online; không đổi nơi lưu hoặc quyền xem ảnh.

## Quy trình kiểm kê thống nhất

1. **Chốt tồn:** chọn kho, xác nhận lưu mốc tồn và khóa giao dịch. Hoàn tất việc giao nhận cần ghi nhận trước khi chốt; tách hàng đang chuyển và hàng mượn tạm khỏi phạm vi tồn thường kiểm kê.
2. **Chọn kho đã chốt:** danh sách hiển thị các kho chờ kiểm trong phạm vi được cấp quyền. Người có quyền kiểm kê tại kho nhận kiểm và chọn giấy hoặc QR. Hệ thống ghi riêng người chốt và người nhận kiểm; một phiên chỉ có một người phụ trách ghi số, Admin tổng có thể hỗ trợ. Không đổi cách kiểm giữa chừng.
3. **Kiểm đếm:** QR quét từng lượt cộng 1; hoặc in **Bảng kiểm đếm thực tế**, ghi số và ký rồi nhập lại vào biên bản. Nhập giấy có tìm kiếm, lọc chưa ghi số, lưu theo trang và giao diện thẻ trên điện thoại. Hàng ngoài danh sách có mục bổ sung theo đúng mã danh mục và đơn giá phần thừa.
4. **Đối chiếu:** phải xác nhận từng mã, kể cả số 0. Chưa ghi số không được coi là 0. Chốt kết luận để lập phiếu điều chỉnh phần chênh lệch; người có quyền Tổng giám đốc/Admin và đủ cấp duyệt mới cập nhật tồn. Không chênh lệch thì kết thúc mà không tạo điều chỉnh. Giữ cảnh báo và dấu vết khi Admin tự duyệt.

Kho khóa từ bước chốt đến khi biên bản không chênh lệch hoàn tất, hoặc phiếu điều chỉnh được duyệt/từ chối/hủy. Phiên chờ kiểm/đang kiểm có thể hủy với lý do. Nhập/xuất/chuyển/mượn/trả và điều chỉnh khác vẫn được lập nháp nhưng không được ghi sổ khi liên quan kho đang khóa; áp dụng cả Admin. Phiếu điều chỉnh đúng biên bản được xử lý để kết thúc khóa. Kho khác tiếp tục vận hành.

Chỉ một biên bản đang xử lý cho mỗi kho. Khóa dòng kho trong giao dịch làm mốc tồn nhất quán với việc ghi sổ; khóa phiên khi nhận kiểm và ghi số để không đếm đè. Giữ kiểm tra biến động/cutoff đến lúc duyệt, kiểm tra phiên bản từng dòng và chống gửi lại lượt quét. Lưu một trang giấy có xung đột thì hoàn tác cả trang. Không cộng chung số lượng khác đơn vị tính.

Ngày nghiệp vụ giữ chính sách hôm nay. Phiên qua ngày cần hủy và chốt mốc mới; phiếu chờ duyệt quá ngày cần được xử lý theo quy tắc chứng từ hiện có. Không tự làm mới mốc tồn hoặc sao chép số đếm cũ sang một mốc mới.

Biên bản cũ được giữ, không bị tự khóa thêm kho khi nâng cấp. Phiên cũ chưa có khóa giao dịch vẫn có bảo vệ cutoff; giao diện nêu rõ cần hủy và kiểm lại nếu đã phát sinh biến động. Chứng từ kiểm kê cũ tiếp tục được tra cứu/xử lý; mở kiểm kê mới qua đường dẫn cũ sẽ dẫn về luồng chốt tồn.

## Kiểm tra và phát hành

- **217/217 bài PostgreSQL đạt**, không bỏ qua: nghiệp vụ hiện có, QR tự động/tự nhập/bắt buộc/trùng/cố định, Excel, ảnh tạo/thêm sau, chốt tồn/khóa kho, hai cách kiểm, người nhận kiểm khác người chốt, quyền/cấp duyệt, số 0, số ngoài sổ, xung đột phiên bản, lưu cả trang và hai người chốt cùng kho.
- Chromium trên dữ liệu cách ly: tạo QR cả hai kiểu, tải ảnh lúc tạo và thêm sau, ảnh thu nhỏ, QR giữ nguyên; chốt tồn và chặn ghi sổ; in bảng giấy/PDF, ghi số kể cả 0, duyệt điều chỉnh rồi giao dịch lại; giải mã ảnh QR thật hai lần ghi đúng 2 đơn vị; Admin tự duyệt phải xác nhận. Nhân viên nhận kiểm kho do Admin chốt, không tự duyệt; Tổng giám đốc duyệt được. Kiểm tra màn hình máy tính/điện thoại và PDF riêng.
- Migration 0017 → 0018 giữ token/tem QR cũ, số lượng, giá trị, tài khoản và lịch sử kiểm. Các kiểm tra nâng cấp cũ cũng chạy đến 0018. Thử việc worker phiên bản cũ hoàn tất thêm hàng trong lúc schema mới đã có: cột bổ sung có mặc định/cho phép chuyển tiếp; tem UUID vẫn quét được.
- Bản đóng gói DEBUG=0/PostgreSQL riêng chụp **dhd_backup_inventory_0018** từ schema 0017 trước nâng cấp, giữ snapshot cũ và giữ nguyên khóa triển khai dùng chung. Snapshot trong cùng database là bản phục hồi migration, không thay thế sao lưu độc lập. Khởi động lặp xác minh lại snapshot thay vì ghi đè.
- Health bản mới yêu cầu migration 0018 và snapshot sẵn sàng. Kiểm thử, ảnh/PDF minh họa và thao tác trình duyệt dùng dữ liệu riêng; không tạo phiếu/hàng/ảnh thử vào công ty. Kiểm tra production sau phát hành chỉ đọc mã release, health, đăng nhập và tài nguyên tĩnh.
