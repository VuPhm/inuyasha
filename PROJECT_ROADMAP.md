# Lộ Trình Phục Hồi Dự Án — InuYasha: Seek Jade (`VN 5.0.4.98`)

**Mốc hiện tại:** `checkpoint-vn-r7.6` trên `master` | **Mục tiêu dài hạn:** Khôi phục đầy đủ nhất có thể nội dung, sự kiện và tính năng của *InuYasha: Seek Jade* cho trải nghiệm cá nhân và nhiều tài khoản cục bộ trên một thiết bị mà không cần máy chủ chính thức hay kết nối Internet.

---

## I. Hiện trạng Baseline Đã Đạt (`R1 – R7.5`)

| Mốc | Trạng thái | Thành phần đã khôi phục & kiểm chứng |
| :--- | :---: | :--- |
| **STABLE (`:8080`)** | Khóa an toàn | `checkpoint-vn-r6.2` (`5fed4bb`), `server/saves`, hồ sơ `OlinaHugh Lv 20` |
| **`R7.2` (`checkpoint-vn-r7.2`)** | Đã xong | Chuẩn hóa tân thủ VN `Lv 1 -> Lv 7`, thưởng bước guide, `Shrine/Refine/Gift/MysteryShop`, tương thích `OlinaHugh` |
| **`R7.4` (`checkpoint-vn-r7.4`)** | Đã xong | `HeroRecruit` (Tầm Mộng / Túc Mệnh / Linh Hồn, `OutZiCount`, `16060005`), nạp offline, Thẻ Tháng, VIP/`ShopGift` 0..20, `SuccessTargetInfo (4900)`, `GoodsUseForBoxChoice` (rương UR `q=18`), `LvPlan` |
| **`R7.5` (`checkpoint-vn-r7.5`)** | Đã xong | Lõi **`EventClock`** (`UTC+7`, `realtime`/`offset`/`fixed`), **`EventRuntime`**, **`EventArchive`** (`scheduled`/`rotating`/`manual`), **`RewardCenter (2400)`**, và khôi phục chơi thật **`DailyTaskInfo (3000)`**, **`Dinner (2706)`**, **`TimedRecruit (9300 - Banner 81 & 82)`**, **`Xxbz (4600)`** (`43/43` unit test PASS + nghiệm thu Pixel 3 XL trên DEV `:8082`) |
| **`R7.6` (`checkpoint-vn-r7.6`)** | **Baseline hiện tại** | Mở rộng gameplay **`Zcsf (2711)`**, **`Xhzw (2303)`**, **`Limitthebounty (6900)`**, **`Treasure LvUp/StepUp (1402/1404)`**, **`Hero/Equip/Treasure Rebirth`** + sửa scale boss/chương xa (`Ch 15..80`) + **Multi-Banner `81+82` đồng thời** (`SelectBanner` tab UI) + **Reset tự động `00:00 UTC+7` & Reset thủ công có xác nhận** + **POC Android Standalone trên Pixel 3 XL** (`48/48` unit test PASS + nghiệm thu trực tiếp Pixel 3 XL) |

---

## II. Định Hướng & Cấu Hình Chính Thức Dự Án (Đã Xác Nhận)

Các quy tắc dưới đây là **định hướng chuẩn mặc định cho bản phục hồi cá nhân**, thay thế mọi giả định giới hạn phát hành đơn lẻ theo live-ops cũ:

### 1. Cấu hình Event Archive mặc định
- **Chu kỳ reset mặc định:** Hằng ngày lúc **`00:00 UTC+7`** (đồng bộ qua `EventClock`, không phụ thuộc đồng hồ OS hay mạng Internet).
- **Chạy đồng thời nhiều sự kiện & nhiều banner:** Không ép chỉ mở 1 banner hay 1 sự kiện tại một thời điểm; cho phép bật song song nhiều sự kiện và nhiều banner đã khôi phục đủ tài nguyên.
- **Tùy chỉnh chu kỳ linh hoạt:** Cho phép ghi đè chu kỳ riêng cho từng sự kiện khi cần (theo ngày, nhiều ngày hoặc thời lượng tùy chọn).
- **Offline hoàn toàn:** Bản Android standalone phải kiểm tra thời gian, đếm ngược và reset sự kiện hoàn toàn cục bộ, **không cần kết nối Internet**.
- *Phân biệt nguồn:* Đây là cấu hình vận hành mặc định của bản phục hồi cá nhân, không nhất thiết phản ánh lịch phát hành độc quyền của máy chủ thương mại trước đây.

