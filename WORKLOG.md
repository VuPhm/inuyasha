# WORKLOG.md — InuYasha: Seek Jade Revival (Round R0)

## 1. Công việc đã hoàn thành trong Round R0
1. **Khởi tạo workspace & Git an toàn**:
   - Khởi tạo Git tại `/Users/vup/Documents/agy/inuyasha`, cấu hình `.gitignore` chặn toàn bộ `originals/*.xapk`, `*.apk`, `*.obb`, `analysis/decompiled/`, `analysis/extracted/`, `server/save_state.json`.
   - Kiểm tra công cụ có sẵn trên Mac (`adb`, `aapt`, `apksigner`, `dexdump`, `objdump`, `nm`, `strings`, `python3`, `node`, `git`).
   - Kiểm tra thiết bị ADB ban đầu: phát hiện `Pixel_3_XL` (`crosshatch`, `192.168.1.89:41301`, Android `12`, ABI `arm64-v8a,armeabi-v7a,armeabi`), chưa cài bất kỳ gói `inuyasha|heitao|qyc|infinite|jade` nào.
2. **Thu thập & lưu bất biến đủ 4 phiên bản gốc (APK + OBB)**:
   - Tải đầy đủ `EN 5.1.1`, `ZH 5.0.0`, `TW 1.4`, `TH 5.1.3.6` vào `originals/` với quyền `chmod 444`, ghi nhận SHA256 và dung lượng chi tiết trong `SOURCE_INVENTORY.md`.
   - Xác minh chữ ký APK gốc của EN 5.1.1 bằng `apksigner` (cert SHA-1 `070989e9de9867fae95ce54387be566b46caeb7a`).
3. **Khảo sát nguồn server cũ & phân biệt game**:
   - Đã kiểm tra GitHub, Aptoide, Internet Archive/Wayback, 3DMGame, các diễn đàn CN/TW/TH và DNS 4 domain `loginsvr.*.moqikaka.com`.
   - Xác nhận toàn bộ server chính thức đã chết và không có source/emulator công khai; loại trừ nhầm lẫn với *InuYasha: Awakening*.
4. **Dịch ngược & giải mã hoàn toàn client**:
   - Disassemble `libcocos2dlua.so` bằng `objdump`: tìm ra chính xác hàm `TextUtils::setLuaEncodeString`, cơ chế XXTEA (`sign="MQKK"`, `key = md5("inuyasha_moqikaka_inuyasha")[:16] = cf68b641311b5201`).
   - Giải mã thành công toàn bộ mã nguồn Lua gốc (plain text UTF-8): EN 5.1.1 (1,120 file), ZH 5.0.0 (1,186 file), TH 5.1.3.6 (1,227 file).
   - Trích xuất schema HTTP JSON RPC (`/API/ServerList_Client.ashx`, `/client.aspx`) và xuất `server/game_data.json` (202 heroes, 439 attacks, 70 chapters, 689 nodes).
5. **Xây dựng & kiểm thử Proof of Concept (Round R0)**:
   - `server/emulator.py`: Local HTTP Server Emulator triển khai `ServerList_Client.ashx`, `Player.Login`, `Player.NewPlayer`, `Player.GetInitData`, `Battle.GetBattleInfo`, `Battle.GetNodeList`, `Battle.GetFightInfo`, `Battle.Fight` + đọc asset trực tiếp từ EN 5.1.1 APK+OBB.
   - `poc/web_poc/`: Giao diện chơi thử tương tác (Title/Connect -> Home/Đội hình & Bản đồ chương -> Trận đánh theo lượt với nền nhiều lớp `pingyuan`, sprite từ Spine `.atlas`, BGM & voice `.mp3`, lưu tiến độ về `emulator.py`).
   - Kiểm thử tự động đã chạy thành công:
     - `node --check poc/web_poc/app.js`: exit code 0.
     - `python3 server/test_emulator.py`: **4/4 tests PASSED** (`0.593s`) kiểm tra toàn bộ RPC flow và asset serving (`/assets/res/ui/dl_21.jpg`, `smap01.jpg`, `hero_quanyecha.png`, `music_login.mp3`, `/api/atlas/hero_quanyecha`, `/api/gamedata`, `/poc/`).

---

