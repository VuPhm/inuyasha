# R7.17 — Hiệu ứng chiến đấu và dữ liệu quái VN

APK standalone **835** (`5.0.4.98-r7.17`) dùng package `com.cmn.inuyasha.revival` và chứng thư ký của APK 834. SHA-256 APK `bea4ee4a18dd042d357899623017144f9225d7ee8ea7a09532bf3d2187c4a08f`. Chứng thư SHA-256 `ef0b2780b540114f011897e8002a464f945541e19cc40f3f0ffa07f8b725672c`. Cả mười tệp backend nhúng khớp mã nguồn. Tài nguyên Lua VN trong hai APK khớp từng byte. [Tải APK 835](analysis/vn/patched/com.cmn.inuyasha.revival_r7_17_835_standalone.apk)

## Tài năng

**1.579/1.699 dòng được hỗ trợ đầy đủ, 15 dòng hỗ trợ một phần, 105 dòng còn thiếu.** Đây là số quan hệ tướng–bậc–tài năng trong cấu hình, tính cả các dòng dùng chung ID. R7.16 đã hỗ trợ 1.324 dòng. Trong 375 dòng còn lại, R7.17 hoàn thiện 255. Bảng dưới phân loại theo cơ chế chính của mỗi dòng chưa xử lý ở R7.16. Kết quả dựa trên dữ liệu và các đường xử lý đã triển khai, với các bài kiểm thử đại diện. [Ma trận R7.16](R7_16_TALENT_MATRIX.md) · [Thống kê R7.17](analysis/qa_r7_17/talent-coverage.log)

| Nhóm trong 375 dòng | Tổng | Đầy đủ | Một phần | Còn thiếu |
|---|---:|---:|---:|---:|
| Cộng/trừ trực tiếp từ một buff, gồm chỉ số, Nộ và miễn hiệu ứng (`typeEnum=2`) | 121 | 112 | 0 | 9 |
| Gói bốn quyền miễn hiệu ứng (`typeEnum=2`) | 15 | 0 | 15 | 0 |
| Gắn buff con, gồm khống chế và buff chỉ số có thời hạn (`typeEnum=6`) | 81 | 65 | 0 | 16 |
| So sánh HP hiện tại giữa hai tướng (`typeEnum=4`) | 54 | 54 | 0 | 0 |
| Điều kiện trạng thái bản thân (`typeEnum=9`) | 29 | 19 | 0 | 10 |
| Điều kiện trạng thái đối phương (`typeEnum=3`) | 19 | 5 | 0 | 14 |
| Cơ chế đặc biệt (`typeEnum=5`) | 24 | 0 | 0 | 24 |
| Biến đổi kỹ năng hoặc dạng tướng (`typeEnum=7`) | 17 | 0 | 0 | 17 |
| Hiệu ứng theo lượng đã mất (`typeEnum=0`) | 2 | 0 | 0 | 2 |
| Nội tại giới hạn theo trận doanh | 3 | 0 | 0 | 3 |
| Chỉ có mô tả trong bảng tài năng | 10 | 0 | 0 | 10 |
| **Tổng** | **375** | **255** | **15** | **105** |

- Python xử lý buff hợp lệ của tướng và NPC qua cùng một đường. Buff lấy từ `AttackModel` và `FightInfo.BuffList`. Mã phát hành chọn ID theo `BuffModel` và chỉ gắn một tầng buff con đã xác minh. Áp dụng đúng các pha trước khi tính, sau từng đòn hoặc sau hành động theo trường kích hoạt. Buff hết theo lượt người đặt, có giới hạn số lần kích hoạt, thời lượng và số lớp theo cấu hình, đồng thời làm mới lớp khi chạm giới hạn. Xóa trạng thái ở mục tiêu đã chết và khi kết thúc đợt. HP và Nộ của đội người chơi tiếp tục chuyển sang đợt sau theo luồng hiện có. [Mã hiệu ứng](server/combat_effects.py) · [Lua FightBuffModel](analysis/vn/decompiled_src/CSCommon/FightBuffModel.lua)
- Choáng/bất động có thể làm mất hành động. Im Lặng chuyển lượt Nộ thành đánh thường. Khóa hồi Nộ và khóa hồi máu áp dụng theo loại hiệu ứng. Có miễn khống chế riêng theo trạng thái, miễn giảm Nộ và kháng khống chế theo `refValue` của dữ liệu VN. Bộ mô phỏng dùng `TeamData.Fsp`, dùng FAP khi hòa và giữ thứ tự ô NPC PvE theo Lua. Chuỗi số ngẫu nhiên của Python và Lua có thể khác nhau với cùng seed.
- Lua trong APK ký xác nhận Miroku đặt Choáng làm mục tiêu bỏ lượt, miễn Choáng giữ lượt đánh và buff hết theo lượt người đặt. InuYasha Phong Thương tăng 4.000 Bạo Kích trong hai lượt của người đặt. Buff Công `20171000 → 14081000` thêm 10% mỗi lớp, tối đa ba, theo trigger đánh của `BuffModel`. Hàng giảm Nộ `10450836` của Kagome dùng mức 25 điểm như giá trị `-2500` trong cấu hình. Tooltip ghi 50 điểm. Lua cho thấy miễn giảm Nộ giữ đủ Nộ để dùng kỹ năng tiếp theo. [Ca thử Lua](poc/test_r717_lua.py) · [Ca thử Python](server/test_r717.py)

