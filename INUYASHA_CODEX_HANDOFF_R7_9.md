# InuYasha: Seek Jade — bàn giao Antigravity → Codex

**Thời điểm tổng hợp:** 20/11/2026 (UTC+7)  
**Mốc được báo cáo mới nhất:** `checkpoint-vn-r7.9`, commit `d24d214`  
**Dự án gốc trên Mac:** `/Users/vup/Documents/agy/inuyasha`  
**Mục đích:** Giúp một phiên Codex **chạy trên Mac và mở đúng thư mục dự án** tiếp tục R7.10–R7.11 mà không lặp lại nghiên cứu/kiểm thử những phần đã nghiệm thu.

> **Ranh giới chứng cứ:** Tài liệu này tổng hợp lời người dùng, các báo cáo/kết quả Agy đã dán vào ChatGPT và năm bản ghi Agy trước đó. Phiên tổng hợp hiện tại chạy trong Linux, **không truy cập được thư mục Mac**; vì vậy các hash, số bài test và trạng thái thiết bị nêu bên dưới là **kết quả Agy báo cáo**, Codex trên Mac phải xác nhận bằng kiểm tra đọc-only trước khi sửa code. Không coi nội dung tài liệu này là một lần audit source mới.

## 1. Mục tiêu sản phẩm — các quyết định người dùng đã chốt

1. **Chơi full game trước, sự kiện và nhánh rìa tiếp theo**, không sa đà quá lâu vào một tính năng nhưng cũng không cực đoan chạy chỉ tiêu trải rộng. Tối ưu theo giá trị trải nghiệm và rủi ro.
2. Ưu tiên **APK Android standalone cục bộ, chơi offline 100%**, không yêu cầu Mac, Internet hoặc private server. Mỗi người bạn tự cài APK, chơi solo và tự giữ save.
3. **Nhiều tài khoản trong cùng thế giới S1 trên một máy**, chuyển TK1/TK2/... để lập đội hình, lưu phòng thủ Arena và đấu với snapshot tài khoản khác cùng S1. Không nhầm đây với multiplayer Internet.
4. Có **Kim Cương, nạp giả lập, tăng VIP, chiêu mộ đa dạng** ngay trong UI, không giao dịch tiền thật; giữ được kinh tế và tiến trình chơi.
5. **Event Archive** giữ lại sự kiện cũ; nhiều event và banner hoạt động **đồng thời**. Mặc định reset **hằng ngày 00:00 UTC+7**, cho phép chu kỳ tùy chỉnh và **reset thủ công có xác nhận**, không xóa tướng/đồ/tiền/save. Khoảng pity và điểm tích lũy tách riêng từng banner.
6. Đặc biệt quan tâm các **sự kiện nhiều người / cộng đồng, rung cây, mở rương, quay xổ số, trò may mắn, đập trứng, đổi quà**, có thể dùng người chơi giả lập hoặc nhiều tài khoản cùng S1 nếu một sự kiện đòi cộng đồng. Không cần dựng private server ở giai đoạn này.
7. Có thể khảo sát dữ liệu máy chủ/phiên bản nước khác (ví dụ TW 1.4), thậm chí phục hồi sự kiện độc quyền khu vực về sau, nhưng phải **đối chiếu ID, schema, tài nguyên, UI và Lua với bản VN 5.0.4.98**; đánh dấu rõ bản gốc, bản chuyển thể, hay luật phần thưởng ước lượng.
8. APK cập nhật bằng **cài đè cùng package + cùng signing key, versionCode tăng dần**, giữ nguyên tiến trình và tài khoản. Sao lưu/export và restore là lớp dự phòng, không thay cho upgrade in-place.
9. **Test the Delta:** ưu tiên test tự động có mục tiêu, smoke test thiết bị đúng màn hình mới/sửa; **không chơi lại tutorial, ải 1-1, các màn đã PASS trong R7.7–R7.9**, trừ khi chính thay đổi động vào đó. Báo cáo thật PASS/FAIL/BLOCKED, có bằng chứng.

## 2. Hiện trạng kỹ thuật (theo báo cáo Agy)

