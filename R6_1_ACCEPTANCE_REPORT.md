# INUYASHA REVIVAL — ROUND R6.1
## Release Isolation & Boss/Arena UI Acceptance Report

**Client:** VN `com.cmn.inuyasha` (`v5.0.4.98`)  
**STABLE Baseline (Running Untouched):** `checkpoint-vn-r5.2` (`81a6e17`), port `:8080`, `PID 6251`, `OlinaHugh` Lv 16  
**DEV Server:** `:8082`, `PID 8431`, working tree (`checkpoint-vn-r6.1`)  
**Pixel 3 XL (`192.168.1.89:40197`):** `com.cmn.inuyasha` (`pid 3438`) **uninterrupted & APK unchanged**

---

## 1. Phase A — Bằng chứng cách ly mã nguồn STABLE / DEV

### Thực trạng phát hiện trước R6.1
Trong `server/env_ctl.py` bản R6, cả `--env stable` và `--env dev` đều gọi chung `server/emulator.py` trực tiếp từ working tree phát triển:
- Do STABLE (`PID 6251`) đã khởi chạy trước khi sửa code R6 nên bộ nhớ vẫn chạy `checkpoint-vn-r5.2`.
- Tuy nhiên, nếu STABLE restart bất kỳ lúc nào (crash, reboot hoặc `env_ctl.py daemon restart --env stable`), STABLE sẽ **tự động nạp code DEV chưa phát hành** từ `server/emulator.py`.

### Giải pháp cách ly đã triển khai (`server/env_ctl.py`, `server/emulator.py`, `.gitignore`)
1. **Tách thư mục phát hành bất biến (`server/releases/`):**
   - Mỗi bản phát hành được xuất từ Git commit/tag bất biến qua `git archive` vào `server/releases/versions/<tag>/` kèm `RELEASE.json` chứa commit hash và bảng SHA-256 của từng tệp `.py`/`.json`.
   - Liên kết nhẹ `analysis` và `poc` về repo root để bản cũ (`checkpoint-vn-r5.2`) vẫn phục vụ APK/OBB/PoC mà không nhân đôi dung lượng, đồng thời bản R6+ hỗ trợ biến `INUYASHA_ROOT_DIR` và đọc `RELEASE.json`.
2. **STABLE ghim cứng vào bản phát hành, tách hẳn working tree DEV:**
   - `server/releases/stable` -> trỏ `versions/checkpoint-vn-r5.2` (`81a6e1755ec08915f33d848a0a9d6b49a1f36f28`).
   - `server/releases/stable_release.json` lưu `active_release`, `previous_release`, `commit`.
   - `start_env_daemon("stable")` kiểm tra SHA-256 và **từ chối khởi chạy** nếu thiếu release hợp lệ hoặc trỏ nhầm vào `server/emulator.py` working tree (`isolated_from_dev == true`).
3. **Gắn phiên bản rõ ràng theo môi trường:**
   - `/health` trả khối `release` (`release_tag`, `commit`, `source`, `release_dir`).
   - `env_ctl.py status` hiển thị đồng thời `release` của STABLE, `working_tree` của DEV, `live_health_release` và danh sách `staged_releases`.
4. **Tách riêng dữ liệu chạy:**
   - STABLE: `server/saves/` + `server/rpc_trace.log` + `server/stable_server.log`.
   - DEV: `server/dev_saves/` + `server/dev_rpc_trace.log` + `server/dev_server.log`.
5. **Cơ chế Stage / Promote / Rollback đơn giản bằng Python:**
   - Stage bản mới không chạm STABLE: `python3 server/env_ctl.py release-stage --ref <tag>`
   - Promote có kiểm soát (dry-run nếu thiếu `--confirm`, tự backup `server/saves/` trước khi chuyển): `python3 server/env_ctl.py promote --ref <tag> --confirm [--restart]`
   - Rollback 1 lệnh về bản trước + kiểm tra SHA-256: `python3 server/env_ctl.py rollback-release [--ref <tag>] [--backup-dir <dir>] --confirm [--restart]`
6. **Kiểm chứng thực tế:**
   - Test tự động `test_24_release_isolation_promote_and_rollback` xác minh snapshot `r5.2` không chứa `BossBattle.GetBossList`, promote/rollback trỏ đúng, sửa bất kỳ 1 byte trong bản STABLE đều bị chặn do lệch SHA-256.
   - Đã chạy thử khởi động snapshot `server/releases/stable/server/emulator.py` trên cổng phụ `18089` -> `/health` trả `ok=True`, `env=stable`.

---

## 2. Phase B — Báo cáo tương thích UI client VN (Đối chiếu EN / TH / ZH / VN)

