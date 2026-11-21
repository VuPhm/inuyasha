# R7.18 — Mở rộng PvE và tiến trình trang bị

Baseline `checkpoint-vn-r7.17` (`b4f1385`), APK 835. Bản phát hành **836** mang versionName `5.0.4.98-r7.18`. Package `com.cmn.inuyasha.revival`. SHA-256 APK `ee70179f04bc46d4927782754de38507e2a75bf3b7729fde3a24ea61c1453252`. Chứng thư ký giữ nguyên. Mười tệp backend nhúng khớp mã nguồn. Hai tệp dữ liệu `bdd_data.json` và `game_data.json` khớp từng byte với APK 835. [APK 836](analysis/vn/patched/com.cmn.inuyasha.revival_r7_18_836_standalone.apk) · [Đối chiếu APK](analysis/qa_r7_18/apk-content-delta.log)

## Inu Kimi và Tứ Đấu Thần

| Tướng trong ảnh | Model | Mảnh để ghép | Rương cố định tương ứng |
|---|---:|---|---|
| Inu Kimi | `12015023` | `15010095`, cần 150 mảnh | `16010024` |
| Tứ Đấu Thần | `12015022` | `15010094`, cần 150 mảnh | `16010023` |

Nguồn xác minh trong VN là **Chiêu Mộ Thần Tướng D (banner 83)**. Quà Thần Tướng D `16060034` cho người chơi chọn một trong hai tướng. Quà Mảnh Thần D `16060033` thuộc các mốc điểm banner 83 và cho chọn mảnh. Cả bốn lựa chọn đã kiểm qua `GoodsUseForBoxChoice` trên APK 832 với rương cấp thử trong save cách ly. Hai rương cố định có đầu ra trong GoodsOutput, nguồn cấp các rương đó chưa được xác minh. Nút “Cách nhận” của trang tướng mở bộ xem nguồn rơi của mảnh đầu tiên. [TimedRecruitModel](analysis/vn/decompiled_src/Config/TimedRecruitModel.lua) · [Mốc thưởng banner](analysis/vn/decompiled_src/Config/TimedRecruitCreditrewardRelation.lua) · [GoodsOutput](analysis/vn/decompiled_src/Config/GoodsOutputRelation.lua) · [Nút Cách nhận](analysis/vn/decompiled_src/Hero/HeroInforLayer.lua)

APK 832 mặc định mở 81/82. Kiểm trực tiếp từ backend trong APK 832 xác nhận `TimedRecruitInfo.SelectBanner [83]` trả `Status=-1` trong cấu hình mặc định. Hiện chưa có nguồn chơi thường được xác minh cho hai tướng trên cấu hình này. R7.18 giữ nguyên lịch sự kiện, tỷ lệ và nguồn cấp tướng. [Đối chiếu APK 832](analysis/qa_r7_18/hero-acquisition-832.log)

## Mộ Thần Binh

**39/51 ải chơi được**, từ tầng nội bộ 11 đến 23, tổng 117 mức khó. R7.18 mở thêm 21 ải và 63 mức khó. Mỗi đội mô phỏng dùng đúng thủ lĩnh trong `BddNodeModel.pic` cùng hai model còn lại của tầng, kỹ năng VN của từng model và tỷ lệ HP/Công/Thủ theo cách đã nghiệm thu R7.15. Sai số so với lực chiến khuyến nghị dưới 25 do làm tròn. Các mức Dễ/Thường/Khó dùng đúng số sao 1/2/3 và Chiến Công 10/20/30 trong lát mới. Phần thưởng lần đầu ở Khó theo từng dòng `BddPointModel`. Giá trị lực chiến trong VN giảm nhẹ từ ải 30 sang 31, nên vẫn dùng đúng bảng gốc tại ranh giới này. [Bảng ải](analysis/vn/decompiled_src/Config/BddNodeModel.lua) · [Độ khó và thưởng](analysis/vn/decompiled_src/Config/BddPointModel.lua)