| Mục | Trạng thái báo cáo |
|---|---|
| Client | VN `5.0.4.98`, game Cocos2d-x/Lua, native ARM **32-bit** (`armeabi`/`armeabi-v7a`) |
| Mac repo | `/Users/vup/Documents/agy/inuyasha`, branch `master`, tag `checkpoint-vn-r7.9`, commit `d24d214` |
| Android app standalone | `com.cmn.inuyasha.revival`, APK 1 file tích hợp OBB, Python 3.11 32-bit backend nhúng + `libinubackend.so` |
| Backend Android | Khởi chạy cùng app; bind chỉ `127.0.0.1:18082`, không cần mạng Internet |
| Android build R7.9 | `analysis/vn/patched/com.cmn.inuyasha.revival_r7_9_standalone.apk`, `versionCode=790` |
| Pixel 3 XL | Android 12; Agy đã test nâng cấp in-place `780 → 790` và vẫn thấy `TK1: FoxZora`, `TK2: OlinaHugh`, `TK3`, `TK4: TomNoel` |
| Kiểm thử R7.9 | `python3 server/test_emulator.py -v` — Agy báo **55/55 PASS**; UI thực tế HomeScene và TimedActivityScene hoạt động, một số RPC mới trả `Status=0` |
| STABLE Mac | `:8080`, checkpoint R6.2 `5fed4bb`; phải giữ độc lập, không tự promote từ DEV |
| DEV Mac | `:8082`, server save/dev_saves theo thông lệ; kiểm tra trạng thái thực tế trước khi dùng |
| Key ký Android | Khóa release cố định ở `~/.inuyasha_release/inuyasha_revival_release.jks` **trên Mac**; không sao chép/publish khóa/secret/log credential |
| ABI | Pixel 3 XL hỗ trợ 32-bit; Android chỉ hỗ trợ 64-bit (một số Pixel đời mới) **không chạy native 32-bit này** |

**Mốc nổi bật:** R7.2 hoàn thiện guide, R7.2A và R7.3 audit dữ liệu VN; R7.4 nạp offline/VIP/đa chiêu mộ; R7.5 EventClock/EventArchive; R7.6 thêm gameplay, multi-banner reset/chu kỳ; R7.7–R7.8 standalone APK, backup và đa tài khoản S1; R7.9 hoạt động lịch sử + TW donor.

### 2.1. Những gì R7.9 được báo cáo đã khôi phục

- Cây Tiền `4432` (`TimedMoneyTreeLayer`), Cây Cầu Nguyện `4409` (`TimedPrayTree`), Quay Số `4412` (`TimedSlotLayer`/`SlotMachine`), Đoạt Bảo `7800` (`YiJiDuoBaoLayer`), Đập Trứng `4426` (`TimedSmashEggLayer`), Chiêu Mộ Thần Binh `4410` (`TimedRecruitEquipLayer`).
- `OnlineReward 3700`, `MonthlySign 2712`, `RandomRedBag 5501`, `TimeSpike 6800`, `TimeSpikeKing 7000`, `ShiWanDiamond 8200`, `TimedInfo 4401..4407/4421/4422/4427`, `TimedChargeGift 4429`, `TimedChargeScore 4428`, `TimedLimitExchange 4406`, `TimedTaskList 4700`, `LimitStore 4300`, `OpenActivity 2600`, `ActiveGift 2716`, `DailyShare 2705`.
- BXH/cộng đồng cùng S1: `OpenSeriveCompetition 7900`, `ChargeRank 4421/4422`, `TimedActivityRank 4430`, kết hợp tài khoản thật cùng máy và peer giả lập.
- Kích hoạt `TimedActivityScene 4400` (GIỜ VÀNG) & `RedDotInfo`, `OpencontestState=1`, theo dõi `recharged_diamonds` và `spent_diamonds`.
- 5 Config từ TW 1.4 được Việt hóa/ánh xạ: `XssbModel`, `CriticalTasksTypeRelation`, `EarlytaskModel`, `EarlytaskRewardRelation`, `TraderConfig`, đóng gói trong `assets/src/Config/`.

**Phải kiểm chứng thêm:** Báo cáo R7.9 mới xác nhận 55 test + một số màn và RPC; **chưa đủ bằng chứng rằng mọi event kể trên đã được chơi trọn vòng trên UI**, nhận thưởng, cập nhật túi, phản hồi lỗi, reset/reload và upgrade giữ save.

### 2.2. Các file/cụm nguồn cần đọc trên Mac

