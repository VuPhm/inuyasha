# INUYASHA: SEEK JADE — R7.2A UI ACCEPTANCE REPORT
**Nghiệm thu trực tiếp hướng dẫn tân thủ & luồng đầu game trên Pixel 3 XL (DEV `:8082`)**

- **Ngày kiểm thử:** 2026-11-19
- **Thiết bị & Client:** Google Pixel 3 XL (`adb -s 192.168.1.89:40197`), APK `com.cmn.inuyasha v5.0.4.98` (`96,806,706` bytes, `sha256: 480e732a16c2fd2a80ea745521b712c2226bd06ba841e38bf84b6de5ae2569db`), OBB `main.98.com.cmn.inuyasha.obb` (`113,083,804` bytes) — **không cài lại hay sửa APK**.
- **STABLE (giữ nguyên):** `checkpoint-vn-r6.2` (`5fed4bb`), cổng `8080` (`PID 12133`), `server/saves/normal_profile.json` (`OlinaHugh`, `PlayerId="200010"`, Lv 20, VIP 0).
- **DEV baseline:** `checkpoint-vn-r7.2` (`31d187c`), cổng `8082` (`PID 19767` sau khi khôi phục), `server/dev_saves/normal_profile.json` (`OlinaHugh`, `PlayerId="200010"`, Lv 20, VIP 3).
- **Phiên thử nghiệm R7.2A cô lập:** Server DEV tạm thời trên `--data-dir server/qa_runs/r7_2a_test_saves --new-player` (`TedGill`, `PlayerId="200001"`), định tuyến an toàn qua `adb shell settings put global http_proxy 192.168.1.250:8888` + proxy HTTP cục bộ (Cocos2d-x `Cocos2dxHttpURLConnection` tôn trọng `http_proxy` hệ thống), log đầy đủ tại `server/qa_runs/r7_2a_dev_rpc_trace.log`.

---

## 1. Sao lưu trước thử nghiệm & trạng thái khôi phục sau thử nghiệm

| Môi trường | File sao lưu | SHA-256 backup | SHA-256 live sau hoàn nguyên | Trạng thái dữ liệu `OlinaHugh` |
| --- | --- | --- | --- | --- |
| **DEV (`:8082`)** | `server/backups/pre_r7_2a_dev/normal_profile.json` | `3e071918b9f9adbe...` | `3e071918b9f9adbe...` | Khớp byte-for-byte (`Lv=20, Vip=3, Gold=1552861, Dia=4695, FAP=58051`) |
| **STABLE (`:8080`)** | `server/backups/pre_r7_2a_stable/normal_profile.json` | `5c65802bc840f892...` | `765aa345f509fc49...` | Toàn bộ nhân vật/tài nguyên/ải giữ nguyên (`Lv=20, Vip=0, Gold=490900, Dia=290, FAP=23679`); chỉ 3 timestamp hồi phục/đăng nhập (`LastLoginTime`, `VITNextRecoverTime`, `STANextRecoverTime`) cập nhật khi Pixel 3 XL tự kết nối lại STABLE lúc kết thúc phiên |

- Cấu hình proxy trên Pixel 3 XL đã được xóa sạch (`settings get global http_proxy` -> `null`), tiến trình proxy/QA tạm đã tắt, APK tự động quay về kết nối STABLE `:8080` và tải lại đúng hồ sơ `OlinaHugh` (`PlayerId="200010"`, Lv 20).

---

## 2. Kết quả kiểm thử giao diện trực tiếp trên Pixel 3 XL (tài khoản mới `TedGill`, Lv 1 -> Lv 12)

Toàn bộ bằng chứng dưới đây được ghi nhận **trực tiếp trên UI APK Pixel 3 XL** kết hợp đối chiếu `server/qa_runs/r7_2a_dev_rpc_trace.log` (`179` dòng log, `37` RPC khác nhau) và ảnh lưu `server/qa_runs/r7_2a_test_saves/normal_profile.json`.

