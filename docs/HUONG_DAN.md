# Hướng dẫn sử dụng

## Thiết lập lần đầu — quản trị viên

1. Đăng nhập tài khoản quản trị, mở **Quản lý kho**, thêm mã kho, tên và địa chỉ.
2. Mở **Nhân viên & quyền** → thêm người dùng → đặt mật khẩu. Chọn vai trò tại phần Nhóm: Nhân viên kho, Quản lý kho hoặc Chỉ xem báo cáo. Không chọn quyền superuser cho người dùng thông thường.
3. Trở lại mỗi kho: gán **Nhân viên được truy cập**, **Quản lý được duyệt nhập kho** và **Người được admin chỉ định duyệt xuất**. Ba danh sách có ý nghĩa khác nhau; chỉ gán nhóm Quản lý kho không tự có quyền duyệt tất cả kho.
4. Thêm danh mục mã hàng, tên, đơn vị và mức tồn tối thiểu mỗi kho.
5. Nếu cần thông tin thêm (ví dụ thương hiệu), vào **Trường bổ sung**, tạo mã `thuong_hieu` và nhãn `Thương hiệu`. Biểu mẫu hàng hóa tự hiện thêm ô này.
6. Tồn ban đầu được tạo bằng phiếu nhập có đơn giá. Một người lập, người khác đủ quyền xác nhận. Không sửa số dư trực tiếp.

## Nhập hàng mua về

Nhân viên → Tạo chứng từ → chọn **Nhập kho** → chỉ chọn **Kho nhập** → chọn hàng, số lượng, đơn giá VNĐ → Lưu nháp. Nhân viên kiểm tra và sửa phiếu nháp nếu cần. Quản lý kho nhận đăng nhập bằng tài khoản riêng → mở phiếu → xác nhận nhập. Lúc này tồn và giá trị mới tăng.

### Nhập từ Excel

Mở **Nhập Excel** → tải file mẫu → điền dữ liệu từ dòng 2, giữ nguyên tiêu đề dòng 1:

| ma_hang | so_luong | don_gia |
| --- | ---: | ---: |
| VT-001 | 10 | 25000 |
| VT-002 | 5 | 180000 |

Mã phải có trong danh mục. Không lặp mã trên cùng file, không dùng công thức. Số lượng dương, đơn giá không âm; cho phép đơn giá 0 nếu hàng miễn phí. Dùng ô dạng số; không gõ `25.000đ` trong ô đơn giá. Tối đa 50 mã hàng, 5 MB; file cũ `.xls` cần lưu lại thành `.xlsx`.

Chọn kho nhận → tải file → Kiểm tra & xem trước. Nếu có lỗi, hệ thống hiển thị dòng lỗi và chưa tạo phiếu. Nếu đúng, xác nhận tạo phiếu nháp. Quản lý kho vẫn phải duyệt trước khi tăng tồn.

## Xuất kho

Nhân viên lập phiếu **Xuất kho**, chỉ chọn **Kho xuất**, số lượng dương và diễn giải. Người được admin chỉ định quyền duyệt xuất tại kho đó xác nhận. Thiếu tồn thì cả phiếu bị từ chối, không trừ một phần. Người lập không tự duyệt.

## Luân chuyển chính thức

Chọn kho xuất và kho nhập khác nhau. Người duyệt xuất xác nhận: hàng trừ tại kho xuất và ở trạng thái đang chuyển. Quản lý kho nhận kiểm tra và xác nhận: hàng mới cộng vào kho nhận, cùng giá trị đã xuất. Không xác nhận khi chưa nhận đủ hàng.

## Mượn trả — sổ trung gian riêng

Lệnh **Cho kho mượn**: chọn kho cho và kho mượn. Người có quyền duyệt xuất tại kho cho xác nhận, chỉ được dùng tồn khả dụng. Hàng được treo trung gian. Quản lý kho mượn xác nhận đã nhận thì hiện **tồn mượn tạm bị khóa**, không cộng vào tồn thường.

Kho mượn chỉ được trả số hàng này theo lệnh gốc, không được xuất dùng, chuyển sang kho khác hoặc cho mượn tiếp. Tồn mua riêng của kho mượn vẫn được quản lý bình thường, tách khỏi tồn mượn.

Lệnh **Trả hàng mượn**: chọn đúng phiếu mượn gốc, đảo chiều hai kho, nhập số lượng cần trả. Hỗ trợ trả từng phần. Người duyệt phía kho mượn xác nhận: giảm tồn mượn tạm, treo hàng đang trả. Quản lý kho cho mượn xác nhận: hàng cộng lại vào tồn khả dụng. Giá trị trả giữ nguyên giá trị đã mượn, không lấy giá vốn của hàng mua riêng tại kho mượn. Không được trả quá số còn nợ; hàng đang trả cũng được tính để chặn trả trùng.

## Kiểm kê và điều chỉnh

**Kiểm kê**: chọn kho tại ô Kho nhập / kiểm kê; số lượng là số **thực đếm của hàng thuộc tồn thường**, không phải số chênh lệch. Không đếm cộng hàng mượn tạm vào đây. Bản đầu chưa có phiếu kiểm kê riêng cho hàng mượn. Nhập 0 nếu hết hàng; ghi lý do. Quản lý kho xác nhận để ghi nhận chênh lệch.

**Điều chỉnh tồn**: chọn kho tại ô Kho nhập, nhập số tăng hoặc số âm khi giảm; bắt buộc lý do. Không thể điều chỉnh xuống âm. Điều chỉnh sai nghiệp vụ phải lập phiếu bù có giải thích, không xóa lịch sử đã ghi sổ.

## Xem số liệu

- **Tồn kho & báo cáo**: lọc kho, mã hàng, hàng dưới định mức; xem giá bình quân và giá trị. Tải CSV để mở bằng Excel.
- **Thẻ kho**: chọn kho và hàng, xem biến động theo phiếu. Hàng mượn tạm theo dõi trong sổ mượn, không trộn vào thẻ tồn thường của bên mượn.
- **Mượn & trả**: theo dõi số đã cho mượn, đã trả, còn phải trả, tồn mượn tạm, hàng đang trả và giá trị trung gian. Lệnh chưa nhận nằm ở phần chờ bên mượn nhận.

Giá bình quân chỉ cập nhật khi ghi sổ, theo từng kho. Hệ thống dùng thời điểm xác nhận, không có nghiệp vụ ghi sổ lùi ngày ở bản đầu.
