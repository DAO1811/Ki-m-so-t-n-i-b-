# Đề xuất nhân sự và quản lý công ty — chờ chủ dự án duyệt

Tài liệu đề xuất, **chưa tạo các chức năng nhân sự mới**. Đợt hiện tại chỉ sửa và kiểm tra các chức năng đang có cùng cơ chế phân quyền. Chủ dự án duyệt phạm vi trước khi phát triển phân hệ mới.

Đã tham khảo tài liệu chính thức Odoo Employees/Time Off và Microsoft Dynamics 365 Human Resources. Chọn cách tổ chức hồ sơ nhân viên, cơ cấu phòng ban, nghỉ phép, thiết bị, tiếp nhận/nghỉ việc và báo cáo; điều chỉnh cho quy mô công ty và dữ liệu kho hiện có, không sao chép toàn bộ một hệ thống lớn vào menu.

## Đề xuất làm đợt đầu

| Chức năng | Nội dung | Kiểm soát bắt buộc |
| --- | --- | --- |
| Cơ cấu tổ chức | Công ty, phòng ban, chức danh, địa điểm làm việc, người quản lý trực tiếp | Dùng một danh mục chung cho kho, mua sắm, nhân sự và báo cáo; lưu lịch sử chuyển phòng ban. |
| Hồ sơ nhân viên | Mã nhân viên, họ tên, liên hệ, ngày vào làm, phòng ban, chức danh, quản lý, tình trạng làm việc, liên hệ khẩn cấp | Tách hồ sơ nhân sự khỏi tên đăng nhập; không đổi tài khoản khi chuyển phòng ban. Thông tin cá nhân nhạy cảm chỉ người được cấp quyền xem. |
| Hợp đồng và hồ sơ | Loại hợp đồng, ngày hiệu lực/hết hạn, phụ lục, tệp và nhắc hạn | Hồ sơ trên Drive sau khi kết nối; từng phiên bản, không ghi đè hợp đồng cũ. Lương, tài khoản ngân hàng, thuế/bảo hiểm là nhóm quyền riêng nếu được đưa vào. |
| Bàn giao / thu hồi tài sản | Nhân viên nhận, tài sản/công cụ, tình trạng, ngày giao/thu hồi, biên bản, vị trí | Liên kết kho; không cấp một tài sản cá thể cho hai người cùng lúc. QR mã hàng hiện tại không thay thế mã tài sản cá thể/serial; cần thiết kế thêm khi duyệt. |
| Tiếp nhận / nghỉ việc | Danh sách việc cần làm: tài khoản, hồ sơ, đào tạo, bàn giao và thu hồi | Nghỉ việc có bước khóa truy cập/thu hồi tài sản; không xóa lịch sử nhân viên, hợp đồng hoặc phiếu cũ. |
| Công việc và báo cáo | Nhân sự đang làm/thử việc/nghỉ, hợp đồng sắp hết hạn, hồ sơ còn thiếu, tài sản theo người giữ, việc chưa hoàn tất | Báo cáo theo quyền công ty/phòng ban/cá nhân; không để người xem tổng hợp tự tải dữ liệu lương hoặc giấy tờ cá nhân. |

Đây là nhóm nên ưu tiên vì liên quan trực tiếp đến tài khoản và quản lý tài sản đang có. Nhân viên, phòng ban và tài sản chỉ khai báo một lần để dùng chung.

## Đề xuất làm sau đợt đầu

1. **Nghỉ phép và công tác:** loại nghỉ, lịch làm việc/ngày lễ, phân bổ phép, xin nghỉ, quản lý duyệt, HR đối soát, số phép còn lại và báo cáo. Phải thống nhất chính sách phép, người duyệt và chuyển phép trước khi lập công thức.
2. **Chấm công và xác nhận công:** ca làm, ngày công, dữ liệu máy chấm công/import, đi muộn/vắng, đề nghị sửa và chốt kỳ. Có thể tích hợp máy chấm công; chưa chọn QR, định vị hoặc nhận diện khuôn mặt trước khi duyệt cách chống chấm hộ và phạm vi thu thập dữ liệu.
3. **Đề nghị mua sắm / thanh toán:** bộ phận đề nghị → duyệt → đơn mua → nhập kho → hóa đơn → thanh toán. Đối chiếu số đề nghị, đặt, thực nhận và hồ sơ; không tự tăng tồn khi mới duyệt mua.
4. **Bảo trì và sửa chữa:** lịch bảo trì, tình trạng hỏng, người chịu trách nhiệm, nhà sửa, chi phí và hồ sơ. Hỏng/mất không tự xóa tài sản; xử lý thanh lý/tiêu hủy có quyền duyệt riêng.
5. **Tuyển dụng, đào tạo và đánh giá:** nhu cầu tuyển, ứng viên, tiếp nhận, kỹ năng/chứng chỉ, khóa đào tạo và mục tiêu đánh giá. Chỉ tạo khi đã thống nhất nhu cầu vận hành, tránh thêm biểu mẫu nhân viên không dùng.
6. **Lương, ngân sách và tích hợp kế toán:** triển khai sau khi công ty chốt cách tính, người duyệt, kỳ chốt, quyền xem và hệ thống kế toán hiện dùng. Không coi báo cáo kho hiện tại là sổ lương/kế toán/thuế hoàn chỉnh.

## Các quyết định cần duyệt trước khi tạo mới

- Có đồng ý làm nhóm đợt đầu ở trên hay chỉ chọn một số mục.
- Nhân viên tự xem được hồ sơ của mình đến mức nào; quản lý được xem nhân viên trực thuộc hay toàn bộ phòng ban.
- Ai được xem/sửa hồ sơ nhân sự, ai quản lý hợp đồng, ai xác nhận bàn giao/thu hồi. Admin vẫn toàn quyền, các tài khoản khác cấp từng chức năng.
- Công ty có bao nhiêu phòng ban/địa điểm và đã có mã nhân viên/danh sách Excel chuẩn chưa.
- Những trường thông tin cá nhân nào thật sự cần; tệp nào cần lưu; thời hạn giữ hồ sơ và ai được tải về.
- Cách quản lý tài sản: chỉ mã hàng và số lượng hay thêm mã tài sản cá thể cho thiết bị phải bàn giao theo từng chiếc.

Sau khi duyệt, sẽ làm đặc tả màn hình và quy trình cụ thể rồi phát triển theo đợt, dùng môi trường thử riêng, kiểm tra phân quyền và luồng nghiệp vụ trước khi đưa lên chính. Không yêu cầu tạo lại hệ thống hiện tại hoặc mua thêm dịch vụ chỉ để có các menu này; hạn mức và cấu hình lưu trữ phải được kiểm tra theo dữ liệu thực tế.

## Nguồn tham khảo đã đọc

- [Odoo 19 — Employees](https://www.odoo.com/documentation/19.0/applications/hr/employees.html): hồ sơ, hợp đồng, phòng ban, đào tạo, thiết bị, onboarding/offboarding.
- [Odoo 19 — Time Off](https://www.odoo.com/documentation/19.0/applications/hr/time_off.html): loại nghỉ, ngày lễ, phân bổ, tích lũy, đề nghị, phê duyệt và báo cáo.
- [Microsoft Dynamics 365 Human Resources — Administration overview](https://learn.microsoft.com/en-us/dynamics365/human-resources/hr-admin-overview): tổ chức các vùng quản lý nhân sự, phát triển nhân viên, lương/phúc lợi, nghỉ phép, tuyển dụng/đào tạo và kiểm soát vận hành hệ thống.
