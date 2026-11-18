# INUYASHA REVIVAL — R5.1 DISPLAY COMPATIBILITY REPORT

## 1. Tóm tắt & Phạm vi
- **Checkpoint nền:** `checkpoint-vn-r5` (`19df390`, giữ nguyên không thay đổi).
- **Thiết bị kiểm thử:** Google Pixel 3 XL (`Android 12`, màn hình vật lý `2960 x 1440` ngang, notch trái `0..171`, vùng compat 16:9 Android 12 `Rect(279, 0 - 2853, 1440)` = `2574 x 1440`).
- **Mục tiêu:** Sửa 2 lỗi hiển thị khi mở client VN (`com.cmn.inuyasha` 5.0.4.98):
  1. Khởi động lạnh hiển thị trong khung ngang hẹp (`1440 x 1440`).
  2. Màn hình chọn server (`StartGameScene`) bị co ngang `1440 x 1440`, tỷ lệ sai và nửa phải đen kịt.
- **Không mở rộng gameplay / không sửa logic backend.** Save `NORMAL` (`OlinaHugh`, Lv 16, `51★`), phân tách `STABLE` (`:8080`) / `DEV` (`:8082`), và khóa ký debug tại chỗ (`adb install -r`) được bảo toàn nguyên vẹn.

---

## 2. Chẩn đoán nguyên nhân gốc rễ

1. **Xung đột hướng màn hình và thiếu `configChanges` trong `AndroidManifest.xml`:**
   - `analysis/vn/apktool/AndroidManifest.xml` khai báo:
     ```xml
     android:screenOrientation="portrait"
     android:configChanges="orientation"
     ```
   - Trong khi đó `assets/AConfig.json` khai báo `"ScreenOrientation": "L"`, và `com.moqikaka.sdk.MQActivity.onCreate()` chỉ gọi `setRequestedOrientation(6)` (`SCREEN_ORIENTATION_SENSOR_LANDSCAPE`) *sau* khi `super.onCreate()` đã tạo `Cocos2dxGLSurfaceView`.
   - Khi khởi động lạnh từ Launcher dọc (`ROTATION_0`), Android cấp cấu hình dọc ban đầu rồi mới xoay sang ngang (`ROTATION_90`), đồng thời thiếu các cờ `screenSize|smallestScreenSize|screenLayout` trong `configChanges`.
2. **Race Condition khi khởi tạo Cocos2d-x & `Adapter.init()` (`1440 x 1440`):**
   - Trong luồng xoay dọc → ngang khi mở app, `Cocos2dxGLSurfaceView` / `Cocos2dxRenderer.onSurfaceCreated -> nativeInit` nhận kích thước khung chưa hoàn tất (`width = 1440`, `height = 1440`) thay vì `2574 x 1440`.
   - `Common/Display.lua` đọc `glview:getFrameSize()` đúng một lần lúc nạp (`display.width = 1440`, `display.height = 1440`), kéo theo `Common/Adapter.lua` khóa:
     - `AutoScaleX = 1440 / 1136 = 1.2676`
     - `AutoScaleY = 1440 / 640 = 2.2500`
     - Lệch tỷ lệ trục ngang/dọc ~`1.775x` (nhân vật bị nén, thanh progress/chữ co vào góc trái `x = [279..1719]`, nửa phải `[1719..2853]` đen hoàn toàn).
3. **Khung tương thích Android 12 (`2574 x 1440`):**
   - Do APK dùng `platformBuildVersionCode="19"` (pre-edge-to-edge / cutout-safe), Android 12 bố trí cửa sổ `MQActivity` tại `mBounds=Rect(279, 0 - 2853, 1440)` (`2574 x 1440`, tỷ lệ `1.7875`, sai khác `<0.7%` so với thiết kế gốc `1136 / 640 = 1.7750`), né hoàn toàn vùng tai thỏ bên trái (`0..171`) bằng vùng đệm đen cân đối mà không làm biến dạng hình ảnh hay cắt nút Lua (`WidthScale` / `HeightScale`).

---

## 3. Các thay đổi đã áp dụng

Các bản vá thực hiện tại lớp Android Manifest / Java-Smali (không chỉnh sửa logic game hay `server/`):

