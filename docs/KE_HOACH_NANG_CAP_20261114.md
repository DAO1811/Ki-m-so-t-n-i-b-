# Kế hoạch nâng cấp và chỉnh sửa – rà soát ngày 14/11/2026

Rà soát trên commit `7eb1e8d` (đang là `main`). Kiểm thử trên PostgreSQL thử riêng: 513/514 bài đạt, 1 bài lỗi chập chờn. Lint, CSS, migration, JavaScript đều đạt.

## Bản chính luôn hoạt động bình thường trong khi nâng cấp và thử

Trong suốt thời gian sửa mã, dựng bản thử và chủ phần mềm thử, **nhân viên vẫn dùng bản chính như thường**. Bắt buộc:

- Mọi việc sửa và thử chỉ làm trên nhánh riêng, dịch vụ bản thử riêng và database thử riêng. **Không deploy, không migrate, không đổi biến môi trường của dịch vụ chính** `kho-viet` và database công ty khi chưa có "Đạt <nhãn>".
- Bản thử không dùng chung database, Drive, email, khóa API hay tên miền với bản chính. Tạo và xóa bản thử không ảnh hưởng bản chính.
- Không push trực tiếp vào `main`. Bản chính có thể tự deploy khi `main` thay đổi, nên chỉ merge vào `main` lúc phát hành đã được duyệt.
- Kiểm tra lại cấu hình Render của dịch vụ chính trước khi tạo bản thử: dịch vụ chính chỉ theo dõi nhánh `main`, dịch vụ thử chỉ theo dõi nhánh `staging`.

**Lúc phát hành** (chỉ sau khi chủ phần mềm báo Đạt):
- Chọn giờ ít người dùng, báo trước cho nhân viên. Có thể có vài phút chậm hoặc gián đoạn khi Render khởi động lại.
- Kiểm tra bản sao lưu database (snapshot trước nâng cấp của `safe_migrate`) trước khi phát hành.
- Thay đổi database phải tương thích ngược: chỉ thêm bảng hoặc cột, không xóa hay đổi tên dữ liệu đang dùng trong cùng một lần phát hành. Nhờ vậy, nếu phải quay về phiên bản trước thì dữ liệu nhân viên đã nhập vẫn còn nguyên.
- Sau khi phát hành, kiểm `/healthz/` đúng phiên bản và chạy nhanh vài dòng trong Bảng nghiệm thu trên bản chính.

## Bảng nghiệm thu bắt buộc cho mỗi lần nâng cấp

**Mỗi lần nâng cấp hoặc chỉnh sửa đều phải có bản thử chạy thật kèm Bảng nghiệm thu.** Không có bảng thì không được đề nghị phát hành.

Quy trình:
1. Làm xong, đưa lên bản thử với nhãn phiên bản (ví dụ `v121-thu`).
2. Gửi chủ phần mềm: đường dẫn bản thử, tài khoản thử, và **Bảng nghiệm thu** đã điền sẵn các cột 1–4 (theo mẫu dưới).
3. Chủ phần mềm tự bấm thử trên bản thử, điền cột "Kết quả": **Đạt** hoặc **Không đạt**, kèm ghi chú.
4. Có dòng **Không đạt** thì sửa, đưa bản thử mới (`v121-thu2`), gửi lại **toàn bộ bảng** để thử lại từ đầu.
5. Chỉ khi **mọi dòng đều Đạt** và chủ phần mềm báo **"Đạt v121-thu2"** thì mới merge đúng commit đó vào `main`, triển khai bản chính và gắn tag `v121`.
6. Sau khi lên bản chính, chủ phần mềm kiểm nhanh lại 3–5 dòng quan trọng trên bản chính. Có sự cố thì quay về phiên bản trước.
7. Lưu bảng đã điền vào `docs/nghiem-thu/<phiên bản>.md` và ghi tóm tắt vào `CHANGELOG.md`.

Bảng gồm hai phần:
- **Phần A – Chức năng mới hoặc vừa sửa**: mỗi thay đổi ít nhất một dòng, gồm cả trường hợp đúng và trường hợp sai hoặc bị chặn (ví dụ nhập sai mật khẩu, tài khoản không có quyền).
- **Phần B – Kiểm tra chức năng cũ vẫn chạy (hồi quy)**: luôn có, kể cả khi thay đổi nhỏ.