| Hệ thống / Màn hình | Tệp Lua đã đối chiếu | Kết quả tương thích RPC & Schema |
|---|---|---|
| **BossBattle (Danh sách & Đánh)** | `Adventure/MonsterLayer.lua` | Tương thích 100%: `GetBossList` (`BattleInfo.{AttackNum,RecoverTime,BuyCount,JiFen,NextBoss}`, `BossList[].{Id,PlayerId,PlayerName,BossModelId,Name,Lv,CurHP,TotalHP,AwayTime,CanHelpTime,DropResource}`), `FriendHelp`, `BuyCount` (`ceil(i/2)*10`), `JiFenRanking` (`Id,PlayerId,Name,Lv,FAP,JiFen,HeadImageId`), `Slot.SlotFormations`. |
| **BossBattle (Xuất hiện & Kết toán)** | `BossAppearLayer.lua`, `BattleLayer.lua`, `BattleSettleLayer.lua`, `BattleWinHintLayer.lua`, `BattleDataCache.lua` | Tương thích luồng trigger `BossId` + `GetBossInfo` + `GetFightInfo` + `Fight` (`HurtValue`, `SingleJiFen`, `BossExist`, `BaseGetGameResourceList`). Đã cập nhật đồng bộ `BattleInfo.HasBoss` (`"True"`/`"False"`) để `BattleLayer:2244` không ghi đè mất trạng thái sau `ConFight`. |
| **Boss Reward** | `Adventure/BossRewardPreviewLayer.lua`, `LuckbossValueShopModel.lua` | Tương thích 100%: `BoxList` trả `[{NeedValue, IsDraw}]` đủ 35 mốc `100..3500`; `DrawBox` và `OneKeyDrawBox` trả `BaseGetGameResourceList` tương thích `MessageBoxLayer:showGetGameResoureList`. `ExchangeInfo`/`Exchange` giữ stub rỗng an toàn. |
| **Arena (Danh sách, Bot, Đánh)** | `Challenge/ArenaHomeScene.lua`, `Grab/FightBalanceLayer.lua`, `Challenge/ArenaRankLayer.lua` | Tương thích 100%: bot mang GUID 36 ký tự (`IdIsValid == true` nên client không tự ép `IsWinFight = 1` ở dòng `1540`); `PVPFight` trả `IsPVP=True`, `FightInfo.FightObjs`, `ChoiceGetGameResource` gồm đúng `1` thẻ `IsDrop=1` + `2` thẻ `IsDrop=0` khớp `FightBalanceLayer:321-418`; `GetPVPTopRankList` trả mảng 5 phần tử khớp `TopRankList[self.mPlayerStep]` ở `ArenaRankLayer:400`; `Slot.SlotFormations` trả đủ `{PlayerInfo, SlotInfos, MateInfos, SlotFormationInfo, SkillInfos, CombatPet}`. |
| **PVP Shop** | `Challenge/ArenaExchangeLayer.lua`, `PvpShopModel.lua` | Đã sửa điều kiện `_rpc_pvp_shop_buy` khớp dòng `23` của `ArenaExchangeLayer.lua`: chỉ kiểm `needRank` khi `step == needStep` (vượt bậc cao hơn `needStep` được phép mua bình thường). Đủ 40 vật phẩm, `BuyNum`/`BuyTotalNum` khớp UI. |
| **Guide Lv 18 & Lv 20** | `AdventureScene.lua`, `EliteLayer.lua`, `ChallengeListLayer.lua`, `ArenaHomeScene.lua`, `GuideMng.lua` | Guide 8 (Lv 18, events `212->215`) và Guide 6 (Lv 20, events `202->204->205->206`) gửi `Player.AlterPlayerStepCount`, lưu bền vững trong `StepCountList`. |

### Kết quả kiểm chứng 2 lỗi client gốc đã ghi nhận

