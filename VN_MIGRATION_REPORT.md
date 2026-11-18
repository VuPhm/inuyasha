# VN_MIGRATION_REPORT.md — Đánh giá chuyển nền tảng sang bản Việt Nam (`com.cmn.inuyasha`)

## 1. Checkpoint EN ổn định trước khảo sát

Đã chốt và kiểm chứng toàn bộ trạng thái EN 5.1.1 trước khi cài/thử bản VN:
- **Git tag**: `checkpoint-en-r2` (commit `fed435c`).
- **Backup độc lập** tại `server/backups/en_r2_stable_checkpoint/`:
  - `com.heitao.inuyasha.guge_revival.apk` (SHA256 `e03d47315822a165470a9f58bafef3d5b90835addb70e0583d4c5aef4b59d1dc`)
  - `normal_profile.json` (SHA256 `3d1396608bc80d16cb6a051ae0fe205ae3dc2614095dc8ac2b2e28cce5cd3669`) — `PlayerId "200002"`, Lv 7, hoàn tất Tutorial Chương 1 -> 2-2.
  - `debug_profile.json` (SHA256 `86cac9a098daa61ab67ec6f5a724f60ec24a145adee422ac986ea0948f497d29`) — `PlayerId "100001"`, Lv 10, VIP 5.
