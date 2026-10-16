# Kiểm soát hàng hóa và chứng từ — bản phát triển

Nhánh `feature/asset-control-details`, phát triển tách khỏi main. Chưa phát hành hoặc chạy migration trên Neon production.

## Quy tắc chủ dự án đã chọn

- Chỉ cho lập và duyệt phiếu ngày hôm nay theo múi giờ Việt Nam. Ngày được điền sẵn, không nhập lùi hoặc tương lai. Phiếu nháp sang ngày mới cần người lập mở sửa, kiểm tra lại và gửi duyệt; thời điểm lập gốc vẫn được giữ.
- Hàng nhập thiếu/hỏng: chỉ số thực nhận đạt yêu cầu được cộng tồn. Số thiếu = số theo chứng từ − số thực nhận − số không nhận. Không cho thực nhận cộng không nhận vượt số theo chứng từ. Có thiếu / không nhận phải ghi lý do. Nếu không có số theo chứng từ, không suy đoán số thiếu.
- Cho ghi nhận thực nhận 0 khi thiếu toàn bộ / không nhận toàn bộ có căn cứ và lý do: không tạo tồn hoặc biến động kho bằng 0.
- Giữ nguyên quy tắc mã hàng / số lượng / giá trị, phân quyền theo kho, người lập không tự duyệt và không âm tồn. Không bật lô / hạn sử dụng khi chủ dự án chưa yêu cầu.

## Thông tin được bổ sung

| Nhóm | Thông tin và cách sử dụng |
| --- | --- |
| Hàng hóa | Nhóm hàng, nhãn hiệu / nhà sản xuất, model / mã nhà sản xuất, quy cách / thông số kỹ thuật, điều kiện bảo quản. Mã / tên / đơn vị / định mức / trường tự tạo vẫn dùng được. |
| Ngày tháng | Ngày nghiệp vụ hôm nay, ngày chứng từ nguồn, thời điểm lập, chuyển đi và ghi sổ riêng biệt. Chuyển liên kho có thể nhận vào ngày khác; ngày trên thẻ kho là ngày của từng bước nhập/xuất, không dùng ngày chuyển đi cho bước nhận. |
| Căn cứ | Số hóa đơn / chứng từ nguồn, đối tác, địa chỉ. Có ngày chứng từ thì phải có số chứng từ. Cảnh báo cùng số chứng từ + đối tác trong phạm vi người xem để kiểm tra nhập trùng; không chặn giao hàng nhiều đợt hợp lệ. |
| Trách nhiệm | Bộ phận / công trình, người giao / bàn giao, người nhận / kiểm đếm. Đây là thông tin bàn giao, không thay thế tài khoản thực sự bấm duyệt; hệ thống ghi tài khoản duyệt riêng. |
| Dòng nhập | Số theo chứng từ, thực nhận đạt, không nhận, thiếu tự tính và tình trạng / lý do. Các thông tin chi tiết nằm trong phần mở rộng để tránh làm dài thao tác thường ngày. |
| Mượn trả | Hạn trả tùy chọn và cảnh báo quá hạn còn giữ; vẫn khóa hàng mượn và trả đúng lệnh gốc. |
| Kiểm kê | Lưu tồn và mốc biến động lúc lập / sửa; hiển thị chênh lệch. Chặn duyệt nếu có biến động sau mốc, kể cả nhập và xuất làm số tồn cuối không đổi. Phiếu kiểm kê cũ chưa có mốc phải kiểm đếm lại rồi lưu sửa. |
| Lịch sử | Bản chụp nội dung và dòng hàng khi lập, sửa, yêu cầu sửa, hủy, chuyển đi, ghi sổ. Giữ tên / mã / đơn vị tại thời điểm lập. Chặn đổi mã và đơn vị hàng đã có chứng từ; đổi quy cách phải lập mã mới. |
| Luồng duyệt | Người duyệt được yêu cầu sửa có lý do. Người lập sửa và gửi lại; phiếu hủy chỉ áp dụng trước ghi sổ / trước chuyển đi. Không xóa lịch sử hoặc hủy hàng đang chuyển. Khóa phiên sửa để tránh ghi đè phiên mới hơn. |
| Tra cứu | Tìm chứng từ nguồn, đối tác, bộ phận; lọc ngày phiếu / ngày biến động; xuất CSV thông tin kiểm soát; in phiếu để đối chiếu nội bộ. |
| Báo cáo | Phiếu nhập thiếu / không nhận, hàng mượn quá hạn còn giữ, phiếu chờ duyệt / yêu cầu sửa / đang chuyển cũ nhất trước. Tôn trọng phạm vi kho và không cộng các đơn vị tính khác nhau. |