- `PROJECT_ROADMAP.md`, `EVENT_RECOVERY_CATALOG.md`, `R7_9_ACCEPTANCE_REPORT.md`, `R7_7_R7_8_STANDALONE_BETA_REPORT.md`.
- `server/emulator.py` (RPC, profile, S1, combat); `server/r79_event_handlers.py` (event R7.9); `server/event_handlers.py`, `server/event_runtime.py`; `server/game_data.json`; `server/economy_audit.py`; `server/test_emulator.py`.
- `poc/build_standalone_apk.py`, `poc/patch_vn_apk.py`, `android/native/inubackend.c`, `android/src/com/cmn/inuyasha/standalone/LocalBackendManager.java`, `LocalBackendService.java`.
- Client source Lua VN, đặc biệt `TimedActivityScene`, `TimedMoneyTreeLayer`, `TimedPrayTree`, `TimedSlotLayer`, `TimedSmashEggLayer`, `TimedRecruitEquipLayer`, `LimittedTimedRecruitLayer`, `HeroRecruit`, `GoodsUseForBoxChoice`, `AccountManage`, `SystemLayer`, `HttpClient`, `StartGameScene`, `GameLoginScene`.
- Donor dữ liệu từng vùng trong `analysis/` hoặc thư mục đã chuẩn bị; so sánh với cấu hình VN, **không copy ID trực tiếp**.

Không tự tạo đường dẫn con khi chưa thấy file thực tế. Đọc tất cả hướng dẫn `AGENTS.md` trong đường dẫn áp dụng trước khi sửa.

## 3. Quy trình nhận repo vào Codex trên chính Mac

**Nếu dùng Codex app/CLI trên Mac:** mở chính thư mục `/Users/vup/Documents/agy/inuyasha` làm workspace. Không cần chuyển file bằng tay vì source và Git đã ở đó. Dán nội dung mục 5 phía dưới vào Codex trong workspace ấy và cho phép Codex đọc repo; ChatGPT project history **không được giả định tự đồng bộ thành file source**.

**Nếu dùng Codex từ môi trường Linux/ChatGPT khác:** repo Mac không tự mount. Người dùng cần attach archive source+docs+assets (cẩn thận dung lượng), hoặc cung cấp Git remote đã cấp quyền; các bản ghi Agy/ChatGPT **không thay thế mã nguồn**. Tránh đưa `~/.inuyasha_release`, session/token, thông tin đăng nhập, save riêng tư không cần thiết vào archive công khai. Việc build APK từ xa cũng cần khóa ký release **trên Mac** hoặc giải pháp ký tin cậy, không yêu cầu người dùng gửi private key trong chat.

### Lần kiểm tra đầu tiên (read-only, không sửa)

Chạy từng lệnh trong repo trên Mac:

```bash
pwd
git status --short --branch
git rev-parse HEAD
git tag --list 'checkpoint-vn-r7.*'
git show --stat --oneline checkpoint-vn-r7.9
git diff --name-status checkpoint-vn-r7.9
rg --files -g AGENTS.md -g 'R7_9_ACCEPTANCE_REPORT.md' -g 'PROJECT_ROADMAP.md' -g 'EVENT_RECOVERY_CATALOG.md'
rg --files server poc android analysis | rg 'r79_event_handlers|event_runtime|emulator.py|test_emulator.py|build_standalone_apk|TimedActivity|TimedRecruit'
```

Sau đó đọc báo cáo, nguồn thật, lưu ý dirty worktree và các file save không được tracked. Kiểm tra tệp APK R7.9 đã tồn tại trước khi thay. Nếu repo có thay đổi sau R7.9, **kế thừa thay đổi mới**, không checkout/reset làm mất dữ liệu.

## 4. Kế hoạch gợi ý: hai round tiếp theo, ưu tiên trải nghiệm thực tế

### R7.10 — Khép kín gameplay sự kiện may mắn + nhận thưởng

1. **Audit delta R7.9:** Lập bảng mỗi sự kiện trọng điểm `UI mở được / RPC đúng / trừ phí / thưởng đúng / vật phẩm vào túi / nút nhận mốc / reset / persistence`. Tập trung `4432,4409,4412,4426,7800,4410` và các event có chest/roulette/lottery. Xác minh qua Lua gốc, payload thật, và dữ liệu VN trước.
2. **Ưu tiên các lỗi chặn gameplay nếu tái hiện được:** không nhận tướng đã quay do giới hạn túi hay schema; cách tăng sức chứa túi; không mở/nhận rương mốc banner; trạng thái thưởng bị đánh dấu đã nhận nhưng vật phẩm không vào túi. Đây là **giả thuyết cần đối chiếu báo cáo/log và tái hiện**, không mặc định là bug đã xác nhận trong source. Nếu sửa, cần xét overflow/mail/RewardCenter, idempotency và không mất quyền nhận.
3. Khôi phục **vòng chơi hoàn chỉnh** của vài event đại diện: click UI → RPC → tiêu phí/đếm lượt → random/reward đúng schema → nhận thưởng vào profile → kết toán/không trùng → reset daily/manual → reload save. Không chỉ fake `Status=0`.
4. Event nào phụ thuộc bảng thưởng/asset bị thiếu: thử nguồn VN; sau đó donor TW/region khác với bảng mapping; cuối cùng fallback rõ ràng. Không khẳng định quy tắc xưa nếu chưa có chứng cứ.
5. Viết test tự động cho event mới/sửa, một smoke test Pixel 3 XL vào đúng các tab mới; không chạy lại tutorial cũ. Kiểm tra server loopback offline và nhiều tài khoản S1 ở các nhánh bị chạm.

