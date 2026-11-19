# Báo Cáo Nghiệm Thu R7.7 → R7.8 — Android Standalone Beta (Ship Candidate)

**Dự án:** InuYasha: Seek Jade (`com.cmn.inuyasha.revival` dựa trên VN `v5.0.4.98`)  
**APK Ship Candidate:** [com.cmn.inuyasha.revival_r7_8_beta.apk](file:///Users/vup/Documents/agy/inuyasha/analysis/vn/patched/com.cmn.inuyasha.revival_r7_8_beta.apk) (`224,083,781 bytes` / `213.7 MB`, SHA-256: `d578da9ff4706c3f15ed63a391cf0f11b652a842055824e865358507f753d8ad`, `versionCode=780`, `versionName=5.0.4.98-r7.8-beta`)  
**Unit test:** `50/50 PASS` (`Ran 50 tests in 22.056s — OK`, 0 fail, 0 skip)  
**Bảo toàn Baseline:** STABLE R6.2 (`:8080`, `checkpoint-vn-r6.2` `5fed4bb`, `OlinaHugh Lv 20`, APK `com.cmn.inuyasha` trên Pixel 3 XL) & DEV (`:8082`, `OlinaHugh Lv 20`) nguyên vẹn 100%.

---

## 1. Bảng tổng hợp tiêu chí P0 (R7.7 → R7.8)

| Hạng mục P0 | Trạng thái | Bằng chứng thực tế trên Pixel 3 XL (`Android 12`, rootless) |
| :--- | :---: | :--- |
| **1. Nhúng Backend Python thật & Tự khởi động (R7.7)** | **PASS** | Nhúng CPython `3.11.17` 32-bit (`armeabi`/`armeabi-v7a`) + [inubackend.c](file:///Users/vup/Documents/agy/inuyasha/android/native/inubackend.c) (`libinubackend.so`, `4,096 bytes`) + [LocalBackendManager.java](file:///Users/vup/Documents/agy/inuyasha/android/src/com/cmn/inuyasha/standalone/LocalBackendManager.java) & [LocalBackendService.java](file:///Users/vup/Documents/agy/inuyasha/android/src/com/cmn/inuyasha/standalone/LocalBackendService.java). Tự giải nén `stdlib.zip` + `server_bundle.zip` và khởi chạy `emulator.py` trong **`863–1128 ms`** khi mở app. |
| **2. Offline thực sự & Chỉ lắng nghe Loopback** | **PASS** | Chạy với `airplane_mode_on = 1` (`cmd connectivity airplane-mode` = `enabled`). `ss -tanp` xác nhận `LISTEN 127.0.0.1:18082` và mọi kết nối RPC đều qua `127.0.0.1:<ephemeral> -> 127.0.0.1:18082`. Không có kết nối nào gọi về Mac (`:8080`/`:8082`). |
| **3. Gameplay thật qua Backend trên điện thoại** | **PASS** | Trace `/storage/emulated/0/Android/data/com.cmn.inuyasha.revival/files/saves/rpc_trace.log` trên máy ghi nhận đầy đủ: `Player.Login`, `Player.NewPlayer ["FoxZora", 1]`, `Player.GetInitData`, `Battle.GetFightInfo`/`Battle.Fight` (`1111..1115`, `1211`), `Battle.DrawRoadBox [11, 111]`, `HeroRecruit.Recruit [2, 1]` (Ayame), `Slot.HeroCombat`, `Equip.EquipCompose`, `Slot.OneKeyEquipCombat`, `Equip.OneKeyEquipLvUp`, `StartWorkReward.GetStartworkReward`. |
| **4. Lưu tiến trình & Tự phục hồi sau `force-stop`** | **PASS** | Lưu tại `/storage/emulated/0/Android/data/com.cmn.inuyasha.revival/files/saves/` kèm bản gương tự động tại `/data/user/0/com.cmn.inuyasha.revival/files/saves_mirror/`. Sau `am force-stop com.cmn.inuyasha.revival`, mở lại app tự khởi động lại backend và giữ nguyên 100% nhân vật `FoxZora (Lv.6, FAP 3579, MaxNodeId 1212)`. |
| **5. Đa tài khoản S1 độc lập & Sao lưu / Khôi phục (R7.8.A)** | **PASS** | Cùng thế giới `S1` hỗ trợ nhiều tài khoản độc lập (`TK1: FoxZora (Lv.6)`, `TK2: OlinaHugh (Lv.20, VIP 3, FAP 58051)`, `TK3` + `+ Tạo TK Mới`). Chuyển `TK1 -> TK2 -> TK1` trực tiếp trong game không ghi đè hồ sơ; hỗ trợ đấu Arena với đội hình phòng thủ đã lưu của tài khoản S1 khác (`test_50` PASS) và xuất/nhập bản sao lưu SHA-256 (`inuyasha_save_backup_latest.json`). |
| **6. Khả năng phát hành 1-file APK & Nâng cấp giữ Save (R7.8.B)** | **PASS** | Gộp toàn bộ `3,672` tệp tài nguyên từ `main.98.com.cmn.inuyasha.obb` trực tiếp vào `assets/res/` trong APK (người dùng chỉ cần cài **1 file `.apk` duy nhất**, không cần chép OBB). Application ID riêng `com.cmn.inuyasha.revival`, ký bằng keystore cố định ngoài repo (`~/.inuyasha_release/inuyasha_revival_release.jks`). Cài nâng cấp `versionCode 770 -> 780` (`adb install -r`) giữ nguyên 100% save `TK1`, `TK2`, `TK3` và file backup. |
| **7. Tài nguyên hệ thống (RAM / Pin / Nhiệt độ / ABI)** | **PASS** | Tổng bộ nhớ: tiến trình game `TOTAL PSS = 193,601 KB (~189 MB)` + tiến trình Python backend `VmRSS = 37,804 KB (~37 MB)` (~226 MB tổng cộng). Pin `100%`, nhiệt độ `39.5°C`. Tương thích mọi thiết bị Android hỗ trợ ABI 32-bit (`armeabi`/`armeabi-v7a`). |
| **8. Khởi động lại toàn bộ HĐH (Full OS Reboot)** | **BLOCKED (Môi trường)** | Pixel 3 XL đang kết nối duy nhất qua Android 12 Wireless Debugging (`192.168.1.89:40197`, không cắm cáp USB) và có khóa màn hình (`locksettings get-disabled = false`). Chạy `adb reboot` sẽ đưa máy vào Direct Boot chờ nhập PIN vật lý và ngắt Wireless ADB. Đã thay thế an toàn bằng `am force-stop` (dừng toàn bộ process tree của app + backend) và cài nâng cấp package `770 -> 780`. |

---

## 2. Kiến trúc kỹ thuật Android Standalone (R7.7 → R7.8)

1. **Một nguồn logic gameplay duy nhất:**
   - Đóng gói nguyên bản [emulator.py](file:///Users/vup/Documents/agy/inuyasha/server/emulator.py), [event_handlers.py](file:///Users/vup/Documents/agy/inuyasha/server/event_handlers.py), [event_runtime.py](file:///Users/vup/Documents/agy/inuyasha/server/event_runtime.py), [combat_sim.py](file:///Users/vup/Documents/agy/inuyasha/server/combat_sim.py), [economy_audit.py](file:///Users/vup/Documents/agy/inuyasha/server/economy_audit.py) và [game_data.json](file:///Users/vup/Documents/agy/inuyasha/server/game_data.json) (`5.8 MB`) vào `assets/inubackend/server_bundle.zip`.
2. **Tuân thủ W^X / SELinux trên Android 10–14+ & Tự phục hồi symlink khi nâng cấp APK:**
   - Mọi thư viện `.so` 32-bit (`libinubackend.so`, `libpython3.11.so`, `libcrypto_python.so`, `libssl_python.so`, `libsqlite3_python.so`, và các C-extension `libpymod_<mod>.so`) đều đặt trong `lib/armeabi/` để Android PackageManager giải nén vào `nativeLibraryDir` (`u:object_r:apk_data_file:s0`, quyền `0755`).
   - Khi khởi chạy, [inubackend.c](file:///Users/vup/Documents/agy/inuyasha/android/native/inubackend.c) tự động đồng bộ symlink từ `nativeLibraryDir/libpymod_<mod>.so` sang `$INUYASHA_DYNLOAD_DIR/<mod>.cpython-311.so` trước khi gọi `Py_BytesMain`, đảm bảo an toàn khi đường dẫn `/data/app/~~.../` đổi hậu tố ngẫu nhiên sau mỗi lần cập nhật APK.
3. **Đánh giá tương thích ABI 32-bit:**
   - Thư viện engine gốc `libcocos2dlua.so` của client VN `5.0.4.98` chỉ tồn tại ở dạng 32-bit ARM (`ELF 32-bit LSB shared object, ARM, EABI5`).
   - APK Standalone tương thích với toàn bộ thiết bị Android 32-bit ARMv7 và 64-bit ARMv8 có hỗ trợ `armeabi-v7a`/`armeabi` trong `ro.product.cpu.abilist` (Pixel 3 XL, các dòng Snapdragon/Exynos/Dimensity hỗ trợ 32-bit). Các thiết bị ARMv9 thuần 64-bit đã bỏ hoàn toàn tập lệnh 32-bit phần cứng (như Pixel 7/8 trở lên) sẽ cần lớp dịch 32-bit nếu chạy binary `libcocos2dlua.so` gốc.

---

## 3. Hướng dẫn cài đặt & sử dụng ngắn gọn (Dành cho người chơi Beta)

1. **Cài đặt lần đầu (Chỉ 1 file duy nhất):**
   - Tải tệp `com.cmn.inuyasha.revival_r7_8_beta.apk` (`213.7 MB`) về điện thoại Android.
   - Chạm vào tệp APK để cài đặt (không cần chép file OBB, không cần Internet, không cần ADB/máy tính, không đụng chạm bản `InuYasha` gốc nếu đang cài trên máy).
2. **Vào game & Chuyển tài khoản S1 / Sao lưu:**
   - Mở ứng dụng **`InuYasha Offline`**. Server cục bộ sẽ tự động khởi chạy ngầm trong ~1 giây.
   - Tại màn hình tiêu đề (hoặc trong game tại **`Hệ Thống -> Đổi Tài Khoản`**), bấm **`TK / Sao Lưu`**:
     - **`TK 1`:** Tài khoản tạo nhân vật mới từ Lv 1 (hoặc nhân vật bạn đang chơi).
     - **`TK 2 (OlinaHugh Lv.20)`:** Tài khoản mẫu Lv 20, VIP 3 có sẵn đội hình & trang bị để trải nghiệm ngay các tính năng cấp trung/cao.
     - **`TK 3` / `+ Tạo TK Mới`:** Tạo thêm các nhân vật độc lập khác trong cùng thế giới S1 (có thể gặp và đấu với đội hình phòng thủ của các tài khoản khác trong Đấu Trường Arena).
     - **`Sao Lưu Save` / `Khôi Phục`:** Xuất toàn bộ hồ sơ S1 ra `Android/data/com.cmn.inuyasha.revival/files/saves/backups/inuyasha_save_backup_latest.json` (kèm mã kiểm tra SHA-256) và khôi phục lại bất cứ lúc nào.
3. **Cập nhật phiên bản mới:**
   - Cài đè trực tiếp file APK bản mới lên bản cũ — toàn bộ tài khoản, nhân vật và bản sao lưu sẽ được giữ nguyên.

---

## 4. Danh sách tính năng đang hoạt động & giới hạn đã biết của bản Beta

### Các hệ thống hoạt động đầy đủ (Offline 100%)
- **Cốt truyện & Chiến đấu:** Phụ bản thường (Chương 1..80, đã cân bằng đường cong độ khó chương xa), Tinh Anh (`EliteBattle`), Quét ải (`ConFight`), Rương đường & Rương sao chương.
- **Tân thủ & Phát triển:** Tạo nhân vật Nam/Nữ, Hướng dẫn tân thủ (`Guide 1`), Nâng cấp/Đột phá/Luyện hóa/Trùng sinh Tướng (`Hero`), Hợp thành/Cường hóa/Trùng sinh Trang bị (`Equip`), Cường hóa/Tăng bậc/Ghép mảnh/Trùng sinh Bảo Vật (`Treasure`), Tầm Ngọc (`Explore`), Ngộ Đạo (`LightenStar`), Danh Vọng (`Glory`).
- **Chiêu mộ & Multi-Banner đồng thời:** Chiêu mộ thường (`Mộng Cảnh`, `Túc Mệnh`, `Linh Hồn`) chạy song song cùng lúc với **Banner Giới Hạn 81 (`Sesshomaru / InuYasha / Naraku`)** và **Banner Giới Hạn 82 (`Inu no Taishou / Izayoi / Takemaru`)** với bộ đếm điểm, rương mốc và bảo hiểm tách biệt 100%.
- **Kinh tế, Nạp Offline & VIP:** Nạp Kim Cương & kích hoạt Thẻ Tháng trực tiếp trong UI offline (`RechargeScene`/`MonthCardLayer`), Phúc lợi VIP `0..20`, Quà VIP (`ShopGift`), Cửa hàng & Tiệm Thần Bí (`MysteryShop`), Rương chọn tướng UR (`GoodsUseForBoxChoice`).
- **Hoạt động & Sự kiện (Reset tự động `00:00 UTC+7`):** Đấu Trường (`PVP` đấu bot + đấu đội hình phòng thủ của tài khoản S1 khác & `PVPShop`), Yêu Vương (`BossBattle`), Nhiệm vụ ngày (`DailyTaskInfo`), Ăn Tối nhận Thể Lực (`Dinner`), Huyết Chiến (`Xxbz`), Mèo Thần Tài (`Zcsf`), Ước (`Xhzw`), Săn Thưởng (`Limitthebounty`), Quà Thành Tích 7 ngày (`SuccessTargetInfo`), Quỹ Mỗi Ngày (`Daydayfund`), Quà Khởi Nghiệp (`StartWorkReward`), Quỹ Trưởng Thành (`LvPlan`), Trung Tâm Thưởng (`RewardCenter`).

### Giới hạn đã biết trong bản Beta (Chưa khôi phục / Tắt chủ động)
- **Chat thế giới TCP (`ChatMng`):** Đã ngắt vòng lặp kết nối socket nền để tiết kiệm pin khi chạy offline.
- **Một số hoạt động rìa / cấp cao chưa mở hoặc đang trả stub an toàn:** `BddInfo (2507 - Mộ Thần Binh)`, `Guild (3400 - Bang Hội)`, `TeambattleInfo (2319 - Tổ Đội)`, và các sự kiện lễ hội thiếu bảng cấu hình gốc phía client (`MonthSignInfo`, `OnlineReward`, `TimedMoneyTree`).
