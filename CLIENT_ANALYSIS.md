# CLIENT_ANALYSIS.md — Phân tích cấu trúc APK, tài nguyên, engine & giao thức (Round R0)

## 1. Engine & Công nghệ cốt lõi (xác minh trực tiếp từ binary)
- **Game Engine**: **Cocos2d-x + LuaJIT** (`lib/armeabi/libcocos2dlua.so`, ~32.47 MB ở EN 5.1.1 / ZH 5.0.0 / TH 5.1.3.6; ~18.47 MB ở TW 1.4).
- **Skeletal Animation**: **Spine 2D binary v2.1.27** (xác minh header `\x072.1.27` trong `assets/res/animation/hero_quanyecha.skel`), đi kèm `.atlas` (LibGDX format), `.png` spritesheet và `.event`.
- **Crash Reporting / SDK**: `libBugly.so`, Java launcher `com.moqikaka.sdk.MQActivity` (`com.moqikaka.sdk.GameApplication`), Heitao proxy SDK (`assets/ht_proxy_config.json`), Facebook / Google / Adjust / Kochava SDK.
- **Kiến trúc CPU**: Tất cả 4 APK chỉ đóng gói thư viện native 32-bit `armeabi`.
  - **Google Pixel 3 XL (`crosshatch`, Android 12)**: `ro.product.cpu.abilist = arm64-v8a,armeabi-v7a,armeabi` -> **Hỗ trợ chạy 32-bit `armeabi` native**.
  - **AVD x86_64 trên Mac (`Pixel_2`, `UVolumeX_API31`)**: `abilist32` rỗng -> không chạy trực tiếp `armeabi`.

---

## 2. Cơ chế mã hóa script Lua & kết quả giải mã
Từ disassembly ARM32 trong `libcocos2dlua.so` (bản EN 5.1.1):
- `AppDelegate::applicationDidFinishLaunching` (`0x0095ccec`) gọi `TextUtils::setLuaEncodeString(LuaStack*)` (`0x0097a550`).
- `TextUtils::setLuaEncodeString` lấy chuỗi `"inuyasha_moqikaka_inuyasha"` (`0x01a4df28`), tính `md5()`, format 8 byte đầu thành 16 ký tự hex (`%02x`), và gọi `LuaStack::setXXTEAKeyAndSign`:
  - **XXTEA Sign**: `"MQKK"` (4 byte đầu của mọi `.luac`)
  - **XXTEA Key**: `md5("inuyasha_moqikaka_inuyasha")[:16]` = **`cf68b641311b5201`**
- **Điểm đặc biệt quan trọng**: Nội dung sau khi giải mã XXTEA là **mã nguồn Lua thuần (plain text UTF-8, còn nguyên comment tiếng Trung)**, không bị biên dịch thành bytecode!
- **Kết quả giải mã hàng loạt**:
  - EN 5.1.1 (`analysis/decompiled/EN_5.1.1/src/`): **1,120** file `.lua`
  - ZH 5.0.0 (`analysis/decompiled/ZH_5.0.0/src/`): **1,186** file `.lua`
  - TH 5.1.3.6 (`analysis/decompiled/TH_5.1.3.6/src/`): **1,227** file `.lua`
  - TW 1.4: dùng hàm `AppDelegate::getXXTEAKey()` (`0x005aadec`) dựng khóa trên stack theo từng ký tự (chưa cần giải mã ở R0 vì đã có full source của EN 5.1.1 / ZH 5.0.0 / TH 5.1.3.6).

---

## 3. Phân bố tài nguyên giữa APK và OBB
Trong EN 5.1.1 (tương tự ZH và TH), tài nguyên chia đôi giữa `APK/assets/res/` và `OBB` (OBB là **ZIP chuẩn nén `store`**, game giải nén OBB vào `getWritablePath() .. "Download/"` khi chạy lần đầu trong `GameLoginScene:unzipObbFile`):

