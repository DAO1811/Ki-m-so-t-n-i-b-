# Lựa chọn lưu trữ miễn phí và Google Drive

Khảo sát ngày 16/10/2026. Điều kiện dịch vụ có thể thay đổi; kiểm tra lại màn hình đăng ký trước khi chọn gói. Chưa tạo tài khoản, dịch vụ có thu phí, website công khai hoặc DB online cho chủ dự án.

## Phương án đề xuất: Render Free + Neon Free

- Render chạy ứng dụng Python/Django và cung cấp địa chỉ web HTTPS. Có cấu hình `render.yaml` cho web service `plan: free`, không khai báo tạo DB trả phí hoặc Render PostgreSQL.
- Neon giữ PostgreSQL online riêng, không lưu DB trong ổ đĩa tạm của web server. Tài liệu chính thức hiện ghi Free: **1 GB / project**, tổng 20 GB cho tài khoản; **100 CU-hours / project / tháng**, 5 GB public network transfer / project; tự ngưng compute sau 5 phút không hoạt động. Compute ngưng không đồng nghĩa dữ liệu bị xóa; kết nối sau cần thời gian khởi động. Không có cam kết uptime cho Free.
- Google Drive giữ file nhập Excel, báo cáo và **bản sao lưu đã xuất**. Chưa tích hợp sao lưu tự động vào Drive, không đặt file DB đang chạy trên thư mục đồng bộ Drive.

Đây là phương án phù hợp để dùng thử nhóm nhỏ, không hứa miễn phí không giới hạn hoặc luôn hoạt động tức thì. Không dùng phần mềm ping liên tục để né cơ chế ngủ hoặc hạn mức của nhà cung cấp.

Nguồn Neon đọc được từ kho tài liệu chính thức (tệp cập nhật 13/10/2026):
https://github.com/neondatabase/website/blob/main/content/docs/introduction/plans.md
https://neon.com/docs/introduction/plans

Render có ví dụ Django chính thức với `plan: free`:
https://github.com/render-examples/django/blob/main/render.yaml
https://docs.render.com/free

Trang giới hạn Free của Render không truy cập trực tiếp được từ mạng khảo sát hiện tại; chưa xác minh lại các con số giờ chạy, thời gian ngủ, hạn mức build hoặc điều kiện xác minh tài khoản. Ví dụ GitHub là căn cứ có hỗ trợ Free cho Django, không phải bảo đảm chính sách khi đăng ký. Nếu giao diện yêu cầu thanh toán hoặc không còn gói Free phù hợp, dừng lựa chọn và xem phương án khác; không tự đăng ký gói trả phí. Không dựa vào Render PostgreSQL Free để lưu dữ liệu kinh doanh lâu dài nếu chưa xác minh thời hạn DB.

## Phương án thay thế: Supabase Free cho PostgreSQL

Tài liệu chính thức ghi **500 MB DB / project**, 2 project miễn phí; 1 GB object storage và 5 GB egress theo hạn mức tổ chức. Supabase không thay thế dịch vụ chạy Django; vẫn cần nơi chạy website. Nhiều chức năng hơn nhu cầu hiện tại (Auth, Realtime, Storage), vì vậy Neon đơn giản hơn khi app đã có đăng nhập và phân quyền riêng.

Nguồn đã đọc:
https://github.com/supabase/supabase/blob/master/apps/docs/content/guides/platform/billing-on-supabase.mdx
https://supabase.com/docs/guides/platform/billing-on-supabase

## Google Drive không phải dịch vụ chạy website / DB

Gói Google One 100 GB cung cấp dung lượng tệp, không bao gồm máy chủ web hoặc PostgreSQL. Google Sheets + Apps Script có thể làm ứng dụng riêng quy mô nhỏ nhưng cần thiết kế nền tảng khác; không phải chỗ đặt nguyên ứng dụng Django này. Với nghiệp vụ khóa tồn, hai người thao tác đồng thời và giá trị hàng hóa, PostgreSQL phù hợp hơn tệp bảng tính đồng bộ.

## Chủ dự án cần làm gì trước

1. Tạo tài khoản tại https://neon.com bằng tài khoản của chính mình, chọn Free, tạo một project PostgreSQL. Không gửi chuỗi kết nối hoặc mật khẩu trong chat.
2. Tạo tài khoản tại https://render.com, kết nối GitHub của chính mình. Chưa cần mua tên miền; dùng địa chỉ do dịch vụ cung cấp.
3. Sau khi mã nguồn được đưa vào GitHub, tạo web service từ `render.yaml`, kiểm tra gói Free trước khi tiếp tục.
4. Nhập `DATABASE_URL` Neon trực tiếp vào phần biến môi trường Render. Chọn URL phù hợp nhà cung cấp (ưu tiên pooled URL nếu có) và giữ cấu hình TLS của URL. Tạo `INITIAL_ADMIN_USERNAME`, `INITIAL_ADMIN_PASSWORD` ngay trong Render; không gửi mật khẩu qua chat. `SECRET_KEY` được tạo tự động; hostname HTTPS tự lấy từ Render.
5. Khi web chạy, đăng nhập quản trị bằng mật khẩu vừa tự đặt. Xóa biến `INITIAL_ADMIN_PASSWORD` sau khi xác nhận đăng nhập; lần deploy sau không đổi mật khẩu người dùng đã có.
6. Tạo nhân viên thật, gán kho và quyền, chạy dữ liệu thử. Thiết lập backup / khôi phục trước khi dùng số liệu thật. Gói Free của Neon có cửa sổ khôi phục giới hạn, không thay thế backup độc lập.

Việc kết nối tài khoản, chọn gói và nhập bí mật cần chủ dự án thực hiện trong giao diện của dịch vụ. Các bước kỹ thuật đã có script để tiếp tục cấu hình, không yêu cầu chủ dự án biết viết mã.
