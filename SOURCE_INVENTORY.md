# SOURCE_INVENTORY.md — InuYasha: Seek Jade Revival (Round R0)

## 1. Phân biệt đúng tựa game
- **InuYasha: Seek Jade / InuYasha: Journey to Seek the Jade** (*犬夜叉-寻玉之旅* / *犬夜叉-尋玉之旅* / *อินุยาฉะ การเดินทางที่ค้นหาหยก*):
  - **Phát triển**: Chengdu Moqikaka Technology (成都摩奇卡卡科技).
  - **Phát hành**: Heitao Interactive (黑桃互动 / Spade Inc.), Infinite (TW), Xiaoyao (台港澳).
  - **Thể loại**: 2D chibi turn-based card RPG, sử dụng Cocos2d-x + Lua + Spine 2D.
  - **Trạng thái gốc**: Đã ngừng vận hành (TW đóng 31/08/2017); các domain `loginsvr.*.moqikaka.com` không còn phân giải DNS.
- **Không nhầm lẫn với**:
  - *InuYasha: Awakening* (*犬夜叉-觉醒*, ví dụ `com.indofun.android.inuyasha.en`): game hành động màn hình ngang ARPG (phát hành sau).
  - *InuYasha: Naraku's War* (*犬夜叉-奈落之战*): game 3D MMOARPG của Giant Network.

---

## 2. Các bản client gốc đã thu thập (bất biến trong `originals/`, gitignored)

Tất cả 4 bản gốc đều tải thành công dưới dạng XAPK đầy đủ (gồm APK + OBB) từ APKPure / CDN `data.winudf.com`, đã đặt quyền read-only (`chmod 444`) và không commit lên Git.

| Phiên bản | Package ID | Nguồn / URL | Dung lượng XAPK (bytes) | SHA256 XAPK | Kiến trúc (`native-code`) | Min / Target SDK | Trạng thái & Độ tin cậy |
| :--- | :--- | :--- | ---: | :--- | :--- | :--- | :--- |
| **EN 5.1.1** (`versionCode 511`) | `com.heitao.inuyasha.guge` | Page: `https://apkpure.net/inuyasha-seek-jade-official/com.heitao.inuyasha.guge` <br> Download: `https://d.apkpure.net/b/XAPK/com.heitao.inuyasha.guge?version=latest` -> `data.winudf.com` | 189,437,389 (~180.7 MB) | `6c020b7bcd108eea94d653060f102ea1283906b467e2ad81e7513566460c4b83` | `armeabi` | API 9 / API 23 | **Đã tải & xác minh chữ ký**: APK v1 sign `CN=xuang, OU=heitao, O=heitao, L=shanghai, ST=shanghai, C=CN`, cert SHA-1 `070989e9de9867fae95ce54387be566b46caeb7a` (khớp chữ ký gốc). |
| **ZH 5.0.0** (`versionCode 500`) | `com.heitao.inuyasha.guge.zh` | Page: `https://apkpure.net/inuyasha-seek-jade-official/com.heitao.inuyasha.guge.zh` <br> Download: `https://d.apkpure.net/b/XAPK/com.heitao.inuyasha.guge.zh?version=latest` -> `data.winudf.com` | 197,850,986 (~188.7 MB) | `4a140623bd1e8be055892ded3884c2bd37692e52085092976d8033f2c8e4bf35` | `armeabi` | API 9 / API 23 | **Đã tải & giải mã Lua thành công** (1,186 `.luac` -> `.lua`). |
| **TW 1.4** (`versionCode 14`) | `com.infinite.qyc4` | Page: `https://apkpure.net/inuyasha-seek-jade/com.infinite.qyc4` <br> Download: `https://d.apkpure.net/b/XAPK/com.infinite.qyc4?version=latest` -> `data.winudf.com` | 140,231,542 (~133.7 MB) | `0661cc985d0783b48e9ebaceae4305a2e033a4be57f41559c698ba58b1d1cc68` | `armeabi` | API 9 / API 23 | **Đã tải đầy đủ APK + OBB** (chứa thêm 237 `.luac` trong OBB; dùng khóa XXTEA obfuscated riêng trong `AppDelegate::getXXTEAKey`). |
| **TH 5.1.3.6** (`versionCode 5136`) | `com.heitao.thbqyc.gp` | Page: `https://apkpure.net/inuyasha-seek-jade/com.heitao.thbqyc.gp` <br> Download: `https://d.apkpure.net/b/XAPK/com.heitao.thbqyc.gp?version=latest` -> `data.winudf.com` | 247,109,547 (~235.7 MB) | `6aa45bde45b57ebb9a7752c0da4a599fdee4546cddb7ba8441818be120d94ef5` | `armeabi` | API 15 / API 23 | **Đã tải & giải mã Lua thành công** (1,227 `.luac` -> `.lua`, bản đầy đủ tài nguyên mới nhất ~235.7 MB). |