## 2. Blocker & Giới hạn ghi nhận tại Round R0
1. **Pixel 3 XL ngắt kết nối Wireless ADB giữa phiên**:
   - Lúc 00:48, Pixel 3 XL (`192.168.1.89:41301`) kết nối bình thường. Đến bước cài APK+OBB (00:57), thiết bị từ chối kết nối (`Connection refused`), `adb mdns services` chỉ còn quảng bá `_adb-tls-pairing._tcp` (`192.168.1.89:42035`), nên **chưa cài và thu logcat trực tiếp của client gốc trên Pixel 3 XL trong R0**.
   - Các AVD có sẵn trên Mac (`Pixel_2`, `UVolumeX_API31`) đều là `x86_64` không có `abilist32` (`armeabi`), nên không dùng để chạy `libcocos2dlua.so` 32-bit thay cho Pixel 3 XL.
2. **Kiểm thử giao diện Web PoC qua Chrome DevTools**:
   - Chrome trên máy chưa bật remote debugging (`DevToolsActivePort` ENOENT), nên subagent `browser` chưa mở tab Chrome tự động để kiểm chứng trực quan Web PoC; phần API/asset/JS syntax đã được kiểm chứng qua `test_emulator.py` và `node --check`.
3. **Cài đặt `apktool`/`jadx` qua Homebrew**:
   - `brew install apktool jadx` bị vướng biên dịch `python@3.15` từ source quá lâu nên đã tạm hủy (`task-44`). Toàn bộ phân tích ở R0 đã hoàn thành bằng `aapt`, `apksigner`, `dexdump`, `objdump`, `nm`, `strings` và Python; ở R1 có thể tải thẳng file `.jar` phát hành chính thức của `apktool` / `jadx` (chạy bằng `java` có sẵn) trong vài giây để repack APK.

---

## 3. Khởi chạy PoC hiện tại
```bash
python3 server/emulator.py --host 127.0.0.1 --port 8080
# Mở trình duyệt tới: http://127.0.0.1:8080/poc/
```

---

## 4. Kết quả thực hiện Round R1 (trên Pixel 3 XL Android 12)
1. **Xác nhận thiết bị & triển khai bản gốc (Chưa patch)**:
   - Thiết bị kết nối qua Wireless ADB: `adb-8A3Y0EDTX-AveQrp._adb-tls-connect._tcp` (`Pixel_3_XL`, `crosshatch`, Android 12).
   - Xác nhận máy chưa cài sẵn package/dữ liệu game cũ (`NO_EXISTING_PACKAGE`).
   - Cài APK + OBB gốc EN 5.1.1 (`main.511.com.heitao.inuyasha.guge.obb`, 122,987,645 bytes) từ `originals/` (giữ bất biến `originals/`).
   - Logcat client gốc xác nhận thư viện native 32-bit `libcocos2dlua.so` (`armeabi`) chạy ổn định (`COCOS2D_BINDING true`), không lỗi ABI/crash native; client chỉ dừng do không phân giải/kết nối được host cũ (`loginsvr.enqyc.moqikaka.com`, `118.89.45.225:80`).
2. **Đóng gói APK trỏ về Mac Emulator (`poc/patch_android_apk.py`)**:
   - Dùng `analysis/tools/apktool_3.0.3.jar` giải nén APK EN 5.1.1 sang `analysis/apktool_en/`.
   - Thêm `android:usesCleartextTraffic="true"` vào `AndroidManifest.xml`.
   - Patch binary chuỗi cấu hình NUL-padded trong `lib/armeabi/libcocos2dlua.so` (`Debug=0` -> `Debug=1`, `ManageCenter` & `ReleaseDomain` -> `http://192.168.1.250:8080/...`).
   - Patch `Entity.smali` (`MQLogin`) bỏ qua đăng nhập Google/SDK ngoài để gọi thẳng `MQHelper.loginEnd` với tài khoản local `uid=100001` và trỏ `MQUtils.smali` log lỗi về `192.168.1.250:8080`.
   - Ký debug APK `analysis/patched/com.heitao.inuyasha.guge_revival.apk` (66,346,031 bytes) bằng `~/.android/debug.keystore` và cài lên Pixel 3 XL.
