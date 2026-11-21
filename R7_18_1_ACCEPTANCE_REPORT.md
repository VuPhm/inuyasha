# R7.18.1 — Khôi phục Thần Tướng D (Banner 83: Inu Kimi & Tứ Đấu Thần)

Baseline `checkpoint-vn-r7.18` (`11c6357`), APK 836. Bản phát hành **837** mang versionName `5.0.4.98-r7.18.1`. Package `com.cmn.inuyasha.revival`. SHA-256 APK `dd70fdd8634d3424b5c98c76d31ab56b27edfcc8100d7bc30c7b85aafe3d0832`. Chứng thư ký (`~/.inuyasha_release/inuyasha_revival_release.jks`), STABLE R6.2 và 4 save S1 giữ nguyên. [APK 837](analysis/vn/patched/com.cmn.inuyasha.revival_r7_18_1_837_standalone.apk)

## 1. Cấu hình Banner 83 & Tài nguyên VN/đa vùng

- **Banner 83 (`TimedRecruitModel[83]`):** `goldHeroModelID = 16060034` (Quà Thần Tướng D), `btnPic = sy_154`, `recruitPrice = 280` KC, `needCredit = 60`, `perRecruitGetCredit = 10`, `outputLowHeroR = 9000`, `outputHighHeroIntervalNum = 9`, `receiveBlessNum = 500`, `firstBless = 320`, `firstBlessR = 0.7`, `blessOddsR = 0.00014`, `limitNum = 500`.
- **Mốc điểm Banner 83 (`TimedRecruitCreditrewardRelation` ID 13–18):** các mốc `60 / 200 / 300 / 400 / 500 / 600` điểm cấp tổng **50 rương `16060033`** (Quà Mảnh Thần D), kèm Đá Đột Phá, Đá Tinh Luyện và Vàng ở mốc 60.
- **Rương & Mảnh:**
  - `16060034` (*Quà Thần Tướng D*): chọn `12015022` (Tứ Đấu Thần) hoặc `12015023` (Inu Kimi).
  - `16060033` (*Quà Mảnh Thần D*): chọn `15010094` (Mảnh Tứ Đấu Thần) hoặc `15010095` (Mảnh Inu Kimi).
  - Mỗi tướng ghép bằng **150 mảnh** (`GoodsModel.maxNum = 150`).
- **Tài nguyên bổ sung từ bản gốc ZH 5.0.0 / TH 5.1.3.6** (9 tệp còn thiếu trong VN APK/OBB, khớp SHA-256 giữa ZH và TH, lưu tại `android/assets_b83/`):
  - `res/ui/xshd_114.png`, `res/ui/xshd_115.png` (ảnh banner Inu Kimi & Tứ Đấu Thần).
  - `res/ui/xy_s_5022.png`, `res/ui/xy_s_5023.png` (icon nhỏ của hai tướng).
  - `src/ComBattle/Config/hero_sidoushen_pugong.luac`, `hero_sidoushen_nuji.luac` và `res/music/effect_sidoushen_pugong1.mp3`, `effect_sidoushen_pugong2.mp3`, `effect_sidoushen_nuji.mp3`.
  - Toàn bộ Spine (`hero_sidoushen.*`, `hero_lingyuexianji.*`, `effect_sidoushen_nuji.*`), icon rương (`dj_60033.png`, `dj_60034.png`), icon nút trang chủ (`sy_154.png`) và âm thanh `hc_*/hs_*` đã có sẵn trong VN APK/OBB.

## 2. Kích hoạt Banner 83 & Cô lập 81 / 82 / 83

- `server/event_runtime.py`: bật `timed_recruit:83` trong `tr_complete_assets`, `DEFAULT_CONCURRENT_EVENTS`, `rotation_pool`, và thêm migration một lần `r7181_migrated` trong `EventRuntime.ensure_state` để các save cũ (bao gồm 832 và 836) tự động kích hoạt Banner 83 ngay mà không ghi đè tiến trình `81/82`.
- `poc/build_standalone_apk.py`: cập nhật nhãn tab `Thần Tướng D (83)` trên `LimittedTimedRecruitLayer.luac` song song với `Sessho (81)` và `InuTaishou (82)`; `TimedRecruitChoiceBoxLayer.luac` giữ guard chống gửi trùng `mDrawingHero` và truyền `{heroID, mBannerId, mEventInstanceId}` khi nhận tướng UR.
- Pool, tỷ lệ, đơn giá (`280` KC) và tiến trình của Banner `81` và `82` được giữ nguyên hoàn toàn.

