# Báo Cáo Nghiệm Thu R7.6 — Mở Rộng Gameplay, Multi-Banner Đồng Thời & Khảo Sát Android Standalone

**Dự án:** InuYasha: Seek Jade (`com.cmn.inuyasha` v5.0.4.98 VN)  
**Phạm vi:** DEV (`:8082` — `server/dev_saves`, PID `27904` sau khôi phục sạch) | **Bảo toàn:** STABLE R6.2 (`:8080`, PID `12133`, `checkpoint-vn-r6.2` `5fed4bb`, `OlinaHugh Lv 20`) & `checkpoint-vn-r7.5` (`fb686cf`)  
**Unit test cuối (sau chỉnh sửa mã nguồn cuối):** `48/48 PASS` (`Ran 48 tests in 15.552s OK`, 0 fail, 0 skip)  

---

## 1. Các hệ thống gameplay đã khôi phục

Bổ sung trích xuất config VN gốc trong [extract_game_data.py](file:///Users/vup/Documents/agy/inuyasha/server/extract_game_data.py) và sinh lại [game_data.json](file:///Users/vup/Documents/agy/inuyasha/server/game_data.json) (`5.8 MB`), gồm: `xhzw_config` (6), `xhzw_lip` (6), `xhzw_reward` (10), `xhzw_reward_refresh_price` (1), `treasure_lv` (100), `treasure_lv_active` (106), `treasure_step` (33), `treasure_step_attr` (60), `hero_rebirth` (18 bậc quality), `equip_rebirth` (8 bậc quality), `treasure_rebirth` (4 bậc quality), `reborn_lv` (340), cùng các bảng R7.5 (`zcsf_type` 6, `zcsf_use` 10, `limitthebounty` 6).

### Các hệ thống chơi thật từ đầu đến cuối

1. **`Zcsf (2711 — Mèo Thần Tài / Chiêu Tài)`** ([event_handlers.py](file:///Users/vup/Documents/agy/inuyasha/server/event_handlers.py#L1219-L1315)):
   - Mở từ Lv 21 (`open_lv = 21`, đăng ký `lucky_cat` trong `EventRuntime`), đọc số lần quay tối đa theo VIP/bảng `ZcsfTypeRelation` và mức tiêu KC / hoàn Vàng từ `ZcsfUseRelation`.
   - Hỗ trợ `Zcsf.ZcsfInfo` & `Zcsf.ZC`: trừ Kim Cương qua `ResourceLedger` (`idempotency_key`), tăng tiến trình `zc_num`/`active_sf`, nối trực tiếp vào `DailyTask #16`, `RedDotInfo["2711"]`, và tự reset theo chu kỳ `00:00 UTC+7`.
2. **`Xhzw (2303 — Ước)`** ([event_handlers.py](file:///Users/vup/Documents/agy/inuyasha/server/event_handlers.py#L1316-L1587)):
   - Mở từ `Tu Luyện -> Ước` tại Lv 30 (`open_lv = 30`, đăng ký `goddess_kiss` trong `EventRuntime`), dùng `XhzwConfig`, `XhzwLipRelation`, `XhzwRewardRelation`, `XhzwRewardRefreshPriceRelation`.
   - Hỗ trợ đầy đủ 6 RPC gốc: `Xhzw.GetXhzwInfo`, `Xhzw.XhzwTurn`, `Xhzw.XhzwAlterLuck` (đổi vận + tiêu KC/lượt miễn phí), `Xhzw.XhzwAlterLuckLock`, `Xhzw.RefreshXhzwRewardList` (miễn phí/KC làm mới bảng thưởng), `Xhzw.ReceiveRewardForOneKey` (nhận quà mốc tích điểm & chống nhận trùng); nối `DailyTask #8` & `RedDotInfo["2303"]`.
3. **`Limitthebounty (6900 — Săn Thưởng)`** ([event_handlers.py](file:///Users/vup/Documents/agy/inuyasha/server/event_handlers.py#L1588-L1659)):
   - Dùng trực tiếp `LimitthebountyModel` (6 mốc `15/20/25/35/45/...`), `Limitthebounty.GetInfo` & `Limitthebounty.ReceivedReward` + `PlayerInfo.LimitthebountyTriggerLv` & `RedDotInfo["6900"]`.
4. **Phát triển & Hoàn Trả Bảo Vật / Tướng / Trang Bị** ([emulator.py](file:///Users/vup/Documents/agy/inuyasha/server/emulator.py)):
   - **`Treasure.TreasureLvUp (1402)`:** Cường hóa Bảo Vật tiêu Vàng + Bảo Vật nguyên liệu/EXP, cộng chỉ số theo `TreasureLvActiveRelation` vào `_compute_slot_property` (tính lại Chiến Lực `FAP` ngay lập tức).
   - **`Treasure.TreasureStepUp (1404)`:** Tinh luyện/Tăng Bậc Bảo Vật theo `TreasureStepRelation` & `TreasureStepAttrRelation`, hỗ trợ cả **Đá Tinh Hoa (`16050020`)** lẫn **Bảo Vật trùng tên** và ghi log hoàn trả `step_materials_used`.
   - **`Hero.HeroRebirth`, `Equip.EquipRebirth`, `Treasure.TreasureRebirth`:** Trùng sinh tướng/trang bị/bảo vật chưa xuất trận về cấp/bậc ban đầu, thu phí KC theo `*RebirthRelation` và hoàn trả Đá Hồn/Vàng/Đá Đột Phá/Đá Tinh Hoa đúng định dạng dict đơn (`HeroInfo`/`EquipInfo`/`TreasureInfo`) mà `NetworkResData:modifyTableItem` yêu cầu.

### Lỗi thật phát hiện và khắc phục khi kiểm thử trên Pixel 3 XL

- **Crash Lv 32 tại `Data/CalcPrefData.luac:773`:** Thiếu trường `Step` trên `slotEquip` (`Weapon/Helmet/Clothes/Necklace`) -> đã bổ sung `setdefault("Step", 0)` trong `_normalize_loaded_state` (`server/emulator.py`).
- **Crash mở `Transmute` tại `Disassemble/DisassembleNewScene.luac:542`:** `getHeroInitData` so sánh `v.LiantiLv > 0` khi một số tướng thiếu khóa `LiantiLv` -> đã bổ sung `"LiantiLv": 0` trong `_build_hero_instance` và chuẩn hóa `LiantiLv/RebornStep/Step/Lv/Exp` trong `_normalize_loaded_state`.
- **Sai quy ước tham số `Treasure.TreasureStepUp`:** UI Lua gốc (`TreasureExtraLayer.lua:345`) gửi `data[2] = tag - 1` (`0` với `[]` cho Đá Tinh Hoa, `1` với `[dupe_id]` cho Bảo Vật trùng), khác với kỳ vọng `bool(data[2])` ban đầu khiến nút `Tăng Cấp` dùng Đá Tinh Hoa trả `status = -1` -> đã sửa `if_sub = len(mat_ids) == 0` trong `_rpc_treasure_step_up` và cập nhật `test_46`.

### Hạng mục chưa hoàn tất / còn mô phỏng

- **`BddInfo (2507 — Mộ Thần Binh)`** đã nằm trong kế hoạch lựa chọn nhưng chưa triển khai gameplay trong R7.6 để dồn trọng tâm cho Multi-Banner, Reset `00:00 UTC+7` và ổn định các lỗi runtime trên thiết bị thật (chuyển sang R7.7).
- Trọng số roll chi tiết nội bộ của `XhzwAlterLuck` (ngoài bảng mốc `XhzwLipRelation` / `XhzwRewardRelation`) dùng RNG tất định phía emulator do logic roll gốc nằm ở server.

---

## 2. Kết quả kiểm tra combat / độ khó ở các chương xa & sửa lỗi

Đã kiểm tra `_build_enemy_wave` và chạy mô phỏng/unit test (`test_44_r7_6_far_chapter_combat_and_boss_node_scaling`) qua các **Chương 15, 30, 50, 70 và 80** ([emulator.py](file:///Users/vup/Documents/agy/inuyasha/server/emulator.py#L2624-L2663)), phát hiện và sửa **2 lỗi thật**:

1. **Lỗi ải Boss cuối chương (`X20`) yếu hơn ải áp chót (`X19`):** Biểu thức cũ `max(1, node_id % 10)` khiến các ải `2020`, `3020`, `5020`, `7020`, `8020` cho `node_id % 10 == 0` bị kẹp thành vị trí `1` thay vì `10` -> đã sửa `node_pos = 10 if (node_id % 10 == 0 and ch_id > 11) else max(1, node_id % 10)`.
2. **Độ dốc cấp độ quá gắt ở chương xa:** Công thức cũ `base_lv = (ch_id - 11) * 4 + node_idx` đẩy Chương 80 (`needLV = 80`) lên tận `Lv 286` (vượt xa ngưỡng đội hình cùng cấp). Đã làm mượt đường cong trên Chương 20 thành `base_lv = 36 + (ch_id - 20) * 2 + node_pos`, giữ thử thách tăng dần ở Ch 30/50/70/80 mà đội 6 tướng đồng cấp vẫn vượt được (`test_44` PASS).

---

## 3. Kiến trúc Multi-Banner đồng thời & cơ chế chọn banner

- **Hạn chế của UI gốc VN:** Trong `LimittedTimedRecruitLayer.lua`, màn hình gốc mặc định chỉ đọc phần tử đầu tiên của `TimedActivityOpenInfo["9300"]` và gửi `TimedRecruitInfo.GetTimedRecruitInfo/Recruit/DrawCreditReward` không kèm ID banner.
- **Giải pháp Backend ([event_runtime.py](file:///Users/vup/Documents/agy/inuyasha/server/event_runtime.py#L450-L473), [event_handlers.py](file:///Users/vup/Documents/agy/inuyasha/server/event_handlers.py#L626-L669)):**
  - Chế độ mặc định R7.6 là `mode = "concurrent"` với `concurrent_events = ["timed_recruit:81", "timed_recruit:82"]`; khi tạo instance cho banner này **không đóng** banner anh em cùng `module_sub = 9300`.
  - `_build_timed_activity_open_info` phát đồng thời tất cả banner `9300` đang mở (`[81, 82]`), cho phép chạy song song **Chiêu mộ thường (`HeroRecruit`) + Banner 81 + Banner 82**.
  - Thêm RPC `TimedRecruitInfo.SelectBanner`, trường `AvailableBanners` trong snapshot, và định tuyến mọi thao tác quay/rương/Chúc Phúc qua tham số `enumId` tường minh hoặc `state["selected_banners"]["9300"]`. Mỗi banner lưu độc lập `instance_id`, `progress` (`my_credit`, `pull_count`, `out_zi_count`, `cooled_time`, `bless_num`, `pending_gold_hero`, `draw_credit_rewards`, `history`) và BXH.
- **Patch chọn banner tương thích trên APK DEV ([patch_vn_apk.py](file:///Users/vup/Documents/agy/inuyasha/poc/patch_vn_apk.py#L474-L558)):** Vá sạch `LimittedTimedRecruitLayer.luac` thêm 2 tab chuyển nhanh **`Sessho (81)`** / **`InuTaishou (82)`** gọi `TimedRecruitInfo.SelectBanner` và đính kèm `enumId` khi gửi RPC, đồng bộ `requestSync()` đúng banner đang chọn. Nghiệm thu trực tiếp trên Pixel 3 XL xác nhận chuyển `81 <-> 82` đổi ngay bộ ba tướng, rương thưởng (`xshd_59` vs `xshd_60`), điểm và lượt bảo hiểm mà không ảnh hưởng banner còn lại, đồng thời Chiêu mộ thường (`Túc Mệnh`) vẫn hoạt động độc lập.

---

## 4. Cơ chế reset tự động `00:00 UTC+7` & reset thủ công có xác nhận

- **Reset tự động mặc định `00:00 UTC+7`:**
  - `EventRuntime` dùng `period_mode = "daily_utc7"` kết hợp `EventClock` (`UTC+7`) sinh `instance_id` dạng `<event_id>:d:YYYY-MM-DD` (và hỗ trợ tùy chỉnh chu kỳ riêng qua `period_overrides` / `period_sec` sang dạng `:p<dur>:<slot_idx>`).
  - Không dùng đồng hồ OS hay Internet.
- **Reset thủ công từng sự kiện (`EventRuntime.manual_reset_event`):**
  - Bắt buộc có `confirm=True`; nếu thiếu `confirm`, endpoint `/admin/events` (`action: "reset"`) trả về HTTP `400` (`Manual reset requires explicit confirmation (confirm=True)`).
  - Khi xác nhận, chỉ tác động **duy nhất `event_id` được chỉ định** theo pipeline 5 bước: (1) Đóng băng instance cũ vào `archive_history`; (2) Kết toán phần thưởng hợp lệ vào `RewardCenter (2400)` gồm cả rương tích lũy đạt mốc chưa bấm nhận (`_settle_timed_recruit_unclaimed_credits`, bật/tắt được qua `settle_unclaimed_credit`) và BXH; (3) Tăng `manual_reset_seq[event_id]` tạo instance mới `:rN`; (4) Reset lượt quay, điểm, rương kỳ mới; (5) **Giữ nguyên 100%** tướng, trang bị, bảo vật, Kim Cương, Vàng và lịch sử các kỳ/banner khác.
- **Kiểm chứng thực tế trên DEV `:8082` + Pixel 3 XL:**
  - `POST /admin/events` thiếu `confirm` -> HTTP `400`.
  - Reset thủ công `timed_recruit:81` (`confirm=true`) -> tạo `timed_recruit:81:d:2026-11-19:r1` (`my_credit = 0`), bản ghi cũ đánh dấu `archived=True, settled=True`, trong khi `timed_recruit:82` vẫn giữ nguyên `my_credit = 110, draw_credit_rewards = [60]` và tài sản nhân vật (`26 heroes, 40 equips, 18 treasures, 42153 KC`) không đổi.
  - Tua `/admin/clock` qua `2026-11-20T00:00:30+07:00`: tất cả `81`, `82`, `Zcsf`, `Xhzw`, `DailyTask`, `Xxbz` đồng loạt sang chu kỳ ngày `2026-11-20` (`archive_history` tăng lên 8 bản ghi) và giữ nguyên trạng thái qua lần restart DEV + đăng nhập lại Pixel 3 XL (`r7_6_59_banners_post_reset.png`).

---

## 5. Kết quả thử nghiệm Android standalone & kiến nghị kỹ thuật

Đã dựng và chạy thử POC tối giản không cần root trên Pixel 3 XL (`com.cmn.inuyasha.standalonepoc`, 3 tệp Java/Manifest tổng `7,214 bytes` tại [poc/android_standalone_poc/](file:///Users/vup/Documents/agy/inuyasha/poc/android_standalone_poc)): [AndroidManifest.xml](file:///Users/vup/Documents/agy/inuyasha/poc/android_standalone_poc/AndroidManifest.xml), [MainActivity.java](file:///Users/vup/Documents/agy/inuyasha/poc/android_standalone_poc/src/com/cmn/inuyasha/standalonepoc/MainActivity.java), [LoopbackService.java](file:///Users/vup/Documents/agy/inuyasha/poc/android_standalone_poc/src/com/cmn/inuyasha/standalonepoc/LoopbackService.java).

### Số liệu đo thực tế trên Pixel 3 XL (`Android 12`, rootless)

- **Chức năng POC:** `LoopbackService` khởi chạy HTTP socket thuần Java trên `127.0.0.1:18082` trả về JSON `/API/ServerList_Client.ashx`; `MainActivity` đo thời gian bind, RTT loopback và ghi/đọc file save ở Scoped Storage.
- **Thời gian khởi động & bind loopback:** `43 ms`.
- **Độ trễ HTTP loopback (`127.0.0.1:18082`):** `2.10 ms`; kiểm tra chéo tiến trình bằng `toybox nc 127.0.0.1 18082` trả ngay `HTTP/1.1 200 OK`.
- **Bộ nhớ tiến trình (`dumpsys meminfo`):** Total PSS **`57,574 KB`** (`oom_adj = 0` khi active), trong đó **Java Heap PSS `1,456 KB`**, Native Heap PSS `5,900 KB`, DEX mmap `26 KB`, phần lớn còn lại là bề mặt đồ họa/EGL (`38,815 KB`) của Activity.
- **Lưu trữ không cần root (Scoped Storage):** Ghi/đọc thành công `/storage/emulated/0/Android/data/com.cmn.inuyasha.standalonepoc/files/save_poc.json` (`53 bytes`, quyền `-rw-rw---- u0_a224 sdcard_rw`).
- *(Đã gỡ sạch APK POC bằng `pm uninstall com.cmn.inuyasha.standalonepoc` và xóa thư mục `build/` tạm sau khi đo xong).*

### Ràng buộc kỹ thuật & kiến nghị kiến trúc

1. **Ràng buộc ABI của APK game gốc:** File [apktool.yml](file:///Users/vup/Documents/agy/inuyasha/analysis/vn/apktool/apktool.yml) / thư viện `libcocos2dlua.so` của `com.cmn.inuyasha` chỉ build cho **32-bit `armeabi`** (`minSdkVersion: 9`, chưa khai báo `targetSdkVersion` nên Android 14+ cần cờ cài `--bypass-low-target-sdk-block` trừ khi nâng/patch tương thích).
2. **So sánh phương án đóng gói Standalone:**
   - **Nếu nhúng trực tiếp Python `server/` (Chaquopy/Cpython):** tái sử dụng nhanh `emulator.py` nhưng **bắt buộc** nạp thêm thư viện `.so` 32-bit (`armeabi`/`armeabi-v7a`) tương thích `libcocos2dlua.so`, làm tăng dung lượng APK thêm khoảng ~25–35 MB và chi phí RAM runtime Python (ước tính ~30–45 MB cho interpreter + nạp `game_data.json` `5.8 MB`).
   - **Kiến nghị tối ưu lâu dài — Engine/Service Java-Kotlin (hoặc Companion App tách tiến trình qua `127.0.0.1`):**
     - Phần HTTP RPC cục bộ thuần Java trong POC chứng minh footprint DEX cực nhỏ (~12 KB APK POC), bind `43 ms`, `1.45 MB` Java Heap, không dính xung đột ABI 32-bit/64-bit với `libcocos2dlua.so`.
     - Có thể đi theo lộ trình 2 bước thực dụng: (a) giai đoạn đầu dùng Companion Service tách APK hoặc Chaquopy `armeabi-v7a` tái sử dụng trực tiếp Python `server/` + `game_data.json`; (b) giai đoạn hoàn thiện port lõi RPC nhẹ sang Java/Kotlin ngay trong `ForegroundService` nội bộ.
3. **Vị trí lưu Save & Archive History:** Đặt mặc định trong App-specific External Storage (`Android/data/<pkg>/files/saves/`, sao lưu thủ công ra thư mục `Documents/` thông qua Storage Access Framework / `ACTION_CREATE_DOCUMENT` để **gỡ cài đặt hay nâng cấp APK không mất tiến trình**), tách biệt hoàn toàn dữ liệu `EventClock`/`EventArchive` khỏi mạng Internet.

---

## 6. Test checklist nghiệm thu trực tiếp trên Pixel 3 XL

Tất cả bước kiểm thử chạy trên DEV `:8082` với APK R7.6 (`analysis/vn/patched/com.cmn.inuyasha_revival_r7_6_dev.apk`, không gắn menu kỹ thuật/cheat vào APK người chơi), tài khoản QA `OlinaHugh`:

- [x] Đăng nhập sạch, kiểm tra log `/api/report.ashx` = **0 lỗi Lua** từ màn Home, Đội Hình, Tu Luyện, Sự Kiện (`r7_6_02b_home.png`, `r7_6_06b_home.png`).
- [x] **`Zcsf (2711 Mèo Thần Tài)`:** Mở từ `HĐ Đặc Sắc`, quay x2 (`25 -> 23` lượt), KC trừ đúng `10 -> 30`, mốc tăng lên `51200` (`r7_6_10_zcsf_open.png`, `r7_6_11_zcsf_after.png`).
- [x] **`Limitthebounty (6900 Săn Thưởng)`:** Nhận thưởng mốc `Lv 15` (`288 KC + 58K Vàng + TB`), panel tiến lên mốc `Lv 20` (`r7_6_12_bounty.png`, `r7_6_13_bounty_claimed.png`).
- [x] **Multi-Banner đồng thời `81 + 82` + Chiêu mộ thường:**
  - Mở `Banner 81 (Sessho)` -> quay miễn phí (`Điểm: 10`, CD `19:59:54`, `Rút thêm 8 lần`) (`r7_6_14_banner81.png`, `r7_6_15b_b81_after.png`).
  - Chuyển tab `InuTaishou (82)` (`SelectBanner [82]`): đổi đúng chân dung tướng `Inu no Taishou / Izayoi / Takemaru`, khởi đầu `Điểm: 0`, quay Free + 10x (`2800 KC`) -> `Điểm: 110`, mở & nhận rương `60 điểm` (`r7_6_16_banner82.png`, `r7_6_19_b82_10x.png`, `r7_6_20_b82_chest.png`, `r7_6_21_b82_claimed.png`).
  - Chuyển ngược về `Sessho (81)`: `Điểm: 10`, bảo hiểm `8`, rương `60 điểm` giữ nguyên độc lập 100% (`r7_6_22_b81_isolated.png`).
  - Chiêu mộ thường (`Túc Mệnh` miễn phí -> ra `Kawaramaru`) hoạt động song song bình thường (`r7_6_24_normal_recruit.png`, `r7_6_25_normal_pulled.png`).
- [x] **`Xhzw (2303 Ước)`:** Mở `Tu Luyện -> Ước`, quay `ƯỚC` (`+6 điểm`), bấm `ĐỔI VẬN` -> nổ 5 mảnh Tử Hồn (`15/100`, `+15 điểm`), bấm `OK` khóa lượt & vào `Nhận Thưởng` nhận mốc `10 điểm (+5000 Vàng)` (`r7_6_28_xhzw_open.png` .. `r7_6_32_xhzw_claimed.png`).
- [x] **Bảo Vật (`TreasureLvUp` & `TreasureStepUp`):** Trang bị `Sách Taishou (14011615)`, Chiến Lực tướng chính `11861 -> 13061`; cường hóa lên `Lv 6` mở kỹ năng `%HP +3%` (`13661`); Tăng Bậc bằng Đá Tinh Hoa lên **`Sách Taishou +1`** (`HP +3600`, `%Sát Thương +2%`) đưa Chiến Lực **`OlinaHugh` lên `18760`** (`CHIẾN LỰC` tổng đội `59035 -> 65934`) (`r7_6_40_book_equipped.png`, `r7_6_48c_lv6.png`, `r7_6_50c_step1_done.png`, `r7_6_51_team_step1.png`).
- [x] **Trùng Sinh (`Hero.HeroRebirth` & `Equip.EquipRebirth`):** Mở `Transmute (CHUYỂN) -> Hoàn Trả`, trùng sinh `Shuran +1 Lv12` nhận hoàn trả `22K Vàng + 2535 Đá Hồn + 50 Đá Đột Phá + Shuran Lv1` (`r7_6_56_hero_rebirth.png`), và trùng sinh trang bị `Kiếm Eimaro Lv18` hoàn trả `12K Vàng` (`r7_6_57b_equip_rebirth.png`), zero lỗi Lua.
- [x] **Reset thủ công & Reset `00:00 UTC+7` + Restart/Relogin:** Đã kiểm chứng qua `/admin/events`, `/admin/clock`, restart DEV và relogin Pixel 3 XL (`r7_6_58b_home_persisted.png`, `r7_6_59_banners_post_reset.png`).

---

## 7. Kết quả chạy unit test & kiểm chứng API

Lệnh chạy sau chỉnh sửa mã nguồn cuối cùng:

```zsh
python3 -m unittest discover -s server -p 'test_*.py' -v
```

- **Kết quả:** `Ran 48 tests in 15.552s — OK` (**48/48 PASS**, 0 failures, 0 errors, 0 skipped):
  - Duy trì toàn bộ 37 test R7.4 + 6 test R7.5 (`test_38`..`test_43`).
  - 5 bộ test mới R7.6 PASS 100%:
    - `test_44_r7_6_far_chapter_combat_and_boss_node_scaling`
    - `test_45_r7_6_zcsf_lucky_cat_and_xhzw_goddess_kiss`
    - `test_46_r7_6_limitthebounty_and_treasure_lv_step_and_rebirth`
    - `test_47_r7_6_concurrent_multibanner_isolation_and_normal_recruit`
    - `test_48_r7_6_daily_utc7_reset_custom_period_and_confirmed_manual_reset`
- **Kiểm chứng API Admin:** `/admin/events` (`reset` thiếu `confirm` -> `400`; `confirm=true` -> `200`; `config`/`status` -> `200`) và `/admin/clock` (`advance`, `realtime` -> `200`) hoạt động đúng trên DEV `:8082`.

---

## 8. Artifact, Checkpoint & Khôi phục môi trường sau kiểm thử

- **Các tệp mã nguồn & tài liệu chính đã cập nhật:**
  - [server/event_runtime.py](file:///Users/vup/Documents/agy/inuyasha/server/event_runtime.py)
  - [server/event_handlers.py](file:///Users/vup/Documents/agy/inuyasha/server/event_handlers.py)
  - [server/emulator.py](file:///Users/vup/Documents/agy/inuyasha/server/emulator.py)
  - [server/extract_game_data.py](file:///Users/vup/Documents/agy/inuyasha/server/extract_game_data.py) & [server/game_data.json](file:///Users/vup/Documents/agy/inuyasha/server/game_data.json)
  - [server/test_emulator.py](file:///Users/vup/Documents/agy/inuyasha/server/test_emulator.py)
  - [poc/patch_vn_apk.py](file:///Users/vup/Documents/agy/inuyasha/poc/patch_vn_apk.py)
  - [poc/android_standalone_poc/](file:///Users/vup/Documents/agy/inuyasha/poc/android_standalone_poc) (mã nguồn Java POC tối giản, đã dọn sạch `build/`)
  - [EVENT_RECOVERY_CATALOG.md](file:///Users/vup/Documents/agy/inuyasha/EVENT_RECOVERY_CATALOG.md), [PROJECT_ROADMAP.md](file:///Users/vup/Documents/agy/inuyasha/PROJECT_ROADMAP.md), [R7_6_ACCEPTANCE_REPORT.md](file:///Users/vup/Documents/agy/inuyasha/R7_6_ACCEPTANCE_REPORT.md)
- **Bằng chứng ảnh chụp Pixel 3 XL:** Thư mục `server/qa_runs/r7_6_*.png` (`r7_6_01_login.png` .. `r7_6_59_banners_post_reset.png`).
- **Trạng thái môi trường sau hoàn tất:**
  - **Pixel 3 XL:** Đã cài lại APK STABLE gốc từ `server/backups/pre_r7_6_apk/com.cmn.inuyasha_pre_r7_6.apk` (`92M`, xác minh khớp SHA-256 trên máy: `480e732a16c2fd2a80ea745521b712c2226bd06ba841e38bf84b6de5ae2569db`).
  - **STABLE (`:8080`, PID `12133`):** Nguyên vẹn `checkpoint-vn-r6.2` (`5fed4bb`), `OlinaHugh` `Lv 20`, `MaxNodeId 2016`, `StarCount 84`, `Diamond 10`.
  - **DEV (`:8082`, PID `27904`):** Đã khôi phục save sạch từ `server/backups/pre_r7_6_dev/` (`OlinaHugh` `Lv 20`, `Vip 3`, `MaxNodeId 1713`), `EventClock` trả về `realtime`, chạy ổn định code R7.6.
- **Checkpoint Git:** Commit hoàn chỉnh trên `master` kèm tag `checkpoint-vn-r7.6` (bảo toàn nguyên vẹn `checkpoint-vn-r6.2` và `checkpoint-vn-r7.5`).

---

## 9. Đề xuất kế hoạch R7.7

*(Giữ nguyên môi trường ở R7.6 sau bàn giao — chưa tự ý promote lên STABLE hay khởi chạy R7.7 khi chưa có xác nhận)*

1. **Khôi phục `BddInfo (2507 — Mộ Thần Binh / Bát Đại Địa Ngục)`:** Mở tại Lv 26 với 51 ải, hệ thống buff, quét 3 sao, `BddShop` và liên kết `DailyTask #21`.
2. **Thiết kế Multi-Account `ServerId = 1` + PvP Bất đồng bộ & Tổ Đội Co-op NPC (`MULTI_ACCOUNT_ARCHITECTURE.md`):** Hỗ trợ nhiều tài khoản nội bộ cùng dùng chung BXH Đấu Trường (`PVP`), `Gddh (2503)`, `GGZJ (2504)`, `OpenContest (7900)` và `TeambattleInfo (2319)` dựa trên dữ liệu `TeambattlePlayerNpc`/`TeambattleHeroNpc`.
3. **Chuẩn bị lộ trình APK Standalone v0.1:** Xây dựng lớp wrapper/dịch vụ cục bộ rootless lưu dữ liệu tại `Android/data/.../files/saves/` (hỗ trợ xuất/nhập save giữ dữ liệu qua nâng cấp APK) và rà soát danh sách sự kiện/tài nguyên thiếu cần preset mô phỏng ở R7.8+.