**Tiêu chí chốt:** Một nhóm sự kiện may mắn chạy **trọn vòng UI** và nhận thưởng có kiểm chứng; không phát sinh dupe/loss; 55 bài test cũ và test mới PASS; ghi rõ event nào còn thiếu nguồn gốc/dữ liệu.

### R7.11 — Cộng đồng offline, Event Archive và bản cập nhật tiếp theo

1. Hoàn thiện event nhóm/cộng đồng với **nhiều tài khoản cùng S1 và bot/snapshot local** khi không có người thật (BXH, tranh hạng, boss, rương, vòng thưởng). Không ép Internet/mở private server.
2. Hoàn thiện multi-banner và Event Archive chạy đồng thời, đổi kỳ theo UTC+7 hoặc cấu hình, reset thủ công xác nhận, bảo hiểm/pity/reward không chảy chéo giữa banner, giữ lịch sử kỳ cũ.
3. Chọn theo **độ chơi được** các event còn thiếu, mở đủ UI, phần thưởng thực, cấu hình chuẩn và feedback rõ. Ghi mức độ phục hồi: nguyên bản VN / chuyển vùng / mô phỏng được chú thích.
4. Build APK standalone mới với **versionCode tăng từ 790** (không tái sử dụng 790), cùng `com.cmn.inuyasha.revival` và release keystore cũ; thử `adb install -r` giữ các tài khoản và save hiện có. Tạo backup trước upgrade. Không uninstall/reinstall xóa dữ liệu.
5. Test đích trên Pixel 3 XL: offline/airplane, event mới, chuyển tài khoản S1, reload, upgrade in-place; chỉ test lại phần cũ nếu có dependency bị sửa.

**Tiêu chí chốt:** APK mới cài đè R7.9 được trên Pixel, bảo toàn save TK1–TK4, ít nhất một event nhóm/may mắn chạy được và có report PASS/FAIL/BLOCKED; cập nhật roadmap/catalog, tạo checkpoint khi nghiệm thu thật.

### Tùy thời gian R7.12

Chỉ lên R7.12 khi cần: mở rộng donor vùng khác, event độc quyền có asset hợp lệ, tương thích thiết bị Android 32-bit của bạn bè, UX backup/restore, và tài liệu ship. Không lấy “đủ số lượng event” làm điều kiện thay thế chất lượng.

## 5. PROMPT DÁN VÀO CODEX TRÊN MAC

