# INUYASHA REVIVAL — R5.2 CONNECTION STABILITY & PLAYABLE BASELINE REPORT

**Ngày:** 2026-11-18  
**Checkpoint nền:** `checkpoint-vn-r5.1` (`217460d`, giữ nguyên)  
**Trạng thái `STABLE`:** **`READY`** (`192.168.1.250:8080`, detached PID-managed daemon, backup đầy đủ, tách biệt hoàn toàn khỏi `DEV` `:8082`)

---

## 1. Phase A — Kết luận phân loại nguyên nhân Disconnect / Văng game

Kiểm tra chéo trên Pixel 3 XL (`Android 12`, `dumpsys activity exit-info`, `logcat`), `server/rpc_trace.log`, `WORKLOG.md` và mã nguồn client (`Network/HttpClient.lua`, `game.lua`, `Chat/ChatMng.lua`) cho kết quả rõ ràng ở cả 7 giả thuyết:

| # | Nguyên nhân khảo sát | Kết quả kiểm tra thực tế | Kết luận |
|---|---|---|---|
| 1 | **Client crash (Java/native)** | `adb logcat -d -b crash` rỗng hoàn toàn (`0` FATAL exception, `0` tombstone). `dumpsys activity exit-info` không có `CRASH`/`SIGNALED`/`ANR`. | **Không phải nguyên nhân** |
| 2 | **Lua exception** | `rpc_trace.log` ghi nhận `36` lần `STEP_POST /api/report.ashx` (thuộc 6 lỗi thiếu field ở R3/R4 như `HeroUpdateScene.luac:227`, `HeroBreakInforLayer.luac:420`, `AutoAdventure.luac:903`, `LevelPlanLayer.luac:277`, `CommonFunc.luac:655`, `RoleInforLayer.luac:378`). Toàn bộ đã được vá ở R3–R5; từ R5 → R5.2 có **`0` lỗi Lua mới**. | **Nguyên nhân UI kẹt trước R5 (đã vá)** |
| 3 | **Server emulator bị dừng / khởi động lại** | Quá trình chạy STABLE trước đây (`task-1317`, PID `3136`, tty `s002`) gắn trực tiếp vào tiến trình nền của phiên hội thoại agent, không có daemon độc lập/PID manager nên khi phiên đổi hoặc restart server, client nhận HTTP `statusCode == -1` ("请检查当前网络连接是否可用") hoặc lỗi kết nối. | **Nguyên nhân thật #1 (đã khắc phục ở Phase C)** |
| 4 | **Mất kết nối LAN / Đổi IP Wi-Fi / Sleep** | `networksetup -getinfo Wi-Fi` cho thấy MacBook dùng **DHCP (`192.168.1.250`)** (`Wi-Fi ID 88:66:5a:5b:08:ac`); trong R5 đã phát hiện APK cũ trỏ `192.168.1.89:8080` khi IP Mac chuyển sang `.250`. Ngoài ra `pmset -g` đặt `sleep 1` (nếu Mac ngủ, Wi-Fi ngắt). | **Nguyên nhân thật #2 (đã ghi nhận điều kiện vận hành)** |
| 5 | **Timeout / Hết hạn Session** | Emulator chạy `HTTP/1.0`, không bao giờ thu hồi Session (`-46`/`-1101`). Client tự gọi `Player.AvatarInfo` mỗi `60s` (`NetworkResData.lua:311`) và `3` lần liên tiếp khi resume (`game.lua:334`), tất cả trả `Status=0`. `ChatMng` thử TCP `:8081` không có chat server nên âm thầm gọi `ChatMng:destroy()` (dòng toast đã comment), không văng khỏi game. | **Không phải nguyên nhân** |
| 6 | **Android đưa về background / OOM kill** | Kiểm tra `dumpsys activity exit-info` & giữ app nền nhiều lần + soak `12` phút: không có bất kỳ lần kill nền/LMK nào trên Pixel 3 XL (`pid=3438` sống liên tục ~30 phút qua battle, resume và soak). | **Không xảy ra khi thử trên Pixel 3 XL** |
| 7 | **Thao tác chủ động của Agy (`force-stop` / `installPackageLI`)** | Toàn bộ `16/16` bản ghi trong `ApplicationExitInfo #0..#15` đều là `reason=10 (USER REQUESTED)` từ `am force-stop` hoặc `adb install -r` (`installPackageLI`) trong quá trình test R4–R5.1. | **Nguồn gián đoạn chính bị nhầm là văng app** |

