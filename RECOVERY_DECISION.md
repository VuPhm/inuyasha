# RECOVERY_DECISION.md — Lựa chọn phương án khôi phục (Round R0)

## 1. Đánh giá 3 phương án theo bằng chứng thực tế

| Phương án | Khả thi | Bằng chứng từ Round R0 | Kết luận |
| :--- | :--- | :--- | :--- |
| **A. Server gốc / private server có sẵn** | **Không khả thi** | Toàn bộ domain chính thức (`loginsvr.enqyc/cnqyc/twqyc/tlqyc.moqikaka.com`) chết DNS. Không có source server hoặc one-click server (`一键端`) công khai trên GitHub/Gitee/cộng đồng. | **Loại bỏ** |
| **B. Giữ client gốc + Local/Remote Server Emulator** | **Rất khả thi (Ưu tiên số 1)** | 1. Đã thu thập đủ 4 bộ XAPK gốc (APK + OBB).<br>2. Đã giải mã 100% Lua source (`1,120` file EN 5.1.1, `1,186` file ZH, `1,227` file TH).<br>3. Giao thức gameplay là **HTTP JSON POST** rõ ràng (`/API/ServerList_Client.ashx` & `/client.aspx`), combat tính toán tại client (`ComBattle`).<br>4. Pixel 3 XL hỗ trợ `armeabi` native. Chỉ cần trỏ `ManageCenter`/`Channel=MQKK` + `usesCleartextTraffic="true"` trên APK là client gốc kết nối được tới emulator Python trên Mac. | **CHỌN LÀM TRỤC CHÍNH** |
| **C. Tái dựng bằng engine mới / Web / Godot dùng tài nguyên gốc** | **Khả thi làm lớp dự phòng & kiểm thử nhanh** | Toàn bộ sprite Spine 2D (`.atlas`, `.skel`, `.png`), UI, map, âm thanh (`.mp3`) và bảng cấu hình (`Config/*.lua`) đã đọc được hoàn toàn. Giúp dựng PoC playable ngay lập tức trong khi hoàn thiện patch APK & thử nghiệm trên Pixel 3 XL. | **KẾT HỢP (B + C)** |

---

## 2. Quyết định cuối cùng cho dự án: **B + C (Trục chính B, PoC kết hợp C trên cùng Server Emulator)**

1. **Server Emulator thống nhất (`server/emulator.py`)**: Viết bằng Python stdlib, triển khai đúng schema JSON của `com.heitao.inuyasha.guge` v5.1.1 (`/API/ServerList_Client.ashx`, `/client.aspx`, đọc dữ liệu thật từ `HeroModel`, `BattleChapterModel`, `BattleNodeModel`). Server này phục vụ đồng thời cả **client Android gốc đã cấu hình endpoint** (trên Pixel 3 XL) lẫn **Web PoC**.
2. **Client Android (Round R1)**:
   - Không động vào gameplay/asset gốc; chỉ giải quyết 3 điểm tương thích Android 12 & server chết:
     1. Bật `android:usesCleartextTraffic="true"` (hoặc `networkSecurityConfig`) để Android 12 cho phép HTTP tới Mac/LAN server emulator.
     2. Chuyển kênh đăng nhập từ `Channel=DZZ` (SDK bên thứ 3) sang `Channel=MQKK` (hoặc stub `MQHelper.login()`) và trỏ `ManageCenter` + `AccountManage` về local emulator.
     3. Cài đặt APK + OBB trên Google Pixel 3 XL qua ADB và đối chiếu logcat từng RPC thực tế để mở rộng `server/emulator.py` (túi đồ, chiêu mộ tướng, cường hóa, đấu trường, v.v.).
3. **PoC hiện có ở Round R0 (`poc/web_poc/`)**: Dùng ngay tài nguyên thật từ EN 5.1.1 APK+OBB (nền đăng nhập `dl_21.jpg`, bản đồ `smap01.jpg`, nền chiến đấu nhiều lớp `changjing_pingyuan_*`, sprite trích từ Spine `.atlas`, nhạc nền & lồng tiếng `.mp3`) và gọi trực tiếp tới `server/emulator.py` để chứng minh vòng lặp Đăng nhập -> Chọn ải -> Chiến đấu -> Lưu phần thưởng hoạt động thực tế.
