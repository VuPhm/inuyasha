# INUYASHA: SEEK JADE — R7.2 ACCEPTANCE REPORT
**Khôi phục hướng dẫn tân thủ & hệ thống phần thưởng gốc VN (`v5.0.4.98`)**

- **Target Environment:** DEV (`http://127.0.0.1:8082`, `server/dev_saves/`, `OlinaHugh` Lv 20 VIP 3 preserved intact)
- **STABLE Baseline (untouched):** `checkpoint-vn-r6.2` (`5fed4bb`) on port `8080` (`PID 12133`, `OlinaHugh` Lv 18)
- **VN Source Baseline:** `analysis/vn/decompiled_src/` (`com.cmn.inuyasha v5.0.4.98`)
- **APK Modification:** None — server-side fixes and extracted VN game data only.

---

## 1. Các thành phần đã khôi phục

1. **Bảng dữ liệu hướng dẫn & đầu game VN (`server/extract_game_data.py` -> `server/game_data.json`):**
   - Bổ sung `guide_relation` (73 luồng hướng dẫn từ `GuideRelation.lua`), `glory_type` (3 loại Điện Vinh Dự từ `GloryTypeModel.lua`), `glory_lv` (201 mốc cấp `0..200` từ `GloryLvRelation.lua`), `gift_login` (quà đăng nhập 7 ngày từ `GiftLoginRelation.lua`), `gift_lv` (20 mốc quà tăng cấp từ `GiftLvRelation.lua`), `mystery_shop_config`, `mystery_shop_fixed` (8 mục), `mystery_shop_odds` (138 dòng tỷ lệ).
2. **Bảo vệ vòng đời tạo nhân vật & khởi đầu Lv 1 (`server/emulator.py`):**
   - `Player.NewPlayer` bảo vệ chống ghi đè hồ sơ đã tạo (`IsNewPlayer == 0` trả về `Status = -1114`), tạo đúng Main Hero (`12010001` / `12010004`), ghi nhận qua `ResourceLedger`.
   - Khởi tạo tài khoản mới đúng chuẩn Lv 1, `StepCountList = {}`, để `GuideMng.initGuidMng()` tự kích hoạt `CgScene` -> `BattleScript0000` -> `Guide 1` theo logic client gốc VN.
3. **Sửa lỗi kích hoạt RedDot Hợp Thành / Rèn trang bị (`1400` / `1405`):**
   - Đối chiếu `BattleLayer.lua:2701, 2726` và `GuideMng.lua:239, 263`: client chỉ bật hướng dẫn Hợp Thành Trang Bị (`7601..7607`) sau ải `1-3` khi `RedDotInfo["1400"]` (`ModuleSub.eEquip`) được bật.
   - Đã cập nhật `_compute_red_dot_info()` bật `"1400"` và `"1405"` bằng `1` khi có `>= 5` trang bị chưa mặc cùng phẩm `colorLV in (1, 2, 3)`.
4. **Lưu bền vững & chống tụt ngược tiến trình hướng dẫn (`_apply_step_count_update`):**
   - Áp dụng thống nhất cho cả `ExtensionString.GuideInfo` và `Player.AlterPlayerStepCount`.
   - Cho phép phục hồi lùi hợp lệ trong lúc đang hướng dẫn (`correctMainGuideOrdinal()`, ví dụ `10 -> 7` khi relogin giữa chừng).
   - Chặn triệt để ghi đè/quay lùi đối với hướng dẫn đã hoàn thành (`guide_id == 1` có `existing >= 900`, hoặc `existing > max_ord` theo `guide_relation`).
