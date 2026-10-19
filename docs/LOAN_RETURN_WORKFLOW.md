# Mượn và trả hàng — bản cập nhật 19/10/2026

## Cách sử dụng

1. Mở **Mượn & trả**, tìm theo số lệnh, mã hàng hoặc tên kho. Mỗi lệnh mượn đã nhận hàng hiển thị một lần và có một nút **Trả hàng**.
2. Chọn lệnh cần trả. Kho đang mượn, kho nhận lại, ngày hôm nay và các mặt hàng được lấy từ lệnh gốc; không phải chọn lại kho, mã hàng hoặc đơn giá.
3. Nhập số thực trả; để `0` ở hàng chưa trả. Có thể dùng **Điền số có thể trả** rồi sửa theo thực tế. Không cộng chung số lượng của các mã có đơn vị khác nhau.
4. Tạo phiếu chờ duyệt. Phiếu nháp giữ phần số lượng đang đề nghị trả để tránh lập trùng. Người lập có thể sửa phiếu còn chờ duyệt hoặc bị từ chối; hủy hoặc từ chối sẽ giải phóng phần giữ này.
5. Người đủ cấp, đúng quyền và kho duyệt chuyển trả. Hàng chuyển sang trạng thái đang trả; kho cho mượn chưa được cộng tồn.
6. Kho cho mượn xác nhận đã nhận lại theo phân quyền duyệt hiện có. Chỉ lúc này tồn được cộng về và số còn phải trả giảm tương ứng.

Admin tổng vẫn có thể xử lý theo quyền hiện có. Khi tự duyệt phiếu của mình, admin phải xác nhận cảnh báo và hệ thống ghi rõ hành động tự duyệt. Tài khoản thường cần người cấp cao hơn có quyền phù hợp duyệt.

## Theo dõi và ràng buộc

- Từng mã hàng hiển thị số đã mượn, đã nhận lại, chờ duyệt, đang chuyển trả và còn có thể lập trả. Lịch sử nằm ngay dưới lệnh gốc, tự mở khi có việc đang chờ.
- Phiếu trả có liên kết lệnh mượn gốc và hướng dẫn bước tiếp theo. Màn hình lệnh mượn cũng có nút trả trực tiếp và danh sách các lần trả.
- Cho phép trả một phần, nhiều lần; mỗi phiếu gắn một lệnh gốc. Không chọn hàng ngoài lệnh, trả vượt phần còn lại hoặc dùng số âm/sai định dạng.
- Hai người lập trả cùng lúc được kiểm tra lại số còn có thể trả trong giao dịch khóa theo lệnh gốc. Sửa phiếu loại phần giữ của chính phiếu đó khỏi giới hạn, nhưng vẫn tính phiếu của người khác.
- Gửi lại thao tác tạo không lập thêm phiếu. Gửi lại thao tác duyệt không được tự chuyển sang bước nhận hàng: mỗi lần duyệt gắn với trạng thái và phiên bản nội dung mà người dùng đang xem.
- Hàng mượn tiếp tục được quản lý riêng với tồn có thể sử dụng của kho mượn. Giữ nguyên cách tính giá trị và phân quyền chức năng/kho/cấp duyệt.

## Bằng chứng kiểm tra

- Toàn bộ **181/181 bài kiểm tra PostgreSQL đạt**, không bỏ qua; gồm các bài hiện có và 18 bài về trả hàng, đặt giữ số lượng, quyền, phiên bản phiếu, gửi lại và xử lý đồng thời. Sau chỉnh phần hiển thị cuối, chạy lại **18/18 bài liên quan đạt**.
- Chromium trên dữ liệu minh họa cách ly: một lệnh có hai mã khác đơn vị, trả một phần mã đầu và bỏ mã thứ hai; điền/xóa số, lưu, sửa, duyệt chuyển trả và xác nhận nhận lại. Kiểm tra tồn chỉ cộng về đúng bước nhận lại và đúng một lần, không đổi tồn khả dụng kho mượn hoặc mã chưa trả.
- Kiểm tra liên kết lệnh gốc, lịch sử thu gọn, không lặp bảng phiếu và bố cục ở các chiều rộng 1440, 1024, 768, 390, 320px; không lỗi JavaScript, HTTP 500 hoặc tràn ngang trong các thao tác đã chạy.
- Không thêm dependency hoặc migration. Kiểm tra import/tên chưa định nghĩa, cú pháp JavaScript, `makemigrations --check --dry-run` và `git diff --check` đạt.
- Docker xây thành công bằng cấu hình đóng gói hiện có; riêng bước tải pip dùng wheelhouse có sẵn. Bản chạy DEBUG=0/PostgreSQL cách ly khởi động và xác minh snapshot hiện có, không có migration mới.

Không dùng tài khoản công ty hoặc tạo/sửa phiếu thực tế để kiểm thử. Kiểm tra sau phát hành chỉ đọc health, trang đăng nhập và tài nguyên tĩnh; kết quả này không thay thế đối chiếu số liệu vận hành của công ty.