1. **`ExtraActivity/StartworkRewardLayer.lua` & `ExtraActivity/StartworkRewardTipLayer.lua` — Lỗi chính tả có sẵn ở cả 4 bản (`EN 5.1.1`, `TH 5.1.3.6`, `ZH 5.0.0`, `VN 5.0.4.98`), KHÔNG crash khi sử dụng thực tế:**
   - `StartworkRewardLayer.lua:90` viết `return self.mCurRewardInfo and #self.self.mCurRewardInfo or 0`. Đối chiếu `Common/Ui.lua:2658` cho thấy dòng `--listview:reloadData()` khi khởi tạo đã bị comment out, còn dòng `127` của `StartworkRewardLayer.lua` gọi `self.mRewardListView:reloadData(self.mCurRewardInfo)` với `dataset != nil`, đi vào nhánh `if dataset then itemCount = #dataset` (`Ui.lua:2507-2508`) và **không bao giờ gọi `numberHandler`**.
   - `StartworkRewardTipLayer.lua:15` truyền `returnAction = function() layer:removeFromParent()() end`. Đối chiếu `Common/ModalColorLayer.lua:55` cho thấy `ModalColorLayer` đọc `params.onCloseCallback` và bỏ qua hoàn toàn `params.returnAction` -> **dead code không bao giờ thực thi**.
   - **Khắc phục lỗi che chức năng trước đó:** Trong `R6`, việc giữ `RedDotInfo["2718"] = 0` vô tình làm `StartworkRewardLayer.lua:61` luôn báo đã nhận thưởng. R6.1 đã sửa `_compute_red_dot_info()` trả `"2718": 1` vào Thứ 2–Thứ 5 khi chưa nhận hôm đó và `"0"` sau khi đã nhận hoặc cuối tuần, khôi phục đúng cơ chế gốc.

2. **`Adventure/BossAppearLayer.lua` — Sai khác thực tế nhẹ ở cả 4 bản (`EN 5.1.1`, `TH 5.1.3.6`, `ZH 5.0.0`, `VN 5.0.4.98`):**
   - **Dòng `479` (`ceil(i/10)` vs `ceil(i/2)`):** Khi mở mua lượt ngay tại popup `BossAppearLayer` lúc `AttackNum == 0`, UI tính nháp giá `math.ceil(i/10) * 10` trong khi `MonsterLayer.lua:133` và `LuckbossConfig.desc` tính `math.ceil(i/2) * 10`. Server giữ đúng công thức gốc `ceil(i/2) * 10`. Hậu quả thực tế: nếu người chơi mua `>= 3` lượt từ `BossAppearLayer` với số Kim Cương nằm đúng giữa khoảng lệch (ví dụ có 30–39 Kim Cương cho 3 lượt đầu), client cho bấm xác nhận nhưng server trả `Status = -1`; bấm nút `+` ở `MonsterLayer` luôn khớp giá 100%.
   - **Dòng `568` (thiếu `playerId` thường):** `BossAppearLayer.lua:568` gọi `setFightBossInfo({Id = ..., IsFullFight = ...})` thiếu trường `playerId` (so với `MonsterLayer.lua:1274`), nên nếu đánh Boss trực tiếp từ popup `BossAppearLayer` khi vừa xong ải, `BattleWinHintLayer.lua:140` ẩn nút "Toàn Server Xin Giúp" tại màn kết toán (không văng lỗi; nút xin giúp trong `BossAppearLayer` và `MonsterLayer` vẫn hoạt động bình thường).

---

## 3. Danh sách lỗi client thực tế còn lại (Client-side Backlog)

1. **`BossAppearLayer.lua:479`** — sai công thức ước tính giá mua lượt `ceil(i/10)` thay vì `ceil(i/2)` (cùng tồn tại ở EN/TH/ZH/VN).
2. **`BossAppearLayer.lua:568`** — thiếu key `playerId` khi vào trận từ popup BossAppear (cùng tồn tại ở EN/TH/ZH/VN).
3. **`MonsterLayer.lua:519`** — truyền `retVal.SkillInfos` thay vì `retVal.Value.SkillInfos` khi xem đội hình top JiFen (an toàn vì `PlayerFormationLayer` nhận `nil`, chỉ không hiện kỹ năng chủ tướng đối thủ nếu sau này bật Skill hệ mới).
4. *(Dead code, không ảnh hưởng chạy)* `StartworkRewardLayer.lua:90` (`#self.self.mCurRewardInfo`) và `StartworkRewardTipLayer.lua:15` (`removeFromParent()()`).

---

## 4. Phase C — Kế hoạch kiểm thử thực tế trên Pixel 3 XL (Đang chờ xác nhận thời điểm)

