# R7.21 — Khôi phục Phó Bản Tổ Đội (`TeambattleInfo`, APK 840)

Baseline `checkpoint-vn-r7.20` (`4a4adce`), APK 839. Bản phát hành **840** (`5.0.4.98-r7.21`) cho package chính `com.cmn.inuyasha.revival`.
- APK: `analysis/vn/patched/com.cmn.inuyasha.revival_r7_21_standalone.apk` (`224.400.359` bytes)
- SHA-256 APK: `19e67d6fd801e2170ff60005940ef414dbf8db8fc4db5008ed32d6c2d56c888f`
- Checkpoint git: `checkpoint-vn-r7.21`

## 1. Xác minh nhanh R7.20 trên APK 839 (chỉ đọc, không sửa save)

- **Hộp thoại xác nhận nút "Cam trở xuống" (`DisassembleNewScene.luac` từ APK 839 trên Pixel 3 XL):** xác nhận có hộp thoại `MessageBoxLayer` (`Xác nhận chuyển hóa nhanh`, nút trái hủy / đóng, nút phải gọi `doBatchRefine()`, `mAutoLianHeroList2`).
- **Tình trạng save `OlinaHugh` (`acct_2`, `s1_acct_2.json`) sau lần chuyển hóa hàng loạt:**
  - Nhật ký thiết bị (`rpc_trace.log` / `audit_ledger.jsonl`) ghi nhận `Hero.HeroRefine` cấp `+328.950` HeroCoin (`-> 464.950`), `+87.500` HeroEXP (`-> 170.335`), `+262.500` Gold.
  - Tại thời điểm nghiệm thu R7.21 (save trên Pixel 3 XL sau R7.20, không ghi đè hay khôi phục): `OlinaHugh` (`PlayerId: 200010`, Lv `30`, `Diamond: 154.160`, `Gold: 6.534.478`, `HeroCoin: 464.950`, `HeroEXP: 174.615`) còn **18 tướng** và `0` tướng chưa luyện phẩm chất Cam trở xuống (`q<18, Step==0, LiantiLv==0`).
- **Tình trạng sao lưu trước chuyển hóa:** không có bản sao lưu ngay trước thời điểm chuyển hóa ở Lv 29 (bản gần nhất trong thiết bị là ngày 19/11 Lv 20 / 12 tướng; trên Mac là ngày 20/11 `server/backups/pre_r7_12_1_pixel_820..822/s1_acct_2.json` ở Lv 23 / 295 tướng). Toàn bộ save `acct_1..acct_4` được giữ nguyên, không tự ý khôi phục.

## 2. Triển khai Phó Bản Tổ Đội (`Teambattle`) & Tài nguyên Đá (`2000`)

- **Trích xuất dữ liệu gốc VN (`server/extract_game_data.py` -> `server/game_data.json`):**
  - `teambattle_config` (`maxHoldTime=43200`, `needVIT=20`, `holdTimeOver=10`, `matchPlayerCloserFAPADD=5`)
  - `teambattle_nodes`: **24 ải** (`1111..1614`, đủ 6 chương × 4 độ khó)
  - `teambattle_hold_drops`: **144** dòng tỷ lệ rơi trấn thủ (`TeambattleHoldDropoddsRelation`)
  - `teambattle_hero_drops`: **4** bảng rơi mảnh tướng (`TeambattleNodeDropHeroRelation`)
  - `teambattle_shop`: **18** món (`TeambattleShopModel`, tab Đá Lv4–Lv6, tiền tệ `16050023`)
  - `teambattle_player_npcs`: **72** đồng đội NPC (`TeambattlePlayerNpc`) & `teambattle_hero_npcs`: **432** đơn vị đội hình (`TeambattleHeroNpc`)
  - `gem_model`: **90** loại Đá (`GemModel`, `rtype = 2000`)