### Mẫu Bảng nghiệm thu

**Phiên bản thử:** `v___-thu__` · **Commit:** `_______` · **Đường dẫn bản thử:** `_______` · **Tài khoản thử:** `_______` · **Ngày gửi:** `__/__/____`

| STT | Chức năng / thao tác | Cách thử (bấm gì, nhập gì) | Kết quả mong đợi | Kết quả (Đạt / Không đạt) | Ghi chú của chủ phần mềm |
|---|---|---|---|---|---|
| A1 | | | | | |
| A2 | | | | | |
| B1 | Đăng nhập | Đăng nhập bằng tài khoản Admin thử, sau đó bằng nhân viên thử | Vào đúng trang, menu đúng theo quyền | | |
| B2 | Lập và duyệt phiếu nhập | Nhân viên lập phiếu nhập 2 mặt hàng, người duyệt cấp cao hơn duyệt | Phiếu ghi sổ, tồn kho tăng đúng số | | |
| B3 | Phiếu xuất / chuyển kho | Lập phiếu xuất 1 mặt hàng, duyệt | Tồn giảm đúng, không xuất quá tồn | | |
| B4 | Tồn kho và sổ kho | Mở Tồn kho, Sổ kho, lọc theo kho | Số khớp với các phiếu vừa làm | | |
| B5 | Kiểm kê | Mở phiên kiểm kê, nhập số đếm, nộp | Hiện chênh lệch, khóa giao dịch kho trong phiên | | |
| B6 | Mượn – trả | Tạo phiếu trả hàng mượn | Tồn khả dụng đúng | | |
| B7 | Nhập Excel | Tải mẫu, nhập file mẫu 3 dòng | Xem trước đúng, tạo phiếu nháp | | |
| B8 | Xử lý sai lệch | Tạo hồ sơ sai lệch, chuyển duyệt | Đúng bước, đúng người duyệt | | |
| B9 | Chat nội bộ | Gửi tin nhắn giữa 2 tài khoản thử | Nhận được, đúng người | | |
| B10 | Trợ lý AI tra cứu | Hỏi "Tồn <mã hàng thử>" bằng tài khoản có và không có quyền | Có quyền thấy số, không quyền bị chặn | | |
| B11 | Phân quyền | Nhân viên chỉ xem thử vào trang lập phiếu | Bị chặn | | |
| B12 | Điện thoại | Mở bản thử trên điện thoại, lập 1 phiếu | Dùng được, không vỡ bố cục | | |

**Kết luận của chủ phần mềm:** ☐ Đạt toàn bộ – cho phát hành `v___-thu__` · ☐ Không đạt – sửa các dòng: `____`

Phần B được rà lại mỗi lần cho đúng màn hình đang có. Không bỏ dòng nào khi chưa có lý do ghi rõ.

## Quy tắc chung cho mọi đợt (bắt buộc)

- Tuân thủ `AGENTS.md`. Mỗi đợt làm trên **nhánh riêng, một pull request riêng**, không merge vào `main`, không triển khai bản chính.
- Không ghi vào database công ty, không nối Drive hoặc email thật. Dùng PostgreSQL thử riêng cùng tài khoản và dữ liệu thử.
- Trước khi đề nghị duyệt phải chạy đủ, và báo kết quả thật:
  `ruff check .` · `python scripts/build_styles.py --check` · `node --check static/*.js` · `python manage.py check` · `python manage.py makemigrations --check --dry-run` · `python manage.py test --noinput` (PostgreSQL) · `python manage.py collectstatic --noinput`.
- Mỗi thay đổi có kiểm thử mới và kiểm thử hồi quy bảo vệ chức năng cũ. Rà soát diff, không có thay đổi ngoài phạm vi.
- Gửi chủ phần mềm đường dẫn bản thử, tài khoản thử và **Bảng nghiệm thu** (mục trên), kèm ảnh chụp từ bản chạy thật có ghi rõ commit và dữ liệu thử. Chỉ phát hành khi chủ phần mềm báo **Đạt** đúng phiên bản đã thử.
- Không viết lại lịch sử Git, không sửa ngày giờ hay tác giả của commit cũ.

