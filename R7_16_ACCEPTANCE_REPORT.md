# R7.16 — Tầm Ngọc, tài năng và chiến đấu

**APK standalone 834**, `5.0.4.98-r7.16`, package `com.cmn.inuyasha.revival`. SHA-256 `c2232db957f334ca3039a7ff6abba27e8089ccd8e0f626551bd3ed3fa6705e09`. Chứng thư ký trùng APK 832. Chín tệp backend nhúng khớp mã nguồn. [APK 834](analysis/vn/patched/com.cmn.inuyasha.revival_r7_16_834_standalone.apk)

## Tầm Ngọc

- Module **5200 Explore** mở từ nút Tầm Ngọc ở sảnh. `Practice.XunYuScene` dùng `Explore.GetInfo []`, `Explore.Explore []`, `Explore.OneKeyExplore []`, `Explore.BuyExploreNum []` và `Explore.DrawDailyReward [mốc]`. Số `1/41` là một lượt còn lại trên sức chứa 41. “Lượt tích lũy” ở đầu màn là số lượt đã sử dụng hôm đó, dùng cho rương 50/75/100.
- APK 832 giữ nguyên `RecoverTime` sau khi qua hạn và không hồi `RemainNum`. Trong khi đó Lua tự cộng một lượt khi hết đếm ngược. Trên Pixel, Lua hiện `1/41` với backend vẫn giữ `0/41`. Nút gọi đúng `Explore.Explore []`, handler đã đăng ký và nhánh hết lượt trả `Status=-1`. Mốc cố định cho thấy lượt thật vẫn dùng được, còn lượt do Lua tự cộng luôn thất bại. [Ảnh lỗi 832](analysis/qa_r7_16/pixel-832-server-error.png) · [Log Pixel 832](analysis/qa_r7_16/pixel-832-explore.log) · [Đối chứng HTTP 832](analysis/qa_r7_16/explore-rpc-832.log)
- Backend tính số lượt hồi từ timestamp Unix theo giây. Lượt tích lũy, rương và giới hạn mua đặt lại theo ngày VN UTC+7. Hồi **1 lượt/900 giây**, dừng khi đầy, bắt đầu đếm mới từ lần tiêu lượt dưới sức chứa. Trước hạn một giây, `GetInfo` trả 0. Đúng hạn trả 1 một lần và `Explore` dùng được lượt đó. Lua chỉ cập nhật số lượt từ phản hồi backend, kể cả khi đếm đến 0 hoặc người dùng chạm lại ở ranh giới. [Đối chứng HTTP 834 đã ký](analysis/qa_r7_16/explore-rpc-834.log) · [Regression Python](server/test_r716.py) · [Regression Lua](poc/test_r716_lua.py)
- Sức chứa gốc 25 cộng giá trị tích lũy `AttrtreeModel.xunyuAddNum`. Ngộ Đạo 160 có +16, nên sức chứa là 41. Khi vượt mốc Ngộ Đạo, chỉ cấp phần chênh lệch một lần. Lên cấp nhận thêm 5 lượt mỗi cấp, tối đa theo sức chứa. Lượt thừa có sẵn trong save cũ vẫn dùng được. Save cũ thiếu dấu ngày được gắn ngày khi đồng bộ lần đầu, giữ số lần mua, số đã dùng và rương đã nhận cho ngày chuyển đổi.
- Điều kiện và giá lấy từ VN. Nút Tầm Ngọc Ngay cần VIP3. Khi hết lượt, mua 10 lượt theo các mức 50, 100, 150 và 200 KC, mức 200 dùng tiếp nếu VIP còn quyền. Một hộp mua còn mở khi lượt đã hồi trả `-5103`, giữ nguyên KC và tự đồng bộ. Hết lượt trả `-5101`, đạt giới hạn mua `-5102`, thiếu KC `-1105`, thiếu tích lũy trong ngày `-5104`, nhận trùng `-7003`. Giao dịch ghi save trước khi công bố sổ giao dịch. Lỗi ghi giữ nguyên lượt, tài nguyên, tiến độ và quyền nhận rương.
- Pixel QA đã đối chứng lượt thật `1/41 → 0/41`, hồi về `1/41` khi đang mở màn, dùng được lượt vừa hồi và số tích lũy đạt 2. Xác nhận hộp mua cũ bị từ chối. Lần mua hợp lệ sau đó tăng lên `10/41` và ví giảm đúng 500 → 450 KC. [Trước khi hồi](analysis/qa_r7_16/pixel-833-last-turn-used.png) · [Sau khi hồi](analysis/qa_r7_16/pixel-833-recovered.png) · [Mua đúng giá](analysis/qa_r7_16/pixel-833-buy-success.png) · [RPC Pixel](analysis/qa_r7_16/pixel-833-explore.log)