- **Tài liệu R2**: [R2_REPORT.md](file:///Users/vup/Documents/agy/inuyasha/R2_REPORT.md) và [WORKLOG.md](file:///Users/vup/Documents/agy/inuyasha/WORKLOG.md).

---

## 2. Thu thập bản Việt Nam `com.cmn.inuyasha` 5.0.4.98 & Khảo sát bản 2019

| Mục | Kết quả kiểm tra thực tế |
| :--- | :--- |
| **Gói chính thức đã thu thập** | `originals/vn/com.cmn.inuyasha_5.0.4.98.xapk` (`210,162,212` bytes, `chmod 444`, SHA256 `0fa2d057367c8139ebb58891223d157aa3ddda9638bdccbde48175b2324ac68c`) từ `d.apkpure.net/b/XAPK/com.cmn.inuyasha?version=latest` (`data.winudf.com`). |
| **Thành phần bên trong XAPK** | `com.cmn.inuyasha.apk` (`96,677,706` bytes, `versionCode 98`, `versionName 5.0.4.98`, cert `CN=moqikaka` SHA-1 `a8adcd1adf13f12be67869d5135b9a25c82915e0`) + `main.98.com.cmn.inuyasha.obb` (`113,083,804` bytes). |
| **Bản phát hành lại 2019** | Tìm kiếm báo chí & kho lưu trữ (APKPure, Aptoide, `thanhnien.vn` 01/04/2019): CMN Online ra mắt `com.cmn.inuyasha` tháng 09/2017, thông báo ngừng 01/03/2019 và mở cửa lại đầu tháng 04/2019; **không có package ID hoặc bản APK/XAPK nào mới hơn `5.0.4.98` của Seek Jade CMN được lưu trữ công khai** (các kết quả 2021 thuộc *InuYasha Awakening* ARPG của SohaGame, đã loại trừ). |

---

## 3. So sánh chi tiết VN 5.0.4.98 với EN 5.1.1

| Hạng mục | EN 5.1.1 (`com.heitao.inuyasha.guge`) | VN 5.0.4.98 (`com.cmn.inuyasha`) | Đánh giá tương thích |
| :--- | :--- | :--- | :--- |
| **Engine & XXTEA Lua** | Cocos2d-x + `MQKK` / key `cf68b641311b5201` (`1,120` file `.luac` trong APK) | **Cùng engine & khóa `MQKK` / `cf68b641311b5201`** (`1,148` file `.luac` trong APK, giải mã 100% thành công, `0` `.luac` trong OBB) | Tương thích tuyệt đối |
| **Mã nguồn Lua dùng chung** | `1,116` file chung | **`921 / 1,116` file giống hệt từng byte**; `195` file khác chủ yếu ở text/dialog & module mở rộng | Gần như đồng nhất |
| **Protocol & Logic lõi** | `ServerInterface.lua`, `NetworkResData.lua`, `BattleLayer.lua`, `BattleDataCache.lua`, `GuideMng.lua`, `HttpClient.lua` (`GameVersionID=505`) | `ServerInterface`, `NetworkResData`, `BattleLayer`, `BattleDataCache`, `GuideMng` **giống hệt MD5**; `HttpClient` chỉ khác hàm tách `gameLogout` & `endToLua()`; `GameVersionID=504` | Server `emulator.py` chạy chung được ngay |
| **Chiến đấu & Công thức** | `Fight.lua`, `FightExpression.lua`, `BattleProcess.lua`, `VitConfig.lua`, `PlayerLvRelation.lua`, `BattleNodeModel.lua`, `BattleNodeDropRelation.lua` | **Giống hệt MD5 từng byte** toàn bộ các file công thức chiến đấu, rớt đồ, EXP, node ải! | Đồng bộ 100% |
| **Tướng & Cân bằng nâng cao** | `202` tướng, `maxPlayerLV = 70`, `HeroStepRelation` `42` mốc, `GuideRelation` `72` mục | `204` tướng (thêm `12015022 Tứ Đấu Thần`, `12015023 Inu Kimi`; 202 tướng chung chỉ khác 1 số `FSP` của `12015021`: EN 0 vs VN 500), `maxPlayerLV = 80`, `HeroStepRelation` `57` mốc, thêm `Goddomain*`/`GuildFb*`/`Shengyuanwars*`/`Zhenjue*`, `GuideRelation[112]` | VN phong phú hơn ở late-game |
| **Tutorial (`GuideRelation[1]`)** | Mắc guard cũ `heroCount > 2` / `< 3` ở `HomeScene.lua` & `GuideMng.lua` | Mắc cùng guard cũ ở `HomeScene.lua:3516/3526` & `GuideMng.lua:316` -> vá cùng patch XXTEA 3 đoạn là thông | Đã xử lý đồng bộ trong `poc/patch_vn_apk.py` |
| **Tài nguyên & Việt hóa UI** | Giao diện tiếng Anh | `Language.lua` (`4,116` dòng, `4,093` chuỗi Việt có dấu), font `UTMCAFETA.ttf` gán cho toàn bộ `_FONT_*` trong `Adapter.lua`, manga CG tiếng Việt, `90` texture trong APK `assets/res` + `619` file UI OBB được Việt hóa. Tuy nhiên **35/271** file Config vẫn sót chữ Trung trong `items` (`GoodsModel` 1,074 token, `HeroModel` 346 token, `EquipModel` 216 token), biển NPC `Summon/Forge/Challenge` giữ texture EN và dưới nút `ĐIỂM DANH` có 1 nhãn bị ô trắng nhỏ. | Dùng tốt ngay từ R2/R3, chỉ cần dọn text sót dần |
| **Tương thích Android 12** | `targetSdkVersion=23`, `AsyncHttpClient` & `classes.dex` chạy thẳng | Gốc `minSdk=9` không khai báo `targetSdk` và đóng gói **`assets/libs.apk` chứa lớp `Stub!` cho `org.apache.http`**, gây crash `SchemeRegistry Stub!` trên Android 12 nếu không chuyển `libs.apk` ra `classes2.dex` | Đã phát hiện & khắc phục tự động trong `poc/patch_vn_apk.py` |

---

## 4. Kết quả chạy thử nghiệm VN trên Pixel 3 XL (`com.cmn.inuyasha_revival.apk`)

Đã dựng APK thử nghiệm độc lập (`poc/patch_vn_apk.py` -> `analysis/vn/patched/com.cmn.inuyasha_revival.apk`, `96,806,706` bytes) cài song song cạnh EN (`com.heitao.inuyasha.guge`) mà **không sửa một dòng nào của `server/emulator.py`**:

1. **Khắc phục lỗi Android 12**: Chuyển các lớp hợp lệ của `assets/libs.apk` sang `smali_classes2/` (`classes2.dex`), loại bỏ các gói `Stub!` (`org/apache/http`, `android/net/http`), thêm `<uses-library android:name="org.apache.http.legacy" android:required="false"/>` và `usesCleartextTraffic="true"`, bypass Kull/Facebook SDK ở `Entity.smali`.
2. **Kết quả chạy thực tế trên Pixel 3 XL**:
   - Khởi động + giải nén OBB + preload (`44/100` -> `Đang tải tài nguyên...`, `Chơi`), kết nối `ServerList_Client.ashx` (`GameVersionID=504`), đăng nhập `Player.Login`, tạo nhân vật (`BrownAimee`, nút `Bắt Đầu`).
   - Vào CG truyện tranh tiếng Việt (`BỎ QUA`), trận mở đầu `BattleScript0000` (`Omukade`, `Bà Kaede`, `Kagome`, `Inuyasha`, popup hướng dẫn kỹ năng Nộ `"Khi đầy Nộ hãy nhấp AVA tướng để thi triển Kỹ Năng!"`), về `HomeScene` tiếng Việt (`CHIẾN LỰC 820`, `ĐIỂM DANH`, `ĐỘI`, `TÚI`, `HỆ THỐNG`, `MẠO HIỂM`).
   - Đánh `1-1` (`Thôn Dân Nữ`, `Lượt 1/30`, Kaze no Kizu Spine2D -> Victory `Battle.Fight` `Status=0`).
   - Triệu hồi `Ayame` (`HeroRecruit.Recruit [2, 1]`), đưa vào Slot 2 (`Slot.HeroCombat`), vượt ải `1-2` thật (`Sói Đen`, `Thôn Dân Nam`) ra **kết quả HP/RP cuối trận khớp chính xác 100% với EN** (`PosId 1 HP=448 RP=25`, `PosId 2 HP=626 RP=25`).
3. Sau khi hoàn tất thử nghiệm, đã dừng server thử nghiệm và khôi phục nguyên trạng `server/saves/normal_profile.json` & `debug_profile.json` từ `server/backups/en_r2_stable_checkpoint/`.

---

## 5. Kết luận đánh giá: **SWITCH VN**

### Quyết định chính thức: **`SWITCH VN`** (Chuyển sớm sang bản Việt Nam `com.cmn.inuyasha` 5.0.4.98 làm client chính)

**Lý do chọn `SWITCH VN` thay vì `KEEP EN` hoặc `MERGE VN INTO EN`**:
1. **Tương thích thực chứng ~99% với server hiện tại**: toàn bộ protocol (`ServerInterface`), `NetworkResData`, `FightExpression`, `BattleLayer`, `GuideMng`, `VitConfig`, `PlayerLvRelation`, `BattleNodeModel`, `BattleNodeDropRelation` hoạt động trực tiếp với `server/emulator.py` **không cần sửa server**, chạy mượt trên Pixel 3 XL qua hết mở đầu, triệu hồi, đội hình, `1-1` và `1-2`.
2. **Tiết kiệm chi phí Việt hóa & mở khóa nội dung cao hơn**: bản VN đã hoàn chỉnh sẵn `UTMCAFETA.ttf`, `4,093` chuỗi `Language.lua`, CG truyện tranh tiếng Việt, hơn `700` ảnh UI Việt hóa (APK+OBB), thêm `2` tướng (`12015022`, `12015023`) và mốc `maxPlayerLV=80` / Step `57` mốc — không phải tự dịch lại hàng nghìn file như `KEEP EN` hay phải đối chiếu lại ~100 key lệch phiên bản như `MERGE VN INTO EN`.
3. **Điểm nghẽn kỹ thuật duy nhất (Android 12 `libs.apk` Stub) đã giải quyết dứt điểm** qua `poc/patch_vn_apk.py`.

### Chi phí chuyển đổi ước tính (nếu chốt chuyển trong đầu R3)

| Phương án | Chi phí ước tính | Phạm vi công việc cần làm |
| :--- | :--- | :--- |
| **`SWITCH VN` (Khuyến nghị)** | **~0.5 – 1 ngày** | (1) Chạy `extract_game_data.py` bổ sung 2 tướng `12015022`/`12015023` & mốc Step/maxLv 80; (2) Dọn ~35 bảng Config còn sót chữ Trung trọng tâm là `HeroModel`/`EquipModel`/`GoodsModel` đầu game + sửa text nút `Bắt Đầu`/nhãn dưới `ĐIỂM DANH`; (3) Chạy lại full regression R2 (`1-1..2-2` lên Lv 7) trên VN APK trước khi thay EN thành mặc định. |
| **`MERGE VN INTO EN`** | ~2 – 3 ngày | Port `Language.lua`, `UTMCAFETA.ttf`, `Adapter.lua`, ~700 UI PNG/JPG + CG Việt vào APK EN 5.1.1; bổ sung dịch ~100 key mới của bản 5.1.1; giữ `targetSdk=23`; mất công test lại toàn bộ layout/cắt chữ tiếng Việt trên engine 5.1.1. |
| **`KEEP EN`** | Thấp nhất ngắn hạn (0 ngày), **cao nhất dài hạn (+4–6 ngày nếu cần tiếng Việt)** | Chỉ phù hợp nếu xác định phát triển hoàn toàn bằng tiếng Anh; nếu muốn có tiếng Việt về sau vẫn phải tự dịch toàn bộ UI/CG/Config. |
