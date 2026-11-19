# Báo Cáo Nghiệm Thu R7.5 — Khôi Phục Hoạt Động, Sự Kiện & Event Archive

**Dự án:** InuYasha: Seek Jade (`com.cmn.inuyasha` v5.0.4.98 VN)  
**Phạm vi:** DEV (`:8082` — `server/dev_saves`)  
**Code/Data/Tests Commit:** `b82b60a` (`master`) | **Checkpoint Tag:** `checkpoint-vn-r7.5`

---

## 1. Danh mục hoạt động và sự kiện gốc tìm được

Đã hoàn thành khảo sát toàn diện toàn bộ 271 bảng `Config/` và cây mã nguồn Lua (`ExtraActivity/`, `OpenActivity/`, `TimedActivity/`, `Task/`, `Practice/`, `Challenge/`, `InstanceZones/`, `NewXZYY/`, `GGZJ/`, `Guild/`) của bản VN `5.0.4.98`, tổng hợp đầy đủ 12 tiêu chí bắt buộc trong [R7_5_EVENT_CATALOG.md](file:///Users/vup/Documents/agy/inuyasha/R7_5_EVENT_CATALOG.md):

- **Nhóm hằng ngày & chu kỳ:** `DailyTaskInfo (3000 - NV Ngày)`, `Dinner (2706 - Tiệc Thể Lực)`, `MonthSignInfo (2712 - Điểm Danh Tháng)`, `OnlineReward (3700 - Quà Online)`, `Zcsf (2711 - Chiêu Tài)`, `StartWork (2718)`, `Daydayfund (2710)`.
- **Nhóm khiêu chiến / boss / PvE:** `Xxbz (4600 - Kho Báu Bí Ẩn)`, `Xhzw (2303 - Ước)`, `BddInfo (2507 - Mộ Thần Binh)`, `BossBattle (2203)`.
- **Nhóm giới hạn thời gian & mở server:** `TimedRecruitInfo (9300 - KM Tướng: 81..86)`, `Limitthebounty (6900)`, `TimeSpike (6800)`, `OpenContest (7900)`, `Swdiamonds (8200)`, `Earlytask`, `TimedCriticalInfo`, chuỗi `TimedActivity` (`TimedMoneyTree`, `TimedSmashingeggsInfo`, `TimedHopetreeInfo`, `TimedExchange`, `TimedInfo.*`, `TimedXssbInfo`).
- **Nhóm đa người chơi / tổ đội / bang:** `PVP (2502)`, `Gddh (2503 - Đấu Võ)`, `PVPinterTop` (PvP Liên Server), `TeambattleInfo (2319 - PB Tổ Đội)`, `GGZJ (2504)`, `GuildBoss / GuildFb (3400)`.

Các bảng config mới đã được bổ sung vào [extract_game_data.py](file:///Users/vup/Documents/agy/inuyasha/server/extract_game_data.py) và sinh lại [game_data.json](file:///Users/vup/Documents/agy/inuyasha/server/game_data.json): `dailytask_config` (1), `dailytask_model` (25), `dailytask_reward` (5), `dailytask_exp` (100), `timed_recruit_credit` (36), `timed_recruit_rank` (24), `timed_recruit_bless` (6), `timed_recruit_ratio` (11), `xxbz_config` (1), `xxbz_model` (3), `xxbz_reward_base` (27), `xxbz_reward_cond` (28), `xxbz_del_cd` (2), cùng `zcsf_type` (6), `zcsf_use` (10), `limitthebounty` (6), `timespike` (8), `activeranking` (12), `opencontest_project` (7), `opencontest_rank` (21).

---

## 2. Phân loại sự kiện đủ dữ liệu, thiếu dữ liệu và chưa rõ

| Phân loại | Chi tiết xác minh trong VN `5.0.4.98` |
| :--- | :--- |
| **Đủ 100% Config + UI + Asset** | `DailyTaskInfo (3000)`, `Dinner (2706)`, `Xxbz (4600)`, `TimedRecruit (9300)` **Banner `81` & `82`**, `Zcsf (2711)`, `Xhzw (2303)`, `BddInfo (2507)`, `Limitthebounty (6900)`, `TimeSpike (6800)`, `OpenContest (7900)`, `Teambattle (2319)` (có `TeambattlePlayerNpc`/`HeroNpc`), `GGZJ (2504)`, `GuildBoss/GuildFb (3400)`, `PVPinter`. |
| **Có Config/UI nhưng cần mô phỏng phần server ẩn** | `TimedRecruit (81 & 82)`: thiếu bảng trọng số chính xác giữa Tướng Tím/Cam ngoài `outputLowHeroR=9000` và đối thủ BXH thực -> đã đánh dấu rõ ràng phần mô phỏng tất định & bảo hiểm Cam 10 lượt / Chúc Phúc 500 điểm. |
| **Thiếu dữ liệu server / thiếu asset** | `EarlytaskModel` & `EarlytaskRewardRelation` **không có** trong Config VN; `CriticalTasksTypeRelation` (`TimedCriticalInfo`) **không có**; `XssbModel` (`TimedXssbInfo`) **không có**; `MonthSignInfo`, `OnlineReward`, `TimedMoneyTree`, `TimedSmashingeggsInfo`, `TimedHopetreeInfo`, `TimedInfo.*`, `TimedLimitExchange` **chỉ có Lua UI** (server gốc trả động bảng phần thưởng); `TimedRecruit 83` thiếu ảnh `xshd_114/115`, `84..86` rỗng `btnPic`/`pic`. |

---

## 3. Kiến trúc Event Runtime đã triển khai

Triển khai tại [event_runtime.py](file:///Users/vup/Documents/agy/inuyasha/server/event_runtime.py) và kết nối vào [emulator.py](file:///Users/vup/Documents/agy/inuyasha/server/emulator.py):

- **`EventClock`:** Tách đồng hồ sự kiện khỏi OS bằng lớp thời gian độc lập theo chuẩn múi giờ VN `UTC+7` (`DEFAULT_VN_TZ_OFFSET_HOURS = 7`), hỗ trợ `realtime`, `offset`, `fixed`, `advance`, đồng bộ qua mọi `TimeTick` trả về cho APK Android mà không đụng giờ hệ thống thiết bị, lưu bền qua `clock_state.json`.
- **`EventDefinition` & `build_default_event_registry`:** Đọc điều kiện `openLv`, khung giờ `VitConfig`, `XxbzModel`, `TimedRecruitModel` trực tiếp từ `game_data.json` để có thể thêm sự kiện theo cấu hình.
- **`EventRuntime`:**
  - Quản lý 3 trạng thái `upcoming` (Chưa mở), `active` (Đang diễn ra), `ended` (Đã kết thúc) + kiểm tra `openLv` / `needVIP`.
  - Hỗ trợ `permanent`, `daily` (kèm `time_windows` phân đoạn trong ngày), `weekly`, `timed`.
  - Quản lý `progress` & `claimed` theo từng `instance_id`, cung cấp `claim_milestone(...)` chống nhận trùng tuyệt đối và cấp `idempotency_key` nhất quán cho `ResourceLedger`.
  - Khi sang ngày/kỳ mới, bản ghi cũ tự đóng gói vào `archive_history` trước khi mở `instance_id` mới.
- **`ModulesInfo` & `TimedActivityOpenInfo` động:** Chỉ bật `IfOpen=1` cho các scene giới hạn (`4400`, `6300`, `6400`) khi có dữ liệu thực, giúp HomeScene sạch sẽ không hiện nút rỗng.

---

## 4. Những sự kiện đã khôi phục thực sự (chơi thật từ đầu đến cuối)

Triển khai đầy đủ tại [event_handlers.py](file:///Users/vup/Documents/agy/inuyasha/server/event_handlers.py) + gắn hook gameplay trong [emulator.py](file:///Users/vup/Documents/agy/inuyasha/server/emulator.py):

1. **Hoạt động hằng ngày / chu kỳ — `DailyTaskInfo (3000 - NV Ngày)` + `PlayerVIT.ReceiveVIT (2706 - Tiệc Thể Lực)`:**
   - **Tiệc Thể Lực (`2706`):** Hoạt động theo đúng 3 khung giờ VN từ `VitConfig` (`12h-14h`, `18h-20h`, `21h-23h`), bật `RedDotInfo["2706"]`, bấm nhận `+50 Thể Lực + 20 Hoạt Lực`, chặn nhận trùng trong cùng khung giờ và tự làm mới ngày hôm sau.
   - **NV Ngày (`3000`):** Toàn bộ 25 đầu việc `DailytaskModel` & 5 rương mốc (`30, 80, 130, 170, 220` điểm); tự tăng tiến độ thực từ các hành vi chơi thật (Ải Thường, Tinh Anh, Đoạt Bảo, Ngộ Đạo, Quyết Đấu, Yêu Vương, Tầm Ngọc, Shop, Shop Bí Ẩn, Cường Hóa TB, Tăng Lv Tướng, **Tiêu KC** qua mọi RPC, và **Kho Báu Bí Ẩn**); hỗ trợ `GetCredit`, `DrawReward` (cộng vật phẩm, Vàng, EXP người chơi & sync lên cấp), `OneKeyDone` (10 KC) & `OneKeyAllDone` (200 KC), làm mới lúc `00:00 UTC+7`.
2. **Sự kiện giới hạn thời gian — `TimedRecruitInfo (9300 - KM Tướng)` Banner `81` & `82`:**
   - Hiện/ẩn nút top bar HomeScene động qua `Avatar.TimedActivityOpenInfo["9300"]` (kèm `ExtraInfo = {ActivityEnumId}` và countdown thực từ `EndDate`).
   - Hỗ trợ Free CD `72000s`, x1 (`280` KC), x10 (`2800` KC) bảo đảm Tướng Cam `q=15`, tích điểm `+10`/lượt, mở tuần tự 6 rương điểm (`60..600`), mở khóa Chúc Phúc (`320` khởi điểm, `+5`/lượt), kích hoạt `DrawGoldHero=0` -> mở `TimedRecruitChoiceBoxLayer` chọn Tướng UR `q=18` (`16060008` / `16060009`).
   - BXH tổng hợp tất định (`RankList`, 25 đối thủ NPC + người chơi khi `>= 500` điểm); tự động quyết toán phần thưởng BXH (`TimedRecruitRankrewardModel`) vào **Trung Tâm Nhận Thưởng (`Reward.Rewars` / `Reward.DrawGiftBags`, RedDot `"2400"`)** một lần duy nhất khi hết kỳ; chặn hoàn toàn mọi RPC khi đã kết thúc/hết hạn.
3. **Hoạt động chiến đấu thực tế — `Xxbz / XxbzInfo (4600 - Kho Báu Bí Ẩn)`:**
   - 3 Boss theo đúng cấp (`Lv 28` KB Vàng `12010012` & Đột Phá `12010011`, `Lv 30` KB Magatama `12010014`), truyền `TreasureId` trong `FightInfo` để kích hoạt HUD đếm Sát Thương / Vàng trực tiếp trong trận chiến Spine 2D `BattleType.eXSBZ`.
   - Quy đổi thưởng chiến đấu theo đúng công thức Lua gốc (`BattleUILayer.lua:361-389`) + `extraOutput = Lệnh Trợ Chiến x2` (`16050092`); mở khóa & chống nhận trùng mốc `100` KC một lần (`Xxbz.DrawReward`), mua lượt theo `VipModel.buyXSBZNum` (`XxbzInfo.BuyCount`), reset lượt/ngày trong khi `HighestHurt` & `DrawnMaxNum` bảo toàn trọn đời; nối thẳng sang `DailyTask #30` và `SuccessTarget #26/#33`.

---

## 5. Những phần của Event Archive đã hoạt động

Triển khai phần nền tảng cốt lõi tại `EventRuntime` + Admin HTTP API `/admin/clock` & `/admin/events` (giới hạn localhost + `X-Admin-Token`, không nhúng menu kỹ thuật vào APK người chơi):

- **`scheduled` (Theo lịch):** Mở/đóng sự kiện đúng khoảng `[start_ts, end_ts]`; tự chuyển `upcoming` -> `active` -> `ended` và khóa nhận thưởng trái phép sau `end_ts`.
- **`rotating` (Luân phiên):** Luân phiên Banner `81` <-> `82` theo chu kỳ cấu hình (mặc định 3 ngày = `259200s`), tự sinh `instance_id` mới (`rot:0`, `rot:1`...) và tất toán kỳ cũ.
- **`manual` (Chọn thủ công):** Cho phép kích hoạt lại bất kỳ sự kiện đã khôi phục (`activate_manual_event`), cấp `instance_id` độc lập (`manual:<seq>:<ts>`), **không tự mở khóa trước bất kỳ phần thưởng nào** và bảo toàn nguyên vẹn toàn bộ lịch sử & phần thưởng các kỳ cũ trong `archive_history`.

---

## 6. Kết quả thử nghiệm thực tế trên Pixel 3 XL (DEV `:8082`)

Kiểm thử trên tài khoản QA cô lập tại `:8082` (chuẩn bị `OlinaHugh Lv 28 VIP 6`), giữ nguyên giờ hệ thống Pixel 3 XL (`Thu Nov 19 09:02:23 +07 2026`), điều khiển thời gian bằng `EventClock`:

1. **Kho Báu Bí Ẩn (`Xxbz 4600`):** Mở Tu Luyện -> Kho Báu Thần Bí (Boss 1 & 2 mở, Boss 3 khóa `Lv30 mở`) -> vào trận 2D Spine bản đồ `rongyan`, HUD hiển thị sát thương/Vàng trực tiếp -> kết toán `16,459` sát thương khớp từng đồng (`+28,522 Vàng` + `2 Lệnh Trợ Chiến`) -> bấm khiêu chiến tiếp hiện đúng dialog `XxbzInfo.BuyCount (20 KC)` -> `HighestHurt` cập nhật `16459/30000` và kích hoạt RedDot NV Ngày.
2. **NV Ngày (`DailyTaskInfo 3000`):** Mở giao diện thấy `Kho Báu Bí Ẩn 1/1` bật nút xanh `Nhận Thưởng` -> nhận `10 điểm + 980 Vàng` -> sang `KM Tướng` rút KC > 300 -> quay lại NV Ngày thấy `Dùng KC 300/300` -> nhận thêm `20 điểm` đạt `30/235` -> mở Rương 30 điểm (`+130 EXP + 5 KC + 5 Lệnh Miễn Chiến`), thanh EXP đáy tăng `0 -> 130/10945`, rương chuyển sang trạng thái đã mở (`Status=2`).
3. **Tiệc Thể Lực (`PlayerVIT.ReceiveVIT 2706`):** Đặt `EventClock` lúc `12:30 UTC+7` -> Hoạt Động bật RedDot trên `Tiệc Thể Lực` -> bấm nhận thưởng hiển thị `+50 Thể Lực; +20 Hoạt Lực`, Thể Lực tăng `230 -> 280/200` và RedDot tắt.
4. **KM Tướng (`TimedRecruitInfo 9300`):** Banner `81` (InuYasha / Sesshomaru / Naraku) hiện trên HomeScene kèm đếm ngược `2 ngày 11:29:59`, mở `XEM HẠNG` hiện BXH 25 NPC (`1. PhongKhuyển 1761`), rút miễn phí CD `20:00:00` + 5 lượt 280 KC giảm bảo hiểm Cam `9 -> 3`, tích `60` điểm -> mở rương `60 điểm` -> nhãn tự chuyển sang `Đạt 200 điểm nhận Rương`.
5. **Đăng nhập lại & Tua `EventClock` +3 ngày (`2026-11-22 12:30 UTC+7`):**
   - Force-stop và đăng nhập lại cùng ngày: toàn bộ `Điểm: 60`, rương `30/235`, `TL 280/200`, `EXP 130/10945` giữ nguyên 100%.
   - Tua `EventClock +259200s` (+3 ngày): `KM Tướng` tự luân phiên sang **Banner `82`** (Inu no Taishou / Midoriko / Takemaru, icon `sy_148`, rương `xshd_60`, `Điểm: 0`), `NV Ngày` reset về `0/235` trong khi EXP `130/10945` không mất, `Tiệc Thể Lực` mở lại chu kỳ mới, và `archive_history` lưu đủ 4 instance ngày `2026-11-19` & `rot:0`.
6. **Khôi phục hậu kiểm thử:** APK gốc STABLE được cài lại lên Pixel 3 XL, `http_proxy = null`, `server/dev_saves` khôi phục sạch từ `pre_r7_5_dev` và DEV `:8082` chạy lại bình thường.

---

## 7. Kết quả test và trạng thái STABLE / DEV

- **Unit Test Suite (`python3 -m unittest discover -s server -p 'test_*.py' -v`):**
  - **43/43 PASS** (`Ran 43 tests in 12.186s OK`): gồm toàn bộ **37/37 test R7.4** và **6 test R7.5 mới (`test_38` – `test_43`)** kiểm chứng `EventClock`, `EventArchive` (`scheduled`/`rotating`/`manual`), `PlayerVIT.ReceiveVIT`, `DailyTaskInfo`, `TimedRecruitInfo` (CD/x1/x10/rương điểm/Bless/UR ChoiceBox/tất toán BXH vào `RewardCenter`/chặn khi hết hạn), `Xxbz` (Boss 1–3/công thức sát thương/mốc 100 KC/BuyCount VIP/reset ngày), và HTTP `/admin/clock` + `/admin/events`.
- **STABLE (`:8080`, PID `12133`):** Không chỉnh sửa; vẫn giữ nguyên `checkpoint-vn-r6.2` (`5fed4bb`), `OlinaHugh Lv 20` trong `server/saves`.
- **DEV (`:8082`, PID `23309`):** Đang chạy bản R7.5 mới trên `server/dev_saves` đã khôi phục sạch (`OlinaHugh Lv 20`, `VIP 3`).

---

## 8. Commit và Checkpoint

- **Branch:** `master`
- **Code/Data/Tests Commit:** `b82b60adace44313bb2a959845e5f68ba3757c72` (`b82b60a`)
- **Tag Checkpoint:** `checkpoint-vn-r7.5` (tại commit báo cáo & code hoàn chỉnh trên `master`)
- **Các file chính:**
  - [event_runtime.py](file:///Users/vup/Documents/agy/inuyasha/server/event_runtime.py) *(mới)*
  - [event_handlers.py](file:///Users/vup/Documents/agy/inuyasha/server/event_handlers.py) *(mới)*
  - [emulator.py](file:///Users/vup/Documents/agy/inuyasha/server/emulator.py)
  - [extract_game_data.py](file:///Users/vup/Documents/agy/inuyasha/server/extract_game_data.py) & [game_data.json](file:///Users/vup/Documents/agy/inuyasha/server/game_data.json)
  - [test_emulator.py](file:///Users/vup/Documents/agy/inuyasha/server/test_emulator.py)
  - [R7_5_EVENT_CATALOG.md](file:///Users/vup/Documents/agy/inuyasha/R7_5_EVENT_CATALOG.md) & [R7_5_ACCEPTANCE_REPORT.md](file:///Users/vup/Documents/agy/inuyasha/R7_5_ACCEPTANCE_REPORT.md)

---

## 9. Danh sách sự kiện còn cần khôi phục (xếp theo độ ưu tiên)

1. **Ưu tiên 1 (Có đủ 100% Config gốc, chơi đơn được ngay):**
   - `Zcsf (2711 - Chiêu Tài / LuckyCat)` — mở Lv 21, nối luôn vào `DailyTask #16` & `SuccessTarget #25`.
   - `BddInfo (2507 - Mộ Thần Binh)` — mở Lv 26, nối luôn vào `DailyTask #21`, mở gameplay leo tháp Thần Binh & shop buff.
   - `Xhzw (2303 - Ước / Goddess Kiss)` — mở Lv 30, nối `DailyTask #8`.
   - `Limitthebounty (6900)` & `TimeSpike (6800)` — gói sự kiện theo mốc cấp độ.
2. **Ưu tiên 2 (Có Config nhưng cần AI đồng đội / BXH hoặc hoàn thiện gameplay):**
   - `TeambattleInfo (2319 - PB Tổ Đội)` — mở Lv 40, sử dụng bảng `TeambattlePlayerNpc` / `HeroNpc` có sẵn trong Config.
   - `GGZJ (2504 - Dũng Sĩ)` & `OpenContest (7900 - Đua Top 7 Ngày)`.
   - `Swdiamonds (8200)` & `GuildBoss / GuildFb (3400)`.
3. **Ưu tiên 3 (Chỉ có UI Lua, thiếu Config server — cần phục dựng minh bạch hoặc tách Event Archive Preset):**
   - `MonthSignInfo (2712)` & `OnlineReward (3700)` (thiếu bảng thưởng gốc phía server).
   - Chuỗi `TimedActivity` động (`TimedMoneyTree`, `TimedSmashingeggsInfo`, `TimedHopetreeInfo`, `TimedInfo.*`, `TimedLimitExchange`) và `TimedXssbInfo` / `TimedCriticalInfo` / `Earlytask`.

---

## 10. Đề xuất các round R7.6+

- **R7.6 — Khôi phục cụm PvE/Daily còn đủ Config + Hệ thống phát triển Lv 25–35:** Hoàn thiện `Zcsf (2711)`, `BddInfo (2507)`, `Xhzw (2303)`, `Limitthebounty (6900)` và chuỗi ải Chính Tuyến/Tinh Anh Lv 20–35 kèm `Artifact`/Thần Binh (`NewWraith`), giúp người chơi tự nhiên vượt mốc sát thương `30k..200k` trong Kho Báu Bí Ẩn.
- **R7.7 — Co-op NPC & Multi-Account Local World:** Triển khai `AccountId/ServerId/PlayerId` theo [MULTI_ACCOUNT_ARCHITECTURE.md](file:///Users/vup/Documents/agy/inuyasha/MULTI_ACCOUNT_ARCHITECTURE.md), khôi phục `Teambattle (2319)` bằng `TeambattlePlayerNpc` + đội hình lưu của tài khoản cùng máy, và nâng cấp BXH `OpenContest`/`TimedRecruit`/`PVP` ghép người chơi cục bộ cùng thế giới.
- **R7.8 — Guild + Event Archive UI / Preset Mở Rộng:** Khôi phục Công Hội cục bộ (`Guild 3400` cho `DailyTask #10/#15`), bổ sung lớp cấu hình/preset minh bạch cho `MonthSignInfo` & `OnlineReward`, và xây dựng trang quản lý **Event Archive** (chọn kỳ/xem lịch sử mùa) trên Web Admin Portal (`:8082/poc/`) tách biệt khỏi giao diện APK gốc.