---

## ĐỢT 0 – Dựng bản thử (staging) và đánh số phiên bản (làm đầu tiên)

Mục tiêu: mọi thay đổi từ Đợt 1 trở đi đều lên **bản thử** cho chủ phần mềm dùng thử trước. Chỉ khi chủ phần mềm đồng ý đúng phiên bản đã thử thì mới đưa lên bản chính.

### Quy trình phát hành áp dụng từ đợt này
1. Bản chính đang chạy phiên bản `vN`, ví dụ `v120`.
2. Mỗi yêu cầu nâng cấp làm trên nhánh riêng. Bản dựng để thử gắn nhãn `vN+1-thu`, sửa tiếp thì thành `-thu2`, `-thu3`…
3. Đưa nhánh lên bản thử (nhánh `staging`). Chủ phần mềm dùng thử như thật.
4. Chủ phần mềm thử theo **Bảng nghiệm thu**. Chỉ khi mọi dòng Đạt và chủ phần mềm báo "Đạt v121-thu2" thì mới merge đúng commit đó vào `main` và gắn tag `v121` trên đúng commit đó.
5. Gặp sự cố trên bản chính thì quay về tag trước đó (`v120`). Ghi hướng dẫn quay lại vào `docs/dev/RELEASE_PROCESS.md`.

### 0.1 Nhận diện bản thử trong phần mềm (sửa mã nhỏ)
- Thêm biến môi trường `APP_ENVIRONMENT` (`production` hoặc `staging`, mặc định `production`) và `APP_VERSION`, ví dụ `v121-thu2`.
- Khi là `staging`: hiện dải chữ cố định **"BẢN THỬ – <phiên bản> – không nhập dữ liệu thật"** ở mọi trang, kể cả trang đăng nhập. Thêm "[THỬ]" vào tiêu đề tab trình duyệt.
- Khi là `staging`, chặn cứng kết nối Drive, gửi email và Groq. Chặn ngay cả khi lỡ khai báo khóa, và hiện thông báo "Bản thử không kết nối dịch vụ thật".
- `/healthz/` trả thêm `environment` và `version`. Chân trang Admin hiện số phiên bản.
- Kiểm thử: bản chính không hiện dải BẢN THỬ, giao diện và hành vi giữ nguyên. Bản thử hiện dải chữ và chặn đủ các kết nối ngoài.

### 0.2 Dữ liệu thử
- Lệnh mới, ví dụ `seed_staging`, nạp dữ liệu mẫu: vài kho, hàng hóa, phiếu ở các trạng thái, tài khoản thử theo từng cấp quyền (Admin, người lập, người duyệt, nhân viên chỉ xem).
- Lệnh này chỉ chạy được khi `APP_ENVIRONMENT=staging`. Đang ở `production` thì lệnh báo lỗi và dừng. Có kiểm thử cho việc chặn này.
- Không sao chép database công ty, kể cả bản ẩn danh.

### 0.3 Hạ tầng bản thử (cần chủ phần mềm đồng ý và tự xác nhận trên tài khoản của mình)
- Tạo **database Neon thử riêng**: project hoặc database mới, trống, không phải branch tách từ database công ty.
- Tạo **dịch vụ Render Free thứ hai**, ví dụ tên `kiemsoatnoibo-thu`, build từ nhánh `staging`, với các biến:
  `APP_ENVIRONMENT=staging`, `APP_VERSION=…`, `DEBUG=0`, `SECRET_KEY` mới, `DATABASE_URL` của database thử, `PRIVATE_MEDIA_PROVIDER=database`, **không** đặt khóa Google, Groq hay TURN, `PASSKEY_RP_ID` là tên miền của bản thử.
- Có thể thêm `staging` vào `render.yaml` hoặc tạo tay trên Render. Phải chắc chắn không đổi cấu hình dịch vụ chính `kho-viet`.
- Ghi rõ: Render Free sẽ ngủ khi không dùng, lần mở đầu chậm. Kiểm tra lại điều kiện gói Free hiện hành của Render và Neon trước khi tạo, không hứa hạn mức.

