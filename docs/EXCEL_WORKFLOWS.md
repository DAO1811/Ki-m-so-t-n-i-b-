# Excel trong từng nghiệp vụ

- **Danh mục hàng hóa → Thêm mã hàng bằng Excel**: thêm danh mục (tên, đơn vị, QR, thuộc tính). Tùy chọn điền đủ Mã kho nhập, Số lượng nhập, Đơn giá nhập để tự tạo phiếu nhập riêng theo kho; duyệt xong mới cộng tồn. Ba cột cùng trống thì chỉ thêm danh mục. Xem [hướng dẫn chi tiết](PRODUCT_EXCEL_IMPORT.md).
- **Nhập kho → Lập phiếu nhập bằng Excel**: nhận hàng thực tế theo các mã đã khai báo; ghi số thực nhận, đơn giá và phần thiếu/hỏng. Chỉ cộng tồn sau khi phiếu được duyệt. Mẫu có cột G `ma_kho` để nhập nhiều kho trong một file; dòng không có mã kho dùng Kho nhận chung trên màn hình. Mỗi kho tạo phiếu riêng, tối đa 50 mã/phiếu. Xem [hướng dẫn nhập kho theo kho](RECEIPT_EXCEL_WAREHOUSES.md).
- **Xuất kho → Lập phiếu xuất bằng Excel**: một file lập một phiếu nháp cho cùng kho, tối đa 50 mã. Tải mẫu gồm `ma_hang`, `so_luong`, `ghi_chu`; mã định dạng văn bản, số lượng dương tối đa 3 số lẻ; không trùng mã/công thức. Tồn có thể xuất được kiểm tra ở bước xem trước và tạo phiếu; khi duyệt tiếp tục kiểm tra dưới khóa giao dịch. Giá vốn lấy theo sổ kho lúc duyệt, không lấy giá người dùng điền. Phiếu nháp không giữ hàng hoặc trừ tồn.

Không còn menu Nhập từ Excel đứng riêng. Cả cách thủ công và Excel dùng cùng quyền tạo phiếu của từng nghiệp vụ. Quyền cũ `tools_import` được giữ tương thích và vẫn bao gồm tạo phiếu nhập kho; không cấp quyền xuất kho. Người chỉ xem không được tạo bằng Excel. Chọn kho chỉ trong phạm vi admin đã cấp.

Xuất Excel có bản xem trước gắn người dùng, hạn 30 phút và ngày hôm nay; xác nhận chỉ dùng dữ liệu đã kiểm tra trong phiên máy chủ. Kiểm tra lại quyền, kho, mã hàng và tồn khi xác nhận. File sai không ghi một phần; xác nhận lặp cùng lượt không tạo thêm phiếu. Không cho bỏ qua cấp duyệt, tự duyệt thường hoặc khóa kho kiểm kê. Admin tự duyệt vẫn phải xác nhận cảnh báo hiện có.

Đã kiểm tra toàn bộ 228 ca PostgreSQL, gồm 11 ca mới cho Excel xuất và điều hướng. Kiểm tra trình duyệt bằng dữ liệu minh họa riêng, không nhập thử vào kho công ty.