| Hạng mục R7.2A | Kết quả trên APK UI | Bằng chứng RPC / Trạng thái save |
| --- | --- | --- |
| **1. Tạo nhân vật** | **PASS** — Đổi giới tính, tung xúc xắc tên `TedGill`, xem/bỏ qua truyện tranh mở đầu | `01:30:30` `Player.NewPlayer ["TedGill", 0]` (`status=0`, tạo `PlayerId="200001"`, Main Hero `12010001`) |
| **2. Hướng dẫn bắt đầu & trận dạo** | **PASS** — Chơi mượt trận cốt truyện *Omukade*, vào `HomeScene` Lv 1 (`820` FAP, `200/200` VIT), bám mũi tên hướng dẫn vào Mạo Hiểm | `Player.AlterPlayerStepCount` + `ExtensionString.GuideInfo` đồng bộ đúng bước |
| **3. Chiến đấu các ải đầu** | **PASS** — Qua các ải `1-1` (`1111`) -> `1-5` (`1115`) -> `2-7` (`1217`), tổng `12` trận qua `Battle.Fight`, mở `Chapters ['11', '12', '13']`, `MaxNodeId=1311`, `StarCount=12` | `Battle.Fight` x12 (`status=0`), không kẹt màn hình thắng/thua |
| **4. Chiêu mộ lần đầu** | **PASS** — Mở Chiêu Mộ, bấm chiêu mộ miễn phí Túc Mệnh, nhận **Ayame** (`12011014`), đồng hồ hồi CD 23h hiển thị bình thường | `01:38:58` `HeroRecruit.Recruit [2, 1]` (`status=0`) |
| **5. Sắp đội hình** | **PASS** — Đưa **Ayame** vào Ô 2, sau tân thủ đưa thêm **Kagome** (`12011005`) vào Ô 3 (`FAP 7236 -> 9286`), kéo thả đổi vị trí từ Ô 3 sang Ô 5 ở màn hình `Trận` | `Slot.HeroCombat` x2 (`01:42:33`, `01:57:32`), `01:59:34` `SlotFormation.Change [1, 2, 5, 4, 3, 6]` (`status=0`, lưu bền vững `embattle`) |
| **6. Nhận thưởng** | **PASS** — Nhặt rương đường `111`, nhận hàng loạt rương sao Chương 11 & 12, nhận Quà Khởi Nghiệp, nhận quà hàng ngày `VipWelfare` VIP 0 (`+10K Gold`, `+5 Bùa Liên Chiến`, nút chuyển `Đã nhận`) | `Battle.DrawRoadBox [11, 111]`, `Battle.OneKeyDrawBoxs` (chương 11, 12), `StartWorkReward.GetStartworkReward` x2, `02:05:02` `VipWelfare.DrawVipWelfare` (`Gold -> 126535`) |
| **7. Hợp thành & mặc trang bị** | **PASS** — Sau ải `1-3`, RedDot trang bị bật tự nhiên -> hướng dẫn Hợp Thành dây chuyền trắng lên phẩm Lục (`13040215`), bấm Mặc Nhanh & Cường Hóa 1 lần lên Lv 24 | `01:46:18` `Equip.EquipCompose`, `Slot.OneKeyEquipCombat` x3, `Equip.OneKeyEquipLvUp` x2 (`13010215/13020215/13040215/13030215` Lv 24) |
| **8. Mở khóa tính năng theo tiến trình** | **PASS** — Chạy xuyên suốt từ Lv 1 đến Lv 12, kích hoạt & hoàn tất chuỗi hướng dẫn chính (`StepCountList["1"]=997`) và các hướng dẫn nhánh (`17=9`, `2=9`, `3=4`, `112=2`), nâng cấp/đột phá tướng & Tầm Ngọc 25 lượt | `Hero.HeroLvUp` (`01:48:51`), `Hero.HeroStepUp` (`01:49:51`), `Explore.Explore` x25 (`PlayerId="200001"` lên Lv 12 tự do thao tác) |
| **9. Đăng xuất & đăng nhập lại** | **PASS** — Mở `Hệ thống -> Đổi Tài Khoản -> Đổi`, quay về `GameLoginScene` (`Vào`), vào lại `StartGameScene -> Chơi -> HomeScene`; `TedGill` Lv 12 (`FAP 9286`) giữ nguyên, không bị reset tân thủ | `Player.Login` x3, `Player.GetInitData` x3; `StepCountList["1"]=997` bảo toàn sau relogin |