### 0.4 Đánh số phiên bản
- Chốt với chủ phần mềm số phiên bản hiện tại của bản chính (ví dụ `v1.0.0` hoặc theo cách đếm của chủ phần mềm), rồi gắn tag cho commit đang chạy production.
- Ghi mỗi lần phát hành vào `CHANGELOG.md`: phiên bản, ngày, nội dung thay đổi bằng tiếng Việt dễ hiểu, nhãn bản thử đã được duyệt.
- Thêm mục "Phiên bản đã thử và được duyệt" vào mẫu pull request.

### Nghiệm thu Đợt 0
- Chủ phần mềm mở được địa chỉ bản thử trên máy tính và điện thoại, đăng nhập bằng tài khoản thử, thấy dải BẢN THỬ và đúng số phiên bản.
- `/healthz/` của bản chính và bản thử trả đúng `environment` và `version`.
- Bản chính không thay đổi gì ngoài thông tin phiên bản (kiểm bằng toàn bộ kiểm thử và ảnh chụp trước/sau).

---

## ĐỢT 1 – Sửa lỗi và rủi ro an toàn

### 1.1 Bài kiểm thử lỗi chập chờn
- Tệp: `ai_assistant/tests.py`, bài `test_catalog_permission_never_reveals_quantity` (dòng ~122).
- Nguyên nhân: kiểm tra "999" không xuất hiện trong câu trả lời, nhưng mã QR ngẫu nhiên (`inventory/product_codes.py:11`, `uuid4().hex`) đôi khi chứa "999".
- Sửa: dùng số tồn thử không thể nằm trong chuỗi hex, ví dụ `987654.321`, hoặc kiểm tra theo trường số tồn thay vì tìm chuỗi. Không giảm mức kiểm tra quyền.
- Nghiệm thu: chạy bài này 200 lần liên tiếp đều đạt.

### 1.2 Bật chế độ gỡ lỗi nhầm khi triển khai Docker ngoài Render
- Tệp: `config/settings.py:10`, `Dockerfile`.
- Hiện trạng: thiếu `RENDER_EXTERNAL_HOSTNAME` và `DEBUG` thì phần mềm tự bật `DEBUG=1`, kéo theo khóa bí mật mặc định, SQLite trong container và trang lỗi chi tiết.
- Sửa: mặc định `DEBUG=0` khi không khai báo. Thêm `ENV DEBUG=0` vào Dockerfile. Máy phát triển và CI vẫn đặt `DEBUG=1` như README và `ci.yml` đang làm. Cập nhật hướng dẫn chạy máy phát triển.
- Kiểm thử: thiếu biến thì `DEBUG=False` và báo lỗi nếu thiếu `SECRET_KEY` hoặc PostgreSQL. Bản Render hiện tại không đổi hành vi.

### 1.3 Chặn dò mật khẩu ở trang đăng nhập
- Tệp: `config/urls.py` (đang dùng `LoginView` mặc định).
- Hiện trạng: passkey có giới hạn thử, đăng nhập mật khẩu thì không. Chủ phần mềm cho phép mật khẩu tự do (`AUTH_PASSWORD_VALIDATORS = []`), giữ nguyên lựa chọn này.
- Sửa: giới hạn số lần sai theo tài khoản và theo IP, ví dụ 5 lần trong 15 phút thì khóa tạm 15 phút. Đếm trong bảng dữ liệu riêng của phần đăng nhập, không dùng cache trong RAM vì có 2 worker. Báo lỗi chung, không tiết lộ tài khoản có tồn tại hay không. Đăng nhập đúng thì xóa bộ đếm. Ghi nhật ký quản trị, không ghi mật khẩu. Thêm lệnh dọn dữ liệu cũ.
- IP lấy từ `X-Forwarded-For` của Render theo cách an toàn, chỉ tin proxy đầu tiên.
- Kiểm thử: khóa đúng ngưỡng, hết hạn thì mở, không ảnh hưởng passkey và các phiên đang đăng nhập.