### 2. Kiến trúc Nhiều Banner Đồng Thời (Multi-Banner)
- Có thể mở đồng thời trên cùng một phiên chơi:
  - **Chiêu mộ thường:** Tầm Mộng (`1`/`10`).
  - **Chiêu mộ Túc Mệnh (`2`) & Linh Hồn (`3`/`30`/`40`).**
  - **Banner Giới Hạn `81`** (`Sesshomaru / InuYasha / Naraku` — `16060008`).
  - **Banner Giới Hạn `82`** (`Inu no Taishou / Midoriko / Takemaru` — `16060009`).
  - Các banner đặc biệt khác khi đã khôi phục đủ Config + ảnh/Spine (VD `Banner 83+` nếu bổ sung/xác minh được tài nguyên còn thiếu).
- **Độc lập tuyệt đối theo từng banner:** Mỗi banner sở hữu riêng `banner_id`/`event_id`, `instance_id` kỳ hoạt động, pool tướng, đơn giá/tài nguyên tiêu hao, bộ đếm lượt quay miễn phí/CD, điểm tích lũy, bộ đếm bảo hiểm (`OutZiCount`, Chúc Phúc) và rương/mốc thưởng. **Nghiêm cấm dùng chung một bộ đếm làm sai lệch banner khác.**
- **Tương thích giao thức/UI gốc (`ModuleSub 9300`):**
  - Client VN gốc (`LimittedTimedRecruitLayer.lua:60`) chỉ đọc `next(TimedActivityOpenInfo[9300])` và gửi RPC `TimedRecruitInfo.*` không kèm ID banner.
  - Để hỗ trợ nhiều banner cùng loại mà không ghi đè dữ liệu, áp dụng **cơ chế chọn banner tương thích** (ví dụ: màn hình/thanh chọn banner trong UI cho `ModuleSub 9300` kết hợp ngữ cảnh/tham số `banner_id` trên backend + chuyển nhanh qua Archive), cho phép chuyển qua lại giữa Banner `81`, `82`, v.v. trong khi dữ liệu từng banner được giữ độc lập 100%.

### 3. Cơ chế Reset Tự Động & Thủ Công (Chuẩn 5 Bước)
Khi kết thúc một chu kỳ (tự động lúc `00:00 UTC+7` hoặc theo chu kỳ riêng, hoặc khi người chơi kích hoạt reset thủ công):
1. **Lưu lịch sử kỳ cũ:** Đóng băng bản ghi kỳ trước vào `archive_history` (gồm điểm, hạng, bảo hiểm tại thời điểm kết thúc, mốc đã nhận).
2. **Kết toán phần thưởng hợp lệ:** Tự động tính và gửi các phần thưởng đủ điều kiện chưa phát (ví dụ thưởng BXH vào `RewardCenter 2400`) đúng 1 lần duy nhất (`idempotency_key` gắn `instance_id`).
3. **Sinh `instance_id` mới:** Tạo phiên kỳ kế tiếp tách biệt hoàn toàn với kỳ cũ.
4. **Làm mới theo cấu hình:** Reset lượt tham gia, nhiệm vụ, rương mốc của kỳ mới (không tự mở khóa sẵn phần thưởng).
5. **Bảo toàn tuyệt đối tài sản nhân vật:** Giữ nguyên toàn bộ tướng, trang bị, bảo vật, vật phẩm, Kim Cương, Vàng, cấp độ, VIP và lịch sử kỳ cũ.

- **Yêu cầu riêng cho Reset Thủ Công:**
  - Phải có bước **xác nhận rõ ràng**.
  - **Chỉ tác động lên sự kiện được chọn**, tuyệt đối không reset dây chuyền sang sự kiện khác hay xóa dữ liệu nhân vật / lịch sử cũ.
