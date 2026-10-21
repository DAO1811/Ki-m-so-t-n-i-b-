# Xem bản thử trên VS Code máy tính

Bản thử chạy riêng trên máy của bạn bằng Docker Desktop. Database PostgreSQL riêng và dữ liệu minh họa; không kết nối Neon thật, không truy cập Drive công ty. Chỉ cập nhật bản chính khi bạn đã xem và duyệt đúng phiên bản thử. VS Code là nơi xem/sửa code; Django chạy trang web, Docker tạo môi trường riêng.

## Lần đầu trên Windows

1. Cài [Git](https://git-scm.com/downloads/win), [VS Code](https://code.visualstudio.com/) và [Docker Desktop](https://www.docker.com/products/docker-desktop/). Nếu Docker yêu cầu WSL 2, làm theo hướng dẫn của Docker và khởi động lại máy. Mở Docker Desktop, đợi trạng thái Engine running. Docker Desktop có điều kiện cấp phép theo quy mô doanh nghiệp; xem điều kiện của Docker trước khi dùng cho công ty.
2. Mở VS Code → Extensions (`Ctrl+Shift+X`) → cài **Dev Containers** của Microsoft (`ms-vscode-remote.remote-containers`).
3. Bấm `Ctrl+Shift+P` → **Git: Clone** → dán `https://github.com/DAO1811/Ki-m-so-t-n-i-b-.git` → chọn nơi lưu → **Open**. Đăng nhập GitHub bằng tài khoản có quyền repository khi được hỏi. Không gửi mật khẩu/token vào chat.
4. Bấm vào tên nhánh ở góc trái dưới → chọn **origin/preview/shared-review**. Nếu chưa thấy, `Ctrl+Shift+P` → **Git: Fetch**, rồi chọn lại. Code ở nhánh này được thử riêng, main vẫn là bản thật.
5. `Ctrl+Shift+P` → **Dev Containers: Reopen in Container**. Lần đầu Docker tải môi trường và thư viện, tạo 2 kho và 3 mã hàng minh họa. Đợi các bước setup hoàn tất, không cần tự cài Python/PostgreSQL trên Windows.
6. Mở tab **Ports** ở khung dưới VS Code. Dòng **8000**, bấm biểu tượng quả địa cầu **Open in Browser**. Hoặc mở `http://localhost:8000`. Trang phải hiện **BẢN CHẠY THỬ**. Nếu cổng 8000 đang dùng, đóng ứng dụng đang dùng cổng rồi mở lại container.
7. Menu **Terminal → Run Task → DHD: Xem tài khoản thử**. Sao chép tài khoản và mật khẩu thử hiển thị ở Terminal vào trang đăng nhập local. Đây là tài khoản riêng, không dùng tài khoản công ty.

Không có bước deploy trong quá trình trên. Không dán DATABASE_URL/Google secret của phần mềm thật vào container. Google Drive cố ý tắt trên bản thử; ảnh/PDF thử lưu trong database local, không gửi lên thư mục công ty.

## Khi tôi gửi bản sửa tiếp theo

Trong VS Code đã mở container, chọn **Terminal → Run Task → DHD: Cập nhật bản thử**. Task chỉ lấy nhánh `preview/*`, cập nhật thư viện/migration của dữ liệu thử rồi chạy lại. Task dừng nếu bạn đang tự sửa code, không tự ghi đè hoặc xóa thay đổi của bạn. Nếu Git báo hai nhánh đã phân kỳ, gửi thông báo lỗi để xử lý; không dùng reset --hard.

Bấm làm mới trang web (`Ctrl+R`) để xem bản mới. Khi tự sửa file Python, Django tự nạp lại; HTML hiện ở lần tải trang tiếp theo. CSS nguồn được tự ghép, rồi bạn làm mới trang. Form đang nhập không bị tự làm mới gây mất nội dung.

Xem phiên bản bằng **DHD: Xem trạng thái bản thử**. Gửi mã phiên bản kèm “Duyệt đưa bản này lên chính” sau khi kiểm tra. Nếu chưa đồng ý, báo điểm cần chỉnh và tiếp tục thử; main/Render chưa thay đổi.

## Dừng, mở lại và kiểm tra lỗi

- Đóng cửa sổ container sẽ dừng các dịch vụ thử; dữ liệu thử giữ trong Docker volume cho lần sau. Không xóa volume nếu cần giữ phiếu thử.
- Mở lại thư mục → **Reopen in Container**, server tự chạy. Có thể chạy task **DHD: Khởi động bản thử** hoặc **DHD: Dừng bản thử**.
- Nếu trang không mở: kiểm tra Docker đang chạy, Ports 8000, rồi Terminal đọc `.preview/server.log`. Không chia sẻ file `.preview/credentials.json`.
- Cấu hình container thay đổi: **Dev Containers: Rebuild Container**. Không cần tạo dịch vụ Render mới.
- Nếu vào terminal ở Windows chưa mở container, các lệnh preview sẽ từ chối chạy; mở container trước.

## Luồng kiểm kê cần bạn xem ở bản này

1. Quản lý kho → Kiểm kê → chốt kho HN → chọn kiểm bằng giấy hoặc QR.
2. Ghi đủ số đếm của mọi mã, chọn ít nhất một mã khác tồn để có chênh lệch. Chốt chênh lệch/gửi duyệt: kho tự mở giao dịch, chưa cộng/trừ tồn.
3. Thử một phiếu nhập/xuất mới tại kho đó. Sau đó duyệt phiếu điều chỉnh: chỉ cộng/trừ chênh lệch đã chốt, giữ các giao dịch mới; chặn nếu làm âm tồn.
4. Hoặc chọn **Không duyệt điều chỉnh**, bắt buộc lý do: không đổi tồn. Kho được kiểm tiếp bằng phiên mới sau quyết định này.
5. Admin mở biên bản → **Xóa phiếu kiểm kê**, nhập lý do và mã xác nhận. Phiếu ẩn khỏi danh sách sử dụng; mở khóa của chính phiên đó nếu còn khóa. Lịch sử được giữ, phiếu đã ghi sổ không bị đảo tồn. Xem lại bằng **Hồ sơ đã xóa**; tài khoản thường không có quyền này.

Không chạy nhiều phiên kiểm kê/điều chỉnh chồng nhau trong cùng một kho khi phiếu trước còn chờ quyết định; giao dịch nhập/xuất/chuyển vẫn được thực hiện sau chốt chênh lệch.