## 3. Kiểm tra hai nhân vật (Tứ Đấu Thần `12015022` & Inu Kimi `12015023`)

- **Phẩm chất & ID:** giữ nguyên `quality = 18` (UR), `raceID = 0`, `specialType = 0`, `stepUpClassID = 15` (Đột Phá +0 → +15), `rebornClassID = 0`.
- **Kỹ năng:**
  - `12015022` (Tứ Đấu Thần): Công thường `1001200` (125% đơn), Nộ `1002200` / `1003010` (3 mục tiêu ngẫu nhiên, 180%/215% + 25%/35% Choáng `20210607`/`20210847`).
  - `12015023` (Inu Kimi): Công thường `1001201` (hồi HP đồng đội mất nhiều máu nhất), Nộ `1002201` / `1003011` (hồi HP toàn đội + 25%/35% tăng 25 Nộ `10460608`/`10460848`).
- **Tài năng (+2..+15):**
  - Toàn bộ tài năng chỉ số/Nộ của cả hai tướng đều áp dụng qua `Property`/`Slot`; các hiệu ứng chiến đấu `+5`/`+10`/`+15` (`10180600`, `11111000`, `10240600`, `10141000`) được hỗ trợ trong `combat_effects.py`. Riêng `+8` của Tứ Đấu Thần (`20300807` -> `12430750` giảm 75% trị liệu mục tiêu 2 lượt) được client Lua xử lý trong trận và chưa nằm trong tập buff đơn giản của `combat_sim.py`.
- **Duyên Phận (`PrModel`):** `12015022` (556–559, 571–572) và `12015023` (552–555, 569–570) hoạt động qua `_active_bonds` (đã xác minh Duyên Phận `Linh Vu` `555`/`559` khi ra trận cùng nhau và Kagome `12011003`).

## 4. Nghiệm thu

- **Python Test the Delta (`server/test_emulator.py` + `test_r713..test_r7181`):** **132/132 PASS**, trong đó `server/test_r7181.py` kiểm tra đủ:
  - Kích hoạt mặc định Banner 83 và nâng cấp giả lập từ save 832 giữ nguyên tiến trình 81/82.
  - Nhận Inu Kimi, nhận Tứ Đấu Thần và nhận đủ cả hai trên cùng một tài khoản S1.
  - Mở rương `16060034` và `16060033`, ghép đủ **150 mảnh** (`<150` bị từ chối).
  - Túi đầy (`-2005`) không mất KC/rương/mảnh, rương chưa nhận, lỗi `DrawGoldHero` (`-3123`, `-3106`, `-3116`), không trừ KC trùng khi đang chờ chọn UR, chống nhận trùng mốc điểm.
  - Đột Phá `HeroStepUp` (+0 → +2), kích hoạt Duyên Phận, chiến đấu `Battle.GetFightInfo`/`Battle.Fight` + `simulate_fight_info`, và save/reload.
  - Chuyển đổi qua lại giữa Banner `81 / 82 / 83` bảo toàn pity, điểm tích lũy và mốc thưởng.
- **Pixel 3 XL nâng cấp trực tiếp 832 → 837 (trong package QA `com.cmn.inuyasha.revival.qa`):**
  - Nạp bản sao lưu 4 save S1 từ bản chính 832 vào QA 832, ghi nhận SHA-256 trước cài đặt, sau đó `adb install -r` lên 837.
  - Toàn bộ 6 tệp `.json` (`accounts_index.json`, `normal_profile.json`, `s1_acct_2..4.json`, `debug_profile.json`) **khớp từng byte (SHA-256 100%)** ngay sau khi cài 837. [Log trước](analysis/qa_r7_18_1/pixel-832-before.log) · [Log sau cài](analysis/qa_r7_18_1/pixel-837-after-install.log)
  - Chạy RPC thật trên backend nhúng của APK 837: `OlinaHugh Lv 28`, `TimedActivityOpenInfo[9300] = [81, 82, 83]`, `SelectBanner 81/82/83` đều `Status=0`, Banner 81 giữ `910` điểm / `9` pity, Banner 82 giữ `610` điểm / `4` pity, rút thử Banner 83 lên `10` điểm mà không ảnh hưởng 81/82. [Log RPC 837](analysis/qa_r7_18_1/pixel-837-rpc-verify.log)
  - Package chính `com.cmn.inuyasha.revival` trên Pixel 3 XL vẫn giữ nguyên APK 832 và toàn bộ 4 save S1 chưa bị chạm vào.