```text
Bạn đang tiếp quản dự án InuYasha: Seek Jade VN 5.0.4.98 từ Antigravity (Agy) tại
/Users/vup/Documents/agy/inuyasha. Người dùng đã cho phép tiếp tục vài round, nhưng
phải giữ toàn bộ save, STABLE và các checkpoint. Mốc Agy mới nhất được báo cáo:
checkpoint-vn-r7.9 / d24d214; APK Android standalone com.cmn.inuyasha.revival
versionCode=790, 55/55 test PASS, Pixel 3 XL nâng cấp 780→790 giữ 4 TK S1.

Nhiệm vụ:
1) Đọc AGENTS.md áp dụng, git status/log/tag và R7_9_ACCEPTANCE_REPORT.md,
PROJECT_ROADMAP.md, EVENT_RECOVERY_CATALOG.md; kiểm chứng tình trạng thật, không
mặc định báo cáo dán vào chat chính là source đã audit. Bảo lưu thay đổi chưa commit.
2) Audit đúng delta của các sự kiện R7.9 trên client VN, server/r79_event_handlers.py,
event_runtime, game_data, UI/Lua và các config donor TW 1.4. Ưu tiên rung/cây tiền,
cầu nguyện, quay số/xổ số, đập trứng, mở rương, may mắn, đoạt bảo, rương mốc banner;
nhất là vòng UI→RPC→tiêu phí→nhận thưởng→lưu→reset.
3) Kiểm tra khả năng nhận tướng chiêu mộ, sức chứa túi, nới túi, rương mốc; nếu lỗi
tái hiện thì sửa an toàn, có test chống mất thưởng/dupe. Không tự suy ra nguyên nhân
khi chưa có log, không tự tạo item/hero ID không tồn tại.
4) Triển khai R7.10 theo các lỗi chặn gameplay lớn nhất, rồi R7.11 cho event nhóm
offline dùng nhiều TK cùng S1 / bot local và Event Archive multi-banner. Có thể
chuyển đổi cấu hình từ bản TW hoặc khu vực khác, nhưng phải map ID/schema/asset
đúng bản VN, phân loại rõ tính nguyên bản.
5) Test the Delta: test tự động nhắm các RPC/event đổi, chỉ vài thao tác UI đúng
nhánh trên Pixel 3 XL; không replay guide và những màn R7.7–R7.9 đã PASS. Test
full unit suite một lần trước nghiệm thu, thêm smoke offline/loopback,
backup+upgrade in-place cùng package/signing key để bảo toàn TK1–TK4.
6) Giữ STABLE :8080 checkpoint R6.2 nguyên vẹn, tránh ảnh hưởng Mac DEV :8082,
không reset --hard, không xóa saves, không uninstall app. Không in/chuyển key ký,
token hoặc thông tin cá nhân. Bản mới tăng versionCode từ 790.
7) Cập nhật PROJECT_ROADMAP.md, EVENT_RECOVERY_CATALOG.md và báo cáo nghiệm thu
có bảng PASS/FAIL/BLOCKED + bằng chứng; checkpoint/tag sau khi đủ tiêu chí.
Giải quyết theo mức độ ảnh hưởng trải nghiệm, không đi quá sâu một nhánh và cũng
không bỏ dở P0 chỉ để mở thêm tên sự kiện. Cho người dùng biết khi nào APK mới
thực sự đủ an toàn để gửi bạn bè; nêu hạn chế thiết bị thuần 64-bit.

Trước khi sửa, hãy đưa ra trạng thái repo xác minh, thiếu sót lớn nhất theo chứng
cứ, và kế hoạch 2 round ngắn. Sau đó tự triển khai các việc nằm trong phạm vi trên.
```

## 6. Hạng mục phải giữ an toàn

- **Đừng đụng STABLE `:8080`** hoặc promote DEV nếu không được yêu cầu rõ.
- **Đừng đổi package name hay release keystore**; cập nhật khác chữ ký làm `INSTALL_FAILED_UPDATE_INCOMPATIBLE` và thường dẫn đến yêu cầu uninstall mất save.
- **Không phá `ServerId`/`PlayerId`/`Session`:** Một S1 có nhiều tài khoản và nhiều nhân vật khác nhau. Không cho các TK ghi đè profile; mỗi event phải bind vào đúng player/world. Server S2 QA giữ tách biệt.
- **Tài sản save**: backup SHA-256, xác minh số tiền/hero/inventory/tiến trình trước/sau upgrade. Save có mirror, không coi mirror là license xóa nguyên bản.
- **Không coi `Status=0` một mình là đủ.** Phải thấy payload khớp Lua, item/hero thật có trong profile/UI, tiêu phí và bảo hiểm đúng, không nhận trùng.
- **Không đưa event độc quyền khu vực khác vào VN nếu không có asset/schema tương thích**; nếu mô phỏng phải ghi rõ và kiểm tra legal/distribution implications trước khi chia sẻ APK ra ngoài.

## 7. Nguồn đã có tại thời điểm bàn giao

1. Tin nhắn người dùng/Agy mới nhất về R7.9 trong hội thoại ChatGPT này (chi tiết 30 sự kiện, 5 config TW, APK R7.9, 55 bài test, 4 tài khoản).
2. Năm bản ghi Agy giai đoạn R7.2–R7.6 mà người dùng đã đưa vào workspace ChatGPT này (nội dung chủ yếu là tiến độ/thông báo thao tác và báo cáo, **không phải mã nguồn**).
3. Các báo cáo và file thực tế phải đọc trong repo Mac tại mục 2.2. Tệp này **chưa** bao gồm bytecode Lua, native `.so`, APK/OBB, server source hoặc save trên Mac.

**Để Codex tiếp tục ngay trên Mac:** mở đúng workspace, cung cấp file bàn giao này vào context và dán prompt ở mục 5. Nếu muốn Codex chạy ở một máy/phiên khác, trước hết cung cấp bản export repo và những asset cần thiết một cách an toàn; không cần gửi private signing key.