**Còn 120 dòng cần xử lý đủ.** Gói 15 dòng đã có miễn choáng, miễn im lặng và miễn giảm Nộ. Phần miễn phản sát thương (`707`) của gói còn thiếu. Các dòng khác cần xác minh sát thương/hồi phục theo lượt, khiên, phản đòn, hồi sinh, biến hình, triệu hồi, công thức phụ thuộc độc và kịch bản nhiều tầng buff, sửa kỹ năng hoặc phạm vi trận doanh. Một số buff giảm hồi máu ghi kích hoạt lúc được trị liệu trong mô tả nhưng dùng trigger 4 trong bảng. Lua dùng trigger 8 cho mục tiêu được trị liệu. Các dòng đó giữ ở trạng thái chờ đối chứng. Những mô tả thiếu cấu hình chưa được gán tỷ lệ hay hiệu ứng mới.

## NPC và wave chiến dịch

`BattleNodeModel` VN cung cấp **689 ải thường**, gồm 620 ải một wave và 69 ải hai wave. Có 280 ảnh đại diện khớp một HeroModel. `BattleNodeGuidenpcRelation` có 34 bản ghi có model thật trong 3.816 dòng, ở **1111, 1211, 1216, 1311, 1316**. Client VN dùng NPC gốc trong 15 ải có kịch bản gắn `guideType` khi mở lần đầu (`Flag=1`). Kịch bản chứa đội hình ban đầu hoặc NPC sinh theo hành động, với một số đòn và kết quả được điều khiển riêng. [Luồng Adventure](analysis/vn/decompiled_src/Adventure/BattleLayer.lua) · [Bảng ải](analysis/vn/decompiled_src/Config/BattleNodeModel.lua) · [Bảng NPC hướng dẫn](analysis/vn/decompiled_src/Config/BattleNodeGuidenpcRelation.lua)

| Chương trên UI | Ải có NPC từ kịch bản VN | Số wave của ải trong `BattleNodeModel` |
|---|---|---|
| 1 | `1111`, `1113`, `1115` | 1 wave mỗi ải |
| 2 | `1211`, `1216`, `1217` | `1217` có 2 wave, các ải còn lại 1 |
| 3 | `1311`, `1316`, `1318` | `1318` có 2 wave, các ải còn lại 1 |
| 4 | `1414`, `1419` | `1419` có 2 wave, `1414` có 1 |
| 5 | `1520` | 2 wave |
| 6 | `1616`, `1620` | `1616` có 1 wave, `1620` có 2 |
| 7 | `1716` | 1 wave |

Số wave trong bảng là cấu hình ải thường. Danh sách NPC gốc xác minh được thuộc lượt có kịch bản. R7.17 tìm được **0 đội hình wave gốc đầy đủ cho đường đánh thường/đánh lại**. XAPK VN chứa 18 tệp `BattleScript`, trong đó 15 tệp có đường vào từ `guideType`. OBB chứa tài nguyên hình, âm thanh, video và manifest. `BattleVerify.lua` có đường đọc dữ liệu kiểm thử từ file và dựng đội hình thử. Sau lần đầu ở ải hướng dẫn, dữ liệu đầy đủ phải đến từ `Battle.GetFightInfo`. Tài nguyên kiểm tra trong round này chưa có bản ghi RPC VN gốc cho các wave đánh thường. [Kịch bản VN](analysis/vn/decompiled_src/ComBattle/Script) · [BattleVerify](analysis/vn/decompiled_src/ComBattle/BattleVerify.lua)

