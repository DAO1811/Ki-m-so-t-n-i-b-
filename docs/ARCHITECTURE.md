# Kiến trúc DHD Kiểm soát nội bộ

Cập nhật cấu trúc ngày 22/10/2026. Đây là một ứng dụng Django chia phân hệ, dùng một database PostgreSQL và một quy trình triển khai. Ranh giới được tách để bảo trì; không cần tách thành nhiều dịch vụ riêng khi chưa có nhu cầu vận hành tương ứng.

## Điểm vào và trách nhiệm

| Thư mục | Trách nhiệm |
| --- | --- |
| `config/` | Cấu hình môi trường, URL gốc, health, WSGI và Django Admin |
| `core/` | Tài khoản/phân quyền ở giao diện, đổi mật khẩu, xuất CSV an toàn, trang chuẩn bị dùng chung |
| `inventory/` | Mô hình dữ liệu, giao dịch kho, quyền, Drive, Excel, QR và kiểm kê |
| `workflows/` | App/URL riêng cho Quy trình; hiện chỉ là trang chuẩn bị |
| `people/` | App/URL riêng cho Nhân sự; hiện chỉ là trang chuẩn bị |
| `deviations/` | Hồ sơ sai lệch toàn công ty; bảng, services, workflow và quyền riêng; mở xử lý sau khi cấu hình quy tắc đã chốt |
| `assets/styles/` | Nguồn CSS theo thành phần và nghiệp vụ |
| `static/app.css` | Bundle CSS sinh từ nguồn, được kiểm tra đồng bộ khi build |
| `templates/` | Các template Django, dùng chung `base.html` |
| `.github/workflows/ci.yml` | Lint, kiểm tra cấu hình/migration/static và test PostgreSQL |

`config/urls.py` ghép URL của các app. Tên route và đường dẫn cũ được giữ: `/team/`, `/account/password/`, `/products/`, `/documents/`, `/processes/`, `/human-resources/`... Các trang và quyền hiện có không thay đổi chỉ vì chuyển file.

## Màn hình kho

`inventory/views.py` cũ được thay bằng package:

- `dashboard.py`: tổng quan.
- `catalog.py`: danh mục, ảnh lúc tạo/sửa, trường bổ sung.
- `warehouses.py`: danh mục kho, phân công và kho đang xem.
- `document_list.py`: danh sách và hàng chờ duyệt.
- `document_editing.py`: tạo/sửa phiếu nháp và kiểm tra dòng.
- `document_detail.py`: xem, duyệt và đóng phiếu.
- `stock.py`: tồn, thẻ kho, báo cáo và API số lượng khả dụng.
- `common.py`, `imports.py`: các trợ giúp và điểm vào tương thích.

`inventory/views/__init__.py` tái xuất các tên hàm cũ. Code mới nên import module cụ thể; lớp tương thích phục vụ URL và tích hợp hiện có. Các luồng chuyên sâu vốn đã có file riêng như `stocktakes.py`, `loan_returns.py`, `product_import.py` và các `*_views.py` vẫn được giữ nguyên.

## Ranh giới dữ liệu và quyền

Tất cả model hiện có vẫn thuộc app `inventory`, kể cả `FunctionAccess` hoặc kết nối Drive được dùng chung. Không đổi tên bảng, khóa ngoại, `app_label` hay migration lịch sử trong một lần tổ chức lại mã. `core.views` sử dụng các model/quyền đó qua import rõ ràng. Việc chuyển model sang app khác nếu có sẽ là một thiết kế migration riêng có kiểm thử dữ liệu.

`FunctionAccessMiddleware` áp dụng cho namespace `core`, `inventory`, `workflows`, `people`, `deviations`. Tài khoản thường bị từ chối khi truy cập một route chưa đăng ký quyền; các route chuẩn bị chỉ cho xem thông báo, chưa có dữ liệu nghiệp vụ. Thêm endpoint ở app mới không được tự bỏ kiểm tra quyền. View phải bảo vệ truy cập chưa đăng nhập; nghiệp vụ tiếp tục kiểm tra quyền, cấp duyệt, phạm vi kho và trạng thái chứng từ tại máy chủ.

Admin dùng toàn bộ chức năng theo yêu cầu chủ dự án. Người duyệt thường phải cao cấp hơn người lập và có quyền phù hợp. Admin tự duyệt phải xác nhận cảnh báo, được ghi lịch sử. Chi tiết hiện hành ở `APPROVAL_HIERARCHY.md`, thay cho mô tả cũ về cấm admin tự duyệt.

## Bất biến nghiệp vụ

