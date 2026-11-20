# R7.14 — Đối chiếu nguồn Mộ Thần Binh

## Dữ liệu VN đã xác nhận

- `ModuleSub 2507` mở ở Lv26. Quét là module 2508 với cấu hình mở Lv45, hoặc VIP9 từ Lv28. [ModuleSubModel](analysis/vn/decompiled_src/Config/ModuleSubModel.lua#L928)
- Đối chiếu khóa thành công cho **51 ải ở 17 tầng**, mỗi ải có đúng ba độ khó, tổng **153 dòng**. VN có sáu điều kiện thắng, thuộc ba nhóm còn đủ số tướng sống, thắng trong giới hạn lượt và còn đủ tỷ lệ HP. [Ải](analysis/vn/decompiled_src/Config/BddNodeModel.lua) · [Độ khó và thưởng](analysis/vn/decompiled_src/Config/BddPointModel.lua) · [Điều kiện thắng](analysis/vn/decompiled_src/Config/BddClearanceModel.lua)
- `BddInfo.Info [1,1,1,1]` phải trả `Info`, `NodeInfo`, `BuffInfo` và `BuyShopInfo`. `BddInfo.GetFightInfo [nodeId,difficulty]` cung cấp `FightInfo` kết nối thẳng với engine chiến đấu. `BddInfo.Fight [nodeId,difficulty,result,verification,optional]` gọi từ màn kết toán và đọc `Value.IsSuccess`. [Màn chính](analysis/vn/decompiled_src/NewXZYY/XzyyMainScene.lua#L749) · [Bắt đầu chiến đấu](analysis/vn/decompiled_src/NewXZYY/XzyyPrepareFightLayer.lua#L147) · [Kết toán](analysis/vn/decompiled_src/Adventure/BattleSettleLayer.lua#L435)
- Công cụ quét tìm 12 phương thức client VN gọi trực tiếp. Ba phương thức trên đi cùng `GetBuffs`, `SelectBuff`, `RewardBox`, `OneKeyThreeStar`, `Reset`, `Ranking`, `EquipShopInfo`, `EquipShopExchange` và `BuyShop`. APK 825 chưa dispatch nhóm này.

## Điều kiện để nghiệm thu lát chiến đấu

Bảng VN có chân dung, điều kiện thắng, lực chiến khuyến nghị và thưởng. Nguồn kiểm tra chưa có đội hình NPC hoặc chỉ số chiến đấu của chúng cho từng cặp ải/độ khó. Các bảng Bdd đã giải mã từ EN, TH và ZH cũng chỉ có các nhóm cấu hình tương ứng. Chân dung và lực chiến khuyến nghị không đủ để dựng chính xác `FightInfo`. Cần đối chiếu payload hoặc dữ liệu NPC đáng tin cậy trước khi bật trận thật.

Lát đầu nghiệm thu với danh sách và mở khóa Lv26, trận thật, kết toán có điều kiện, số sao và reload cùng một save. Kết toán phải đối chiếu với trận vừa được tạo để chặn trả thưởng trùng. Dùng cấu hình VN cho thưởng lần đầu và Chiến Công. Luồng buff, quét, shop, DailyTask #21 và sự kiện 4420 tiếp tục sau khi qua lát chiến đấu. [Roadmap](PROJECT_ROADMAP.md#iv-lộ-trình-các-round-tiếp-theo-r77)

## Trạng thái APK 827

Sáu ải đầu đã dùng đội hình mô phỏng có ghi nhãn và bám lực chiến khuyến nghị VN. Các bảng đội hình/chỉ số NPC gốc vẫn cần cho đối chiếu. Danh mục hiển thị 51 ải, 45 ải còn lại giữ khóa. [Nghiệm thu R7.14](R7_14_ACCEPTANCE_REPORT.md)