5. **Hệ thống phần thưởng theo bước (`GetStepCountReward`) & xác minh 4 mã đặc biệt:**
   - **`2071` (Xác minh LÀ phần thưởng — `GuideEventModel[2071]`, `HomeScene.lua:1463`, Guide 7 Lv 24):** Phát 5x tướng `12013054` (*Tamotu*, `specialType=1`, phân giải ra `1116` Hồn Ngọc / `1117` Mảnh Hồn) cho tính năng Phân Giải Tướng.
   - **`2181` (Xác minh LÀ phần thưởng — `GuideEventModel[2181]`, `HomeScene.lua:1398`, Guide 9 Lv 22):** Phát 3x `16040009` (*Ngọc Miêu Tả*, nhóm `1604` `ResourcetypeSub.eDiploma`, `outputNum=20` EXP/viên -> `60 EXP >= GloryLvRelation[1].EXPTotal=50`) cho Điện Vinh Dự (`ShrineScene`).
   - **`274` (Xác minh LÀ phần thưởng — `GuideEventModel[274]`, `BattleLayer.lua:403`, `CommonFunc.lua:2896`):** Phát 1x `16030006` (*Thuốc Thể Lực 2* / `nameC="体力丸"`).
   - **`313` (Xác minh KHÔNG PHẢI phần thưởng trong VN `5.0.4.98`):** Trong `GuideEventModel[313]` (`eventTypeEnum=1`) & `GuideRelation[23]` (Lv 26), `313` là mũi tên chỉ nút Thần Binh Địa Huyệt (`ModuleSub.ePracticeBloodyDemonDomain`, `ChallengeListLayer.lua:626`), và `GuideMng.lua:613` tự bỏ qua bước này (`newOrdinal = guideMaxOrdinal + 1`). Chỉ còn nhánh code cũ sót lại ở `HomeScene.lua:1900-1903`. Emulator không tự chế vật phẩm/Yêu Linh giả; ánh xạ `313: []`, trả `Status = 0` lần đầu và `Status = -1136` nếu gọi lại.
   - Các mã còn lại trong `STEP_REWARD_MAP` (`76001, 1641, 1602, 1625, 1761, 1881, 293`) được kiểm chứng khớp VN Lua/config; mã không hợp lệ trả `Status = -1`, nhận trùng trả `Status = -1136`.
6. **Chống nhận trùng & sửa bug vận hành:**
   - `HeroRecruit.Recruit`: thực thi cooldown chiêu mộ miễn phí (`is_free == 1` trả `Status = -1` khi chưa hết CD), xóa bùa `16050003` khi hết và đồng bộ `GoodsInfo`.
   - Toàn bộ phần thưởng bước, `GiftLv`, `GiftLogin`, `MysteryShop`, `DrawRoadBox`, `Hero/Equip/TreasureRefine` ghi sổ qua `ResourceLedger` với `idempotency_key` / cờ trạng thái bền vững trên đĩa.
7. **Khôi phục tính năng đầu game gắn với hướng dẫn:**
   - Điện Vinh Dự (`Glory`), Phân Giải (`Hero/Equip/Treasure Refine`), Quà Đăng Nhập 7 Ngày (`GiftLogin`), Quà Cấp Độ (`GiftLv`), Tiệm Thần Bí thường/cao cấp (`MysteryShop`).
   - Cộng thưởng STA & chỉ số HP/AP/DEF từ Điện Vinh Dự vào `_sync_player_recover_times()` và `_compute_slot_property()` (0 tác động khi Shrine Lv 0).

---

## 2. Những thành phần còn thiếu hoặc chưa thể phục hồi

- **Kiểm thử giao diện trực tiếp trên Pixel 3 XL trỏ vào DEV (`:8082`):** Thiết bị Pixel 3 XL hiện cài APK `com.cmn.inuyasha v5.0.4.98` trỏ vào STABLE (`:8080`) đang chạy phiên chơi thực (`MaxNodeId=1820`), và ràng buộc round không được sửa STABLE hay trộn dữ liệu STABLE. Vì vậy thao tác UI thực tế trên DEV `:8082` được ghi nhận là **Chưa kiểm chứng**.
- **Nhánh phụ thuộc dữ liệu chưa mở rộng ở round sau:** Nội dung cao cấp ngoài phạm vi tân thủ (Yêu Linh / Wraith, bang hội, Arena thời gian thực, chat đa người chơi) chưa bật ở R7.2 và để dành cho bước kiểm kê toàn bộ tính năng sau R7.2.

---

## 3. Các RPC đã bổ sung / sửa đổi (`server/emulator.py`)