### 1.4 Thông báo sai trong `bootstrap_admin`
- Tệp: `inventory/management/commands/bootstrap_admin.py`.
- `validate_password` không bao giờ chặn vì danh sách kiểm tra trống, nhưng mã vẫn có thông báo "mật khẩu chưa đủ mạnh". Thêm yêu cầu tối thiểu riêng cho mật khẩu Admin đầu tiên, ví dụ ≥ 12 ký tự, chỉ áp dụng cho lệnh này. Không đổi chính sách mật khẩu của nhân viên.

### 1.5 Giới hạn thời gian xử lý không thống nhất
- `start.sh` (Render) chạy Gunicorn mặc định 30 giây, `Dockerfile` đặt 120 giây. Thêm `--timeout 120` vào `start.sh` để nhập Excel lớn và xuất báo cáo Drive không bị cắt. Nên gom lệnh khởi động về một nơi (`start.sh`) để Dockerfile gọi lại.

### 1.6 Mã phiên bản sai ở `/healthz/`
- Tệp: `config/health.py`. Khi thiếu `RENDER_GIT_COMMIT` thì đang trả nhãn cũ `"admin-function-permissions"`. Đổi thành `"unknown"`. Cập nhật kiểm thử liên quan.

### 1.7 Mã thư mục Drive ghi cứng
- Tệp: `config/settings.py` (`GOOGLE_DRIVE_EXPECTED_FOLDER_ID`).
- **Kiểm tra trước** hosting Render đã khai báo biến này chưa. Chỉ bỏ giá trị mặc định khi chủ phần mềm xác nhận đã đặt biến trên Render. Nếu chưa, ghi lại và hỏi chủ phần mềm, không tự đổi.

### 1.8 Kiểm thử trên SQLite
- 2 lỗi chỉ xảy ra trên SQLite: bảng `chat_message` bị khóa, và trang dung lượng thiếu chữ "1 GB" trong `inventory/test_storage.py:122`. Đánh dấu bỏ qua có lý do khi chạy SQLite, hoặc sửa cho chạy được. Không ảnh hưởng kết quả trên PostgreSQL.

### 1.9 Nhắc bảo mật khi dùng Groq Free
- Thêm dòng nhắc rõ trong khung trò chuyện Groq: không dán dữ liệu khách hàng, giá vốn hay mật khẩu. Không đổi luồng đồng ý, hạn mức và quyền hiện có.

---

## ĐỢT 2 – Sắp xếp mã nguồn theo chuẩn nhóm phát triển chuyên nghiệp

Mục tiêu: kho mã gọn, nhất quán, dễ bàn giao cho lập trình viên khác. **Chỉ sắp xếp và định dạng, không đổi hành vi.** Mỗi mục là một PR riêng để dễ rà soát.

### 2.1 Công cụ định dạng và quy ước chung
- Thêm `.editorconfig`, cấu hình `ruff format` (Python), `djlint` (template Django), `prettier` (JS/CSS nguồn trong `assets/styles/`, không đụng `static/vendor`).
- Thêm `pre-commit` và chạy các công cụ trên trong CI.
- Thêm `CONTRIBUTING.md`: quy ước đặt tên nhánh (`feat/…`, `fix/…`, `chore/…`), lời commit theo Conventional Commits (`feat:`, `fix:`, `refactor:`, `docs:`, `test:`), mỗi commit một việc.

### 2.2 Định dạng lại template HTML
- Hiện có 144 dòng HTML dài trên 200 ký tự. Ví dụ `templates/stocktake_paper.html` có 15 dòng nhưng chứa cả form lớn.
- Dùng `djlint` định dạng từng nhóm màn hình (kho, kiểm kê, sai lệch, chat…), mỗi nhóm một commit.
- Nghiệm thu: toàn bộ kiểm thử đạt, ảnh chụp trước và sau mỗi màn hình giống nhau.

### 2.3 Ghi chú trong mã
- Viết lại các ghi chú kiểu lời dặn ("Never…", "Only our…", "Owner-confirmed…") thành ghi chú kỹ thuật ngắn: lý do thiết kế, ràng buộc, đường dẫn tài liệu. Dùng thống nhất một ngôn ngữ (đề xuất tiếng Anh cho mã, tiếng Việt cho giao diện và tài liệu).
- Thêm docstring ngắn cho các hàm nghiệp vụ chính trong `inventory/services.py`, `deviations/services/`, `chat/services.py`.