- **Chính sách điểm tích lũy, bảo hiểm & quà chưa nhận:**
  - Ưu tiên áp dụng đúng **quy tắc gốc** khi Config/Lua VN xác định rõ (ví dụ: `DailyTask` làm mới điểm mỗi ngày, `Xxbz` giữ `HighestHurt`/`DrawnMaxNum` trọn đời nhưng reset lượt ngày, `TimedRecruit` kết toán thưởng BXH khi hết kỳ).
  - Nếu quy tắc gốc phía server không xác định được (ví dụ chuyển tiếp bảo hiểm/chúc phúc giữa các lần reset tay của cùng một banner hoặc quà mốc tích lũy chưa bấm nhận lúc đổi kỳ), áp dụng **chính sách rõ ràng, cấu hình được** (`carry_over_pity` hoặc `auto_settle_unclaimed_milestones` trước khi đóng kỳ) để tránh mất quyền lợi ngoài dự kiến của người chơi.

### 4. Định hướng Trải nghiệm Cá nhân
- Ưu tiên chơi thoải mái, tự do mở lại các sự kiện cũ đã khôi phục đầy đủ bất cứ lúc nào thay vì giữ lịch phát hành độc quyền khắt khe.
- Vẫn giữ nguyên điều kiện mở khóa (`Lv`, `VIP`), cơ chế tiêu hao (`Thể Lực`, `Kim Cương`, `Đá/Lệnh`) và bảng thưởng gốc để gameplay giữ đúng nhịp và ý nghĩa.

---

## III. Kế Hoạch Tích Hợp Vào R7.6 (DEV `:8082`)

R7.6 triển khai theo hướng cân bằng — **không** dồn toàn bộ round chỉ vào giao diện Event Archive nếu gameplay chính còn khuyết, mà tận dụng `EventRuntime`, `EventClock`, `EventArchive` từ R7.5 và giữ nguyên `checkpoint-vn-r7.5`, STABLE R6.2 cùng toàn bộ dữ liệu save hiện có.

### 4 Trụ cột của R7.6
1. **Khôi phục Gameplay còn thiếu / chưa hoàn chỉnh (Ưu tiên tài nguyên VN đầy đủ):**
   - Khôi phục nhóm hoạt động PvE & tính năng phát triển đã có đủ 100% Config VN:
     - **`Zcsf (2711 - Chiêu Tài)`** (`Lv 21`, nối `DailyTask #16` & `SuccessTarget #25`).
     - **`BddInfo (2507 - Mộ Thần Binh / Bát Đại Địa Ngục)`** (`Lv 26`, 51 ải + Shop/Buff + quét 3 sao, nối `DailyTask #21`).
     - **`Xhzw (2303 - Ước)`** (`Lv 30`, nối `DailyTask #8`) &/hoặc **`Limitthebounty (6900)` / `TimeSpike (6800)`** + nhóm nâng cấp sức mạnh cốt lõi còn thiếu (`Treasure LvUp/StepUp/Compose`, `Rebirth`).
2. **Nâng cấp Multi-Banner & Multi-Event Đồng Thời:**
   - Mở rộng `EventArchive` hỗ trợ kích hoạt song song nhiều banner/sự kiện (`concurrent_events`), phát đủ danh sách active trong `TimedActivityOpenInfo`.
   - Tách riêng hoàn toàn state/pity/tích điểm/phần thưởng giữa Chiêu mộ thường (`HeroRecruit`), `Banner 81`, `Banner 82` và các banner/sự kiện khác.
   - Thiết kế phương án tương thích UI/RPC cho các banner cùng loại (`ModuleSub 9300` chọn banner an toàn, không ghi đè dữ liệu).
