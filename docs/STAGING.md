# Bản thử (staging)

Bản thử dùng để chủ phần mềm bấm thử mọi thay đổi trước khi cập nhật bản chính. Bản thử chạy đúng mã nguồn cần duyệt nhưng **không dùng chung** database, Drive, email, khóa API hay tên miền với bản chính.

## Phần mềm nhận diện bản thử

| Biến | Giá trị | Tác dụng |
|---|---|---|
| `APP_ENVIRONMENT` | `production` (mặc định) hoặc `staging` | Giá trị khác làm ứng dụng dừng khi khởi động. |
| `APP_VERSION` | ví dụ `v121-thu2` | Hiện trong dải BẢN THỬ, chân trang Admin và `/healthz/`. Không đặt thì là `unknown`. |

Khi `APP_ENVIRONMENT=staging`:

- Mọi trang, kể cả trang đăng nhập, trang in hồ sơ sai lệch và trang Admin, hiện dải chữ cố định **"BẢN THỬ – <phiên bản> – không nhập dữ liệu thật"**. Tiêu đề tab trình duyệt có thêm `[THỬ]`.
- Google Drive bị chặn trước khi gửi bất kỳ yêu cầu mạng nào, kể cả khi lỡ khai báo khóa Google. Tệp tải lên được lưu trong database thử (`PRIVATE_MEDIA_PROVIDER` bị ép về `database`).
- Gửi email bị chặn: thư bị bỏ, chỉ ghi một dòng cảnh báo vào log, không ghi nội dung thư.
- Groq bị chặn kể cả khi có `GROQ_API_KEY`. Khung trò chuyện báo "Bản thử không kết nối dịch vụ thật". Tra cứu nội bộ vẫn dùng được.
- `/healthz/` trả `"environment": "staging"` và `"version"`.

Bản chính (`production`) không tải `staging.css`, không hiện dải chữ và giữ nguyên hành vi. Kiểm thử bảo vệ nằm ở `config/tests.py`.

## Dữ liệu thử

```bash
APP_ENVIRONMENT=staging python manage.py seed_staging
```

- Chỉ chạy khi `APP_ENVIRONMENT=staging` và database trống. Ở `production` lệnh báo lỗi, dừng và không ghi gì.
- Tạo 2 kho thử, 4 mã hàng `THU-001`…`THU-004`, các phiếu ở trạng thái đã ghi sổ, chờ duyệt, yêu cầu sửa, đang chuyển kho.
- Tài khoản thử: `thu_admin` (Admin), `thu_nguoilap` (Nhân viên, lập phiếu), `thu_nguoiduyet` (Leader, duyệt tại 2 kho), `thu_chixem` (Nhân viên, chỉ xem phiếu nhập/xuất, không xem tồn).
- Mật khẩu chung lấy từ biến `STAGING_SEED_PASSWORD`. Chạy tay mà không đặt biến này thì lệnh tạo mật khẩu ngẫu nhiên và in ra **một lần**. Khi khởi động (`--auto`), thiếu biến thì bỏ qua, không tự tạo mật khẩu.
- Không sao chép database công ty vào bản thử, kể cả bản ẩn danh.

## Hạ tầng (chủ phần mềm đồng ý và tự xác nhận trên tài khoản của mình)

Hiện trạng đã kiểm tra ngày 14/11/2026: dịch vụ chính là `kiemsoatnoibolemon` (Render, Docker, vùng Singapore, nhánh `main`, tự triển khai khi `main` đổi), database chính là project Neon "Phần mềm KSNB".

1. Tạo **database Neon thử riêng**: project mới, trống (ví dụ `ksnb-thu`, vùng Singapore). Không dùng branch tách từ database công ty.
2. Trên Render, tạo **dịch vụ Web thứ hai** `kiemsoatnoibo-thu`: cùng repository, runtime **Docker** (giống bản chính), **Branch: `staging`**, vùng Singapore, gói Free.
3. Biến môi trường của dịch vụ thử:
   `APP_ENVIRONMENT=staging`, `APP_VERSION=<nhãn>`, `DEBUG=0`, `SECRET_KEY` mới, `DATABASE_URL` của database thử, `PRIVATE_MEDIA_PROVIDER=database`, `PASSKEY_RP_ID=kiemsoatnoibo-thu.onrender.com`.
   **Không** đặt khóa Google, Groq, TURN hay `GOOGLE_DRIVE_*`.
4. Chủ phần mềm tự thêm biến `STAGING_SEED_PASSWORD` (mật khẩu chung của 4 tài khoản thử) trên trang Environment của dịch vụ thử. Render khởi động lại; `start.sh` gọi `seed_staging --auto` để nạp dữ liệu thử đúng một lần. Gói Free không có Shell nên không cần chạy lệnh tay.
5. Kiểm tra lại dịch vụ chính `kiemsoatnoibolemon`: Branch vẫn là `main`, không đổi biến môi trường nào.

`render.yaml` không được sửa trong đợt này, để tránh Render Blueprint tự tạo hoặc đổi dịch vụ.

Lưu ý: Render Free ngủ khi không có truy cập, lần mở đầu có thể chậm khoảng một phút. Điều kiện gói Free của Render và Neon thay đổi theo thời gian; kiểm tra trên tài khoản trước khi tạo, không hứa hạn mức.

## Đưa một phiên bản lên bản thử

1. Push nhánh thay đổi, rồi cập nhật nhánh `staging` trỏ tới đúng commit đó.
2. Đổi `APP_VERSION` của dịch vụ thử thành nhãn mới (ví dụ `v121-thu2`).
3. Chờ `/healthz/` của bản thử báo `status=ok`, `environment=staging`, đúng `version` và `release` (commit).
4. Gửi chủ phần mềm đường dẫn, tài khoản thử và Bảng nghiệm thu (`docs/nghiem-thu/`).