1. `analysis/vn/apktool_patched/AndroidManifest.xml` (dòng `43`):
   - Đổi `android:screenOrientation="portrait"` → `"sensorLandscape"` để hệ thống định hướng ngang ngay trước khi Activity tạo `GLSurfaceView`.
   - Đổi `android:configChanges="orientation"` → `"keyboard|keyboardHidden|orientation|screenLayout|screenSize|smallestScreenSize|uiMode"` để xử lý thay đổi kích thước/cấu hình không recreate sai luồng.
2. `analysis/vn/apktool_patched/smali/org/cocos2dx/lib/Cocos2dxRenderer.smali` (hàm `onSurfaceChanged`, dòng `331-342`):
   - Đồng bộ `mScreenWidth = p2` và `mScreenHeight = p3` khi `p2 > 0 && p3 > 0` trước khi gọi `nativeOnSurfaceChanged(p2, p3)`.
3. `analysis/vn/apktool_patched/smali/com/moqikaka/sdk/MQActivity.smali` (hàm `onWindowFocusChanged`, dòng `1011-1015`):
   - Gọi thêm `MQUtils.hideSystemUI(this)` khi `hasFocus == true` để giữ trạng thái immersive (`0x1706`) và khung `2574 x 1440` ổn định mỗi lần quay lại ứng dụng (background → resume).

---

## 4. Sao lưu & Đóng gói APK

- **Sao lưu trước khi thay APK (`server/backups/vn_r5_display_before/`):**
  - APK cũ: `com.cmn.inuyasha_revival.apk` (`SHA-256: 525704d96df5d3c89a73aa6e429f1a6e7afe050e1e50c4140ab3386159aa0aea`).
  - Save snapshot (`MANIFEST.json`, `created_at: 2026-11-18 19:14:27 +0700`): `normal_profile.json` (`3b9f647ff4f6f529a84cea81cb942eb5d6f7a67130428922f11f9f553f8f7f08`), `debug_profile.json` (`544bb258f9967637bfe03c0f32c08f2a8ba86e406dc22b27c465f9f496c15831`), `audit_ledger.jsonl` (`c2ecbb5c2ffe7770cfd9e476be1ac3bdd17634680cd852b213d027712babeba4`).
- **APK đã vá & cài đè tại chỗ:**
  - Đường dẫn: `analysis/vn/patched/com.cmn.inuyasha_revival.apk` (`SHA-256: 480e732a16c2fd2a80ea745521b712c2226bd06ba841e38bf84b6de5ae2569db`).
  - Build qua `apktool_3.0.3.jar`, `zipalign` (`build-tools/36.1.0`), ký bằng cùng `~/.android/debug.keystore` và cài bằng `adb -s 192.168.1.89:40197 install -r` (`Success`).

---

## 5. So sánh Trước / Sau trên Pixel 3 XL

### Đo đạc `WindowManager` / `SurfaceFlinger` & vùng pixel hiển thị thực tế