| Thành phần | Trong APK (`assets/`) | Trong OBB (`main.511...obb`) |
| :--- | :--- | :--- |
| Script & Config | 1,120 `.luac` (gồm 237 bảng `Config/*.lua`, `ComBattle/`, `Login/`, `Network/`, `Home/`) | Không (riêng TW 1.4 có thêm 237 `.luac` trong OBB) |
| Spine2D skeletons | 494 `.atlas`, 494 `.skel`, 307 `.event` | Phần lớn `.png` spritesheet của animation (`res/animation/*.png`, 426 file) |
| UI & Map | 322 `.png`, 22 `.jpg`, 22 `.plist`, `FZPangWa-M18S.ttf`, `FZZY-GBK.TTF` | 3,377 `res/ui/*`, 130 `res/map/*`, 45 `res/resManual/*` |
| Âm thanh / Nhạc | 61 `.mp3` (có `music_login.mp3`) | 888 `.mp3` (BGM trận đấu, lồng tiếng nhân vật `hs_*`/`hc_*`, SFX kỹ năng `effect_s_*`), 1 `.mp4` |
| Cập nhật (OTA) | `assets/res/project.manifest` (Cocos2d-x `AssetsManagerEx`) | `project.manifest` |

Dữ liệu tĩnh đã trích xuất từ `EN_5.1.1/src/Config/` sang `server/game_data.json`:
- **202** tướng (`HeroModel.lua`), **439** đòn đánh/kỹ năng (`AttackModel.lua`), **70** chương (`BattleChapterModel.lua`), **689** ải chiến đấu (`BattleNodeModel.lua`), **18** kịch bản trận mở đầu/cốt truyện (`ComBattle/Script/BattleScript*.lua`).

---

## 4. Cấu hình, Endpoint & Giao thức mạng

### 4.1. Cấu hình client (`assets/AConfig.json` & `libcocos2dlua.so`)
- **EN 5.1.1**:
  - `Version`: `"505"`, `GameID`: `"35"`, `Default`: `Channel=DZZ|LoginKey=1d7f0abf-7822-4c68-a18a-48522680cfdf` (`PartnerID=1121` trong `AndroidManifest.xml`).
  - `ManageCenter`: `http://loginsvr.enqyc.moqikaka.com/API/ServerList_Client.ashx`
  - `ReleaseDomain`: `http://loginsvr.enqyc.moqikaka.com/`
- **ZH 5.0.0**: `ManageCenter=http://loginsvr.cnqyc.moqikaka.com/API/ServerList_Client.ashx`
- **TW 1.4**: `ManageCenter=http://loginsvr.twqyc.moqikaka.com/API/ServerList_Client.ashx`
- **TH 5.1.3.6**: `ManageCenter=http://loginsvr.tlqyc.moqikaka.com/API/ServerList_Client.ashx`
- **Cơ chế chuyển server test có sẵn trong `src/main.lua`**: Nếu tồn tại file `debug` trong `getWritablePath()`, client đọc `DebugDomain` và ghi đè `ManageCenter`. Ngoài ra, khi `Channel=MQKK`, `GameLoginScene` hiển thị giao diện đăng nhập/đăng ký nội bộ (`createMqkkUI`) + `createDebugUi()`.

### 4.2. Giao thức HTTP JSON RPC (`src/Network/HttpClient.lua` & `src/Login/StartGameScene.lua`)
Toàn bộ gameplay (đăng nhập, khởi tạo dữ liệu, bản đồ ải, chiến đấu, kết toán, tướng, túi đồ) dùng **HTTP POST JSON thuần** tới `<ServerUrl>/client.aspx` (không mã hóa binary socket — chỉ `Chat/ChatMng.lua` dùng `SocketManager` cho chat):

1. **Lấy danh sách server**: `POST <ManageCenter>` (`application/x-www-form-urlencoded`: `gameID`, `PartnerID`, `GameVersionID`, `EncryptedString`, `RandNum`, `ResourceVersionName`, `UserID`, `LoginInfo`)
   - Trả về JSON: `{ "Code": 0, "Data": { "Server": [{ "ServerID", "ServerName", "ServerState", "ServerHeat", "ServerUrl" }], "ServerHistory": [...], "Resource": {}, "UserInfo": {...} } }`
   - Khi `Data.Resource` rỗng (`{}`), client bỏ qua kiểm tra tải hot-update và chạy preload local ngay.