**Kết luận tổng hợp:** Không tái hiện được hiện tượng disconnect tự phát hay văng crash ở phiên bản hiện tại. Cảm giác "hay disconnect/văng" trong các round trước đến từ việc **ngắt/khởi động lại server & `force-stop`/cài APK trong lúc test**, cộng thêm **đổi IP DHCP của MacBook** (`192.168.1.89 -> .250`) và **các lỗi thiếu schema Lua đã vá ở R3–R5**. Vì vậy không tự ý chèn cơ chế heartbeat/reconnect giả vào client.

---

## 2. Phase B — Kết quả kiểm tra độ ổn định trên Pixel 3 XL

Kiểm tra thực địa trên Pixel 3 XL (`192.168.1.89:40197` → `192.168.1.250:8080`, giữ nguyên APK R5.1 & save `OlinaHugh`):

1. **Khởi động lạnh 3 lần & Đăng nhập Home:**
   - 3 lần khởi động lạnh liên tiếp (`StartGameScene`, `SERVERLIST` -> `Player.Login` -> `Player.GetInitData` -> `HomeScene`): đều vào `HomeScene` bình thường, `0` lỗi Lua (`pid` lần #3 = `3438`). *(Các lần `force-stop` trước mỗi lần cold launch chỉ phục vụ thiết lập môi trường test, không dùng làm bằng chứng disconnect; sau lần #3 không dùng `force-stop` nữa).*
2. **Chạy 2 trận chiến thực tế:**
   - Trận #1 & #2 ở ải `7-2` `Dễ` (`Battle.GetFightInfo` → `Battle.Fight`, `status=0`, thắng hợp lệ): `Gold` tăng `173655 -> 173795`, `Đá Hồn` `295 -> 365`, `EXP` `233/1540 -> 553/1540`, `TL 10/200 -> 0/200`, `pid=3438` giữ nguyên.
3. **Background / Resume 5 lần liên tiếp:**
   - Thực hiện 5 chu kỳ `KEYCODE_HOME` (nền 3s) → `am start` quay lại `MQActivity`: mỗi lần resume đều đồng bộ `Player.AvatarInfo` (`handled=True status=0`), giao diện `HomeScene` giữ nguyên tỷ lệ `2574 x 1440`, `pid=3438` không đổi.
4. **Idle Soak ở `HomeScene` (~12 phút liên tục):**
   - Bắt đầu: `19:51:29` (`rpc_trace.log` dòng `495`) → Kiểm tra kết thúc: `20:03:49` (**12 phút 20 giây**).
   - Client tự gửi đều đặn **`12/12` nhịp heartbeat `Player.AvatarInfo`** mỗi phút (`19:52:24`, `19:53:24`, ..., `20:03:23`), tất cả `handled=True status=0`.
   - `pid=3438`, `mWakefulness=Awake`, `logcat -b crash` rỗng, `logcat cocos2dx` `0` lỗi, `ApplicationExitInfo` không có entry thoát mới nào.
5. **Khôi phục trạng thái sau soak & resume nền 10s:**
   - Sau `12` phút idle: mở `RoleInforLayer` (`Thể Lực: 0/200`, `Hồi Thể Lực: 00:05:10`), thoát ra, đưa app về nền `10s` (gặp cả toast thông báo Messenger hệ thống), mở lại → mở `Shop` (`ShopGoods.ShopGoodsList status=0`), thoát về `HomeScene` (`Enemy.GetEnemyList status=0`) trên cùng `pid=3438`.

*(Ảnh kiểm chứng lưu tại `/Users/vup/.gemini/antigravity/brain/6b5ac818-de8d-45ca-a178-b12bf898b223/scratch/r52_*.png`.)*

---

## 3. Phase C & D — Hạ tầng STABLE độc lập & Quy trình Chơi / Phát triển

### Các sửa đổi thực hiện (nhỏ, không thay đổi gameplay/APK)
1. **`server/emulator.py` (An toàn đa luồng & ghi save nguyên tử):**
   - Bổ sung `threading.RLock()` trên `ProfileStore` bảo vệ `handle_rpc`, `save`, `reset_state`, `admin_state_summary`, `admin_set_vip`, `admin_grant`, `admin_prepare_account`.
   - Đổi `ProfileStore.save()` & `_load_or_init()` sang ghi file tạm `.tmp.<pid>.<tid>` rồi `os.replace(...)` để tránh hỏng JSON nếu tiến trình tắt giữa chừng.
   - Bổ sung `_trace_lock` khi ghi `rpc_trace.log`, xử lý êm `(BrokenPipeError, ConnectionResetError)` trong `_send_bytes`, và bắt `SIGTERM` gọi `srv.shutdown()` có kiểm soát.
2. **`server/env_ctl.py` (Quản lý tiến trình độc lập + Khảo sát macOS `LaunchAgent`):**
   - Đã thử cấu hình `LaunchAgent` (`com.inuyasha.revival.stable` trỏ `/usr/bin/python3` tới `server/emulator.py`), nhưng vì workspace nằm dưới `~/Documents/` (được bảo vệ bởi **macOS TCC**), tiến trình con trực tiếp của `launchd` bị hệ điều hành chặn với lỗi `[Errno 1] Operation not permitted`. Không tìm cách vượt cơ chế TCC; giữ sạch `~/Library/LaunchAgents`.
   - Thay thế bằng lệnh `python3 server/env_ctl.py daemon {start,stop,restart,status} --env {stable,dev}` khởi chạy **daemon tách phiên hệ điều hành** (`start_new_session=True`, `TTY ??`), lưu PID vào `.stable.pid`/`.dev.pid` và log ra `server/stable_server.log` / `server/dev_server.log`, **sống độc lập hoàn toàn sau khi phiên Terminal/Agy kết thúc**.
3. **`server/test_emulator.py`:**
   - Thêm `test_19_concurrent_rpc_and_atomic_save_persistence` kiểm thử đa luồng RPC đồng thời + lưu nguyên tử không sót file `.tmp`.

### Xác minh STABLE & Khởi động lại có kiểm soát
- Chuyển đổi từ task nền sang detached daemon & kiểm tra khởi động lại 2 lần liên tiếp (`6187 -> 6241 -> 6251`): `ok: true`, `listening: true`, không mất save (`OlinaHugh` Lv 16, `51★`, `Gold=173795`, `Diamond=655`).
- Pixel 3 XL (`pid=3438`) tiếp tục bấm `Shop` ngay sau khi daemon STABLE đổi PID sang `6251` thành công (`20:15:40 ShopGoods.ShopGoodsList status=0`).
- Bật/tắt `DEV` daemon (`:8082`, `PID 6287`) + `env_ctl.py smoke --url http://127.0.0.1:8082 --server-id 2`: tách biệt hoàn toàn, không đụng chạm `STABLE` (`PID 6251` giữ nguyên).
- Đã tạo backup an toàn: `server/backups/vn_r5_2_before/`, `server/backups/vn_r5_2_pre_service/`, và **`server/backups/vn_r5_2_baseline/`**.

### Chính sách Chế độ Vừa chơi Vừa phát triển (Phase D)
- **STABLE (`0.0.0.0:8080`, `server/saves/`):** Dành riêng cho người dùng chơi trên Pixel 3 XL. Tuyệt đối **không dùng `NORMAL` để chạy QA**, không tự động `adb install` lại APK khi người dùng đang chơi.
- **DEV (`127.0.0.1:8082`, `server/dev_saves/`):** Mọi tính năng mới, chỉnh sửa RPC và Fast QA phát triển/chạy thử tại đây trước.
- **Điều kiện nâng cấp STABLE:** Phải qua `test_emulator.py` + `qa_runner.py` + `env_ctl.py smoke` trên `DEV`, tạo backup `env_ctl.py backup --tag ...` trước khi chạy `env_ctl.py daemon restart --env stable`.
- **Khuyến nghị mạng MacBook:** Đặt DHCP Reservation trên router (`192.168.1.1`) gán cố định `192.168.1.250` cho MAC Wi-Fi `88:66:5a:5b:08:ac` (hạn chế trôi IP LAN) và giữ Mac không tự sleep trong lúc đang chơi.

---

## 4. Phase E — Khảo sát Lv 16–20 bằng Fast QA & Đề xuất phạm vi R6

- **Chạy Fast QA độc lập (`qa_runner.py`):**
  - `STARTER` (`35` ải, `2★`): **`0.8291s`**, đạt **Lv `19`** (`MaxChapterId=15`, `Node=1517`, `35★`, `FAP=9280`).
  - `PROGRESSION` (`25` ải): **`0.5591s`**, đạt **Lv `24`** (`MaxChapterId=14`, `Node=1416`, `25★`, `FAP=35377`).
  - `qa_runner.py benchmark`: `10` ải trong `0.3199s`, hồi quy `25` ải + phụ trợ Lv 19 trong `0.6929s`, `FAILURE` (`1620`) thua ở round 2 trong `0.0132s`.
- **Tính năng & Hướng dẫn mở khóa tại mốc Lv 16–20 (`Config/FunctionOpenModel.lua`, `ModuleSubModel.lua`, `GuideRelation.lua`):**
  - **Lv 16 — `Ngộ Đạo` (`ModuleSub 2302`, `Guide 10`):** Đã có `LightenStar.*` từ R3.
  - **Lv 18 — `Ải Tinh Anh` (`ModuleSub 2202`, `Guide 8`):** Đã có `EliteBattle.*` từ R4; cần kiểm chứng kích hoạt hướng dẫn thực tế ở Lv 18.
  - **Lv 18 — `Ma Vương / Yêu Vương` (`ModuleSub 2203`/`2205`):** **`BossBattle.*` CHƯA PHỤC HỒI** (`MonsterLayer.lua:1097` truy cập `Value.BattleInfo.RecoverTime` + `BossList` -> sẽ lỗi nil khi mở từ Home).
  - **Lv 19 — `Quỹ Mỗi Ngày` (`ModuleSub 2710`):** `Daydayfund.Invest` (`CoinFundLayer.lua`, ưu tiên phụ).
  - **Lv 20 — `Quyết Đấu / Arena` (`ModuleSub 2502`, `Guide 6`):** **`PVP.*` & `PVPShop.*` CHƯA PHỤC HỒI** (`Guide ID=6` kích hoạt bắt buộc ở Lv 20 dẫn vào `ArenaHomeScene.lua`).
  - **Lv 20 — `Quét 10 lần` (`BattleForTen 2204`) & `Thời Trang` (`5600..5603`):** `Battle.ConFight` đã hỗ trợ tối đa `10` lượt; `Fashion.{DressUp,StepUp,Resolve}` tùy chọn mở rộng thêm.

### Đề xuất phạm vi Round R6 (chỉ phát triển trên DEV trước)
1. **Trọng tâm 1 (Bắt buộc cho mốc Lv 18–20):** Phục hồi hoàn chỉnh **`BossBattle.*`** (`GetBossList`, `GetBossInfo`, `GetFightInfo`, `Fight`, `BoxList`, `DrawBox`, `OneKeyDrawBox`, `ExchangeInfo`, `Exchange`, `BuyCount`, `FriendHelp`, `JiFenRanking`) và cơ chế trigger Yêu Vương sau khi qua ải trên `DEV`.
2. **Trọng tâm 2 (Hướng dẫn bắt buộc Lv 20):** Phục hồi **`PVP.GetPVPInfo`**, **`PVP.Refresh`**, **`PVP.PVPFight`** (bảng đấu NPC/bot hợp lệ từ `Pvp*` config) và **`PVPShop.PVPShopBuy`**.
3. **Bổ sung phụ trợ sạch UI Home:** Kiểm tra/đáp ứng `StartWorkReward.GetStartworkRewardInfo`, `Daydayfund.Invest` (Lv 19), `Fashion.*` (Lv 20) bằng dữ liệu VN/ZH/EN đối chiếu, rồi kiểm thử bằng Fast QA (`Lv 16 -> Lv 22+`) trên `DEV` trước khi kiểm tra chọn lọc trên Pixel tại đúng mốc Lv 18 & Lv 20.

---

## 5. Kết quả kiểm thử sau chỉnh sửa

- `python3 server/test_emulator.py`: **19/19 PASS** (`4.544s`).
- `/usr/local/bin/node --check poc/web_poc/app.js`: `node syntax OK` (`exit 0`).
- `python3 server/env_ctl.py smoke --url http://127.0.0.1:8080 --server-id 2`: `ok: true` (trên STABLE daemon `PID 6251`).
- `python3 server/env_ctl.py smoke --url http://127.0.0.1:8082 --server-id 2`: `ok: true` (trên DEV daemon cô lập).
- `python3 server/qa_runner.py benchmark`: toàn bộ benchmark & `FAILURE` guard đạt chuẩn.
