# Bảng nghiệm thu – Hiển thị phiên bản (v122-thu)

**Phiên bản thử:** `v122-thu` (bản chính đang là `v121`) · **Commit:** xem `/healthz/` của bản thử (`release`) · **Đường dẫn bản thử:** https://kiemsoatnoibo-thu.onrender.com · **Tài khoản thử:** `thu_admin`, `thu_nguoilap` · **Ngày gửi:** 15/11/2026

Quy ước đánh số (chủ phần mềm chốt ngày 15/11/2026): bản chính hiện đúng số đang dùng; bản thử hiện số bản chính + 1 kèm "-thu".

## Phần A – Chức năng mới

| STT | Chức năng / thao tác | Cách thử | Kết quả mong đợi | Kết quả (Đạt / Không đạt) | Ghi chú của chủ phần mềm |
|---|---|---|---|---|---|
| A1 | Trang đăng nhập | Mở bản thử trên máy tính và điện thoại | Trong khung đăng nhập, dưới "Cần hỗ trợ?", có "Phiên bản v122-thu" | | |
| A2 | Menu trái | Đăng nhập `thu_admin`, nhìn dưới tên tài khoản ở góc dưới menu trái | Có "Phiên bản v122-thu" | | |
| A3 | Chân trang | Mở Tổng quan, Tồn kho, kéo xuống cuối trang | Có "DHD · Kiểm soát nội bộ · Phiên bản v122-thu" | | |
| A4 | Tài khoản nhân viên | Đăng nhập `thu_nguoilap` | Cũng thấy số phiên bản như trên | | |

## Phần B – Hồi quy (rút gọn vì chỉ đổi giao diện hiển thị)

| STT | Chức năng / thao tác | Cách thử | Kết quả mong đợi | Kết quả | Ghi chú |
|---|---|---|---|---|---|
| B1 | Đăng nhập, menu theo quyền | Đăng nhập `thu_admin`, rồi `thu_chixem` | Vào đúng trang, menu đúng quyền | | |
| B2 | Lập và duyệt phiếu | `thu_nguoilap` lập phiếu nhập, `thu_nguoiduyet` duyệt | Tồn tăng đúng | | |
| B3 | Khóa đăng nhập (v121) | Sai mật khẩu `thu_chixem` 5 lần, `thu_admin` mở khóa | Hoạt động như v121 | | |
| B4 | Điện thoại | Mở bản thử trên điện thoại | Không vỡ bố cục | | |

**Kết luận của chủ phần mềm:** ☐ Đạt – cho phát hành `v122-thu` · ☐ Không đạt – sửa: `____`

Bằng chứng phía phát triển: kiểm thử tự động PostgreSQL đạt toàn bộ; chỉ đổi 3 tệp giao diện (`templates/base.html`, `templates/login.html`, `static/login.css`) và thêm 1 bài kiểm thử.
