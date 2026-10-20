# Thêm hàng hóa hàng loạt từ Excel

## Sử dụng

Mở **Hàng hóa → Nhập hàng hóa từ Excel → Tải mẫu Excel**. Điền dữ liệu ở trang **Hàng hóa**, bắt đầu từ dòng 2, rồi tải lên để xem trước. Chỉ khi mọi dữ liệu hợp lệ mới có nút xác nhận thêm. Sau khi lưu, danh mục hiển thị riêng các mã vừa thêm; có liên kết trở về toàn bộ hàng hóa.

- Bắt buộc: **Mã hàng, Tên hàng, Đơn vị tính**. Định dạng mã hàng là văn bản để giữ số 0 đầu mã.
- Tùy chọn: nhóm hàng, nhãn hiệu/nhà sản xuất, model, quy cách/thông số kỹ thuật, điều kiện bảo quản, mức tồn tối thiểu và các trường bổ sung đang được cấu hình. Mẫu có trang hướng dẫn; mức tồn tối thiểu để trống được hiểu là 0.
- Tối đa **500 hàng hóa / 5 MB**, định dạng `.xlsx`. Mỗi mã một dòng; bỏ qua dòng trống. Không dùng công thức. Có thể đổi thứ tự cột; dùng tiêu đề trong mẫu hoặc các tên cột tương ứng được hỗ trợ.
- Chỉ thêm mã mới; mã đã có hoặc trùng trong tệp phải được sửa trước khi xác nhận. Hệ thống không tự ghi đè hàng đang sử dụng.
- Mỗi hàng hóa mới tự có mã QR riêng. Ảnh bổ sung ở hồ sơ hàng hóa; hóa đơn gắn theo phiếu nhập/đợt nhập hiện có.
- Đây là nhập danh mục, không phải ghi nhận tồn ban đầu hoặc nhập kho. Số lượng và giá vốn được ghi nhận bằng phiếu nhập và quy trình duyệt hiện có.

## Quyền và kiểm soát

Admin có toàn quyền. Tài khoản khác cần quyền **Hàng hóa: Thêm hàng hóa**; không sử dụng quyền nhập phiếu Excel để thay thế quyền tạo danh mục. Cả trang tải mẫu, xem trước và xác nhận đều kiểm tra phía máy chủ; kiểm tra lại quyền tại giao dịch lưu.

Xem trước không tạo bản ghi. Dữ liệu được giữ ở phiên làm việc phía máy chủ, gắn người dùng và mã lượt nhập, hết hạn sau 30 phút. Khi xác nhận, kiểm tra lại toàn bộ dữ liệu, mã trùng và cấu hình trường bổ sung. Lưu toàn bộ trong một giao dịch; gặp lỗi hoặc xung đột đồng thời thì không thêm dở một phần. Gửi lại xác nhận không tạo thêm mã trùng. Không tin dữ liệu hàng hóa gửi kèm yêu cầu xác nhận của trình duyệt.

Tệp có giới hạn dung lượng nén/giải nén, số dòng/cột và cấu trúc XML trước khi đọc dữ liệu. Chặn ô công thức, ô lỗi Excel, mã kiểu số, trường bắt buộc thiếu, trường quá dài và định mức âm/sai độ chính xác. Không tải ảnh hoặc tệp từ liên kết trong Excel. Không cần kết nối Google Drive để thêm danh mục.

## Kiểm tra phát hành 20/10/2026

- **204/204 kiểm thử PostgreSQL đạt**, không bỏ qua. Trong đó **23 bài về Excel hàng hóa**: mẫu thật, thông tin tùy chọn và trường bổ sung, mã có số 0 đầu, QR riêng, lỗi từng dòng/toàn tệp, quyền và thu hồi quyền, phiên hết hạn, dữ liệu thay đổi sau xem trước, chống gửi lại, giới hạn 500 dòng, truy vấn theo lô và hai người nhập trùng mã đồng thời.
- Chromium dùng dữ liệu thử cách ly: tải mẫu thật, tệp sai không có nút xác nhận và không ghi dở; xem trước/tạo đúng hai mã, kiểm tra ảnh QR; danh sách sau lưu chỉ hiển thị mã vừa thêm; nhập lại bị báo trùng; xem trước đủ 500 dòng; không lỗi JavaScript hoặc HTTP 500 trong các thao tác đã chạy. Kiểm tra bố cục ở 1440, 1024, 768, 390 và 320px.
- Đối chiếu dữ liệu trước/sau thử nghiệm: chỉ danh mục hàng hóa tăng, số bản ghi phiếu, tồn và biến động giữ nguyên.
- Không thêm migration hay dependency. Kiểm tra cú pháp/import và `git diff --check` đạt. Bản đóng gói được kiểm tra riêng trước khi phát hành.

Các kiểm thử nghiệp vụ dùng tài khoản và cơ sở dữ liệu thử; không tạo hàng hóa thử hoặc phiếu thử trong dữ liệu công ty. Sau phát hành kiểm tra chỉ đọc mã release, trạng thái cơ sở dữ liệu, trang đăng nhập, tài nguyên giao diện và yêu cầu đăng nhập của đường dẫn mới.