- **Backend (`server/teambattle_handlers.py`, nối vào `ProfileStore` trong `server/emulator.py`):**
  - Triển khai đủ **22 RPC** của `TeambattleInfo`, `TeambattleFightinfo`, `TeambattleHoldinfo`, `TeambattleShopinfo`.
  - Mở khóa 24 ải theo đúng chuỗi `needNodeModelID`; khóa 1 lần thắng/chương/ngày (UTC+7); giữ quyền đánh lại nếu thất bại (`IsWinFight == 0`).
  - Hỗ trợ chơi một mình cùng **đồng đội NPC** từ `TeambattlePlayerNpc`/`TeambattleHeroNpc` qua `FightForMatch`, `InviteFriends`, `InviteFriendsForOneKey`, `InviteAll` (kích hoạt `+5%` chỉ số bạn/guild mỗi vị trí qua `matchPlayerCloserFAPADD`), giữ cấu trúc thành viên `kind: "player" | "npc"` để mở rộng đa người chơi qua private server về sau.
  - Đội địch dùng **3 BOSS nguyên bản từng chương** (`12015001..12015018`, `百战域boss1..6`) cân bằng từ chỉ số thực và chỉ số phụ trung bình của `TeambattleHeroNpc` tại chính ải đó (`5.8x HP`, `1.48x AP`, `1.0x DEF`; riêng chương 3 áp dụng hệ số hình học `0.85` cho 2 BOSS tuyến sau). Xóa trạng thái phòng ngay khi kết thúc `Fight` để thoát giữa trận hoặc khởi động lại game không bị kẹt.
  - Khôi phục **Trấn thủ 12h** (`HeroHold`, trừ `20` Thể Lực, kiểm tra sở hữu tướng 5 sao `starNum == 5, specialType ~= 255` và không trùng giữa các ải), `DrawHoldReward`, `QuickDrawHoldReward` (trừ Kim Cương theo giờ lẻ còn lại), và giữ khóa chương qua ngày mới cho tới khi nhận thưởng trấn thủ.
  - Khôi phục **Shop Phụ Bản 18 món** (`16050023`) và đường lưu **Đá (`2000`)** trong `state["gems"]`, trả về qua `Player.GetInitData.GemInfo`; đồng thời các **Túi Đá (`16020037`, `16020039`, `16020040..46`)** đã mở được bình thường qua `Goods.GoodsUse`.
  - Liên kết tiến trình **Nhiệm vụ ngày `#34`** (`DailyTaskInfo` khi tham gia `Fight`) và **Thành tích ngày 8+ `#27`** (`SuccessTargetInfo` khi `HeroHold`).
- **Client Lua & Build (`poc/build_standalone_apk.py`):**
  - Đóng gói `teambattle_handlers.py` vào `server_bundle.zip`.
  - Vá `InstanceNewMainScene.luac` kiểm tra `event.Status == 0` trước khi mở `TeamWaitScene` (tránh mở phòng rỗng khi bị từ chối `-7403`/`-7409`/`-7414`) và vá `TeamWaitScene.luac` làm mới danh sách đội ngay khi bấm `Mời toàn server` trong phòng tạo tay.

## 3. Nghiệm thu

- **Kiểm thử Python (`100/100 PASS` trong `95.808s`):** gồm `test_emulator`, `test_r718`, `test_r7181`, `test_r719`, `test_r720`, và `test_r721` (kiểm đủ toàn bộ 24 ải, mở khóa tuần tự, thất bại/đánh lại, lưu phòng khi khởi động lại, trấn thủ 12h, tăng tốc KC, 18 món shop + lưu Đá, mở 8 túi Đá `16020037`/`16020040..46`, `DailyTask #34`, `SuccessTarget #27`, và không ảnh hưởng chiêu mộ/túi tướng/Tầm Ngọc).
- **Kiểm thử Lua trong APK 840 (`3/3 PASS`):** `poc/test_r721_lua.py` xác nhận bản vá `InstanceNewMainScene.luac`, `TeamWaitScene.luac` và `teambattle_handlers.py` trong APK ký chính thức.
- **Cài đè APK 840 & Kiểm thử giao diện thực tế trên Pixel 3 XL (`adb install -r`):**
  - Kiểm nghiệm trực tiếp bằng save QA cách ly tạm thời `acct_5` (`R721QA`, Lv.85): vào `Tu Luyện` → `PB Đội` (`InstanceNewMainScene`), bấm `Tìm Nhanh` vào phòng chờ (`TeamWaitScene`, hiện 2 đồng đội NPC `DaytimeHeng Sha` & `Black`), bấm `Chiến Đấu` thắng `BOSS Jinenji Yokai` (`1111`), hiện `CHIẾN THẮNG` (`InstanceWinHintLayer`) kèm `10 Mảnh Đá` + `1 Túi Đá Lv3`, nhận `Quà Qua Ải Lần Đầu` (`40 KC`, `40 Mảnh Đá`, `3 Túi Đá`), mở khóa độ khó `KHÓ` (`1112`), vào `Shop Phụ Bản` (`InstanceExchangeLayer`) mua `Đá Bạo Kích LV4` (`20001004`, trừ `550 -> 500` Mảnh Đá), và xác nhận lưu `gems`, `nodes["1111"]`, `shop["1"]` trên đĩa.
  - Sau khi xóa save QA tạm `acct_5` và trả chỉ mục về `acct_2`, toàn bộ 6 tệp save gốc (`accounts_index.json`, `normal_profile.json`, `debug_profile.json`, `s1_acct_2.json` [OlinaHugh], `s1_acct_3.json`, `s1_acct_4.json`) trên Pixel 3 XL **khớp SHA-256 từng byte** với bản chụp trước kiểm thử.