| Ải trên UI | Tầng nội bộ | Điều kiện thắng của VN | Lực chiến đề xuất Dễ/Thường/Khó ở đầu → cuối tầng |
|---|---:|---|---|
| 19–21 | 17 | Sống đủ 6 tướng | 600/710/850 nghìn → 940/1.090/1.310 nghìn |
| 22–24 | 18 | Trong tối đa 3 lượt | 1.020/1.170/1.410 nghìn → 1.500/1.730/2.080 nghìn |
| 25–27 | 19 | Còn trên 70% HP | 1.640/1.890/2.280 nghìn → 2.350/2.710/3.250 nghìn |
| 28–30 | 20 | Sống đủ 6 tướng | 2.520/2.890/3.470 nghìn → 3.360/3.840/4.600 nghìn |
| 31–33 | 21 | Trong tối đa 3 lượt | 3.290/3.750/4.480 nghìn → 4.070/4.610/5.490 nghìn |
| 34–36 | 22 | Còn trên 70% HP | 4.340/4.900/5.820 nghìn → 5.330/5.990/7.090 nghìn |
| 37–39 | 23 | Sống đủ 6 tướng | 5.630/6.310/7.450 nghìn → 6.350/7.110/8.380 nghìn |

- Save cũ đã nhận rương cuối tầng 16 được quyền chọn buff chuyển tầng một lần. Sao, kỷ lục, buff đã chọn, lịch sử rương và Chiến Công giữ nguyên khi mở save. Rương cuối lát mới lấy đúng tầng thưởng từ backend và giao diện reset đọc đúng số ải đã vượt ngay cả khi danh sách tầng tiếp theo trống.
- Kiểm một đường chơi đủ 39 ải bằng đội QA gồm sáu tướng Lv80 +15 có nguồn trong 81/82, trang bị Đỏ và bảo vật VN. Bài kiểm thử dùng Khó ở tầng 11–19, Dễ ở tầng 20–23 và chọn buff từ các lượt đề xuất hợp lệ. Kết quả 93 sao, nhận đủ 13 rương tầng, chặn nhận trùng, cửa hàng mở ở ngưỡng 90 sao, nhiệm vụ ngày ghi nhận, quét giữ kỷ lục và tải lại được. Các đội thử dùng các vật phẩm trong cấu hình; đây là save dựng cho QA. [Regression Python](server/test_r718.py)
- 12 ải cuối giữ khóa. Thử mở xa hơn cho thấy điều kiện thắng trong ba lượt của tầng 24 nhạy với đội hình và seed ở cùng mức đầu tư. Tầng 25 còn thiếu đường vượt ổn định trong mẫu kiểm. Các bảng VN hiện có chưa cung cấp đội hình/server payload gốc để căn lại phần mô phỏng. [Audit nguồn gốc](R7_14_SOURCE_AUDIT.md) · [Điều kiện VN](analysis/vn/decompiled_src/Config/BddClearanceModel.lua)

## Trang bị Kim và NPC chiến dịch

**0/20 món Kim có nguồn cấp gameplay được xác minh.** Quét 276 bảng Lua VN và lặp lại kiểm tra các pool backend. Các ID Kim chỉ xuất hiện trong `EquipModel` và `EquipStepRelation`, gồm bốn nhóm Naohi, Tensho, Spi, Crime/Yêu Thần và nhóm bốn món lẻ. Dữ liệu phụ bản, shop, rương, bảng triệu hồi, Mộ Thần Binh và sự kiện hiện nối chưa có đầu ra Kim. Nguồn hoạt động gần nhất là shop Mộ Thần Binh đổi Naohi Hồng +10 lên Đỏ. Bảng tham khảo TW có bước Đỏ → Kim yêu cầu sẵn một món Kim, chưa xác nhận được nguồn món đầu. Ca đã sở hữu Kim vẫn kiểm được gắn đúng ô, `Property`/`FightInfo`, Tiến Giai và hoàn tác bằng save QA. Cường Hóa Kim vẫn khóa theo mã `-1331` vì thiếu giá VN. [Kiểm kê R7.15](R7_15_ACCEPTANCE_REPORT.md) · [Quét nguồn R7.18](analysis/qa_r7_18/vn-gold-source-audit.log)

