> Cập nhật 19/10/2026: đợt cấp duyệt mới dùng snapshot `dhd_backup_inventory_0017`, health yêu cầu migration 0017. Giữ nguyên snapshot 0016 trước đó. Khóa triển khai dùng chung `1811000016` giữa các phiên bản để không chạy migration đồng thời. [Chi tiết đợt này](APPROVAL_HIERARCHY.md).

# Bản chụp dữ liệu tự động trước nâng cấp

Theo yêu cầu ngày 17/10/2026 chủ dự án tự động cập nhật bản chính, bước giữ dữ liệu trước migration được chuyển sang Render. Không yêu cầu chủ dự án gửi DATABASE_URL hoặc tạo nhánh Neon thủ công để thực hiện đợt này.

## Cách chạy

Docker và `start.sh` gọi `python manage.py safe_migrate` trước khi khởi động Gunicorn. Lệnh dùng kết nối PostgreSQL sẵn có trên hosting; với Neon transaction pooling, mở một kết nối trực tiếp để giữ khóa phiên triển khai. Hai lần triển khai chồng nhau không cùng chạy migration.

Trong một transaction `REPEATABLE READ`, lệnh chụp tất cả bảng dữ liệu thường thuộc schema `public` sang **`dhd_backup_inventory_0016`**, giữ kiểu dữ liệu và mọi giá trị. Manifest lưu tên/cột/kiểu/default/ràng buộc gốc, số dòng, sequence, danh sách migration và thời điểm/commit. Không in dữ liệu hoặc thông tin đăng nhập vào log. Thu hồi quyền PUBLIC ở schema và các bảng bản chụp; không có đường dẫn web tải bản chụp.

Chỉ sau khi sao chép và đối chiếu số dòng thành công, transaction bản chụp mới commit và lệnh migrate mới chạy. Nếu sao chép thất bại, không giữ một nửa bản chụp, không chạy migration. Chạy lại giữ bản chụp hoàn tất đầu tiên và kiểm tra lại số dòng; không ghi đè bằng dữ liệu sau nâng cấp. Không tự xóa bản chụp.

`/healthz/` ở production chỉ báo sẵn sàng khi kết nối database, migration 0016 và manifest bản chụp đều hiện diện. Trả mã release và thời điểm/migration nguồn của bản chụp; không trả manifest, tên người dùng, số dư hoặc nội dung bảng. Việc đối chiếu số dòng chạy trong startup, không quét toàn bộ bản chụp ở mỗi request health.

## Giới hạn cần hiểu đúng

- Đây là **bản chụp dữ liệu trong cùng database Neon**, phục vụ phục hồi khi nâng cấp. Không bảo vệ khi toàn bộ database/tài khoản Neon bị xóa hoặc mất quyền truy cập. Chưa thay thế backup độc lập/PITR/nhánh Neon.
- Tốn thêm dung lượng bằng bản sao dữ liệu trước nâng cấp, không sao chép lại các bản chụp cũ. Nếu thiếu dung lượng/quyền/schema không phù hợp hoặc không kết nối được endpoint trực tiếp, dừng bước nâng cấp.
- Không phải `pg_dump` hoàn chỉnh. Bảng chụp không có FK/default/index vận hành như bảng gốc; phải dựng lại schema gốc bằng các migration tương ứng trước khi phục hồi dữ liệu. Không đổi `search_path` để chạy ứng dụng trực tiếp trên schema bản chụp.
- Không sao lưu bí mật hosting, vai trò PostgreSQL, views/functions tùy chỉnh hoặc tệp Google Drive. Ứng dụng hiện tại dùng các bảng Django và kiểu PostgreSQL chuẩn. Không hỗ trợ bảng partition/custom schema trong cơ chế này.
- Khóa triển khai không khóa thao tác người dùng; bản chụp có mốc dữ liệu nhất quán nhờ MVCC. Phục hồi sẽ trở về mốc chụp, nên phải xác định và đối soát mọi giao dịch phát sinh sau đó.
- Các migration cần DDL locks trong khoảng chuyển đổi. Không khẳng định hai phiên bản đều ghi dữ liệu an toàn trong lúc đổi schema. Website hiện tại giữ nguyên suốt thời gian phát triển/kiểm tra, bản mới chỉ đưa lên sau khi push main.
- Snapshot này dành cho target inventory 0016. Đợt có migration mới cần đổi tên/schema target và điều kiện health, giữ khóa triển khai dùng chung giữa các phiên bản, thử lại từ schema production thật tương ứng; không dùng snapshot 0016 như bản sao lưu mới cho mọi đợt tương lai.

## Phục hồi có kiểm soát

Chỉ thực hiện khi đã quyết định phục hồi và dừng các tiến trình ghi; không tự phục hồi sau lỗi vì có thể làm mất giao dịch mới. Trước đó giữ thêm dữ liệu hiện tại để đối soát.

1. Đọc manifest trong `dhd_backup_inventory_0016._dhd_snapshot_manifest`, kiểm tra target, thời điểm, bảng/cột/kiểu, số dòng và migration nguồn. Giữ nguyên SECRET_KEY tương ứng nếu có dữ liệu Drive mã hóa.
2. Dùng mã/migration của phiên bản trước để dựng lại schema public tương ứng. Rollback code đơn thuần không rollback schema. Không xóa schema chứa snapshot.
3. Trong transaction, kiểm tra tập bảng/cột khớp manifest; làm rỗng đúng tập bảng public cần phục hồi, hoãn kiểm tra FK, chèn dữ liệu bằng danh sách cột rõ ràng từ snapshot và khôi phục sequence theo manifest. Giữ nguyên snapshot.
4. Đối chiếu tài khoản/mật khẩu băm, số lượng/giá trị, chứng từ/ngày và bảng django_migrations. Đăng nhập và kiểm tra nghiệp vụ, đối soát giao dịch sau mốc chụp trước khi cho ghi trở lại.

Đã diễn tập tự động trên PostgreSQL thử: schema 0007 có tài khoản, hàng, số dư và chứng từ lịch sử → chụp → nâng 0016 → thay đổi dữ liệu → dựng lại schema 0007 → phục hồi toàn bộ dữ liệu/sequence từ snapshot → đối chiếu mật khẩu/số dư/ngày/migration → nâng 0016 lại. Mã diễn tập nằm ở `inventory/test_asset_migrations.py`; không chạy trên dữ liệu production. Các bài riêng kiểm tra sao chép lỗi, ghi đồng thời, restart giữ bản gốc, snapshot bị sửa, khóa hai deployment và thông tin health đã được che đúng.