### 2.4 Tổ chức tài liệu
- Tách `docs/` thành:
  - `docs/user/`: hướng dẫn sử dụng (`HUONG_DAN.md`, `WORKSPACE_GUIDE.md`, kiểm kê, Excel…)
  - `docs/dev/`: kiến trúc, triển khai, phát hành, quyền
  - `docs/archive/`: các báo cáo `*_VALIDATION.md`, `RELEASE_2026_10_16.md`, `PASSKEY_VERIFICATION_*.md`, đề xuất cũ
  - `docs/images/`: ảnh minh họa còn dùng; ảnh xem thử cũ chuyển vào `archive`
- Sửa toàn bộ liên kết trong README và các tài liệu. Kiểm tra không còn link hỏng.
- Viết lại README ngắn gọn: giới thiệu, ảnh màn hình, cài đặt, chạy thử, cấu trúc, liên kết tài liệu.
- Giữ nguyên `AGENTS.md` (quy tắc của chủ phần mềm), không xóa.

### 2.5 Quản lý phiên bản
- Thêm `CHANGELOG.md` bằng tiếng Việt, viết lại từ lịch sử hiện có theo các mốc đã phát hành.
- Đề xuất gắn tag `v1.0.0` cho commit đang chạy production (chờ chủ phần mềm xác nhận), từ đó tăng phiên bản theo SemVer.
- Hiển thị số phiên bản ở chân trang Admin và trong `/healthz/`.

### 2.6 Cấu hình GitHub cho làm việc nhóm
- Thêm `.github/pull_request_template.md` (mục: Mục đích, Phạm vi, Kiểm thử, Ảnh bản thử, Rủi ro), `.github/ISSUE_TEMPLATE/` (báo lỗi, đề xuất), `CODEOWNERS`.
- Nhắc chủ phần mềm bật quy tắc bảo vệ nhánh `main` (bắt buộc CI đạt và có duyệt). Workflow không tự đổi cấu hình này.
- Thống nhất tên tác giả cho commit **từ nay về sau** (`git config user.name`). Không sửa commit cũ.

### 2.7 Tệp lớn trong Git (tùy chọn, cần chủ phần mềm đồng ý)
- `static/vendor/transformers-3.8.1` (22 MB) và `static/chat-assets` (3 MB) đang nằm thẳng trong Git. Phương án: tải lúc build và kiểm SHA-256 (đã có `PROVENANCE.json`), hoặc dùng Git LFS. Chỉ làm sau khi chốt mục 4.6 (có giữ AI trong trình duyệt hay không).

### 2.8 Thứ tự mã trong từng app
- Rà các app cho thống nhất: `models.py`, `services/`, `views/`, `forms.py`, `urls.py`, `tests/`. Ví dụ `inventory` đang để 25 tệp `test_*.py` ở thư mục gốc của app, nên chuyển vào `inventory/tests/`.
- Không đổi tên bảng, không đổi migration, không đổi URL đang dùng.

---

## ĐỢT 3 – Bố cục và giao diện cho dễ dùng, chuyên nghiệp

**Làm theo thứ tự: chụp hiện trạng → đề xuất → chủ phần mềm duyệt → mới thực hiện.**

### 3.1 Khảo sát hiện trạng
- Chụp toàn bộ màn hình trên máy tính (1440px) và điện thoại (390px), chế độ sáng và tối, với tài khoản Admin và tài khoản nhân viên ít quyền. Dùng dữ liệu thử.
- Lập danh sách vấn đề: menu, tiêu đề trang, vị trí nút, bảng tràn ngang, trạng thái trống, thông báo lỗi, chỗ nút trợ lý AI che nội dung.