2. **RPC Gameplay**: `POST <ServerUrl>/client.aspx`
   - Request JSON: `{ PartnerId, ServerId, Session, PlayerId, GameVersionId, ResourceVersionName, MAC, IDFA, ModuleName, MethodName, Data, ExtensionString, SendTick }`
   - Response JSON: `{ Status: 0, TimeTick, Avatar, GuildAvatar, Value }`
   - Các luồng cốt lõi đã xác minh schema từ `StartGameScene.lua`, `RoleCreateScene.lua`, `NetworkResData.lua`, `BattleLayer.lua`, `BattleSettleLayer.lua`, `CSCommon/ServerInterface.lua`, `ComBattle/BattleVerify.lua`:
     - `Player.Login` / `Player.Login_ForTest` -> trả `PlayerId`, `Session`, `IsNewPlayer`, `PlayerInfo`.
     - `Player.NewPlayer` -> tạo nhân vật mới.
     - `Player.GetInitData` -> trả `PlayerInfo`, `HeroInfo`, `SlotInfo`, `SlotFormationInfo`, `ModulesInfo`, v.v.
     - `Battle.GetBattleInfo` / `Battle.GetNodeList` -> trả danh sách chương và ải.
     - `Battle.GetFightInfo` -> trả `FightInfo.FightObjs[1].Heros[1..12]` + `TeamData[1..2]`.
     - **Engine chiến đấu chạy hoàn toàn ở client (`ComBattle/BattleLayer.lua` & `BattleProcess.lua`)** và gửi kết quả về server qua `Battle.Fight` (`{ ChapterId, NodeId, StarCount, Result, VerifyData, IsBreak }`).

---

## 5. Phát hiện giao thức bổ sung khi chạy Client thật trên Pixel 3 XL (Round R1)
1. **Nén HTTP Response bằng `zlib`**:
   - Disassembly hàm `LuaMinXmlHttpRequest` trong `libcocos2dlua.so` cho thấy mặc định `_isNeedUnzip = 1`, mọi response từ `ManageCenter` (`/API/ServerList_Client.ashx`), `/API/ServerList_CheckResource.ashx` và `/client.aspx` được đưa qua `ZipUtils::inflateMemory` (`inflateInit2(..., 47)`). Nếu trả JSON thuần không nén zlib/gzip, client báo lỗi parse ở ký tự đầu tiên (`Expected value but found T_END at character 1`).
2. **Endpoint kiểm tra tài nguyên khởi động**:
   - Ngay khi vào `GameLoginScene`/`game.lua`, client gọi `POST /API/ServerList_CheckResource.ashx` (`VersionID=0`), mong đợi `{ "Code": 0, "Data": {} }` dạng zlib.
3. **Các ràng buộc schema bắt buộc của Lua client**:
   - `ServerList_Client.ashx` (`Data.Server[]`) bắt buộc có `ChatServerUrl` (`"<ip>:<port>"`), vì `Chat/ChatMng.lua:80` gọi `string.trim(serverInfo.ChatServerUrl)`.
   - `IdIsValid(entityId)` trong `Common/CommonFunc.lua:586` kiểm tra độ dài chuỗi bằng `EMPTY_ENTITY_ID` (**36 ký tự UUID**). Các `HeroInfo.Id` ngắn hơn 36 ký tự đều bị coi là không hợp lệ.
   - `Avatar` trong response JSON RPC chạy `NetworkResData:updateAvatar` **trước** callback `updateInitData`. Không được trả `"Lv"` trong `Player.NewPlayer` (khi `mFormationInfo` chưa tồn tại) và nên bỏ qua `"Lv"` ở các RPC thường để tránh gọi `modifyMainHeroLv` / kích hoạt popup lên cấp giả. Phải kèm `"TimedActivityOpenInfo": {}` để khởi tạo `mTimedActivityOpenInfo` trước khi `HomeScene:createTop` kiểm tra `ModuleSub.eTimedRecruit`.
   - `ModulesInfo` dùng cấu trúc `{ SubModuleId, OrderNum, IfOpen }` (không phải `ModuleId`/`IsOpen`).
   - `BagInfo` bắt buộc có các `BagModelId` hợp lệ (`1..6` theo `BagModel.lua`) để `checkFunc` khi vào ải đọc được `.Size`.
   - `SlotInfo[].Property` cần đủ các hệ số tính chỉ số trong `PlayerFormationLayer.lua:3538` (`FAP`, `FSP`, `AP1`, `APR1`, `AP2`, `APR2`, `APAdd`, `APHero`, `APHeroR`, `DEF1`, `DEFR1`, ..., `HP1`, `HPR1`, ..., `APToHPHeroR`) và `HeroInfo` cần `WarfareColorLv` / `WarfareLv`.
   - `Battle.Fight` trả `BaseGetGameResourceList` dưới dạng mảng các object nhóm theo loại: `[{"PlayerAttr": [{"ResourceTypeSub": 1101|1112|1117, "Num": <int>}]}]` để `BattleWinHintLayer:initRewardList` hiển thị phần thưởng Victory đúng.
