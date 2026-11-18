# INUYASHA REVIVAL — R5 FAST QA, ADMIN/VIP & STABLE/DEV REPORT

**Date:** 2026-11-18  
**Base Checkpoint:** `checkpoint-vn-r4-partial` (`975e046`)  
**Scope:** R4 Recovery → R5 Fast QA Engine, Simulated Top-Up/VIP Admin API, STABLE/DEV Isolation, and Selective Hardware Verification.

---

## 1. Kiến trúc Fast QA Engine (`server/qa_runner.py`)

Công cụ Fast QA chạy trực tiếp qua RPC và dữ liệu cấu hình xác thực của game (`server/game_data.json`), hỗ trợ hai chế độ transport:
- **In-process cô lập:** Khởi tạo `GameEmulatorState` trong thư mục riêng dưới `server/qa_runs/` (`env="dev"`).
- **HTTP tới DEV:** Gọi qua `/client.aspx` + `/admin/*` (yêu cầu `X-Admin-Token`), **từ chối tuyệt đối** cổng `8080` và thư mục `server/saves/` (`SafetyViolationError`).

### Mô phỏng chiến đấu trung thực (`simulate_fight_info`)
- Đọc trực tiếp `FightInfo.FightObjs` từ `Battle.GetFightInfo` và `game_data["attacks"]`.
- Triển khai đúng công thức trong `CSCommon/FightExpression.lua`, `CSCommon/BattleCalc.lua` và bảng ánh xạ `FightEnum_Target` (`CSCommon/FightEnum.lua`):
  - Giới hạn tối đa `30` hiệp/wave, mang HP/RP đồng minh qua các wave.
  - Tính `hurtStrength = max(AP - DEF, 0.1 * AP)`, `factor / 10000`, `useRP` scaling `(1 + (RP - needRP) / 200)`, tỷ lệ Né/Bạo/Đỡ (`HIT/DOD/CRI/TEN/BLO/BOG`), sát thương chí mạng `1.5 + (CRId - TEND)/10000` và hồi máu (`type == 1`).
  - Không ép thắng, không thay đổi công thức gốc, không buff chỉ số giả tạo; nếu thua (`won=False`), nộp đúng `won=False` và `verify_data` lên `Battle.Fight`, dừng và ghi nhận lỗi/thất bại thực tế.

### Bộ Preset kiểm thử (`apply_preset`)
- `STARTER`: Tài khoản mới Lv 1, tiến trình tự nhiên qua hướng dẫn tân thủ, chiêu mộ, trang bị và cường hóa từ tài nguyên kiếm được.
- `PROGRESSION`: Chuẩn bị tài khoản ở cấp kiểm thử (`target_lv`, mặc định Lv 12) với tướng hợp lệ (`12011005`, `12011006`, `12011007`), trang bị xanh (`130x0404`), thuốc Thể lực (`16030006`) và Gold/HeroEXP qua ledger.
- `STRONG`: Chuẩn bị Lv 18 + nạp giả lập đạt VIP 5 (`PlayerCharge.ConfirmOrder` 60/300/3280) + đội hình tướng/trang bị tím-cam hợp lệ (`12011004`, `12012005`, `130x0602`, `130x0503`).
- `FAILURE`: Tài khoản Lv 1 không nâng cấp đánh boss ải `1620` (Ch 16, `star_lv=3`) — kiểm chứng thua thực sự ở Round 2 (`ally_fap=820`, `stages_won=0`, `stop_reason="battle_defeat"`).

---

## 2. Benchmark: Chơi tay Pixel vs Fast QA

| Hạng mục đo | Chơi tay trên Pixel (R4) | Fast QA Engine (R5) |
|---|---|---|
| Cơ chế chạy | ADB tap + chờ hiệu ứng/thoại + chụp màn hình liên tục | RPC trực tiếp + tính toán `simulate_fight_info` theo cấu hình gốc |
| Vượt **10 ải** đầu tiên (`STARTER`, `star_lv=2`) | Nhiều phút thao tác thủ công | **`0.1621s`** in-process (`10/10` thắng, đạt Lv `11`, Node `1216`) |
| Hồi quy **25 ải** + hệ thống (`ShopGoods`, `TreasureLoot`/`Compose`, `EliteBattle`, `PlayerCharge`, `LvPlan`, `VipWelfare`) | Không thực hiện lặp tự động | **`0.3813s`** in-process (`25/25` thắng, đạt Lv `19`, 25 sao) |
| Chạy QA qua HTTP tới **DEV** (`127.0.0.1:8082`, `STARTER` 5 ải) | — | **`0.7958s`** (`5/5` thắng, mở Ch 12 Node `1211`, Lv `6`) |
| Ca thất bại (`FAILURE` Lv 1 vs Node `1620` 3★) | — | **`0.0055s`** (`stop_reason="battle_defeat"`, `stages_won=0`, `StarCount=0`) |