## Tài năng đột phá tướng

VN có 57 dòng tăng chỉ số và tiên công trong `HeroStepRelation`. Nhóm 10 có bậc +0…+8, nhóm 13/15/255 có +0…+15. Tài năng là dữ liệu riêng gồm **1.699 quan hệ, 138 model tướng/NPC, 238 model tài năng được tham chiếu**. 1.324 dòng có hiệu ứng gameplay đã hoạt động trong 834. 375 dòng còn thiếu xử lý. Tính theo dòng cấu hình, một ID giống nhau xuất hiện ở nhiều bậc vẫn chỉ cộng một lần trên cùng tướng. [Bảng đầy đủ theo tướng và bậc](R7_16_TALENT_MATRIX.md)

| Bậc | Dòng hoạt động | Chưa áp dụng | Ví dụ hoặc mốc dữ liệu |
|---:|---:|---:|---|
| +0 | — | — | Nộ, chỉ số, đánh thường và Nộ Công từ HeroModel. |
| +1 | 0 | 43 | Nam chính mô tả đổi số mục tiêu Nộ Công, bảng chưa có ID kỹ năng thay thế. |
| +2 | 138 | 0 | Cộng Công cố định. |
| +3 | 138 | 0 | Nam chính +50 Nộ đầu trận. InuYasha cộng Bạo. |
| +4 | 135 | 3 | Nam chính cộng 500 HP đội. |
| +5 | 51 | 87 | InuYasha hồi 25 Nộ khi bạo kích. Nhóm buff phức hợp còn để lại. |
| +6 | 138 | 0 | InuYasha, Sesshomaru và nhiều tướng đạt 100 Nộ đầu trận. |
| +7 | 137 | 1 | HP cố định của nhiều tướng, Nam chính cộng HP đội. |
| +8 | 40 | 86 | Có các mốc chỉ số như Đỡ và các buff phức hợp chưa áp dụng. |
| +9 | 96 | 0 | Tỷ lệ Công, HP, Thủ theo phạm vi VN. |
| +10 | 26 | 70 | Sesshomaru hồi 50 Nộ khi Nộ Công bạo kích. |
| +11 | 102 | 0 | Cộng sát thương và miễn giảm sát thương phẳng. |
| +12 | 102 | 0 | HP cố định. |
| +13 | 102 | 0 | Chính Xác, Phá Kích hoặc các chỉ số tương ứng theo tướng. |
| +14 | 102 | 0 | Công cố định. |
| +15 | 17 | 85 | Có mốc miễn giảm ST theo %, nhiều buff đặc biệt còn để lại. |

Các chỉ số có tác động được tổng hợp lại từ bậc hiện tại mỗi lần đổi đội hoặc đọc save. Phạm vi bản thân và cả đội đọc từ `attrEffectRange` của VN. Tỷ lệ Công/HP/Thủ đi vào phần tỷ lệ của tướng trong Property như hệ Duyên Phận. FightInfo mang Nộ đầu trận, chỉ số cuối và buff tương thích với cả Lua và Python. Hai kiểu hồi Nộ sau bạo kích `10350000` và `10550000` chạy sau hành động, một lần khi có bạo kích, kể cả khi buff bị lặp trong payload. Không tìm thấy thay đổi NAID/RAID có giá trị khác 0 trong các tài năng được tham chiếu.