| Nhóm / RPC | Trạng thái | Ghi chú logic VN |
| --- | --- | --- |
| `Player.NewPlayer` | Sửa | Chặn tạo đè (`IsNewPlayer == 0` -> `-1114`), cấp Main Hero & ghi `ResourceLedger` |
| `Player.Login` | Sửa | Cập nhật `gift_login.login_days` theo ngày phân biệt (1..7) |
| `Player.AlterPlayerStepCount` / `ExtensionString.GuideInfo` | Sửa | Dùng `_apply_step_count_update()`, chống quay lùi guide đã xong |
| `Player.GetStepCountReward` | Sửa | `STEP_REWARD_MAP` đủ `76001,1641,1602,1625,1761,1881,2071,2181,274,293,313([])`; unknown `-1`, trùng `-1136` |
| `HeroRecruit.Recruit` | Sửa | Chặn `is_free == 1` khi chưa hết cooldown (`GoodReadyAt`/`ExcellentReadyAt`) |
| `Hero.HeroRefine`, `Equip.EquipRefine`, `Treasure.TreasureRefine` | Mới | Phân giải tướng/trang bị/bảo vật chưa mặc theo `outputResource` |
| `MysteryShop.{GetInfo,RefreshtGoodsList,MysteryShopBuyGoods}` & `Senior*` | Mới | Sinh danh sách, đổi/làm mới, mua hàng (dùng `IsSell: 0` = còn hàng, `1` = đã bán) |
| `Glory.{GetGloryData,GloryLvUp,GloryLvUpForOneKey}` | Mới | Nâng cấp Điện Vinh Dự bằng `1604`, cộng HP/AP/DEF & STA |
| `GiftLv.{LvGiftBags,DrawGiftBags}` | Mới | Quà mốc cấp `5..100` (5,10,12,15,18,20...) + chống nhận trùng |
| `GiftLogin.{SignInfo,DrawGiftBox}` | Mới | Quà đăng nhập 7 ngày + chống nhận trước ngày / nhận trùng |

---

## 4. Kết quả thử nghiệm tài khoản mới Lv 1 (Test A)

- **Phân loại:** **PASS bằng kiểm thử giao thức** (cả `unittest` qua `test_28_r7_2_fresh_lv1_tutorial_progression` và HTTP thực trên DEV `:8082`).
- **Luồng đã xác minh từng bước:**
  1. `Player.Login` (`IsNewPlayer=1`) -> `Player.NewPlayer` tạo Main Hero `12010004`, `IsNewPlayer=0`, gọi lại `NewPlayer` trả `Status=-1114`.
  2. `Battle.Fight` ải `1111` (1-1) -> `Lv=2` + `GuideInfo[1]=1` (hoặc `10`).
  3. `HeroRecruit.Recruit [2, 1]` -> nhận Ayame `12011014`, gọi lại miễn phí trả `-1`, `Slot.HeroCombat` vào Slot 2 thành công.
  4. `Battle.Fight` `1112` (1-2) -> `Lv=3` -> `Battle.DrawRoadBox [11, 111]` nhận thưởng, gọi lại trả `-1`.
  5. `Battle.Fight` `1113` (1-3) -> `Lv=4`, đủ `>= 5` dây chuyền trắng `13040130`, `Avatar.RedDotInfo["1400"] == 1` & `"1405"] == 1`.
  6. `Equip.EquipCompose` hợp 5x `13040130` -> `13040215`, `RedDotInfo["1400"]` về `0` -> `Slot.OneKeyEquipCombat` + `Equip.OneKeyEquipLvUp` tăng cấp trang bị thành công.
  7. Hoàn thành `1114` (`Lv=5`) -> `1115` (`Lv=6`, mở Chương 12) -> `1211` (`Lv=6`) -> `1212` (`Lv=7`) -> `AlterPlayerStepCount [1, 997]`.

---

## 5. Kết quả kiểm thử lưu tiến trình & chống nhận thưởng trùng (Test B & Test C)

- **Phân loại:** **PASS bằng kiểm thử giao thức** (`test_29`, `test_30`, và 2 lần restart daemon DEV `:8082` qua HTTP thực).
- **Test B — Tính liên tục:**
  - Cập nhật `Guide 1` lên `10`, phục hồi lùi hợp lệ về `7`, dừng & khởi động lại DEV daemon: `StepCountList["1"] == 7` và `IsNewPlayer == 0` được giữ nguyên.
  - Sau khi hoàn thành `Guide 1 = 997` và `Guide 7 = 9` (`max_ord=8 -> 9`), các gói tin cũ gửi `12` / `15` / `4` đều bị bỏ qua.