Đối chiếu nguồn NPC trong bảng hướng dẫn, phụ bản bang, đội phối hợp và kịch bản cho thấy mỗi nhóm có đường truy cập riêng. Dữ liệu mới xem thuộc các mode khác, chưa có quan hệ có căn cứ với wave chiến dịch thường. Giữ mốc 15 ải có NPC kịch bản gốc thuộc chương 1–7. Sáu mẫu chương 1, 35 và 70 trên APK 835/836 cho cùng NPC, wave, kỹ năng, FSP và chỉ số. Chưa có nguồn xác minh để thay đội mô phỏng chiến dịch. [Danh sách kịch bản gốc](R7_17_ACCEPTANCE_REPORT.md) · [Đối chiếu FightInfo](analysis/qa_r7_18/campaign-source-audit.log)

## Chiến đấu

- **Kanna:** Kỹ năng `1002025` dùng buff `10610000` để xóa hiệu ứng có cờ `isDebuff` sau hồi máu. Thử nghiệm xóa giảm Chính Xác và giữ Choáng. Kỹ năng cùng buff cũng dùng cơ chế này.
- **Manten:** Nộ `1002046` dùng buff `10720400`, trừ 10% HP tối đa một lần mỗi lần tung Nộ, giữ ít nhất 1 HP và tăng 30% sát thương trong đòn. Đối chiếu nguyên bản và phiên bản bỏ bonus trong ca chạy Lua.
- **Tài năng Nộ:** `10530600` có xác suất VN 45%, tăng 25 Nộ cho một đồng đội còn sống có Nộ thấp nhất sau đánh thường, loại người đánh khỏi danh sách. Hosenki, Tsubaki, Abi và Byakuya chia sẻ hiệu ứng này. Shippo/Rin dùng `10530400` với 30%. Simulator phân xử theo ô khi nhiều đồng đội hòa Nộ. Chuỗi số ngẫu nhiên có thể khác Lua.

Tổng **1.585/1.699** dòng tài năng hỗ trợ đầy đủ theo cấu hình, **15** dòng một phần và **99** dòng chưa hỗ trợ. Sáu dòng mới thuộc cơ chế Nộ. Hai hiệu ứng Kanna và Manten đi kèm kỹ năng, tính riêng. [Đối chiếu hiệu ứng](analysis/qa_r7_18/targeted-combat-coverage.log) · [Ca thử Lua](poc/test_r718_lua.py)

## Nghiệm thu

- **Test the Delta đạt 126/126 Python và 31/31 Lua**. Kiểm điều kiện thắng/thua, trạng thái và thưởng trước/sau, trùng phiên, buff, shop, nhiệm vụ, quét, phần thưởng cuối và tải lại. [Log Python](analysis/qa_r7_18/test-the-delta-python.log) · [Log Lua](analysis/qa_r7_18/test-the-delta-lua.log)
- **Pixel 3 XL, APK 832 → 836 trong package QA.** Save đã vượt 18 ải khớp từng byte ngay sau cài. APK mới đọc lại 54 sao, 1.515 Chiến Công, chọn được buff chuyển tầng và mở ải 19. Ải 19 Khó thắng ba sao và nhận 30 Chiến Công cùng 50 KC lần đầu. Ải 20 Thường thắng hai sao và nhận 20 Chiến Công. [Đối chiếu nâng cấp](analysis/qa_r7_18/pixel-832-to-836.log) · [Ải 19](analysis/qa_r7_18/pixel-836-stage19-result.png) · [Ải 20](analysis/qa_r7_18/pixel-836-stage20-result.png)
- Các trận tiếp theo chạy qua RPC thật của APK 836 trên cùng Pixel. Nhận rương tầng 23 từ giao diện được 150 Chiến Công và một túi, màn kết thúc hiện đúng ải 39. Sau khởi động lại, save giữ **39 ải, 92 sao, 3.070 Chiến Công**, chặn nhận rương trùng. Sao, kỷ lục từng ải và lịch sử nhận thưởng đầu của 18 ải cũ vẫn có đủ. [Log trận và tải lại](analysis/qa_r7_18/pixel-continuation.log) · [Rương cuối](analysis/qa_r7_18/pixel-836-final-chest.png) · [Màn hoàn tất](analysis/qa_r7_18/pixel-836-reset-after-39.png)
- Package chính tiếp tục dùng APK 832. Bốn save S1, chỉ mục, STABLE R6.2, checkpoint trước, package và signing key được bảo toàn. Checkpoint bản thử đạt là `checkpoint-vn-r7.18`. [Đối chiếu save chính](analysis/qa_r7_18/owner-verification.log)