**Bảo vệ `NORMAL`:** Hash SHA-256 của `server/saves/normal_profile.json` (`200010 OlinaHugh`, Lv `16`, `MaxNodeId=1713`, `StarCount=51`, `Gold=173655`, `Diamond=655`) giữ nguyên trong suốt các lần chạy Fast QA và kiểm thử trên DEV.

---

## 3. Cơ chế Nạp giả lập, Admin API & VIP (`server/emulator.py` & `server/economy_audit.py`)

### API quản trị cục bộ có xác thực
Chỉ chấp nhận kết nối từ localhost (`127.0.0.1` / `::1`) và header `X-Admin-Token` khớp bằng `hmac.compare_digest` (token cấu hình qua `--admin-token` / `INUYASHA_ADMIN_TOKEN` hoặc sinh ngẫu nhiên lưu vào `.admin_token` quyền `0600`):
- `GET /admin/state?profile=normal|debug`
- `GET /admin/audit?account_id=...&limit=...`
- `POST /admin/grant`: Cấp tài nguyên trong `ALLOWED_PLAYER_RESOURCES`, vật phẩm (`goods_model`/`treasure_debris`/`treasures`/`equips`), tướng (`heroes` giới hạn cấp theo `Lv` và `maxPlayerLV`), trang bị (`equips`). Từ chối mọi key/ID giả mạo bằng HTTP `400`.
- `POST /admin/vip`: Đặt `VipEXP` qua `ResourceLedger`, tự suy diễn `Vip`/`VIPLv` từ `game_data["vip_model"]`.
- `POST /admin/prepare`: Đồng bộ cấp mục tiêu theo `player_lv EXPTotal` qua `ResourceLedger`.

Mọi biến động đều ghi vào `audit_ledger.jsonl` (truy vấn qua `/admin/audit`). `NORMAL` vẫn giữ nguyên kinh tế gốc, chỉ thay đổi nếu người dùng hoặc quản trị viên chủ động kích hoạt luồng nạp giả lập/Admin trên máy cục bộ.

### RPC Cửa hàng Nạp & Thẻ Tháng
- `PlayerCharge.GetChargeList`, `PlayerCharge.ChargeInfo`, `PlayerCharge.DrawChargeBox` (đúng cấu hình `Config/ChargeConfig.lua` mức `60/300/900`), `PlayerCharge.GenerateOrderID`, `PlayerCharge.ConfirmOrder`.
- `CardInfo.GetInfo`, `CardInfo.GenerateOrderID`, `CardInfo.Activity`, `CardInfo.DrawDailyReward`, `CardInfo.DrawBuyReward` (đúng cấu hình `Config/CardModel.lua`).

---

## 4. Vận hành STABLE / DEV (`server/env_ctl.py`)

| Môi trường | Mục đích | Cổng mặc định | Thư mục lưu dữ liệu | Trace log |
|---|---|---|---|---|
| **STABLE** | Người dùng chơi ổn định trên Pixel 3 XL | `8080` (`--env stable`) | `server/saves/` | `server/rpc_trace.log` |
| **DEV** | Phát triển, QA tự động, thử nghiệm tính năng mới | `8082` (`--env dev`) | `server/dev_saves/` | `server/dev_rpc_trace.log` |

Lệnh vận hành chuẩn:
```bash
# 1. Sao lưu STABLE (kèm SHA-256 MANIFEST.json)
python3 server/env_ctl.py backup --tag truoc_khi_cap_nhat

# 2. Khởi tạo/đồng bộ dữ liệu sang DEV để thử nghiệm tách biệt
python3 server/env_ctl.py sync-to-dev

# 3. Chạy DEV server và kiểm thử hồi quy trước khi chạm vào STABLE
python3 server/emulator.py --env dev --host 127.0.0.1 --port 8082
python3 server/test_emulator.py
python3 server/qa_runner.py benchmark

# 4. Chạy STABLE server cho Pixel 3 XL chơi và smoke check
python3 server/emulator.py --env stable --host 0.0.0.0 --port 8080
python3 server/env_ctl.py smoke --url http://127.0.0.1:8080 --server-id 2

# 5. Xem trạng thái hai môi trường & rollback nếu gặp sự cố
python3 server/env_ctl.py status
python3 server/env_ctl.py rollback server/backups/<backup_tag>
```