| Chương | Dữ liệu gốc có thể dùng | FightInfo thường còn mô phỏng |
|---|---|---|
| 1 (`11`) | `1111` mở với ba dân làng bị điều khiển ở ô 9, 10 và 12, Lv1 với 7.371 HP / 3.142 Công / 10 Thủ / 50 Nộ mỗi tướng. `1115` đặt Yura ở ô 8 với 25.000 HP, 50 Nộ và kỹ năng `1001042/1002042`, cùng năm NPC phụ. | `1111` dùng dân làng 168 / 37 / 8 cùng hai Sói Đen. Đánh lại `1115` dùng Yura Lv3, 1.007 / 224 / 48 và ba Sói Đen. |
| 35 (`45`) | `4511` có 1 wave, `4520` có 2 wave. Ảnh `4520` là Chokyukai. Hệ số Khó 1,3808. | `4520` có bốn ô địch mỗi wave. Khó wave 1 dùng dân làng 2.435 / 543 / 116 ở giữa. Wave 2 thay bằng Chokyukai Lv96, 12.686 / 1.160 / 603, kỹ năng VN `1001069/1002069`. |
| 70 (`80`) | `8011` có 1 wave, `8020` có 2 wave. Ảnh `8020` là Naraku. Hệ số Khó 1,237. | `8020` có bốn ô địch mỗi wave. Khó wave 1 dùng dân làng 3.637 / 811 / 173 ở giữa. Wave 2 thay bằng Naraku Lv166, 19.397 / 4.328 / 922, kỹ năng VN `1001024/1002024`. |

Đối chiếu `Battle.GetFightInfo` 834 và 835 cho sáu ải mẫu ở mọi độ khó có sẵn trong mẫu cho thấy đội hình, chỉ số và FSP giữ nguyên. NPC mẫu xuất phát với 50 Nộ trong FightInfo thường. Lv, HP, Công, Thủ, vị trí và lựa chọn đội hình dự bị vẫn lấy từ bộ mô phỏng hiện tại trên cả 689 ải đánh thường. Dáng quái lặp lại và chênh lệch sức mạnh giữa các wave phụ thuộc đội hình chung, model đợt cuối và hệ số từng ải. R7.17 giữ công thức hiện có và sửa xử lý thứ tự hành động/hiệu ứng trong Python. [Đối chiếu RPC theo wave](analysis/qa_r7_17/campaign-delta.log)

## Nghiệm thu

- **Test the Delta đạt 120/120 Python và 27/27 Lua.** Tám ca Python mới và ba ca Lua mới kiểm trước/sau buff, kháng và miễn, mất lượt, Nộ và kỹ năng Nộ, cộng dồn, điều kiện HP, tiên công NPC, kết thúc đợt và thắng/thua. Bộ hồi quy giữ các ca R7.16, trận thua giữ tài nguyên, kiểm kết quả thắng/thua mâu thuẫn và chống nhận trùng thưởng. [Log Python](analysis/qa_r7_17/test-the-delta-python.log) · [Log Lua](analysis/qa_r7_17/test-the-delta-lua.log)
- **Pixel 3 XL, nâng cấp đè 834 → 835 ở package QA.** Save cách ly khớp từng byte ngay sau cài. HTTP `Battle.GetFightInfo [11,1115,1]` trả `Status=0` trên hai bản. Miroku +6 giữ 100 Nộ đầu trận và 835 thêm `BuffList=20210401`. Sau khi chơi lại 1-5 trên giao diện, `Battle.Fight` trả `Status=0`. Giao diện và save xác nhận thắng một sao, +55 vàng, +700 EXP, −5 thể lực, `FightCount` 0 → 1. [Ảnh trong trận](analysis/qa_r7_17/pixel-835-fight.png) · [Ảnh kết quả](analysis/qa_r7_17/pixel-835-result.png) · [RPC và save](analysis/qa_r7_17/pixel-835-battle.log) · [So sánh FightInfo](analysis/qa_r7_17/pixel-fightinfo-delta.log)
- Checkpoint **`checkpoint-vn-r7.17`** ghi lại mã nguồn đã kiểm thử. Bản S1 chính trên Pixel tiếp tục chạy APK 832. Bốn save và chỉ mục S1 khớp từng byte trước và sau khi mở lại bản 832. STABLE R6.2, checkpoint R7.16, APK 832/834, package, khóa ký và bảng cân bằng đã xác minh được bảo toàn. [Đối chiếu save chính](analysis/qa_r7_17/owner-verification.log)

Round sau ưu tiên đối chứng nhóm kháng/miễn và cơ chế đặc biệt còn thiếu bằng ca Lua riêng, đồng thời tìm nguồn VN có roster và chỉ số cho từng wave đánh thường. Dùng roster gốc theo nhóm chương khi đủ dữ liệu.