3. **Hoàn thiện Reset Hằng ngày (`00:00 UTC+7`) & Reset Thủ Công:**
   - Chuẩn hóa lịch `00:00 UTC+7` làm chu kỳ mặc định cho các hoạt động/sự kiện cấu hình ngày + cho phép override chu kỳ riêng theo sự kiện.
   - Xây dựng cơ chế **Reset thủ công từng sự kiện** kèm bước xác nhận (`confirm=True`), pipeline 5 bước (lưu lịch sử -> kết toán quà hợp lệ -> sinh `instance_id` mới -> làm mới theo config -> giữ nguyên tướng/vật phẩm/KC/lịch sử cũ) và cấu hình chính sách bảo toàn quyền lợi minh bạch.
4. **Khảo sát kỹ thuật ngắn cho bản Android Standalone:**
   - Đánh giá ngắn gọn, dựa trên cấu trúc thực tế của `server/` (100% Python Stdlib, `game_data.json` ~5.6 MB) và APK `com.cmn.inuyasha` (`libcocos2dlua.so` `armeabi`, `LuaJavaBridge`/`HttpClient`):
     - Kiến trúc nhúng server cục bộ trên Android (`Termux` vs `Foreground Service / Chaquopy` vs porting `NanoHTTPD/Kotlin`).
     - Lưu save & `archive_history` ngoài sandbox `Android/data/` để nâng cấp APK giữ nguyên dữ liệu.
     - Vận hành offline `EventClock`/`EventArchive` không cần Internet & giới hạn phần cứng trên Pixel 3 XL.

### Tiêu chí Nghiệm thu Dự kiến cho R7.6
- Các gameplay mới khôi phục chơi thật từ đầu đến cuối trên DEV `:8082` và Pixel 3 XL.
- Kích hoạt **đồng thời** Chiêu mộ thường + Túc Mệnh/Linh Hồn + Banner `81` + Banner `82`; thao tác trên banner này không làm đổi lượt/điểm/bảo hiểm của banner khác.
- Kiểm chứng cả **reset tự động `00:00 UTC+7`** (qua `EventClock`, không sửa giờ Android) và **reset thủ công từng sự kiện** (từ chối nếu thiếu xác nhận, giữ lịch sử kỳ cũ và tài sản nhân vật, kết toán phần thưởng hợp lệ vào `RewardCenter`).
- Toàn bộ unit test R7.4 + R7.5 + R7.6 PASS 100%; `checkpoint-vn-r7.5` và STABLE R6.2 còn nguyên vẹn.
- Báo cáo R7.6 có mục khảo sát kỹ thuật Android standalone rõ ràng.

---

## IV. Lộ Trình Các Round Tiếp Theo (`R7.7+`)

| Giai đoạn | Trọng tâm chính | Ghi chú kỹ thuật |
| :--- | :--- | :--- |
| **R7.6** *(Đã xong)* | **`Zcsf (2711)`**, **`Xhzw (2303)`**, **`Limitthebounty (6900)`**, **`TreasureLvUp/StepUp`**, **`Hero/Equip/Treasure Rebirth`**, sửa combat chương xa (`Ch 15..80`) + **Multi-Banner `81+82` đồng thời** + **Reset `00:00 UTC+7` & Reset thủ công** + **POC Android Standalone** | Hoàn tất `checkpoint-vn-r7.6`; xem [R7_6_ACCEPTANCE_REPORT.md](file:///Users/vup/Documents/agy/inuyasha/R7_6_ACCEPTANCE_REPORT.md) |
| **R7.7** *(Kế tiếp)* | **`BddInfo (2507 - Mộ Thần Binh)` + Multi-Account `ServerId = 1` + PvP Bất đồng bộ + Co-op NPC** (`MULTI_ACCOUNT_ARCHITECTURE.md`, `Teambattle 2319` dùng `TeambattlePlayerNpc`, `GGZJ 2504`, `OpenContest 7900`) | Hỗ trợ nhiều nhân vật cùng chung BXH, Lãnh địa và Tổ đội cục bộ trên 1 thiết bị |
| **R7.8+** | **Guild cục bộ (`3400`), Preset Sự kiện Thiếu Config (`MonthSignInfo`/`OnlineReward`/`TimedMoneyTree`...), UI Event Archive & Đóng gói Android Standalone** | Phân tách rạch ròi Preset mô phỏng với Config gốc; cài đặt 1-chạm hoàn toàn offline trên Android |