---

## 5. Sửa lỗi Phase 0, Cập nhật APK & Kiểm tra chọn lọc trên Pixel 3 XL

### Sửa lỗi Lua từ log R4 (`R4_PARTIAL_REPORT.md` §4)
1. `Home/RoleInforLayer.luac:378`: Bổ sung `VITNextRecoverTime` và `STANextRecoverTime` dạng số nguyên hợp lệ (`_sync_player_recover_times`) trong state mặc định, `_normalize_loaded_state`, `Player.Login`, `Player.GetInitData`, và `Avatar` sync.
2. `ExtraActivity/LevelPlanLayer.luac:277` & `VipWelfare`: Triển khai `LvPlan.GetLvPlanInfo` (`CanRewardLvList`, `RewardLvList`), `LvPlan.OpenLvPlan`, `LvPlan.ReceiveLvPlan`, `VipWelfare.GetVipWelfare` (`CanDraw`, `ResourceList`), `VipWelfare.DrawVipWelfare` (`BaseGetGameResourceList`), và `MonthSignInfo.GetInfo` (`[]`).
3. Phát hiện khi kiểm tra mạng Pixel 3 XL (`192.168.1.89`) rằng bản `com.cmn.inuyasha_revival.apk` cũ đang trỏ IP `192.168.1.89:8080` trong khi IP hiện tại của MacBook là `192.168.1.250`. Đã vá lại `analysis/vn/apktool_patched/lib/armeabi/libcocos2dlua.so` và `MQUtils.smali` sang `192.168.1.250:8080`, đóng gói, ký và cập nhật bằng `adb install -r` (giữ nguyên dữ liệu save trên máy).

### Kết quả kiểm tra tự động & chọn lọc
- `python3 server/test_emulator.py`: **18/18 PASS** (`2.295s`), bao gồm 4 test mới (`test_15`..`test_18`) cho recover time, ExtraActivity schemas, Admin Auth/Audit, Store Charge/Card, STABLE/DEV isolation và Fast QA (`STARTER`/`PROGRESSION`/`STRONG`/`FAILURE`).
- `/usr/local/bin/node --check poc/web_poc/app.js`: Exit `0`.
- `python3 server/env_ctl.py smoke`: Đạt trên cả `http://127.0.0.1:8080` (`STABLE`) và `http://127.0.0.1:8082` (`DEV`).
- Kiểm tra chọn lọc trên Pixel 3 XL (`192.168.1.89:40197` → `192.168.1.250:8080`):
  - Đăng nhập `OlinaHugh` Lv 16 (`51★`, `20575` chiến lực) thành công, `0` lỗi Lua (`STEP_POST`).
  - Màn hình `RoleInforLayer` ("Thông tin NV") hiển thị đúng `Thể Lực: 10/200`, `Hồi Thể Lực: 00:00:45`, `H.Lực: 93/20`, `HL đầy!`, `0` lỗi Lua.
  - Màn hình Shop (`ShopGoods.ShopGoodsList`) & `RechargeScene` ("Nạp", `PlayerCharge.GetChargeList handled=True status=0`) hiển thị VIP 0/60 + 8 gói kim cương X2 lần đầu, `0` lỗi Lua.
  - Ghi chú: lượt chạm UI mở tab `HĐ Đặc Sắc` trên màn hình chính chưa kịp mở trước lúc app tắt do độ trễ màn hình chờ; toàn bộ RPC của `LvPlan`, `VipWelfare`, `MonthSignInfo` đã được xác nhận bằng `test_15`, `env_ctl.py smoke` và `qa_runner.py`.

---

## 6. Điểm cần lưu ý tiếp theo
- APK hiện trỏ cứng IP LAN hiện tại của MacBook (`192.168.1.250:8080`); nên đặt DHCP reservation cho MacBook hoặc nếu đổi mạng Wi-Fi thì cập nhật lại IP khi cần.
- Các tab hoạt động phụ chưa đụng tới (ví dụ `CoinFund`, `DailyShare`, `GiftBack`, `Friend`, `Arena`) sẽ tiếp tục được mở rộng theo nhu cầu thực tế trên `DEV` trước khi gộp về `STABLE`.