---

## 3. Lỗi & bất thường ghi nhận trong phiên (ngoài phạm vi hướng dẫn R7.2)

Không phát sinh lỗi chặn luồng hướng dẫn R7.2 trên APK (`0` sửa đổi mã R7.2 là cần thiết trong R7.2A). Các vấn đề phát hiện khi mở rộng thao tác tự do sau Lv 11 đã được đưa thẳng vào báo cáo kiểm kê `R7_3_FULL_RECOVERY_AUDIT.md`:

1. **Lỗi Lua tại `QUÀ THÀNH TÍCH` (mở ở Lv 11, `ModuleSub.eSuccessReward = 4900`):**
   - Trace `01:52:40`: `RPC SuccessTargetInfo.GetInfo handled=False status=0 data=[]` -> client gửi báo cáo lỗi về `/api/report.ashx`:
     `[string "OpenActivity/SuccessTargetLayer.luac"]:151: bad argument #1 to 'pairs' (table expected, got nil)`
   - Nguyên nhân: `SuccessTargetInfo.GetInfo` chưa được xử lý trong `server/emulator.py`, trả về `{}` thiếu trường `TargetList` mà `SuccessTargetLayer.lua:151` duyệt bằng `pairs(serverInfo.TargetList)`.
2. **Chiêu mộ Linh Hồn trả trùng Kagome (`12011005`):**
   - Trace `01:52:53` (`[3, 1]`) và `01:52:56` (`[3, 0]`) đều cấp tướng `12011005` (*Kagome*). Phân tích nguyên nhân gốc tại `R7_3_FULL_RECOVERY_AUDIT.md` Mục B.1.
3. **Bấm Nạp Kim Cương / Thẻ Tháng không cộng tài nguyên trên APK:**
   - Trace `01:27:04..10` và `01:53:00`: client gửi `PlayerCharge.GenerateOrderID` / `CardInfo.GenerateOrderID`, sau đó gọi `com.kull.sdk` (`Dialogs.showPaymentByPackage`) vốn không thể thanh toán thật khi chạy local/offline và không gọi `ConfirmOrder` / `Activity`. Chi tiết tại `R7_3_FULL_RECOVERY_AUDIT.md` Mục B.2.
4. **Lỗi hiển thị/text gốc của client VN `5.0.4.98` (không chặn chơi):**
   - Nút `"Bắt Đầu"` ở `RoleCreateScene` xuống 2 dòng; vài câu `GuideEventModel` thiếu khoảng trắng trước tag màu `{d80000}` hoặc ngắt dòng (`"tương ứ/ng."`); `AccountSwitchLayer` hiển thị `"Server: S1 Normal Revival (Lv1)1"`; hộp `Thông Báo` trống do `Notice.GetNoticeList` trả `[]`.

---

## 4. Kết luận nghiệm thu R7.2A

- **Kết luận:** Toàn bộ các hạng mục hướng dẫn tân thủ R7.2 **ĐẠT (PASS) khi kiểm thử giao diện thực tế trên Pixel 3 XL** với tài khoản mới Lv 1 `TedGill`, chuyển sang DEV `:8082` cô lập và hoàn nguyên sạch về STABLE `:8080` sau khi xong.
- **Khuyến nghị quyết định:** Không tự động promote DEV lên STABLE ở bước này vì định hướng dự án đã mở rộng sang khôi phục full game (ưu tiên sửa Chiêu mộ, Nạp/VIP tức thì, Quà VIP, và `SuccessTargetInfo` ở R7.4).