3. **Bổ sung giao thức & kiểm thử luồng chơi thực tế trên Pixel 3 XL**:
   - Phát hiện `LuaMinXmlHttpRequest` mặc định giải nén `zlib/gzip` (`_isNeedUnzip = 1` -> `ZipUtils::inflateMemory`), nên đã cập nhật `emulator.py` nén `zlib` cho `/API/ServerList_Client.ashx`, `/API/ServerList_CheckResource.ashx` và `/client.aspx` (giữ `X-Plain-Json: 1` cho Web PoC).
   - Sửa các schema bắt buộc từ log/traceback thực tế trên máy:
     - Bỏ `"Lv"` khỏi `Avatar` ở `Player.Login`/`NewPlayer`/`GetInitData` (tránh crash `mFormationInfo` nil trước `GetInitData`).
     - Chuẩn hóa `ModulesInfo` (`{SubModuleId, OrderNum, IfOpen}`), UUID 36 ký tự cho `HeroInfo.Id` (khớp `IdIsValid`), `SlotInfo.HeroModelId` + đầy đủ trường `Property` (`APR1`, `FSP`, `FAP`, v.v.), `ChatServerUrl` & `ChargeServerUrl`, `BagInfo` (`BagModelId 1..9`), `BaseGetGameResourceList: [{"PlayerAttr": [...]}]` (`ResourceTypeSub` 1101/1112/1117, `Num`).
     - Bổ sung các RPC: `Player.AlterPlayerStepCount`, `Player.SyncAvatarInfo`, `Player.AvatarInfo`, `Notice.GetNoticeList`, `Enemy.GetEnemyList`, `OnlineReward.OnlineRewardInfo`, `HeroRecruit.RecruitInfo`, `TraderInfo.GetInfo`, `YiYuan.GetInfo`, `TeambattleInfo.GetInviteInfo`, `GiftLogin.SignInfo`, `Reward.Rewars`.
   - **Luồng đã xác minh chạy thành công trên Pixel 3 XL**:
     - Khởi động + giải nén OBB + preload (`GameLoginScene` -> `StartGameScene`, hiện server `S1 Sengoku Revival (Local)` và nút `Enter`).
     - Đăng nhập local (`Player.Login`) & Tạo nhân vật (`RoleCreateScene` -> `Player.NewPlayer` -> `Player.GetInitData` -> `CgScene` truyện tranh mở đầu với nút `Skip`).
     - `HomeScene` hoàn chỉnh (VIP 5, Lv 10, `St 120/200`, `En 40/40`, `8888 Diamond`, `50K Gold`, `Power 18500`, NPC Summon/Forge/Challenge, bảng `Notification`).
     - Chọn màn chơi (`AdventureScene` Chương 1: `Battle.GetBattleInfo`, `Battle.GetNodeList`, mở popup `1-1 Simple`).
     - Chiến đấu & Kết toán (`Battle.GetFightInfo` -> trận Spine2D thật theo lượt trên Pixel 3 XL ở `1-1` và `1-2 (Elite)` -> `Battle.Fight` thắng +55 Gold / +30 EXP / 30 HeroExp -> `BattleWinHintLayer` Victory -> quay lại `AdventureScene` cập nhật `★ 2/5` và mở khóa `1-3`).
4. **Lỗi còn lại / giới hạn ngoài luồng chính ở Round R1**:
   - Khi nhấn nhanh vào tab `Team` (`PlayerFormationLayer.luac:1563`), client báo thiếu `HeroInfo.WarfareColorLv` (nil vs `0`); đã bổ sung `"WarfareColorLv": 0, "WarfareLv": 0` vào `server/emulator.py` sau lần chạy trên điện thoại (chưa test lại trực tiếp trên máy cho subscreen `Team`).
   - Chưa kiểm thử đầy đủ mọi tính năng phụ trong `HomeScene` (như bấm Gacha/Summon thực tế, Forge, Shop, Guild, PvP, Chat socket TCP port 8081).
   - Máy chủ emulator chạy trên Mac LAN (`python3 server/emulator.py --host 0.0.0.0 --port 8080`).

## 5. Khởi chạy cho client Android thật trên Pixel 3 XL
```bash
python3 server/emulator.py --host 0.0.0.0 --port 8080
```

---

