# Cấu trúc để tiếp tục phát triển

- `config/`: cấu hình, URL, WSGI. Đọc PostgreSQL từ `DATABASE_URL`; SQLite chỉ dành cho phát triển một người.
- `inventory/models.py`: danh mục, chứng từ, dòng hàng, sổ biến động, số dư.
- `inventory/services.py`: nghiệp vụ ghi sổ trong transaction, khóa dòng PostgreSQL, kiểm tra quyền, chống âm tồn và ghi sổ hai lần.
- `inventory/forms.py`: biểu mẫu và trường bổ sung hàng hóa.
- `inventory/views.py`: màn hình và xuất CSV, kiểm soát phạm vi kho tại máy chủ.
- `templates/` và `static/`: giao diện tiếng Việt, tương thích màn hình nhỏ, không cần dịch vụ font hoặc thư viện bên ngoài.
- Django Admin: kho, hàng hóa, nhân viên, vai trò và trường bổ sung. Không mở chỉnh sửa trực tiếp sổ kho, số dư hoặc phiếu đã ghi sổ.
- `inventory/tests.py`: kiểm thử nghiệp vụ, phân quyền, giao diện và cập nhật tồn đồng thời trên PostgreSQL.

## Quy tắc định giá

VNĐ, giá vốn bình quân liên hoàn theo từng kho / mã hàng. Số lượng 3 chữ số thập phân, đơn giá nhập 4 chữ số thập phân, giá trị sổ 2 chữ số thập phân (làm tròn half-up). Xuất hết số lượng sẽ xuất hết giá trị còn lại để không lưu dư tiền do làm tròn. Màn hình có thể làm tròn giá trị VNĐ; CSV giữ số thập phân.

Phiếu nhập phải khai báo đơn giá; được nhập 0 cho hàng không thu tiền. Phiếu xuất dùng bình quân tại kho xuất. Luân chuyển chính thức và xuất cho mượn dùng giá vốn bình quân tại kho cho ở thời điểm duyệt xuất. Hàng mượn lưu vào `LoanHolding`, tách biệt `Balance` khả dụng; trả hàng giữ nguyên giá trị trung gian, không dùng giá bình quân hàng mua riêng của kho mượn. Kiểm kê nhập số lượng thực đếm, điều chỉnh nhập số chênh lệch. Chênh lệch giảm dùng giá bình quân hiện tại; tăng dùng đơn giá nhập trên phiếu hoặc bình quân hiện tại. Hàng chưa có tồn cần nhập đơn giá.

Không bao gồm thuế, vận chuyển phân bổ, kế toán công nợ hoặc tính giá FIFO. Không so sánh giá trị giữa các đơn vị tính khác nhau.

## Mở rộng

Trường bổ sung hàng hóa được khai báo bằng mã và nhãn; giá trị lưu JSON, nhập qua biểu mẫu hàng hóa. Bản đầu hỗ trợ trường văn bản tùy chọn cho hàng hóa; trường số/ngày, trường bắt buộc, trường cho phiếu hoặc quy trình tự cấu hình cần mở rộng tiếp, không tự động được hỗ trợ bởi JSON.

Những báo cáo nên bổ sung tiếp: nhập–xuất–tồn đầu/cuối kỳ theo khoảng ngày; hàng không phát sinh 30/60/90 ngày; chênh lệch kiểm kê; tần suất và giá trị điều chỉnh; tuổi nợ mượn; dashboard mua bổ sung. Báo cáo bản đầu gồm tồn hiện tại và định giá, cảnh báo dưới tối thiểu, thẻ kho, đối chiếu mượn trả, xuất CSV tồn và thẻ kho.

## Phân quyền và hai giai đoạn

`Warehouse.members` là phạm vi truy cập; `managers` là người duyệt nhập / kiểm kê / điều chỉnh; `issue_approvers` là người được admin chỉ định duyệt xuất. Vai trò nhóm cấp quyền tạo chứng từ / danh mục, không thay thế phân quyền duyệt từng kho. Superuser hỗ trợ mọi kho nhưng không tự duyệt phiếu đã lập.

Phiếu liên kho: DRAFT → TRANSIT (trừ tồn khả dụng hoặc giảm tồn mượn tạm khi trả) → POSTED (nhận vào tồn thường, riêng LOAN nhận vào LoanHolding bị khóa). Giá trị đi đường cố định tại lúc duyệt xuất. Các xác nhận chạy trong transaction; khóa Document, phiếu mượn gốc khi cần và Warehouse theo thứ tự ID để serialize biến động.

Excel nhập phiếu IN dùng openpyxl + defusedxml, giới hạn kích thước nén/giải nén, không chạy công thức, kiểm tra toàn file trước khi tạo nháp. Xem trước lưu server session; `Document.import_key` unique chống tạo trùng khi gửi lại xác nhận.