Đối chứng Lua 5.1 đọc bản ký. InuYasha đủ 100 Nộ đánh Nộ Công ngay ở hành động đầu. Sau bạo kích còn 25 Nộ, khi bỏ buff còn 0. Tăng Nộ đầu lên 150 cho cú đánh mạnh hơn và vẫn còn 25 sau cú đánh. Python giờ dùng Nộ trước khi đánh để tính sát thương, xóa Nộ khi dùng kỹ năng, và tính Nộ từ đánh thường trúng, chịu sát thương hoặc hạ mục tiêu theo Lua. Công thức giảm sát thương và tỷ lệ trị liệu dùng trường VN của FightInfo.

`AttackModel` có 441 kỹ năng, trong đó 130 gắn buff. Lua VN đã xử lý Im Lặng của Midoriko từ kỹ năng gốc. Kiểm thử chạy trận thật ở hai seed cố định, thấy mục tiêu đủ Nộ nhưng chuyển sang đánh thường khi trúng Im Lặng. Python vẫn thiếu hệ thống thời hạn, kháng/giải khống chế, sát thương theo thời gian, phản đòn, hồi sinh, liên kích và các trigger phức hợp. Chưa đưa các buff tài năng cần các hệ này vào FightInfo để tránh cùng trận cho kết quả khác giữa Lua và backend. Hệ số FAP riêng của tài năng và tác động theo trận doanh còn cần nguồn xác thực. [Hợp đồng FightInfo VN](analysis/vn/decompiled_src/CSCommon/ServerInterface.lua) · [Công thức Lua](analysis/vn/decompiled_src/CSCommon/FightExpression.lua) · [Luồng buff](analysis/vn/decompiled_src/CSCommon/FightBuffModel.lua)

## Độ chính xác quái theo chương

VN có 70 chương, 689 ải thường. Số đợt gốc đã phục hồi từ `fightRound` gồm 620 ải một đợt và 69 ải hai đợt. Có 280 ải có `pic` trùng HeroModel cho ảnh đại diện. Emulator dùng model đó làm boss mô phỏng ở đợt cuối, giữ kỹ năng NA/RA của model và hệ số Thường/Khó trong `BattleNodeModel`. Đây là căn cứ tốt cho số đợt, định danh model và tỷ lệ độ khó. Cấp, HP, Công, Thủ và đội hình gốc của phần lớn ải chưa có.

| Chương và ải đại diện | Dữ liệu VN | FightInfo 834 và sai lệch quan sát |
|---|---|---|
| Chương 1 · 1111 và 1115 | 1111 có đội hình hướng dẫn Lv1. Kịch bản 1115 đặt Yura HP 25.000 cùng năm địch phụ. | Trận hướng dẫn dựng riêng bằng BattleGuider. RPC 1111 có ba quái mô phỏng, tâm là Thôn Dân Nữ 168 HP / 37 Công / 8 Thủ. Hướng dẫn VN của 1111 có năm quái, gồm Thôn Dân Nữ 7.371 / 3.142 / 10 và Sói Đen 154 / 42 / 8. Khi đánh lại 1115, FightInfo thường dùng Yura mô phỏng Lv3, 1.007 / 224 / 48. |
| Chương 35 · 4511 và 4520 | 4511 một đợt và 4520 hai đợt. Ảnh 4520 là Chokyukai, hệ số Khó 1,3808. | 4520 dùng Chokyukai Lv96 mô phỏng ở đợt 2, 9.188 / 840 / 436 ở Dễ và 12.686 / 1.160 / 603 ở Khó. Đợt 1 dùng bộ quái chung. Hai đợt có cùng số ô địch. |
| Chương 70 · 8011 và 8020 | 8011 một đợt và 8020 hai đợt. Ảnh 8020 là Naraku, hệ số Khó 1,237. | 8020 dùng Naraku Lv166 mô phỏng ở đợt 2, 15.680 / 3.499 / 745 ở Dễ và 19.397 / 4.328 / 922 ở Khó. Đội hình phụ và đợt 1 lặp các model chung. Cổng chương Lv80 và cấp quái mô phỏng là hai giá trị riêng. |