## 6. Kết quả thực hiện Round R2 (Khôi phục Tutorial & Đa hồ sơ EN 5.1.1)
- Chi tiết đầy đủ trong [R2_REPORT.md](file:///Users/vup/Documents/agy/inuyasha/R2_REPORT.md).
- **Khôi phục Tutorial & Luồng tân thủ**: Sửa `Player.Login` (`IsNewPlayer=1` cho `NORMAL_PROFILE`), xử lý `ExtensionString.GuideInfo`, bổ sung các RPC `HeroRecruit.Recruit`, `Slot.HeroCombat`, `Battle.DrawRoadBox`, `Battle.DrawBox`, `Player.GetStepCountReward`, `Equip.EquipCompose`, `Equip.EquipOneKeyCompose`, `Slot.OneKeyEquipCombat`, `Equip.OneKeyEquipLvUp`, `Equip.EquipLvUpForCount`, `SlotFormation.*`; sửa guard lỗi thời `> 2`/`< 3` trong `HomeScene.luac` & `GuideMng.luac` qua XXTEA trong `poc/patch_android_apk.py`.
- **Tách 2 hồ sơ**: `ServerId=1` (`NORMAL_PROFILE`, `server/saves/normal_profile.json`) và `ServerId=2` (`DEBUG_PROFILE`, `server/saves/debug_profile.json`).
- **Kiểm thử tự động & trực tiếp**: `python3 server/test_emulator.py` **5/5 PASSED** (`0.651s`); Pixel 3 XL chạy thông suốt từ tạo nhân vật `DylanBes` -> `1-1..1-5` -> Chapter 2 (`2-1..2-2`) lên **Lv 7**, tắt/mở lại không lặp tutorial, và xác minh `DEBUG_PROFILE` chạy độc lập.
- **Nền tảng Admin Ledger**: Tạo `server/economy_audit.py` (`ResourceTransaction`, `ResourceLedger` có idempotency, JSONL audit, cấm chỉnh chỉ số chiến đấu, VIP dẫn xuất từ `VipEXP`).

---

## 7. Đánh giá chuyển nền tảng sang bản Việt Nam (`com.cmn.inuyasha` 5.0.4.98)
- Chi tiết đầy đủ trong [VN_MIGRATION_REPORT.md](file:///Users/vup/Documents/agy/inuyasha/VN_MIGRATION_REPORT.md).
- **Checkpoint EN bất biến**: Git tag `checkpoint-en-r2` (`fed435c`) + backup tại `server/backups/en_r2_stable_checkpoint/`.
- **Thu thập & Thử nghiệm song song**: Tải XAPK `originals/vn/com.cmn.inuyasha_5.0.4.98.xapk` (`210,162,212` bytes, `chmod 444`), đóng gói bản thử nghiệm cô lập `poc/patch_vn_apk.py` (chuyển `libs.apk` sang `classes2.dex` và bỏ `Stub!` để chạy sạch trên Android 12).
- **Thử nghiệm trực tiếp Pixel 3 XL với `emulator.py` không sửa đổi**: Chạy thông suốt `StartGameScene` -> Tạo nhân vật (`BrownAimee`) -> CG tiếng Việt -> `BattleScript0000` -> `HomeScene` -> `1-1` -> Triệu hồi & Đội hình `Ayame` -> `1-2` (cho ra kết quả HP/RP cuối trận khớp EN 100%).
- **Kết luận**: **`SWITCH VN`** (tương thích protocol/combat/data ~99%, sẵn Việt hóa `Language.lua` + `UTMCAFETA.ttf` + CG/UI, chi phí chuyển đổi ước tính ~0.5–1 ngày); giữ nguyên APK & dữ liệu EN ở checkpoint cho đến khi hoàn tất dọn text & regression R3.

---

## 8. Kết quả thực hiện Round R3 (`SWITCH VN`, Combat & Star System Fidelity, Lv 1 -> Lv 10+)
- Chi tiết đầy đủ trong [R3_REPORT.md](file:///Users/vup/Documents/agy/inuyasha/R3_REPORT.md).
- **Chốt chuyển nền tảng VN (`com.cmn.inuyasha` 5.0.4.98)**:
  - Chuyển `server/extract_game_data.py` sang đọc config VN mặc định (`analysis/vn/decompiled_src/Config`, giữ `--client en`), xuất `server/game_data.json` gồm 204 heroes, 441 attacks, 70 chapters, 689 nodes, 34 non-zero guide NPCs, 1,001 `AttrtreeModel` nodes, 14 `AttrtreeSlotRelation` slots, 65 Nightmare chapters / 639 Nightmare nodes, và các bảng `Explore*`/`BattleConfig`.
  - Cập nhật `AssetArchive` trong `server/emulator.py` ưu tiên APK/OBB VN (`analysis/vn/extracted/com.cmn.inuyasha.apk`, `main.98.com.cmn.inuyasha.obb`) có fallback EN.
- **Khôi phục Pipeline Chiến đấu & Công thức gốc (`Phase B`)**:
  - Xác minh `CSCommon/ServerInterface.lua` (`CheckBattleResult`), `FightExpression.lua`, `BattleCalc.lua`: enemy roster thường theo từng ải không đóng gói trong client APK (`BattleNodeGuidenpcRelation` chỉ chứa `34/3816` dòng NPC hướng dẫn kịch bản), nên `_build_enemy_wave` tạo wave đúng số lượng `fightRound`, đặt boss `node_cfg["pic"]` ở wave cuối, gán `Step`/`RebornStep` thật của đồng minh và nhân hệ số độ khó `diff_mult` (`1★ -> 1.0x`, `2★ -> commonNPCAttrR/10000`, `3★ -> hardNPCAttrR/10000`) không buff ảo người chơi hay nerf quái trên `NORMAL_PROFILE`.
  - Bổ sung `_verify_battle_payload` đối soát `verifyData` (`hp` wave cuối khi client gửi lên) trong `Battle.Fight`.
- **Khôi phục Hệ thống Chấm sao, Rương & Ngộ Đạo (`Phase C`)**:
  - Giải mã nguyên nhân trận thắng thường chỉ 1 sao ở đầu game: `BattleNodeModel.lua` quy định `starCount = 1` cho Chương `11..19` (chỉ có độ khó Dễ), `2` sao cho Chương `20..22`, `3` sao từ Chương `23+`, còn `Nightmare` (`Ác Mộng`) chấm `1..6` sao.
  - Sửa lỗi `IfDrawBoxA/B/C` khởi tạo `0` thay vì boolean `False`/`True` trong `_make_chapter_state` (do Lua coi `0 == false` và `not 0` đều sai ở `BattleLayer.lua`), kích hoạt nhận rương sao & `HOÀN MỸ`.
  - Triển khai `Battle.ConFight`, `Battle.ResetCount`, `Battle.OneKeyDrawBoxs`, kiểm tra điều kiện sao trong `Battle.DrawBox`, và hệ thống `LightenStar.*` (`GetLightenStarInfo`, `LightenStar`, `LightenStarForOneKey`) cộng `AttrtreeModel` (`431 AP`, `432 HP`, `433 DEF`) vào `Slot["Property"]`.
- **Onboarding liên tục tới Lv 10+ & Sửa lỗi Live (`Phase D/E/F`)**:
  - Bổ sung `Hero.HeroLvUp`, `Hero.HeroStepUp`, `Explore.*` (`GetInfo`, `Explore`, `OneKeyExplore`, `BuyExploreNum`, `DrawDailyReward`), thưởng thăng cấp `PlayerLvRelation` + `ExploreConfig.critNum` (`+5`), `"WarfarespiritInfo": []` (sửa crash `HeroUpdateScene.luac:227`), và trường `Slot["FAP"]` (sửa lỗi popup `HeroBreakInforLayer.luac:420` sau khi Đột Phá).
  - Kiểm thử trực tiếp trên **Google Pixel 3 XL** với client VN (`PlayerId "200010"`, `"OlinaHugh"`): vượt trọn vẹn NewPlayer -> CG -> Prologue -> `1-1..1-5` -> `Ayame` Gacha/Formation -> Ch 1 & Ch 2 `HOÀN MỸ` (`DrawRoadBox`, `DrawBox`, `OneKeyDrawBoxs`) -> Lv 7 `Hero.HeroLvUp` -> Lv 8 `Hero.HeroStepUp` -> Lv 9 `Tầm Ngọc` (`Explore.Explore`) -> Ch 3 (`3-1..3-4`) -> **Lv 10** (`FAP 7160`, `4 trang bị Lv 20`, `Ayame +1`, `16★`), lực chiến & tiến trình lưu bền vững qua force-stop/mở lại; kiểm chứng trận thua `0★` khi đi thiếu trang bị/đội hình yếu ở `2-2`.
  - Khôi phục nguyên trạng `server/saves/debug_profile.json` từ `pre_r3_live_test` (`100001 InuYasha Lv 10 VIP 5`).
- **Kiểm thử tự động & Checkpoint**:
  - `python3 /Users/vup/Documents/agy/inuyasha/server/test_emulator.py`: **8/8 tests PASSED** (`0.675s`).
  - `node --check /Users/vup/Documents/agy/inuyasha/poc/web_poc/app.js`: exit code 0.
  - Tạo checkpoint khôi phục tại `server/backups/vn_r3_stable_checkpoint/` và git tag `checkpoint-vn-r3`.


## Round R5 — R4 Recovery → Fast QA, Simulated Top-Up/VIP Admin & STABLE/DEV Separation
- **Phase 0 Checkpoint Preserved:** Rescued R4 live play progression (`OlinaHugh` `200010` Lv `16`, `7-3` unlocked, `51★`), 14/14 passing tests, and backup `server/backups/vn_r4_partial_checkpoint/` into commit `975e046` (`checkpoint-vn-r4-partial`) without altering `checkpoint-vn-r3` (`476dcfa`).
- **Phase 0 Trace Bug Fixes (`server/emulator.py`):**
  - Added `_sync_player_recover_times()` to maintain valid integer `VITNextRecoverTime` and `STANextRecoverTime` across state init, normalization, `Login`, `GetInitData`, and `Avatar` sync (`RoleInforLayer.luac:378` fixed).
  - Implemented `LvPlan.{GetLvPlanInfo,OpenLvPlan,ReceiveLvPlan}`, `VipWelfare.{GetVipWelfare,DrawVipWelfare}`, and `MonthSignInfo.GetInfo` (`[]`).
- **Phase 3 Simulated Top-Up, CardInfo & Authenticated Local Admin (`server/emulator.py`, `server/economy_audit.py`):**
  - Added localhost + `X-Admin-Token` (`hmac.compare_digest`, `.admin_token` `0600`) gated endpoints: `GET /admin/state`, `GET /admin/audit`, `POST /admin/grant`, `POST /admin/vip`, `POST /admin/prepare` backed by `ResourceLedger` validation and `audit_ledger.jsonl`.
  - Implemented `PlayerCharge.{GetChargeList,ChargeInfo,DrawChargeBox,GenerateOrderID,ConfirmOrder}` and `CardInfo.{GetInfo,GenerateOrderID,Activity,DrawDailyReward,DrawBuyReward}`.
- **Phase 1 & 4 Fast QA Engine & Dual Environments (`server/qa_runner.py`, `server/env_ctl.py`):**
  - Built `server/qa_runner.py` with real `FightExpression.lua` / `BattleCalc.lua` / `FightEnum_Target` wave simulation (`simulate_fight_info`), presets (`STARTER`, `PROGRESSION`, `STRONG`, `FAILURE`), safety block refusing `:8080` and `server/saves/`, and benchmark suite (`10` stages in `0.1621s`, `25`-stage R3/R4 regression + subsystems in `0.3813s`, `FAILURE` defeat in `0.0055s`).
  - Added `--env {stable,dev}` (`8080` `server/saves/` vs `8082` `server/dev_saves/`) and `server/env_ctl.py` (`status`, `backup`, checksum-verified `rollback`, `sync-to-dev`, `smoke`).
- **Selective Pixel Verification & Suite (`server/test_emulator.py`):**
  - Updated `com.cmn.inuyasha_revival.apk` endpoint to current MacBook IP `192.168.1.250:8080` via `adb install -r` and selectively verified `Home`, `RoleInforLayer`, `Shop`, and `RechargeScene` with zero `STEP_POST` Lua errors.
  - All `18/18` tests in `server/test_emulator.py` passed (`2.295s`), `node --check poc/web_poc/app.js` exited `0`, and `env_ctl.py smoke` passed on both `8080` and `8082`.

## Round R5.1 — Display Compatibility (`Pixel 3 XL` Android 12)
- **Root Cause & Backups:** Diagnosed cold-start & `StartGameScene` `1440 x 1440` half-screen squashing (`1.775x` horizontal compression inside Android 12 compat bounds `Rect(279, 0 - 2853, 1440)` = `2574 x 1440`) caused by `AndroidManifest.xml` declaring `android:screenOrientation="portrait"` + `android:configChanges="orientation"` racing `MQActivity.onCreate` / `Cocos2dxRenderer` / `Display.lua`. Backed up pre-R5.1 APK & `server/saves/` to `server/backups/vn_r5_display_before/` before rebuilding.
- **APK Fixes (`analysis/vn/apktool_patched/`):**
  - Updated `AndroidManifest.xml` to `android:screenOrientation="sensorLandscape"` and `android:configChanges="keyboard|keyboardHidden|orientation|screenLayout|screenSize|smallestScreenSize|uiMode"`.
  - Updated `Cocos2dxRenderer.smali` (`onSurfaceChanged`) to keep `mScreenWidth`/`mScreenHeight` synced before `nativeOnSurfaceChanged`, and `MQActivity.smali` (`onWindowFocusChanged`) to call `MQUtils.hideSystemUI`.
  - Rebuilt & signed `analysis/vn/patched/com.cmn.inuyasha_revival.apk` with debug keystore (`adb install -r` preserved saves).
- **Verification & Report:** Verified cold launch, close/re-open, Server Selection -> Home, background/resume (`Requested w=2574 h=1440`, `mBounds=Rect(279, 0 - 2853, 1440)`), `AdventureScene`, `BattleScene` (`7-2`), left/right edge buttons (`Avatar` `380,135`, `SHOP` `2730,105`, `SHOP X` `2750,75`, `MẠO HIỂM` `2700,1280`), zero `NORMAL` save gameplay loss (`OlinaHugh` Lv 16, `51★`), zero R5.1 `STEP_POST` Lua errors, `18/18` tests OK, `env_ctl.py smoke` OK, `node --check` OK. Documented in `R5_1_DISPLAY_REPORT.md`.

## Round R5.2 — Connection Stability, Detached STABLE Daemon & Lv 16–20 Survey
- **Phase A Root-Cause Audit:** Verified `logcat -b crash` (`0` Java/native crashes), `dumpsys activity exit-info` (`16/16` historical exits were intentional `reason=10 USER REQUESTED` `force-stop` / `installPackageLI` during testing), and `rpc_trace.log` (`0` Lua `report.ashx` errors after R5 schema fixes). Real spontaneous instability traced to ephemeral agent-scoped emulator lifetime + MacBook DHCP IP drift (`192.168.1.89` -> `.250`, Wi-Fi MAC `88:66:5a:5b:08:ac`) & `pmset sleep 1`. No spontaneous reconnect/session-timeout bugs found.
- **Phase B Pixel 3 XL Soak & Stability Verification:** Executed 3 cold starts -> 2 real `7-2` replays (`OlinaHugh` `Gold` `173655->173795`, `Soul` `295->365`) -> 5x background/resume (`Player.AvatarInfo` 3x burst `status=0`) -> `12m20s` uninterrupted `HomeScene` soak (`12` consecutive `60s` `Player.AvatarInfo` ticks `19:52:24..20:03:23`) -> post-soak `RoleInforLayer` / `10s` background+resume / `ShopGoodsList` all on unchanged `pid=3438` with zero errors.
- **Phase C & D Persistent STABLE Hardening (`server/emulator.py`, `server/env_ctl.py`, `server/test_emulator.py`):**
  - Added `ProfileStore` `threading.RLock`, atomic temp-file + `os.replace` saves, `_trace_lock`, benign `(BrokenPipeError, ConnectionResetError)` handling, and graceful `SIGTERM` `srv.shutdown()`.
  - Tested `LaunchAgent` (`com.inuyasha.revival.stable`), confirmed macOS TCC blocks direct `launchd` access to `~/Documents/` (`EPERM`); cleaned up failing plist and implemented PID-tracked OS-detached daemon control `server/env_ctl.py daemon {start,stop,restart,status}` (`start_new_session=True`, `.stable.pid`, `stable_server.log`).
  - Verified two controlled STABLE restarts (`6187 -> 6241 -> 6251`), DEV daemon isolation (`:8082`), seamless Pixel `Shop` RPC against restarted PID `6251`, and saved baseline backup `server/backups/vn_r5_2_baseline/`.
- **Phase E Lv 16–20 Survey & Tests:** Verified Fast QA progression to Lv 19 (`STARTER`, `0.8291s`) and Lv 24 (`PROGRESSION`, `0.5591s`), identified critical R6 targets (`BossBattle.*` at Lv 18 `Ma Vương`, `PVP.*`/`PVPShop.*` for mandatory Lv 20 `Guide ID=6` `Quyết Đấu`), passed `19/19` tests (`test_19` concurrency & atomic save), `node --check`, `qa_runner.py benchmark`, and `env_ctl.py smoke` on both STABLE and DEV; documented in `R5_2_STABILITY_REPORT.md`.
