"""Original artwork atlas: fixed identifiers, never arbitrary image URLs or markup."""

EMOTIONS = (
    "Xin chào",
    "Đồng ý",
    "Yêu thích",
    "Cười vui",
    "Chúc mừng",
    "Cảm ơn",
    "Đang nghĩ",
    "Chờ một chút",
    "Đang làm việc",
    "Hoàn tất",
    "Xin lỗi",
    "Chào buổi sáng",
)
STICKERS = {
    f"{pack}-{n + 1:02}": {
        "id": f"{pack}-{n + 1:02}",
        "label": label,
        "pack": title,
        "index": start + n,
    }
    for pack, title, start in (
        ("lemon", "Lemon vui vẻ", 0),
        ("cat", "Mèo công sở", 12),
        ("robot", "Bạn bạc", 24),
    )
    for n, label in enumerate(EMOTIONS)
}

# Stable, original Vietnamese captions reuse the artwork without extra downloads.
WORK_CAPTIONS = (
    "Đã nhận nhé!",
    "Mình kiểm tra ngay",
    "Cảm ơn đồng đội",
    "Chốt như vậy nhé",
    "Làm tốt lắm!",
    "Nhờ bạn hỗ trợ",
    "Đang xác minh",
    "Chờ mình một chút",
    "Đang xử lý",
    "Đã hoàn tất",
    "Mình cập nhật lại",
    "Khởi động ngày mới",
    "Xin chào cả nhóm",
    "Thông tin chuẩn rồi",
    "Phối hợp thật tốt",
    "Cùng làm cho xong",
    "Tuyệt vời đồng đội",
    "Cảm ơn bạn nhiều",
    "Cần thêm thông tin",
    "Mình sẽ phản hồi",
    "Tập trung nào",
    "Đã cập nhật",
    "Mình sửa ngay",
    "Chúc ngày thuận lợi",
    "Kết nối thôi!",
    "Đồng ý triển khai",
    "Một đội thật đỉnh",
    "Giữ tinh thần nhé",
    "Cả đội xuất sắc",
    "Biết ơn hỗ trợ",
    "Để mình đối chiếu",
    "Mình đang theo dõi",
    "Đang tổng hợp",
    "Đã kiểm tra xong",
    "Sẽ làm tốt hơn",
    "Cùng tiến về trước",
)
FRIENDLY_CAPTIONS = (
    "Chào bạn nè!",
    "Quá là chuẩn!",
    "Thương đồng đội",
    "Vui quá đi!",
    "Ăn mừng thôi!",
    "Cảm ơn thật nhiều",
    "Đang suy nghĩ…",
    "Đợi mình xíu nha",
    "Chăm chỉ chút nào",
    "Xong rồi nè!",
    "Xin lỗi bạn nhé",
    "Cà phê thôi nào",
    "Có mình đây!",
    "Mình đồng ý",
    "Gửi bạn một tim",
    "Cười lên nhé!",
    "Đáng khen quá!",
    "Cảm ơn vì có bạn",
    "Cho mình nghĩ chút",
    "Sắp xong rồi!",
    "Cố lên đồng đội",
    "Một việc đã xong",
    "Mình rút kinh nghiệm",
    "Một ngày thật vui",
    "Rất vui gặp bạn",
    "Đã hiểu ý bạn",
    "Hợp tác vui vẻ",
    "Năng lượng tích cực",
    "Chúc mừng cả đội",
    "Một lời cảm ơn",
    "Cùng tìm cách nhé",
    "Mình vẫn ở đây",
    "Cùng cố gắng nào",
    "Hoàn thành mục tiêu",
    "Mình sẽ chú ý hơn",
    "Nạp năng lượng thôi",
)
for prefix, title, captions in (
    ("work", "Công việc", WORK_CAPTIONS),
    ("friendly", "Gắn kết", FRIENDLY_CAPTIONS),
):
    for original in list(STICKERS.values())[:36]:
        index = original["index"]
        key = prefix + "-" + original["id"]
        STICKERS[key] = {
            **original,
            "id": key,
            "label": captions[index],
            "caption": captions[index],
            "pack": title + " · " + original["pack"],
        }

# Emoji artwork is supplied by the device's font, without remote images or tracking.
# These IDs and captions are stable, just like the original atlas stickers.
for number, (symbol, caption) in enumerate(
    (
        ("🤣", "Cười xỉu luôn!"),
        ("🤭", "Hí hí, biết rồi nha"),
        ("🥳", "Quẩy cùng đồng đội!"),
        ("😎", "Chất như nước cất"),
        ("🫠", "Tan chảy mất thôi"),
        ("🤯", "Bất ngờ chưa!"),
        ("😴", "Nạp pin một xíu"),
        ("☕", "Cà phê cứu tinh"),
        ("🐸", "Có gì hot không?"),
        ("🦆", "Đồng đội vịt vàng"),
        ("🐼", "Gấu trúc chăm chỉ"),
        ("🦦", "Chill chút nha"),
        ("🐧", "Có mặt liền đây"),
        ("🦥", "Chậm mà chắc nhé"),
        ("🍋", "Lemon lên mood!"),
        ("🤖", "Đang chạy hết công suất"),
        ("💃", "Vui là phải nhảy"),
        ("🕺", "Cuối tuần tới rồi!"),
        ("🚀", "Tăng tốc thôi nào!"),
        ("🔥", "Đội mình quá cháy!"),
        ("💪", "Việc khó có mình"),
        ("🫡", "Rõ, nhận nhiệm vụ!"),
        ("👏", "Vỗ tay thật lớn"),
        ("🫶", "Gửi tim cả nhà"),
    ),
    start=1,
):
    key = f"fun-{number:02}"
    STICKERS[key] = {
        "id": key,
        "label": caption,
        "caption": caption,
        "symbol": symbol,
        "pack": "Vui nhộn · Đồng đội",
    }