- Ghi sổ chạy trong transaction, có khóa dòng và kiểm tra lại tồn/quyền/trạng thái; không cập nhật tồn trực tiếp từ giao diện.
- Giá vốn bình quân liên hoàn theo từng kho/mã. Số lượng 3 số lẻ, đơn giá nhập 4 số lẻ, giá trị sổ 2 số lẻ, làm tròn half-up. Xuất hết sẽ kết chuyển hết giá trị còn lại.
- Ngày lập/ghi nhận nhập, xuất mới chỉ dùng ngày hôm nay. Chuyển hàng và xác nhận nhận là các giai đoạn riêng; giữ mốc chuyển đi.
- `DRAFT → TRANSIT → POSTED` áp dụng cho luân chuyển hai giai đoạn. Phiếu nhập/xuất thông thường có quy tắc duyệt hiện có; không tự bổ sung luồng nhiều cấp từ một đề xuất chưa được chốt.
- Hàng mượn nằm trong `LoanHolding`, tách khỏi tồn sở hữu `Balance`; trả từng phần giữ giá trị mượn và chống trả vượt.
- Phiếu đã ghi sổ không sửa nội dung/xóa. Tệp đính kèm có lịch sử bổ sung/thu hồi, giữ tệp cũ. Chưa có quy trình sửa phiếu qua email.
- Kiểm kê theo kho: chốt tồn/khóa giao dịch, chọn giấy hoặc QR, đối chiếu và tạo phiếu chênh lệch. Chỉ điều chỉnh tồn khi phiếu được duyệt.
- QR tự tạo/tự nhập là duy nhất và cố định trong vòng đời mã hàng. Mỗi lượt quét kiểm kê cộng 1, có chống gửi lại.
- Excel kiểm tra toàn file, không chạy công thức, giới hạn kích thước, lưu bản xem trước ở server và chống tạo trùng. Phân bổ kho tạo phiếu nháp, chưa cộng tồn.
- Ảnh và hóa đơn/PDF ở Drive riêng tư đã được cấp OAuth. PostgreSQL giữ chỉ mục; không dựa vào ổ đĩa tạm Render để lưu tệp thực tế.

## Giao diện và nguồn CSS

Các file `foundation`, `layout`, `controls`, `inventory`, `responsive`, `records`, `loans`, `imports`, `stocktakes`, `navigation`, `states` trong `assets/styles/` được ghép theo thứ tự cố định bởi `scripts/build_styles.py`. Không có bước tải CSS qua dịch vụ bên ngoài hoặc dependency Node để build.

Màu nhận diện dùng `--accent*`, `--silver*`; trạng thái thành công dùng `--success*`. Tông vàng/bạc không thay thế màu lỗi/cảnh báo. Palette sáng/tối nằm cùng nguồn; CSS in có quy tắc riêng. Không còn stylesheet `company-theme.css` ghi đè toàn ứng dụng hoặc các quy tắc đăng nhập cũ không sử dụng trong bundle. Trang đăng nhập dùng `static/login.css` riêng.

## Kiểm tra và triển khai

Kiểm thử PostgreSQL bao gồm tồn/giá vốn, cạnh tranh cập nhật, quyền, luồng duyệt, QR, Excel và migration/snapshot. Các test thêm cho cấu trúc app kiểm tra URL tương thích và chống bỏ quyền khi đổi namespace. Kiểm tra trình duyệt và ảnh trước–sau bổ sung cho các thay đổi giao diện; số lượng test không thay thế kiểm tra hành vi thực tế.

`safe_migrate` có khóa triển khai và snapshot nhất quán trước thay đổi schema. Snapshot cùng Neon phục vụ khôi phục migration; cần backup độc lập cho sự cố toàn database. Refactor cấu trúc này không có migration dữ liệu mới.

Xem `RELEASE_PROCESS.md` để phát hành. Quy trình CI chạy tự động theo file workflow; bảo vệ nhánh và chế độ tự triển khai Render phải được quản lý trong cấu hình GitHub/Render, không tự suy ra đã bật từ việc có workflow.

## Phân hệ sai lệch bổ sung

Bản nền và ranh giới thay đổi được mô tả tại [deviations/README.md](../deviations/README.md). Bảng mới `deviations_*` không thay cấu trúc bảng kho. Tích hợp dùng các điểm thêm menu, quyền và một loại lưu trữ tệp; các nhánh xử lý cũ giữ nguyên. Quy trình chi tiết chưa chốt thì giữ đóng xử lý; không tự thêm nghiệp vụ Nhân sự/Quy trình.
