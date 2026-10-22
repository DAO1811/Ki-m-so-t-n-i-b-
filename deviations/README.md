# Phân hệ Xử lý sai lệch

Bản nền theo khung đã được duyệt ngày 22/10/2026. Chỉ bổ sung chức năng mới; không đổi quy trình, dữ liệu tồn, chứng từ, Excel, QR, kiểm kê hoặc giao diện của phân hệ kho.

## Cấu trúc bảo trì

| Thành phần | Trách nhiệm |
| --- | --- |
| `models.py`, `migrations/` | Các bảng riêng `deviations_*`; mã hồ sơ, hành động, đánh giá, tệp, đề nghị gia hạn, lịch sử và quy tắc |
| `constants.py` | Mã trạng thái ổn định và các quyền/route của phân hệ |
| `workflow.py` | Một bảng khai báo các bước, điều kiện chuyển và quyền cần có |
| `services/cases.py` | Ghi nhận, bổ sung, phân công và xác minh |
| `services/workflow.py` | Chuyển bước và đánh giá hiệu quả trong giao dịch |
| `services/actions.py` | Kế hoạch, thực hiện, đề nghị và quyết định gia hạn |
| `services/policies.py` | Cấu hình có phiên bản; không tự suy ra quy tắc từ tài liệu tham khảo |
| `access.py` | Quyền xem, người phụ trách, người thực hiện và điều kiện xác nhận |
| `storage.py` | Adapter ảnh/PDF dùng hạ tầng Drive riêng tư đã có |
| `selectors.py` | Truy vấn danh sách, bộ lọc, thống kê; không ghi nghiệp vụ |
| `forms.py`, `views.py`, `mutations.py`, `configuration.py` | Biên HTTP, kiểm tra dữ liệu nhập và hiển thị; chuyển mọi ghi nghiệp vụ tới services |
| `navigation.py`, `templates/deviations/`, `assets/styles/deviations.css` | Menu và giao diện riêng; CSS giới hạn bằng tiền tố của phân hệ |
| `tests/` | Phân quyền, luồng, tệp, tính toàn vẹn, gửi lặp và tranh chấp PostgreSQL |

Không tách microservice, không thêm dịch vụ trả phí, không sao chép mật khẩu hoặc dữ liệu sản xuất để tạo mẫu.

## Các lựa chọn còn chờ công ty chốt

- Mặc định `WorkflowPolicy.enabled=False`. Nhân viên có quyền tạo được lập nháp, bổ sung bằng chứng và gửi ghi nhận. Chưa tự chạy các bước tiếp nhận/xác minh/kế hoạch/thực hiện/đánh giá.
- Admin chỉ mở xử lý sau khi chọn rõ cấp xác nhận tối thiểu, tính độc lập và yêu cầu cao cấp hơn người lập. Không có SLA, số lần gia hạn hoặc thời hạn chung lấy sẵn từ PDF.
- `max_extensions=NULL`: chưa mở gia hạn; `0`: không gia hạn. Hạn cũ giữ nguyên đến khi đề nghị được đồng ý.
- Cấu hình được chụp khi tiếp nhận lần đầu. Thay cấu hình không viết lại quy tắc của hồ sơ cũ. Tắt xử lý tạm dừng các bước tiếp theo của mọi hồ sơ; ghi nhận vẫn mở.
- Bản nền có báo cáo số hồ sơ, chờ tiếp nhận, chưa kết thúc, có công việc quá hạn, đã kết thúc và tổng hợp theo nhóm. Phân tích xu hướng, tái diễn, thời gian và SLA chi tiết cần bổ sung khi quy trình được chốt.
- Chưa gửi email, chưa gán chế tài, chưa kết nối nghiệp vụ Quy trình/Nhân sự. Phân hệ này không tạo, sửa hoặc duyệt phiếu kho.

## Bất biến nghiệp vụ