Các trường bổ sung về đối tác, hóa đơn, bộ phận, người bàn giao và hạn trả là tùy chọn khi công ty chưa có dữ liệu. Không ép mọi phiếu phải có hóa đơn (ví dụ nhập ban đầu / hàng biếu). Kho, hàng, số lượng và kiểm tra giá vẫn bắt buộc theo nghiệp vụ; lý do kiểm kê, điều chỉnh, chênh lệch, yêu cầu sửa và hủy bắt buộc. Nếu công ty muốn bắt buộc căn cứ / người nhận theo từng loại phiếu, cần chốt chính sách đó trước khi áp dụng.

## Excel

Mẫu mới: `ma_hang, so_luong, don_gia, sl_chung_tu, sl_khong_nhan, ly_do`. Ba cột đầu vẫn là mẫu cũ được hỗ trợ. Ngày, đối tác và chứng từ nguồn nhập trên màn hình rồi được giữ qua bước xem trước / xác nhận. Phiên xem trước qua ngày mới bị hủy để tải lại. Không ghi tồn trước khi người được phân công duyệt. Tối đa 50 mã, 5 MB; chặn công thức, trùng mã và dữ liệu sai kiểu.

## Cơ sở tham khảo

Đã đọc tài liệu chính thức, ngày 16/10/2026:

- [ERPNext — Stock Entry](https://docs.frappe.io/erpnext/user/manual/en/stock-entry): loại nghiệp vụ, kho nguồn / đích, thời điểm ghi sổ và kiểm tra chất lượng.
- [ERPNext — Purchase Receipt](https://docs.frappe.io/erpnext/user/manual/en/purchase-receipt): hàng nhận, hàng bị từ chối, căn cứ mua hàng và kho nhận.
- [ERPNext — Stock Reconciliation](https://docs.frappe.io/erpnext/user/manual/en/stock-reconciliation): đối chiếu số lượng và giá trị thực tế với sổ kho.
- [Odoo — Inventory locations](https://www.odoo.com/documentation/19.0/applications/inventory_and_mrp/inventory/warehouses_storage/inventory_management/use_locations.html): tách kho nội bộ, trung chuyển và kiểm kê.

Áp dụng có chọn lọc: hàng không nhận chỉ là số đối chiếu trên phiếu, không tự tạo kho hàng hỏng; trung chuyển và tồn mượn vẫn tách khỏi tồn khả dụng. Đây là kiểm soát nội bộ cho kho, chưa phải phân hệ kế toán tài sản cố định / khấu hao, chữ ký số, mua hàng theo hợp đồng hoặc cam kết tuân thủ đầy đủ pháp luật kế toán.

## Nâng cấp và giới hạn dữ liệu cũ

Migration 0008–0011 bổ sung dữ liệu; không đặt lại tài khoản, không ghi lại số tồn hoặc giá trị cũ. Ngày phiếu cũ suy từ thời điểm chuyển đi, ghi sổ hoặc lập đã lưu, theo múi giờ Việt Nam; không gán toàn bộ lịch sử thành hôm nay. Không bịa nhật ký hoặc tên hàng lịch sử chưa từng lưu. Tên / đơn vị chụp nguyên trạng và nhật ký chi tiết bắt đầu cho phiếu được thao tác bằng bản mới.

Trước phát hành phải sao lưu Neon và thử phục hồi. Môi trường phát triển chưa có quyền backup production. Kiểm thử nâng cấp trên database tách riêng không thay thế bản backup production. Website thật tiếp tục chạy main đến khi chủ dự án duyệt phát hành.