- **Test C — Phần thưởng & chống nhận trùng:**
  - `GetStepCountReward`: mã lạ `999999` -> `-1`; nhận `2071` -> 5x `12013054` -> `Hero.HeroRefine` tăng `HeroCoin`; nhận `2181` -> 3x `16040009` -> `Glory.GloryLvUpForOneKey` lên Shrine Lv 1 & tăng `FAP`; nhận `274` -> 1x `16030006`; nhận `313` -> `[]`.
  - Gửi lại `2071`, `313` (cả cùng phiên và sau khi khởi động lại DEV daemon) -> tất cả trả `Status = -1136`.
  - `GiftLogin.DrawGiftBox`: ngày 1 hợp lệ (`0`), nhận lại trả `-1`, đòi ngày 2 ở ngày 1 trả `-1`.
  - `GiftLv.DrawGiftBags`, `MysteryShop.MysteryShopBuyGoods`: nhận/mua lại đều trả `-1`; mọi biến động tài nguyên đi qua `ResourceLedger`.

---

## 6. Kết quả hồi quy & trạng thái STABLE / DEV (Test D & Test E)

- **Unit & Regression (`server/test_emulator.py`):** **PASS bằng kiểm thử giao thức** — `31/31` bài test đạt (`test_01`..`test_31`, chạy trong `7.966s`).
- **QA Benchmarks (`python3 server/qa_runner.py benchmark`):** **PASS bằng kiểm thử giao thức** — Ten-stage (`10/10` win, `Lv 12`), R3/R4 (`25/25` win, `Lv 19`, `VIP 2`, Elite + Shop + LvPlan + VipWelfare OK), Failure preset (`battle_defeat` ở `1620`).
- **Test D — Hồ sơ `OlinaHugh` trên DEV (`http://127.0.0.1:8082`):** **PASS bằng kiểm thử giao thức** — `OlinaHugh` (`200010`, `Lv=20`, `Vip=3`, `Gold=1552861`, `Diamond=4695`, `HeroCount=12`, `EquipCount=37`, `StepCountList["1"]=997`) bảo toàn nguyên vẹn; `GetStepCountReward [1761]` -> `-1136`; `AlterPlayerStepCount [1, 1]` bị chặn; `GiftLv.LvGiftBags` trả `[5, 10, 12, 15, 18, 20]`.
- **Client Pixel 3 XL (`com.cmn.inuyasha v5.0.4.98`, PID `23236`):** Đang kết nối trực tiếp STABLE `:8080` (`rpc_trace.log` hoạt động ở `1816..1820`), không bị gián đoạn; riêng kiểm thử giao diện Pixel 3 XL trên DEV `:8082` là **Chưa kiểm chứng**.
- **Trạng thái STABLE / DEV:**
  - **STABLE (`8080`, `PID 12133`):** `checkpoint-vn-r6.2` (`5fed4bb`), `OlinaHugh` Lv 18 — **chưa chạm tới**.
  - **DEV (`8082`, `PID 15599`):** chạy working-tree R7.2, `OlinaHugh` Lv 20 đã khôi phục sạch sau kiểm thử, `smoke` OK.

---

## 7. Commit & Checkpoint

- Sẵn sàng commit toàn bộ thay đổi R7.2 và gắn tag `checkpoint-vn-r7.2` trên nhánh làm việc (STABLE giữ nguyên ở `checkpoint-vn-r6.2` theo đúng quy định round).

---

## 8. Những vấn đề ảnh hưởng tới khả năng chơi full game & bước tiếp theo

1. **Cần 1 vòng kiểm thử UI trên APK trỏ DEV `:8082`** để nâng trạng thái các luồng R7.2 từ *PASS bằng kiểm thử giao thức* lên *PASS thực tế trên client* (tạo tài khoản mới Lv 1 từ màn hình tạo nhân vật -> hết Lv 7 + Hợp Thành trang bị + Điện Vinh Dự + Phân Giải) trước khi cân nhắc promote STABLE.
2. **Định hướng tiếp theo (trước R7.3 multiplayer):** Thực hiện **kiểm kê toàn bộ tính năng và nội dung game** (đối chiếu 100% module trong `FunctionOpenModel` / `ModulesInfo` / `Store` / `Activity` / `Wraith` / `VIP` / `Diamond`) để xác định phần nào đã chạy thật, phần nào còn stub, và lập lộ trình khôi phục full game trước khi làm R7.3.