1. Mọi nhân viên đăng nhập hoạt động xem được toàn bộ hồ sơ theo quyết định của chủ phần mềm. Không tự được cấp quyền xem phiếu nguồn trong kho.
2. Bốn quyền ghi riêng: `deviations_create`, `deviations_manage`, `deviations_work`, `deviations_review`. Không cấp tự động cho tài khoản cũ. Admin toàn quyền nhưng tự xác nhận việc liên quan mình cần checkbox cảnh báo và lưu dấu xác nhận.
3. Sau khi gửi ghi nhận, báo cáo không sửa trực tiếp; chỉ bổ sung khi được yêu cầu. Kế hoạch đã xác nhận không đổi trực tiếp. Công việc đã hoàn thành giữ kết quả. Không có API xóa hồ sơ/tệp gốc.
4. Mã `SL-năm-ID` giữ nguyên trong vòng đời. Đánh giá chưa hiệu quả tăng lượt và bổ sung hành động trong cùng hồ sơ. Lượt trước giữ nguyên.
5. Ghi nghiệp vụ dùng transaction, khóa hồ sơ trước và đối chiếu revision. Khóa tài khoản theo thứ tự ID, đọc lại quyền hiện hành. Gửi lặp hoặc màn hình cũ không ghi đè bản mới. Đánh dấu hồ sơ trùng khóa cả hai hồ sơ theo ID để ngăn liên kết vòng do tranh chấp.
6. Đánh giá và xác nhận kết thúc là bước riêng, chỉ sau khi hành động của lượt hiện tại đã hoàn thành và không còn đề nghị gia hạn chờ. Không dùng ngày đánh giá tương lai.
7. Các liên kết nguồn là tùy chọn `SET_NULL`; không tạo ràng buộc cấm xóa dữ liệu cũ ngoài các quy tắc vốn có. Lịch sử vẫn lưu ID nguồn đã ghi nhận.
8. Tệp nhận JPG/PNG/WebP/PDF được kiểm tra nội dung, tối đa 8 MB/tệp, 50 tệp/hồ sơ. Tệp không sử dụng vẫn giữ bản gốc và lý do. Đọc có kiểm tra SHA-256, không cache công khai.
9. Drive sử dụng nhánh `XuLySaiLech/<năm>/<mã hồ sơ>` dưới thư mục riêng đã kết nối; không đổi thư mục hàng hóa/hóa đơn. Database giữ metadata; bytes chỉ dùng trong môi trường DEBUG với provider database. Drive lỗi không tự lưu bytes vào database sản xuất.

## Khi thay đổi sau này

- Đổi nhãn hiển thị: sửa choices/label, giữ nguyên mã trạng thái đã lưu.
- Thêm trường: tạo migration **trong app deviations**; không sửa migration đã phát hành. Chọn trường theo bước, whitelist service, lịch sử và kiểm thử tương ứng.
- Thêm bước: sửa registry trong `workflow.py`, guard/service và quyền route, sau đó thêm kiểm thử chuyển hợp lệ/bị từ chối. Không ghi trạng thái trực tiếp từ view.
- Thay ý nghĩa quy tắc: thêm phiên bản schema mới và xử lý tương thích; không sửa JSON của hồ sơ đã tiếp nhận.
- Thay nhà lưu trữ: thay adapter `storage.py`; không đưa SDK, HTTP hay bí mật vào logic trạng thái.

## Kiểm tra và phát hành

Chạy trên PostgreSQL thử riêng:

```sh
python manage.py test deviations core inventory.test_module_navigation --noinput
python manage.py test --noinput
ruff check .
python scripts/build_styles.py --check
python manage.py makemigrations --check --dry-run
```

Chạy thử giao diện bằng Python và PostgreSQL riêng theo README gốc. Chỉ push nhánh preview; không merge main hoặc gọi deploy trước khi chủ phần mềm xem và chấp thuận đúng bản thử. Tệp Drive thực tế cần kiểm tra đọc/ghi trong môi trường thử đã được chủ thư mục cấp quyền; kiểm thử tự động giả lập HTTP không thay thế bước này.