Bảng `BattleNodeGuidenpcRelation` có 3.816 dòng, 34 dòng thực có model ở **1111, 1211, 1216, 1311, 1316**. Client dùng 15 kịch bản gốc theo `guideType` cho lượt đầu ở chương 1–7, gồm cả các kịch bản khai báo NPC trực tiếp như Yura ở 1115. Các cảnh dùng ô, chỉ số, tướng trợ diễn và đôi lúc đòn đánh viết sẵn. Giữ đường hướng dẫn VN cho lượt đầu. Với lần đánh lại và chương giữa/cuối, roster phổ thông lặp lại, level là công thức dựa trên số chương và chỉ số tăng tuyến tính từ HeroModel. Hệ số Khó theo từng ải làm chênh lệch Dễ/Khó có thể nhỏ dần. Chỉ số, số đợt và nhóm quái mô phỏng giữ như 832. FightInfo chiến dịch đã sửa tiên công hai phe bằng tổng FSP của các unit được gửi, thay giá trị cố định 2.000/1.200 làm lệch thứ tự đánh trên Lua. [Đối chiếu 832/834 theo wave](analysis/qa_r7_16/campaign-delta.log) · [Nguồn NPC hướng dẫn](analysis/vn/decompiled_src/Config/BattleNodeGuidenpcRelation.lua) · [Kịch bản Yura](analysis/vn/decompiled_src/ComBattle/Script/BattleScript1115.lua)

## Nghiệm thu và phần còn lại

**Test the Delta đạt 112/112 Python và 24/24 Lua.** Bộ kiểm có hồi lượt qua ranh giới và restart, giao dịch lỗi, chỉ số và Nộ tích lũy của tài năng, trùng buff, Im Lặng gốc và tiên công các chương đầu/giữa/cuối. [Log Python](analysis/qa_r7_16/test-the-delta-python.log) · [Log Lua](analysis/qa_r7_16/test-the-delta-lua.log)

Đã cài đè APK 834 vào package QA trên Pixel 3 XL và so save từng byte trước khi mở game. 834 đọc lại `10/41`. Tầm Ngọc Ngay dùng đúng 10 lượt, nâng tích lũy từ 2 lên 12, ví giữ 450 KC. Đã chơi xong 1-5 một lần bằng kịch bản VN và một lần dùng FightInfo thường. Cả hai `Battle.Fight` trả `Status=0`, kết quả một sao. Nam chính +3 và InuYasha +6 có 100 Nộ đầu trận trong save QA. [Tầm Ngọc Ngay](analysis/qa_r7_16/pixel-834-one-key.png) · [Trận đánh lại](analysis/qa_r7_16/pixel-834-fightinfo-result.png) · [Trace 834](analysis/qa_r7_16/pixel-834-delta.log)

Đã tạo `checkpoint-vn-r7.16` cho mã nguồn đã nghiệm thu. Package chính trên Pixel tiếp tục dùng APK 832. Bốn save S1 và chỉ mục tài khoản khớp từng byte với bản sao trước QA. APK 832, STABLE R6.2, checkpoint R7.14, package, khóa ký và các tỉ lệ/công thức nâng bậc được bảo toàn. [Đối chiếu save](analysis/qa_r7_16/owner-verification.log)

Round sau ưu tiên tìm payload VN có đội hình và chỉ số thật cho từng wave ngoài hướng dẫn, rồi khôi phục theo nhóm chương. Nhóm combat cần tiếp tục gồm thời hạn buff, khống chế trong Python, trigger phức hợp, phạm vi theo trận doanh và xác minh hệ số FAP tài năng.
