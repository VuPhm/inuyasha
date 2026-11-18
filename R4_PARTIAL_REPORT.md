# R4_PARTIAL_REPORT.md — InuYasha Revival (R4 Partial Checkpoint)

Báo cáo bảo toàn thành quả Round R4 trước khi chuyển hướng sang **R5 Fast QA + STABLE/DEV**.

---

## 1. Phạm vi thay đổi đã kiểm kê từ R3 (`476dcfa`)

Các file thay đổi trên git trước khi tạo checkpoint:
- [extract_game_data.py](file:///Users/vup/Documents/agy/inuyasha/server/extract_game_data.py): Bổ sung `parse_vip_buy_limit` và trích xuất thêm `goods_model` (`1,043`), `shop_goods` (`6`), `shop_goods_price`, `vip_buy_limit`, `treasures` (`46`), `treasure_debris` (`228`), `treasure_loot_config`, `elite_nodes` (`36`), `elite_config` từ config VN (`analysis/vn/decompiled_src/Config`).
- [game_data.json](file:///Users/vup/Documents/agy/inuyasha/server/game_data.json): Tái xuất từ config VN (`3,250,407` bytes).
- [emulator.py](file:///Users/vup/Documents/agy/inuyasha/server/emulator.py):
  - Cô lập môi trường test (`trace_path` tùy chọn trên `ProfileStore` & `GameEmulatorState` để test không ghi vào `server/rpc_trace.log`).
  - Sửa lỗi khai thác nhận lặp `Battle.DrawRoadBox` (kiểm tra `CanDrawRoadBox{suffix} == 1`) và đồng bộ `Avatar["XYCurCount"]` / `Avatar["GoodsInfo"]` / `Avatar["TreasureDebrisInfo"]`.
  - Sửa bug cộng dồn số lượng hiển thị trong `BaseGetGameResourceList[...]["Goods"]` (trả về delta `rnum`, còn `Avatar["GoodsInfo"]` gửi tổng stack).
  - Triển khai mới: `Battle.AllChapterInfo`, `ShopGoods.ShopGoodsList`, `ShopGoods.GetShopGoodsInfo`, `ShopGoods.BuyGoods`, `Goods.GoodsUse`, `TreasureLootProtect.GetTreasureLootProtectInfo`, `TreasureLootProtect.TreasureLootProtect`, `TreasureLoot.TreasureDebrisTargetList`, `TreasureLoot.TreasureLoot`, `TreasureLoot.TreasureLootForCount`, `TreasureDebris.TreasureDebrisCompose`, hỗ trợ gắn `Book` / `Horse` vào `Slot.OneKeyEquipCombat` + cộng chỉ số Treasure trong `_compute_slot_property`, phần thưởng `GetStepCountReward` (`1761`, `1881`), và bộ RPC `EliteBattle.*` (`GetBattleInfo`, `GetFightInfo`, `Fight`, `DrawFirstReward`, `BuyFightCount`).
- [test_emulator.py](file:///Users/vup/Documents/agy/inuyasha/server/test_emulator.py): Bổ sung `test_09` đến `test_14` (tổng **14 ca kiểm thử**), chạy hoàn toàn độc lập với `server/saves/` và `server/rpc_trace.log`.

---

## 2. Kết quả kiểm thử tự động & Trạng thái Save

- **Automated tests**:
  - `python3 /Users/vup/Documents/agy/inuyasha/server/test_emulator.py`: **14/14 PASSED** (`1.434s`).
  - `/usr/local/bin/node --check /Users/vup/Documents/agy/inuyasha/poc/web_poc/app.js`: exit code `0`.
- **Trạng thái save tại thời điểm dừng R4**:
  - `NORMAL_PROFILE` (`server/saves/normal_profile.json`, `PlayerId="200010"`, `"OlinaHugh"`): **Lv 16** (`EXP=5808`), **Chương 7 (`maxCh=17`, `maxNode=1713` — đã qua `7-2`, mở `7-3`)**, Chương 1–6 hoàn thành (`51 ★`), `FAP=20575`, `Gold=173655`, `Diamond=655`, `VIT=10`, `STA=93`, `StarId=9` (đã test `Ngộ Đạo` / `LightenStar` trực tiếp trên Pixel), `4` heroes (gồm `4` slot đội hình), `25` equips, `1` treasure (`Ngựa Xương` `14020501` ghép từ `Đoạt Bảo` và trang bị trên Slot 1), `18` goods.
  - `DEBUG_PROFILE` (`server/saves/debug_profile.json`, `PlayerId="100001"`): Nguyên vẹn không bị ghi đè (`sha256` trùng khớp `vn_r3_stable_checkpoint`).

---

## 3. Đối chiếu đa phiên bản đã xác minh (Phase B)

| Thành phần | VN (`5.0.4.98`) | EN (`5.1.1`) | ZH (`5.0.0`) | TH (`5.1.3.6`) | Ghi chú tương thích |
| :--- | :---: | :---: | :---: | :---: | :--- |
| Lua files / Config `.lua` | `1148` / `271` | `1120` / `363` (top) | `1186` / `405` (top) | `1227` / `420` (top) | `EN-VN = []`; `ZH` thêm 5 file (`Zhenjue*`, `XxbzFightnumBuyRelation`); `TH` thêm `Goddomain*` |
| `maxPlayerLV` | `80` | `70` | `80` | `60` | VN khớp ZH (`80`) |
| `HeroModel` / `AttackModel` | `204` / `441` | `202` / `439` | `204` / `441` | `204` / `442` | `ZH == VN` 100%; `EN` thiếu `12015022, 12015023` |
| `BattleChapter` / `BattleNode` | `70` / `689` | `70` / `689` | `70` / `689` | `80` / `789` | VN/EN/ZH giống nhau hoàn toàn |
| `Equip` / `Treasure` / `TreasureDebris` | `140` / `46` / `228` | `140` / `46` / `228` | `140` / `46` / `200` | `140` / `46` / `200` | `TreasureDebrisModel`: VN = EN (`228`), khác ZH/TH (`200`) |
| `HeroStepRelation` / `GuideRelation` | `57` / `73` | `42` / `72` | `57` / `73` | `67` / `73` | `EN` thiếu `Guide[112]` |
| MD5 lõi (`FightExpression`, `Vit/Sta/PlayerLv/Explore/TreasureLoot/Elite`) | Khớp 100% giữa VN/EN/ZH/TH (`FightExpression` = `54b96bf9`) | Khớp 100% | Khớp 100% | Khớp 100% (`BattleCalc` TH khác `6cb563a9`) | Công thức chiến đấu, hồi thể lực, EXP cấp, Tầm Ngọc dùng chung an toàn tuyệt đối |

*(Phiên bản `com.infinite.qyc4_1.4` TW vẫn giữ nguyên trong `originals/` ở trạng thái XAPK/OBB mã hóa riêng, chưa giải mã `.luac`.)*

---

## 4. Lỗi ghi nhận từ `server/rpc_trace.log` (chuyển sang R5 để xử lý)

Qua rà soát log thực tế trên Pixel 3 XL (`rpc_trace.log` dòng `306–337`, phiên `16:37–16:41`):
1. `RoleInforLayer.luac:378`: `attempt to perform arithmetic on field 'STANextRecoverTime' (a nil value)` khi mở bảng thông tin nhân vật từ HomeScene do state player chưa khởi tạo `VITNextRecoverTime` / `STANextRecoverTime`.
2. `ExtraActivity/LevelPlanLayer.luac:277` & `Common/CommonFunc.luac:655` (`NumberToBigUnit` nil compare) khi mở `LvPlan.GetLvPlanInfo` và `VipWelfare.GetVipWelfare` (`handled=False`, trả `{}`).
3. `PlayerCharge.GetChargeList`, `CardInfo.GetInfo`, `CardInfo.GenerateOrderID` đang `handled=False` khi bấm vào giao diện Nạp / Thẻ tháng trong game.

---

## 5. Checkpoint

- **Backup thư mục**: `server/backups/vn_r4_partial_checkpoint/` (`normal_profile.json`, `debug_profile.json`, `audit_ledger.jsonl`, `game_data.json`, `rpc_trace.log`, `com.cmn.inuyasha_revival.apk`, `MANIFEST.json`).
- **Git tag**: `checkpoint-vn-r4-partial` (giữ nguyên vẹn `checkpoint-vn-r3` tại `476dcfa` và `server/backups/vn_r3_stable_checkpoint/`).