### 3.2 Đề xuất bố cục (gửi ảnh phác thảo từ bản chạy thử để duyệt)
- Menu bên trái gom theo phân hệ: Tổng quan · Kho (Danh mục, Phiếu, Tồn kho, Kiểm kê, Mượn trả, Báo cáo) · Sai lệch · Chat · Quản trị. Thu gọn được trên điện thoại.
- Phân hệ chưa có nghiệp vụ (Quy trình, Nhân sự): ẩn với nhân viên, hoặc gắn nhãn "Sắp có", tùy chủ phần mềm chọn.
- Mọi trang dùng cùng một khuôn: tiêu đề, đường dẫn (breadcrumb), nút chính ở góc phải, bộ lọc phía trên bảng.
- Bảng trên điện thoại chuyển thành dạng thẻ. Có thanh tìm nhanh toàn hệ thống (mã hàng, số phiếu).
- Trang tổng quan: việc chờ tôi duyệt, phiếu nháp của tôi, cảnh báo tồn, kiểm kê đang mở. Mỗi người chỉ thấy theo quyền.
- Giữ màu nhận diện vàng kim – bạc theo `docs/COMPANY_COLOUR_THEME.md`, giữ phân biệt màu trạng thái.

### 3.3 Thực hiện
- Sửa trong `assets/styles/` rồi build lại `static/app.css`. Không đổi quyền, dữ liệu hay luồng nghiệp vụ.
- Kiểm thử: toàn bộ kiểm thử cũ, kiểm thử phân quyền menu, kiểm tra bàn phím và độ tương phản, ảnh trước và sau từng màn hình.

---

## ĐỢT 4 – Chức năng chưa hoàn thành (cần chủ phần mềm chốt nghiệp vụ trước)

Không tự triển khai theo giả định. Với mỗi mục: viết đặc tả ngắn → chủ phần mềm duyệt → làm thành phân hệ và bảng dữ liệu riêng.

| # | Chức năng | Hiện trạng | Cần chủ phần mềm cung cấp |
|---|---|---|---|
| 4.1 | Quản lý nhân sự (`/human-resources/`) | Chỉ có trang báo; đề xuất trong `docs/HR_COMPANY_PROPOSAL.md` | Chọn phạm vi bản đầu (hồ sơ nhân viên, phòng ban, chức vụ…) |
| 4.2 | Quy trình (`/processes/`) | Chỉ có trang báo | Danh sách quy trình cần số hóa, các bước duyệt |
| 4.3 | Quản lý phiên đăng nhập | Mới là đề xuất | Đồng ý tính năng: xem thiết bị đang đăng nhập, đăng xuất từ xa khi nghỉ việc |
| 4.4 | Lưu và đọc tệp trên Google Drive thật | Kiểm thử mới dùng phản hồi giả lập | Thử trên tài khoản Drive thử riêng, sau đó chủ phần mềm tự xác nhận trên Drive thật |
| 4.5 | Sao lưu và thử phục hồi độc lập | Chưa có quy trình | Nơi lưu bản sao lưu, tần suất; viết lệnh và hướng dẫn phục hồi, thử trên database riêng |
| 4.6 | Trợ lý AI | Đang có 2 đường song song: Qwen trong trình duyệt (tải ~786 MB) và Groq Free | Chọn giữ cả hai hay một. Nếu giữ Qwen thì thử trên máy Windows 8 GB và báo tốc độ thật |
| 4.7 | Cuộc gọi trong chat | Chỉ có STUN, chưa có TURN; gọi khác mạng dễ lỗi | Có dùng máy chủ TURN miễn phí hoặc tự dựng không (không tạo dịch vụ trả phí) |
| 4.8 | Sửa phiếu qua email | Chưa có | Có cần không |

---

## Thứ tự đề xuất

0. Đợt 0: dựng bản thử và đánh số phiên bản. Từ đây mọi đợt sau đều lên bản thử cho chủ phần mềm dùng thử trước.
1. Đợt 1, mục 1.1 → 1.9 (có thể gom 1.1, 1.4, 1.5, 1.6, 1.8 vào một PR nhỏ; 1.2 và 1.3 mỗi mục một PR).
2. Đợt 2, mục 2.1 → 2.6, sau đó 2.8; mục 2.7 sau khi chốt 4.6.
3. Đợt 3 (chờ duyệt bố cục).
4. Đợt 4, từng chức năng theo đặc tả được duyệt.

Mỗi đợt kết thúc theo đúng quy trình: bản thử có nhãn → gửi Bảng nghiệm thu → chủ phần mềm thử và điền Đạt / Không đạt → mọi dòng Đạt và chủ phần mềm báo "Đạt <nhãn>" → phát hành và gắn tag.
