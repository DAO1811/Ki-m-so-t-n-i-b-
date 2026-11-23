# Việc đang chờ chủ phần mềm xử lý

Lưu ngày 23/11/2026 theo yêu cầu của chủ phần mềm: tạm dừng, chủ phần mềm xử lý sau. Không ai tự làm thay các bước cần tài khoản của chủ phần mềm.

## Tình trạng hiện tại

| Nơi | Phiên bản | Nội dung |
|---|---|---|
| Bản chính https://kiemsoatnoibolemon.onrender.com | `v123` (commit `37d9b0a`, 23/11/2026) | Đăng nhập Face ID kiểu app ngân hàng, khóa ứng dụng, Trợ lý AI v2, thiết bị đang đăng nhập, ẩn Quy trình/Nhân sự với nhân viên |
| Bản thử https://kiemsoatnoibo-thu.onrender.com | `v124-thu` (cùng mã với bản chính) | Chờ đợt nâng cấp tiếp theo |

Nhánh khôi phục database đã tạo trên Neon: `khoi-phuc-truoc-v121-20261115`, `khoi-phuc-truoc-v122-20261115`, `khoi-phuc-truoc-v123-20261123` (xóa khi bản chính chạy ổn lâu dài).

## Việc cần chủ phần mềm làm

Không dán khóa hay mật khẩu vào khung chat. Chỉ dán vào đúng ô trên Render.

### 1. Khóa Groq cho bản thử (để thử Trợ lý AI v2)
1. https://console.groq.com → đăng nhập.
2. Settings → Billing: giữ gói **Free**, không nhập thẻ.
3. Settings → Data Controls: bật **Zero Data Retention** (nếu có).
4. API Keys → Create API Key, tên `ksnb-ban-thu` → Copy chuỗi `gsk_...` (chỉ hiện một lần).
5. https://dashboard.render.com → dịch vụ **`kiemsoatnoibo-thu`** (không phải `kiemsoatnoibolemon`) → Environment → thêm:
   - `GROQ_API_KEY` = chuỗi `gsk_...`
   - `GROQ_FREE_ZDR_CONFIRMED` = `1`
   - `STAGING_ALLOW_GROQ` = `1`
6. Save Changes, chờ khoảng 3 phút, báo "đã dán khóa Groq bản thử".

### 2. Khóa Groq cho bản chính
Chỉ **kiểm tra**: Render → `kiemsoatnoibolemon` → Environment, có dòng `GROQ_API_KEY` chưa. Khi phát hành `v123`, nếu chưa có thì tạo khóa thứ hai `ksnb-ban-chinh` và thêm `GROQ_API_KEY`, `GROQ_FREE_ZDR_CONFIRMED=1`. **Không** thêm `STAGING_ALLOW_GROQ` vào bản chính.

### 3. Gmail thử cho Google Drive (mục 4.4)
Tạo Gmail mới chỉ để thử (ví dụ `ksnb.thu.drive@gmail.com`), tạo thư mục Drive `KSNB thu`. Bước tạo ứng dụng Google Cloud sẽ hướng dẫn sau.

### 4. Gmail gửi thư thông báo (mục 4.8, chỉ khi muốn dùng email)
1. Dùng Gmail riêng (ví dụ `thongbao.ksnb@gmail.com`).
2. https://myaccount.google.com/security → bật Xác minh 2 bước.
3. https://myaccount.google.com/apppasswords → App name `KSNB` → Create → giữ mật khẩu 16 ký tự.
4. Nhân viên cần có email trong hồ sơ tài khoản để nhận thư.

### 5. Tag phiên bản trên GitHub
https://github.com/DAO1811/Ki-m-so-t-n-i-b-/releases → Draft a new release → Choose a tag (gõ tên, chọn "Create new tag") → Target → Recent commits → chọn commit → Publish release.

| Tag | Commit | Ghi chú |
|---|---|---|
| `v120` | `7eb1e8d` | bỏ chọn "Set as the latest release" |
| `v121` | `2de2acb` | bỏ chọn "Set as the latest release" |
| `v122` | `ddf4b76` | để chọn "Set as the latest release" |

### 6. Mô tả nghiệp vụ Nhân sự (4.1) và Quy trình (4.2)
**Nhân sự:** thông tin cần lưu; có danh sách phòng ban/chức vụ không; nghỉ phép; chấm công; ai được xem/sửa; thông tin nào chỉ Admin xem (lương, CCCD…).

**Quy trình** (mỗi quy trình): tên; ai lập; các bước duyệt theo thứ tự; các ô thông tin và tệp đính kèm; duyệt xong thì lưu hay báo cho ai. Có mẫu giấy Word/Excel thì chụp gửi.

### 7. Thử và duyệt `v123-thu`
Thử theo [nghiem-thu/v123-thu.md](nghiem-thu/v123-thu.md) (phần AI cần làm việc 1 trước). Mọi dòng đạt thì báo "Đạt v123-thu, phát hành".

## Việc phía phát triển còn lại (chưa bắt đầu, chờ chủ phần mềm cho làm tiếp)

| Mục | Nội dung |
|---|---|
| 4.5 | Sao lưu tự động mỗi đêm (mã hóa) và thử phục hồi định kỳ, không dùng dịch vụ trả phí |
| 4.7 | Gọi điện khác mạng (máy chủ trung chuyển TURN miễn phí); cần chủ phần mềm tạo tài khoản dịch vụ |
| 4.8 | Email thông báo phiếu chờ duyệt / bị trả về sửa (tắt mặc định, cần việc 4) |
| 4.4 | Cho bản thử nối Google Drive thử (cần việc 3) |
| Đợt 2 | Sắp xếp mã nguồn, định dạng, tổ chức tài liệu, mẫu GitHub |
| Đợt 3 | Giao diện: tìm nhanh toàn hệ thống, bảng thành thẻ trên điện thoại, khu "Việc của tôi" |
| 4.1, 4.2 | Nhân sự, Quy trình (cần việc 6) |
| Bảo vệ nhánh `main` | Chủ repository tự bật trên GitHub (Settings → Rules) |