- **Hiện trạng thiết bị:** Pixel 3 XL (`192.168.1.89:40197`) đang chạy `com.cmn.inuyasha` (`pid 3438`) kết nối vào `192.168.1.250:8080` (`STABLE`). Do URL `192.168.1.250:8080` được cấu hình thẳng trong client VN đang cài, mọi kiểm thử giữ nguyên APK đều cần cho phép tạm chuyển cổng `:8080` sang bản `checkpoint-vn-r6.1` trong lúc test (hoặc cài APK DEV riêng — không ưu tiên).
- **Quy trình 6 bước không chạm tài khoản `NORMAL` (`OlinaHugh`):**
  1. Đợi xác nhận thời điểm từ người dùng -> chạy `promote --ref checkpoint-vn-r6.1 --confirm --restart` (đã có backup `pre-r6-release-check` + tự tạo thêm backup trước promote; downtime ~2 giây).
  2. Trên `ServerId=2` (`S2 Debug R1`) — **không chạm `ServerId=1` (`OlinaHugh`)** — dùng QA API/preset nâng `ServerId=2` lên Lv 18 và Lv 20 kèm Boss kích hoạt sẵn.
  3. Mở game trên Pixel chọn **Server 2**, kiểm tra trực tiếp 6 mục:
     - Mở màn **Ma Vương (`MonsterLayer`)** -> kiểm tra danh sách Boss, `NextBoss`, rương mốc 35 điểm, bảng xếp hạng JiFen.
     - **Khiêu chiến Boss** (thường hoặc Toàn Lực) -> nhận thưởng kết toán `HurtValue`, `SingleJiFen`, nhận rương mốc.
     - Kiểm tra **Guide Lv 18 (Guide 8)** / **Guide Lv 20 (Guide 6)** khi vào Ải Tinh Anh và Quyết Đấu.
     - Mở **Arena (`ArenaHomeScene`)** -> kiểm tra danh sách bot thật, làm mới (`Refresh`), xem đội hình 1 bot (`Slot.SlotFormations`).
     - **Đánh 1 trận bot** -> kiểm tra replay combat, thắng/thua thực, lật 3 thẻ `FightBalanceLayer`.
     - Mở **PVP Shop (`ArenaExchangeLayer`)** -> đổi thử 1 vật phẩm bằng `PVPCoin`.
  4. Ngay sau khi nghiệm thu: giữ nguyên R6.1 trên STABLE nếu đạt, hoặc rollback về `r5.2` tức thì bằng 1 lệnh nếu phát hiện lỗi UI.

---

## 5. Phase D — Kế hoạch phát hành R6 lên STABLE & Rollback

### Trạng thái sẵn sàng (Chưa tự promote)
- **Bộ regression tests:** `24 / 24 PASS` (`test_emulator.py`, gồm `test_20..test_24`).
- **Fast QA benchmark:** 10-stage (`10/10`), R3/R4 (`25/25`), `FAILURE` defeat chuẩn xác.
- **Schema save `OlinaHugh` Lv 16:** Tương thích ngược 100%, không mất tiến trình hay tài nguyên.
- **Backup STABLE mới nhất:** `server/backups/pre-r6-release-check` (đủ SHA-256 `MANIFEST.json`).
- **Bản phát hành R6 đã chuẩn bị:** `checkpoint-vn-r6` và `checkpoint-vn-r6.1` (sẵn sàng promote).

### Lệnh Promote lên STABLE (khi người dùng xác nhận)
```bash
# Kiểm tra dry-run
python3 server/env_ctl.py promote --ref checkpoint-vn-r6.1

# Áp dụng phát hành lên STABLE (tự backup saves -> chuyển release pointer -> restart :8080)
python3 server/env_ctl.py promote --ref checkpoint-vn-r6.1 --confirm --restart

# Smoke check sau khi lên STABLE
python3 server/env_ctl.py smoke --url http://127.0.0.1:8080 --server-id 2
python3 server/env_ctl.py status
```

### Lệnh Rollback khẩn cấp về `checkpoint-vn-r5.2`
```bash
# Quay lại mã nguồn R5.2 (chỉ đổi code về R5.2, giữ save hiện tại hoặc kèm --backup-dir để khôi phục save)
python3 server/env_ctl.py rollback-release --ref checkpoint-vn-r5.2 --confirm --restart

# Hoặc rollback cả mã nguồn + save backup trước promote:
python3 server/env_ctl.py rollback-release --ref checkpoint-vn-r5.2 --backup-dir server/backups/pre-r6-release-check --confirm --restart
```

---

## 6. Đề xuất Round R7 (sau khi phát hành R6 thành công)
1. **Nghiệm thu UI Lv 20–30 tiếp theo:** Luyện Tháp / Thí Luyện (`Wrestle` / `Tower`), Tẩy Luyện / Tinh Luyện Trang Bị, Chiến Trận (`Warfarespirit`), Pet.
2. **Bản vá Lua client gọn (tùy chọn khi cần cập nhật hotfix):** Sửa `BossAppearLayer.lua:479` (`ceil(i/2)`), `BossAppearLayer.lua:568` (`playerId`), `MonsterLayer.lua:519` (`retVal.Value.SkillInfos`), dọn dead-code `StartworkRewardLayer.lua:90` / `StartworkRewardTipLayer.lua:15`.
3. **Thưởng xếp hạng Arena hàng ngày (22:00) / Hệ thống Thư (`Mail`)** để người chơi solo nhận phần thưởng cuối ngày từ `PvpRankRewardRelation_1..5` trực tiếp trong hòm thư.