| Trạng thái | Trước khi sửa (Rendered Frame) | Sau khi sửa (Window Bounds & SurfaceView) | Tỷ lệ (vs thiết kế `1.775`) |
|---|---|---|---|
| **Khởi động lạnh (`Cold Start`)** | `r51_before_1_coldstart.png`: `1437 x 1425` (`x=[280..1716]`, tỷ lệ `1.008`, logo CMN méo & mất nửa phải) | `r51_after_1_coldstart.png`: `mBounds=Rect(279, 0 - 2853, 1440)`, `Requested w=2574 h=1440`, `x=[280..2852]` (`1.806` trên bước lấy mẫu `4x16`, chuẩn cửa sổ `1.7875`) | Chính xác (`~0.7%`) |
| **Chọn Server (`StartGameScene`)** | `r51_before_2_serverselect.png`: `1437 x 1425` (`x=[280..1716]`, tỷ lệ `1.008`, hình minh họa bị nén lên nửa trên, nửa phải đen) | `r51_test_server_ready.png` & `r51_test_reopen_server.png`: `geomBufferSize=[0 0 2574 1440]`, `visibleRegion=[279, 0, 2853, 1440]`, `ROT_90` | Chính xác (`1.7875`) |
| **Vào `HomeScene` từ Server Selection** | Co cụm `1440 x 1440` bên trái | `r51_test_home_clean.png`: `Requested w=2574 h=1440`, `mBounds=Rect(279, 0 - 2853, 1440)`, đầy đủ nút cạnh trái/phải | Chính xác (`1.7875`) |
| **Đóng app & Mở lại / Resume** | Sai tỷ lệ `1440 x 1440` | `r51_test_reopen_server.png` (sau `force-stop` + mở lại) & `r51_after_dumpsys_resume.txt` (`KEYCODE_HOME` -> `am start`): giữ nguyên `Requested w=2574 h=1440`, `Frames: [279,0][2853,1440]` | Ổn định |
| **Vào `AdventureScene`** | — | `r51_test_adventure.png`: Chương 2..7 (`ẢI THƯỜNG`, `TINH ANH`, `YÊU VƯƠNG`, `ÁC MỘNG`, rương sao, bản đồ Chương 7) vừa khít `2574 x 1440` (`x=[280..2844]`) | Chính xác |
| **Vào `BattleScene` (Chiến đấu 7-2)** | — | `r51_test_battle.png`: `Lượt 1/30`, đội hình (`OlinaHugh`, `Kagome`, `Ayame`, `Shuran` vs quái), `HỦY ỦY THÁC`, `BỎ QUA` cân đối (`2574 x 1440`, `Requested w=2574 h=1440`). Đã `force-stop` trước khi kết thúc trận để giữ nguyên Thể Lực/Save | Chính xác |

### Kiểm thử chạm nút sát hai cạnh (`Edge Touch Accuracy`)
- **Cạnh trái (`HomeScene`):** Chạm Avatar sát mép trái `(380, 135)` → mở đúng popup **`Thông tin NV`** (`RoleInforLayer`, ảnh `r51_test_edge_left.png`), đóng đúng bằng nút `X` `(2425, 195)`.
- **Cạnh phải (`HomeScene`):** Chạm nút **`SHOP`** góc trên bên phải `(2730, 105)` → mở đúng **`Shop`** (`r51_test_edge_right.png`), chạm nút `X` sát mép phải `(2750, 75)` để đóng, rồi chạm **`MẠO HIỂM`** góc dưới bên phải `(2700, 1280)` → mở đúng `AdventureScene` (`r51_test_adventure.png`).

*(Ghi chú: Ảnh chụp trước/sau và log `dumpsys` lưu tại thư mục scratch phiên làm việc `/Users/vup/.gemini/antigravity/brain/6b5ac818-de8d-45ca-a178-b12bf898b223/scratch/r51_*`.)*

---

## 6. Xác minh Hồi quy & Bảo vệ bản Save `NORMAL`

- **Save `NORMAL` (`server/saves/normal_profile.json`):** So sánh trực tiếp với backup `server/backups/vn_r5_display_before/normal_profile.json`:
  - Giữ nguyên tuyệt đối tiến trình: `PlayerId="200010"`, `PlayerName="OlinaHugh"`, `Lv=16`, `Vip=0`, `Gold=173655`, `Diamond=655`, `MaxNodeId=1713`, `StarCount=51` (`VIT=10`, `STA=93` hiển thị khớp trên `RoleInforLayer`).
  - Sai khác duy nhất chỉ là dấu thời gian đăng nhập (`LastLoginTime`, `STANextRecoverTime`, `VITNextRecoverTime`) phát sinh tự nhiên khi đăng nhập trên Pixel 3 XL.
- **Log máy chủ (`server/rpc_trace.log`):** 0 lỗi Lua (`STEP_POST /api/report.ashx`) phát sinh trong toàn bộ quá trình kiểm thử R5.1.
- **Kiểm thử tự động & Môi trường:**
  - `python3 server/test_emulator.py`: **18/18 tests OK** (`2.254s`).
  - `python3 server/env_ctl.py status`: `stable` (`:8080`, `listening: true`, `server/saves`) tách biệt hoàn toàn với `dev` (`:8082`, `server/dev_saves`).
  - `python3 server/env_ctl.py smoke --url http://127.0.0.1:8080 --server-id 2`: `ok: true`, `/admin/*` trả `401` khi thiếu token.
  - `/usr/local/bin/node --check poc/web_poc/app.js`: `node syntax OK` (`exit 0`).
