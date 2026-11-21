# Lộ Trình Phục Hồi Dự Án — InuYasha: Seek Jade (`VN 5.0.4.98`)

**Bản S1 chính trên Pixel 3 XL:** R7.21, APK standalone 840 | **Checkpoint:** `checkpoint-vn-r7.21` | **Mục tiêu dài hạn:** Khôi phục đầy đủ nhất có thể nội dung, sự kiện và tính năng của *InuYasha: Seek Jade* cho trải nghiệm cá nhân và nhiều tài khoản cục bộ trên một thiết bị mà không cần máy chủ chính thức hay kết nối Internet.

---

## I. Hiện trạng Baseline Đã Đạt (`R1 – R7.18`)

| Mốc | Trạng thái | Thành phần đã khôi phục & kiểm chứng |
| :--- | :---: | :--- |
| **STABLE (`:8080`)** | Khóa an toàn | `checkpoint-vn-r6.2` (`5fed4bb`), `server/saves`, hồ sơ `OlinaHugh Lv 20` |
| **`R7.2` (`checkpoint-vn-r7.2`)** | Đã xong | Chuẩn hóa tân thủ VN `Lv 1 -> Lv 7`, thưởng bước guide, `Shrine/Refine/Gift/MysteryShop`, tương thích `OlinaHugh` |
| **`R7.4` (`checkpoint-vn-r7.4`)** | Đã xong | `HeroRecruit` (Tầm Mộng / Túc Mệnh / Linh Hồn, `OutZiCount`, `16060005`), nạp offline, Thẻ Tháng, VIP/`ShopGift` 0..20, `SuccessTargetInfo (4900)`, `GoodsUseForBoxChoice` (rương UR `q=18`), `LvPlan` |
| **`R7.5` (`checkpoint-vn-r7.5`)** | Đã xong | Lõi **`EventClock`** (`UTC+7`, `realtime`/`offset`/`fixed`), **`EventRuntime`**, **`EventArchive`** (`scheduled`/`rotating`/`manual`), **`RewardCenter (2400)`**, và khôi phục chơi thật **`DailyTaskInfo (3000)`**, **`Dinner (2706)`**, **`TimedRecruit (9300 - Banner 81 & 82)`**, **`Xxbz (4600)`** (`43/43` unit test PASS + nghiệm thu Pixel 3 XL trên DEV `:8082`) |
| **`R7.6` (`checkpoint-vn-r7.6`)** | Đã xong | Mở rộng gameplay **`Zcsf (2711)`**, **`Xhzw (2303)`**, **`Limitthebounty (6900)`**, **`Treasure LvUp/StepUp (1402/1404)`**, **`Hero/Equip/Treasure Rebirth`** + sửa scale boss/chương xa (`Ch 15..80`) + **Multi-Banner `81+82` đồng thời** (`SelectBanner` tab UI) + **Reset tự động `00:00 UTC+7` & Reset thủ công có xác nhận** (`48/48` unit test PASS) |
| **`R7.7–R7.8` (`checkpoint-vn-r7.8`)** | Ship Beta (giữ nguyên) | **Android Standalone Beta** (`com.cmn.inuyasha.revival`, `versionCode=780`, `5.0.4.98-r7.8-beta`), Python 3.11 nhúng `libinubackend.so`, nhiều tài khoản S1, Arena đấu đội hình S1, sao lưu/xuất-nhập save (`50/50` unit test PASS) |
| **`R7.9` (`checkpoint-vn-r7.9`)** | Đã xong | **Khôi phục 30 sự kiện & đa quốc gia (`TW 1.4 -> VN`)**: Cây Tiền (`4432`), Cây Cầu Nguyện (`4409`), Slot (`4412`), Đoạt Bảo (`7800`), Đập Trứng (`4426`), Thần Binh (`4410`, TW 1.4 `XssbModel`), Online (`3700`), Điểm Danh Tháng (`2712`), Lì Xì (`5501`), Giờ Vàng (`6800`), Trùm Mua Sắm (`7000`), 10 Vạn KC (`8200`), Chuỗi Nạp/Tiêu/Đổi/Shop Điểm (`4401..4430`), NV Hạn Giờ (`4700`, TW 1.4), Thương Nhân (`4300`, TW 1.4), NV Tăng Cấp (`2600`, TW 1.4), Đua Top SV Mới 7 Ngày (`7900`), Giftcode (`2716`), Chia Sẻ (`2705`) + **`55/55` unit test PASS** + nâng cấp tại chỗ `780 -> 790` trên Pixel 3 XL giữ nguyên save |
| **`R7.10` (`checkpoint-vn-r7.10`)** | Đã xong | Cây Tiền, Slot và rương banner đã được kiểm thử delta. Vé quay đúng ID VN, nới túi tướng, giữ quyền chọn UR khi đổi kỳ và chống trùng khóa nhận thưởng giữa TK S1. Xem [báo cáo R7.10](R7_10_ACCEPTANCE_REPORT.md). |
| **`R7.11` (`checkpoint-vn-r7.11`)** | Đã xong | BXH Slot và Thần Tướng cùng S1, bản ghi Đập Trứng từ lượt chơi thật, kết toán Slot và Cây Tiền, reset và tùy chọn bảo lưu pity theo banner. APK 810 nâng cấp giữ save trên Pixel 3 XL. Xem [báo cáo R7.11](R7_11_ACCEPTANCE_REPORT.md). |
| **`R7.12` (`checkpoint-vn-r7.12`)** | Đã xong | Bảo toàn Túi Đá, sửa nút X Quà xếp hạng, kho tướng 300–400, Tầm Bảo từ Đột Phá và Cây Ước tính nạp theo kỳ. APK 820 cài đè giữ đủ bốn save S1 trên Pixel. [Nghiệm thu R7.12](R7_12_ACCEPTANCE_REPORT.md). |
| **`R7.12.1` (`checkpoint-vn-r7.12.1`)** | Checkpoint bảo toàn | APK 823 gắn lựa chọn tướng với banner và kỳ đã cấp quyền, đồng bộ thành tích 4918 và rương theo ngày, phục hồi búa Đập Trứng đã ghi sổ. [Nghiệm thu hotfix](R7_12_1_ACCEPTANCE_REPORT.md). |
| **R7.12.2 (APK 824)** | **Đã nghiệm thu** | Đột Phá tiêu đúng nguyên liệu và đồng bộ Túi. Cài đè trên Pixel giữ đủ bốn save S1. [Nghiệm thu R7.12.2](R7_12_2_ACCEPTANCE_REPORT.md). |
| **R7.13 (APK 825)** | **Đã nghiệm thu** | Shop Thần Bí, hợp thành đỏ, chiêu mộ 4417, thời trang và tiến trình theo kỳ. Cài đè giữ đủ bốn save S1 trên Pixel. [Nghiệm thu R7.13](R7_13_ACCEPTANCE_REPORT.md). |
| **R7.14 (APK 827)** | **Đã nghiệm thu** | Đồng bộ sao Ngộ Đạo, xác minh giới hạn Hợp Thành VN, mở danh mục 51 ải Mộ Thần Binh và sáu trận mô phỏng. [Nghiệm thu R7.14](R7_14_ACCEPTANCE_REPORT.md). |
| **R7.15 (APK 828)** | **QA backend** | Mở 18 ải Mộ Thần Binh, phục hồi Tiến Giai và hoàn tác trang bị. Kiểm kê 20 model Kim và các nguồn cấp. [Nghiệm thu R7.15](R7_15_ACCEPTANCE_REPORT.md). |
| **R7.15.1 (APK 832)** | **Đã nghiệm thu** | Duyên Phận áp dụng vào trận, Đồng Đội lưu theo hồ sơ, Tiến Giai đúng giá và sao quét Mộ Thần Binh chính xác. 105/105 Python, 21/21 Lua. Cài đè giữ đủ bốn save S1 trên Pixel. [Báo cáo R7.15.1](R7_15_1_ACCEPTANCE_REPORT.md). |
| **R7.16 (APK 834)** | **Đã nghiệm thu với save QA trên Pixel** | Lượt hồi Tầm Ngọc, tài năng tướng và tính Nộ theo Lua VN, đối chiếu quái ở chương đầu/giữa/cuối. 112/112 Python, 24/24 Lua. [Báo cáo R7.16](R7_16_ACCEPTANCE_REPORT.md). |
| **R7.17 (APK 835)** | **Đã nghiệm thu với save QA trên Pixel** | Hoàn thiện 255 dòng tài năng, phục hồi buff theo lượt và tiên công trong mô phỏng, kiểm kê NPC gốc ở 15 ải có kịch bản. 120/120 Python, 27/27 Lua. [Báo cáo R7.17](R7_17_ACCEPTANCE_REPORT.md). |
| **R7.18 (APK 836)** | **Đã nghiệm thu với save QA trên Pixel** | 39/51 ải Mộ Thần Binh, sửa rương cuối và chuyển tầng từ save 832, thêm 6 dòng tài năng Nộ và đối chứng hai kỹ năng NPC. Nâng cấp QA trực tiếp 832 → 836. 126/126 Python, 31/31 Lua. [Báo cáo R7.18](R7_18_ACCEPTANCE_REPORT.md). |
| **R7.18.1 (APK 837)** | **Đã nghiệm thu với save QA trên Pixel** | Khôi phục **Banner 83 (Thần Tướng D: Inu Kimi & Tứ Đấu Thần)**, bổ sung 9 asset còn thiếu từ ZH/TH, mở song song `81/82/83`, rương `16060034`/`16060033` và ghép 150 mảnh. Nâng cấp QA trực tiếp 832 → 837 bảo toàn 100% 4 save S1. 132/132 Python. [Báo cáo R7.18.1](R7_18_1_ACCEPTANCE_REPORT.md). |
| **R7.21 (APK 840)** | **Đã nghiệm thu trên Pixel** | Khôi phục **Phó Bản Tổ Đội (`TeambattleInfo`)** đủ 24 ải với đồng đội NPC (`TeambattlePlayerNpc`/`TeambattleHeroNpc`), trấn thủ 12h, Shop 18 món, lưu Đá (`2000`) + mở túi Đá, `DailyTask #34`, `SuccessTarget #27`. 100/100 Python, 3/3 Lua. [Báo cáo R7.21](R7_21_ACCEPTANCE_REPORT.md). |

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
| **R7.7 → R7.8** *(Baseline hiện tại)* | **Android Standalone Beta (Ship Candidate `com.cmn.inuyasha.revival`)**: Nhúng CPython `3.11.17` 32-bit + `libinubackend.so` + `LocalBackendManager`/`LocalBackendService` (`127.0.0.1:18082` loopback-only) + Gộp toàn bộ `3,672` file OBB vào 1 APK duy nhất + **Đa tài khoản S1 độc lập & Đấu Arena phòng thủ giữa các TK S1** + **Sao lưu/Khôi phục SHA-256** + **Nâng cấp phiên bản giữ Save (`770 -> 780`)** | Hoàn tất `checkpoint-vn-r7.8` (`50/50` unit test PASS); xem [R7_7_R7_8_STANDALONE_BETA_REPORT.md](file:///Users/vup/Documents/agy/inuyasha/R7_7_R7_8_STANDALONE_BETA_REPORT.md) |
| **R7.11** *(Đã xong)* | Xếp hạng sự kiện cùng S1, bot cục bộ, kết toán đúng kỳ và hoàn thiện Event Archive | Nâng cấp standalone trên Pixel, Test the Delta |
| **R7.12.2** *(Đã nghiệm thu)* | Đồng bộ đá sau Đột Phá và tiêu đúng nguyên liệu VN | 76/76 Python, 8/8 Lua. APK 824 cài đè giữ đủ bốn save S1 trên Pixel. [Báo cáo](R7_12_2_ACCEPTANCE_REPORT.md). |
| **R7.13** *(Đã nghiệm thu)* | Đồng hồ Shop Thần Bí, hợp thành đỏ, phí 4417, chỉ số thời trang và nạp/tiêu theo kỳ | 86/86 Python, 9/9 Lua. Test the Delta và nâng cấp 824 → 825 trên Pixel. [Báo cáo](R7_13_ACCEPTANCE_REPORT.md). |
| **R7.14A/B** *(Lát đầu đã nghiệm thu)* | Ngộ Đạo, giới hạn Hợp Thành và Mộ Thần Binh. Danh mục 51 ải, chơi sáu ải mô phỏng có thưởng và tiến trình S1. | 94/94 Python, 12/12 Lua. Giữ 45 ải còn lại khóa đến khi có nguồn đội hình/chỉ số gốc hoặc lát mô phỏng tiếp theo đã cân chỉnh. [Audit nguồn](R7_14_SOURCE_AUDIT.md). |
| **R7.15** *(Lát hai đã nghiệm thu)* | 18 ải Mộ Thần Binh, Tiến Giai trang bị VN và quyền nhận thưởng theo kỷ lục. | 100/100 Python, 14/14 Lua. Giữ 33 ải ngoài lát khóa, tiếp tục tìm nguồn đội NPC gốc và nguồn cấp Kim. [Báo cáo](R7_15_ACCEPTANCE_REPORT.md). |
| **R7.15.1** *(Đã nghiệm thu trên Pixel)* | Duyên Phận và Đồng Đội, Tiến Giai dấu +, quét và mở khóa Mộ Thần Binh. | 105/105 Python, 21/21 Lua. APK 832 cài đè 827 và bảo toàn save S1. [Báo cáo](R7_15_1_ACCEPTANCE_REPORT.md). |
| **R7.16** *(Đã nghiệm thu trên Pixel)* | Tầm Ngọc đồng bộ theo backend, tài năng đột phá, đối chiếu Combat và quái theo chương. | APK 834 và `checkpoint-vn-r7.16`. Lát sau tiếp tục tìm roster gốc theo wave, buff có thời hạn, khống chế và hệ số FAP tài năng. [Báo cáo](R7_16_ACCEPTANCE_REPORT.md). |
| **R7.17** *(Đã nghiệm thu với save QA trên Pixel)* | Buff theo lượt, khống chế, miễn và kháng, hiệu ứng Nộ và điều kiện HP. Đối chiếu sâu NPC chương 1, 35 và 70. | APK 835 và `checkpoint-vn-r7.17`. Còn 120 dòng tài năng cần xử lý đủ và cần nguồn roster đánh thường theo wave. [Báo cáo](R7_17_ACCEPTANCE_REPORT.md). |
| **R7.18** *(Đã nghiệm thu với save QA trên Pixel)* | Mộ Thần Binh 39/51 ải và kiểm kê nguồn Kim. Khôi phục tẩy hiệu ứng, hao HP để tăng sát thương và cấp Nộ cho đồng đội ít Nộ nhất. | APK 836 và `checkpoint-vn-r7.18`. Còn 12 ải Mộ Thần Binh, 114 dòng tài năng cần xử lý đủ và cần dữ liệu VN về nguồn cấp Kim đầu tiên cùng roster đánh thường. [Báo cáo](R7_18_ACCEPTANCE_REPORT.md). |
| **R7.18.1** *(Đã nghiệm thu với save QA trên Pixel)* | Khôi phục Banner 83 (Inu Kimi & Tứ Đấu Thần), bổ sung 9 asset, giữ độc lập 81/82/83 và nâng cấp 832 → 837. | APK 837 và `checkpoint-vn-r7.18.1`. 132/132 Python PASS. [Báo cáo](R7_18_1_ACCEPTANCE_REPORT.md). |
| **R7.21** *(Đã nghiệm thu trên Pixel)* | Khôi phục Phó Bản Tổ Đội (`Teambattle`) 24 ải với đồng đội NPC, trấn thủ 12h, Shop 18 món và tài nguyên Đá (`2000`). | APK 840 và `checkpoint-vn-r7.21`. 100/100 Python, 3/3 Lua PASS. [Báo cáo](R7_21_ACCEPTANCE_REPORT.md). |
| **Tiếp theo** | Bang Hội cá nhân, Lãnh Địa, Luyện Thể và 12 ải Mộ Thần Binh còn lại. | Bám sát dữ liệu VN gốc, giữ nguyên STABLE R6.2 và 4 save S1. |