### Chi tiết thành phần APK & OBB bên trong các XAPK

| Bản | File nội bộ | Dung lượng (bytes) | SHA256 |
| :--- | :--- | ---: | :--- |
| EN 5.1.1 | `com.heitao.inuyasha.guge.apk` | 66,101,724 | `8eeae5eb12eecb08369473d604640dc041f7b99459022ce8292c6c698e075909` |
| EN 5.1.1 | `main.511.com.heitao.inuyasha.guge.obb` | 122,987,645 | `65dac429b0471f6a1b36a3c4f9aa785f212df3274135f8d9055e4f2f5a8a298c` |
| ZH 5.0.0 | `com.heitao.inuyasha.guge.zh.apk` | 85,988,673 | `68a24e438abdc3c483e37762d144631f54ea73f4f7388b32cdce60a948e2f492` |
| ZH 5.0.0 | `main.500.com.heitao.inuyasha.guge.zh.obb` | 111,494,735 | `4a351d2dada527f3c0fea865c2a557cb0fcf2550db0997ff84958f38e1d67189` |
| TW 1.4 | `com.infinite.qyc4.apk` | 47,185,414 | `73edddac84a9a41648bfc2b1782c02a78de5567252e73a80f824c4e32882629a` |
| TW 1.4 | `main.14.com.infinite.qyc4.obb` | 92,985,800 | `f0232f51b6980225544f307274b4dc09244a5b6ab792cbbf2253512fd3748ac7` |
| TH 5.1.3.6 | `com.heitao.thbqyc.gp.apk` | 86,592,183 | `014897348bb000470027351d095374fdbaeb863a7356897e70f64ed004b8884b` |
| TH 5.1.3.6 | `main.5136.com.heitao.thbqyc.gp.obb` | 160,153,228 | `d53bc2b96797a6dd0f6c2fe4edfbb8edf9f0580ef814155a85b79fef4f829899` |

---

## 3. Khảo sát server cũ, private server, source, asset dump & archive

| Nguồn khảo sát | Kết quả kiểm tra thực tế | Ghi chú / Độ tin cậy |
| :--- | :--- | :--- |
| `d.apkpure.com/b/APK/...` & `/b/XAPK/...` | HTTP 403 (`cf-mitigated: challenge`) | Không vượt qua Cloudflare challenge; dùng `d.apkpure.net` (HTTP 302 -> `data.winudf.com` HTTP 200) hợp lệ. |
| GitHub (`api.github.com/search/repositories`) | `total_count: 0` cho `inuyasha seek jade`, `犬夜叉 寻玉`, `com.heitao.inuyasha` | Không có source server hoặc emulator công khai trên GitHub. |
| Gitee / 52pojie / Tieba / Taobao / web search (EN, ZH giản thể, ZH phồn thể, TH) | Không có source/one-click server (`一键端`) công khai miễn phí. Một số tin rao "BT/满V" không kèm source và tiềm ẩn mã độc. | Không coi quảng cáo private server là bằng chứng có source. |
| Aptoide API (`ws2.aptoide.com`) | `0` kết quả cho các package Seek Jade (`guge`, `qyc4`, `thbqyc.gp`). Từ khóa chung trả về *Inuyasha Awakening* (`com.indofun.android.inuyasha.en`). | Đã loại trừ *Awakening*. |
| Internet Archive (`archive.org`) & Wayback CDX | Search trả về 0 item Seek Jade; Wayback CDX gặp `Internet Archive: Temporarily Offline` hoặc trả `[]`. | Không lấy được snapshot server từ Wayback tại thời điểm kiểm tra. |
| 3DMGame (`3dmgame.com`) | Trang tìm kiếm trả về `404`. | Link tải cũ tại web CN đã chết. |
| DNS các domain gốc (`loginsvr.enqyc.moqikaka.com`, `loginsvr.cnqyc.moqikaka.com`, `loginsvr.twqyc.moqikaka.com`, `loginsvr.tlqyc.moqikaka.com`) | Không phân giải được DNS (`dig +short` rỗng). Riêng `passport.moqikaka.com` còn trỏ tới `118.89.45.225` (nhưng không dùng cho luồng login Heitao/local). | Toàn bộ game server chính thức đã ngừng hoạt động. |
