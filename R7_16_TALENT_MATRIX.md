# R7.16 — Bảng tài năng VN theo tướng và bậc

Bảng lấy từ HeroTalRelation, TalModel và BuffModel trong client VN. Mốc +0 dùng chỉ số, Nộ và kỹ năng cơ bản của HeroModel. Các bậc có dữ liệu nhưng thiếu dòng tài năng riêng chỉ tăng chỉ số theo HeroStepRelation. Mô tả tài năng và phạm vi cấu hình được ghi riêng khi hai nguồn khác nhau.

Tình trạng áp dụng dưới đây nói về hiệu ứng gameplay. Hệ số FAP riêng của tài năng chưa áp dụng. Tài năng đã mở được tính theo ID và phạm vi để dòng lặp không cộng thêm lần nữa.

## 1NamChính (`12010001`)

Bậc tối đa từ HeroStepRelation +15. Bậc tài năng cao nhất trong bảng +10.

| Bậc | TAL | Hiệu ứng VN | Dữ liệu áp dụng | R7.16 |
|---:|---:|---|---|---|
| +1 | `10320000` | Mục tiêu Kỹ Năng Nộ từ 1 thành 3 ngẫu nhiên | Chỉ có mô tả | Chưa áp dụng |
| +2 | `10330000` | Công +100 | Bản thân · Công +100 | Hoạt động |
| +3 | `10010000` | Mới bắt đầu tăng 50đ Nộ, lượt đầu có thể Nộ Công | Bản thân · Nộ +50 | Hoạt động |
| +4 | `10340000` | HP của tất cả Tướng +500 | Đội xuất trận · HP +500 | Hoạt động |
| +5 | `10350000` | Công của tất cả Tướng +200 | Đội xuất trận · Công +200 | Hoạt động |
| +6 | `10360000` | Né +1200 | Bản thân · Né +1200 | Hoạt động |
| +7 | `10370000` | HP của tất cả Tướng +2000 | Đội xuất trận · HP +2000 | Hoạt động |
| +8 | `10380000` | Đỡ +3000 | Bản thân · Đỡ +3000 | Hoạt động |
| +9 | `10390000` | Tất cả thuộc tính của Tướng +5% | Đội xuất trận · % Công +5%, % HP +5%, % Thủ +5% | Hoạt động |
| +10 | `10400000` | Bạo Kích +3000 | Bản thân · Bạo +3000 | Hoạt động |

## 1主角女初始 (`12010004`)

Bậc tối đa từ HeroStepRelation +15. Bậc tài năng cao nhất trong bảng +10.

| Bậc | TAL | Hiệu ứng VN | Dữ liệu áp dụng | R7.16 |
|---:|---:|---|---|---|
| +1 | `10320000` | Mục tiêu Kỹ Năng Nộ từ 1 thành 3 ngẫu nhiên | Chỉ có mô tả | Chưa áp dụng |
| +2 | `10330000` | Công +100 | Bản thân · Công +100 | Hoạt động |
| +3 | `10010000` | Mới bắt đầu tăng 50đ Nộ, lượt đầu có thể Nộ Công | Bản thân · Nộ +50 | Hoạt động |
| +4 | `10340000` | HP của tất cả Tướng +500 | Đội xuất trận · HP +500 | Hoạt động |
| +5 | `10350000` | Công của tất cả Tướng +200 | Đội xuất trận · Công +200 | Hoạt động |
| +6 | `10360000` | Né +1200 | Bản thân · Né +1200 | Hoạt động |
| +7 | `10370000` | HP của tất cả Tướng +2000 | Đội xuất trận · HP +2000 | Hoạt động |
| +8 | `10380000` | Đỡ +3000 | Bản thân · Đỡ +3000 | Hoạt động |
| +9 | `10390000` | Tất cả thuộc tính của Tướng +5% | Đội xuất trận · % Công +5%, % HP +5%, % Thủ +5% | Hoạt động |
| +10 | `10400000` | Bạo Kích +3000 | Bản thân · Bạo +3000 | Hoạt động |

## 2主角男突破+1 (`12010009`)

Bậc tối đa từ HeroStepRelation +15. Bậc tài năng cao nhất trong bảng +10.

| Bậc | TAL | Hiệu ứng VN | Dữ liệu áp dụng | R7.16 |
|---:|---:|---|---|---|
| +1 | `10320000` | Mục tiêu Kỹ Năng Nộ từ 1 thành 3 ngẫu nhiên | Chỉ có mô tả | Chưa áp dụng |
| +2 | `10330000` | Công +100 | Bản thân · Công +100 | Hoạt động |
| +3 | `10010000` | Mới bắt đầu tăng 50đ Nộ, lượt đầu có thể Nộ Công | Bản thân · Nộ +50 | Hoạt động |
| +4 | `10340000` | HP của tất cả Tướng +500 | Đội xuất trận · HP +500 | Hoạt động |
| +5 | `10350000` | Công của tất cả Tướng +200 | Đội xuất trận · Công +200 | Hoạt động |
| +6 | `10360000` | Né +1200 | Bản thân · Né +1200 | Hoạt động |
| +7 | `10370000` | HP của tất cả Tướng +2000 | Đội xuất trận · HP +2000 | Hoạt động |
| +8 | `10380000` | Đỡ +3000 | Bản thân · Đỡ +3000 | Hoạt động |
| +9 | `10390000` | Tất cả thuộc tính của Tướng +5% | Đội xuất trận · % Công +5%, % HP +5%, % Thủ +5% | Hoạt động |
| +10 | `10400000` | Bạo Kích +3000 | Bản thân · Bạo +3000 | Hoạt động |

## 2主角女突破+1 (`12010010`)

Bậc tối đa từ HeroStepRelation +15. Bậc tài năng cao nhất trong bảng +10.

| Bậc | TAL | Hiệu ứng VN | Dữ liệu áp dụng | R7.16 |
|---:|---:|---|---|---|
| +1 | `10320000` | Mục tiêu Kỹ Năng Nộ từ 1 thành 3 ngẫu nhiên | Chỉ có mô tả | Chưa áp dụng |
| +2 | `10330000` | Công +100 | Bản thân · Công +100 | Hoạt động |
| +3 | `10010000` | Mới bắt đầu tăng 50đ Nộ, lượt đầu có thể Nộ Công | Bản thân · Nộ +50 | Hoạt động |
| +4 | `10340000` | HP của tất cả Tướng +500 | Đội xuất trận · HP +500 | Hoạt động |
| +5 | `10350000` | Công của tất cả Tướng +200 | Đội xuất trận · Công +200 | Hoạt động |
| +6 | `10360000` | Né +1200 | Bản thân · Né +1200 | Hoạt động |
| +7 | `10370000` | HP của tất cả Tướng +2000 | Đội xuất trận · HP +2000 | Hoạt động |
| +8 | `10380000` | Đỡ +3000 | Bản thân · Đỡ +3000 | Hoạt động |
| +9 | `10390000` | Tất cả thuộc tính của Tướng +5% | Đội xuất trận · % Công +5%, % HP +5%, % Thủ +5% | Hoạt động |
| +10 | `10400000` | Bạo Kích +3000 | Bản thân · Bạo +3000 | Hoạt động |

## 3主角男紫10 (`12010007`)

Bậc tối đa từ HeroStepRelation +15. Bậc tài năng cao nhất trong bảng +10.

| Bậc | TAL | Hiệu ứng VN | Dữ liệu áp dụng | R7.16 |
|---:|---:|---|---|---|
| +1 | `10320000` | Mục tiêu Kỹ Năng Nộ từ 1 thành 3 ngẫu nhiên | Chỉ có mô tả | Chưa áp dụng |
| +2 | `10330000` | Công +100 | Bản thân · Công +100 | Hoạt động |
| +3 | `10010000` | Mới bắt đầu tăng 50đ Nộ, lượt đầu có thể Nộ Công | Bản thân · Nộ +50 | Hoạt động |
| +4 | `10340000` | HP của tất cả Tướng +500 | Đội xuất trận · HP +500 | Hoạt động |
| +5 | `10350000` | Công của tất cả Tướng +200 | Đội xuất trận · Công +200 | Hoạt động |
| +6 | `10360000` | Né +1200 | Bản thân · Né +1200 | Hoạt động |
| +7 | `10370000` | HP của tất cả Tướng +2000 | Đội xuất trận · HP +2000 | Hoạt động |
| +8 | `10380000` | Đỡ +3000 | Bản thân · Đỡ +3000 | Hoạt động |
| +9 | `10390000` | Tất cả thuộc tính của Tướng +5% | Đội xuất trận · % Công +5%, % HP +5%, % Thủ +5% | Hoạt động |
| +10 | `10400000` | Bạo Kích +3000 | Bản thân · Bạo +3000 | Hoạt động |

## 3主角女紫10 (`12010008`)

Bậc tối đa từ HeroStepRelation +15. Bậc tài năng cao nhất trong bảng +10.

| Bậc | TAL | Hiệu ứng VN | Dữ liệu áp dụng | R7.16 |
|---:|---:|---|---|---|
| +1 | `10320000` | Mục tiêu Kỹ Năng Nộ từ 1 thành 3 ngẫu nhiên | Chỉ có mô tả | Chưa áp dụng |
| +2 | `10330000` | Công +100 | Bản thân · Công +100 | Hoạt động |
| +3 | `10010000` | Mới bắt đầu tăng 50đ Nộ, lượt đầu có thể Nộ Công | Bản thân · Nộ +50 | Hoạt động |
| +4 | `10340000` | HP của tất cả Tướng +500 | Đội xuất trận · HP +500 | Hoạt động |
| +5 | `10350000` | Công của tất cả Tướng +200 | Đội xuất trận · Công +200 | Hoạt động |
| +6 | `10360000` | Né +1200 | Bản thân · Né +1200 | Hoạt động |
| +7 | `10370000` | HP của tất cả Tướng +2000 | Đội xuất trận · HP +2000 | Hoạt động |
| +8 | `10380000` | Đỡ +3000 | Bản thân · Đỡ +3000 | Hoạt động |
| +9 | `10390000` | Tất cả thuộc tính của Tướng +5% | Đội xuất trận · % Công +5%, % HP +5%, % Thủ +5% | Hoạt động |
| +10 | `10400000` | Bạo Kích +3000 | Bản thân · Bạo +3000 | Hoạt động |

## 4主角男橙13 (`12010002`)

Bậc tối đa từ HeroStepRelation +15. Bậc tài năng cao nhất trong bảng +15.

| Bậc | TAL | Hiệu ứng VN | Dữ liệu áp dụng | R7.16 |
|---:|---:|---|---|---|
| +1 | `10320000` | Mục tiêu Kỹ Năng Nộ từ 1 thành 3 ngẫu nhiên | Chỉ có mô tả | Chưa áp dụng |
| +2 | `10330000` | Công +100 | Bản thân · Công +100 | Hoạt động |
| +3 | `10010000` | Mới bắt đầu tăng 50đ Nộ, lượt đầu có thể Nộ Công | Bản thân · Nộ +50 | Hoạt động |
| +4 | `10340000` | HP của tất cả Tướng +500 | Đội xuất trận · HP +500 | Hoạt động |
| +5 | `10350000` | Công của tất cả Tướng +200 | Đội xuất trận · Công +200 | Hoạt động |
| +6 | `10360000` | Né +1200 | Bản thân · Né +1200 | Hoạt động |
| +7 | `10370000` | HP của tất cả Tướng +2000 | Đội xuất trận · HP +2000 | Hoạt động |
| +8 | `10380000` | Đỡ +3000 | Bản thân · Đỡ +3000 | Hoạt động |
| +9 | `10390000` | Tất cả thuộc tính của Tướng +5% | Đội xuất trận · % Công +5%, % HP +5%, % Thủ +5% | Hoạt động |
| +10 | `10400000` | Bạo Kích +3000 | Bản thân · Bạo +3000 | Hoạt động |
| +11 | `10590000` | Sát thương tất cả Tướng gây ra +2000 , miễn giảm sát thương +2000 | Đội xuất trận · ST cộng +2000, Miễn giảm ST +2000 | Hoạt động |
| +12 | `10600000` | HP+15000 | Bản thân · HP +15000 | Hoạt động |
| +13 | `10610000` | Chính Xác+1500 | Bản thân · Chính Xác +1500 | Hoạt động |
| +14 | `10620000` | Công+2100 | Bản thân · Công +2100 | Hoạt động |
| +15 | `10630000` | Tất cả các thuộc tính +10% | Bản thân · % Công +10%, % HP +10%, % Thủ +10% | Hoạt động |

## 4主角女橙13 (`12010005`)

Bậc tối đa từ HeroStepRelation +15. Bậc tài năng cao nhất trong bảng +15.

| Bậc | TAL | Hiệu ứng VN | Dữ liệu áp dụng | R7.16 |
|---:|---:|---|---|---|
| +1 | `10320000` | Mục tiêu Kỹ Năng Nộ từ 1 thành 3 ngẫu nhiên | Chỉ có mô tả | Chưa áp dụng |
| +2 | `10330000` | Công +100 | Bản thân · Công +100 | Hoạt động |
| +3 | `10010000` | Mới bắt đầu tăng 50đ Nộ, lượt đầu có thể Nộ Công | Bản thân · Nộ +50 | Hoạt động |
| +4 | `10340000` | HP của tất cả Tướng +500 | Đội xuất trận · HP +500 | Hoạt động |
| +5 | `10350000` | Công của tất cả Tướng +200 | Đội xuất trận · Công +200 | Hoạt động |
| +6 | `10360000` | Né +1200 | Bản thân · Né +1200 | Hoạt động |
| +7 | `10370000` | HP của tất cả Tướng +2000 | Đội xuất trận · HP +2000 | Hoạt động |
| +8 | `10380000` | Đỡ +3000 | Bản thân · Đỡ +3000 | Hoạt động |
| +9 | `10390000` | Tất cả thuộc tính của Tướng +5% | Đội xuất trận · % Công +5%, % HP +5%, % Thủ +5% | Hoạt động |
| +10 | `10400000` | Bạo Kích +3000 | Bản thân · Bạo +3000 | Hoạt động |
| +11 | `10590000` | Sát thương tất cả Tướng gây ra +2000 , miễn giảm sát thương +2000 | Đội xuất trận · ST cộng +2000, Miễn giảm ST +2000 | Hoạt động |
| +12 | `10600000` | HP+15000 | Bản thân · HP +15000 | Hoạt động |
| +13 | `10610000` | Chính Xác+1500 | Bản thân · Chính Xác +1500 | Hoạt động |
| +14 | `10620000` | Công+2100 | Bản thân · Công +2100 | Hoạt động |
| +15 | `10630000` | Tất cả các thuộc tính +10% | Bản thân · % Công +10%, % HP +10%, % Thủ +10% | Hoạt động |

## 5主角男橙15 (`12010003`)

Bậc tối đa từ HeroStepRelation +15. Bậc tài năng cao nhất trong bảng +15.

| Bậc | TAL | Hiệu ứng VN | Dữ liệu áp dụng | R7.16 |
|---:|---:|---|---|---|
| +1 | `10320000` | Mục tiêu Kỹ Năng Nộ từ 1 thành 3 ngẫu nhiên | Chỉ có mô tả | Chưa áp dụng |
| +2 | `10330000` | Công +100 | Bản thân · Công +100 | Hoạt động |
| +3 | `10010000` | Mới bắt đầu tăng 50đ Nộ, lượt đầu có thể Nộ Công | Bản thân · Nộ +50 | Hoạt động |
| +4 | `10340000` | HP của tất cả Tướng +500 | Đội xuất trận · HP +500 | Hoạt động |
| +5 | `10350000` | Công của tất cả Tướng +200 | Đội xuất trận · Công +200 | Hoạt động |
| +6 | `10360000` | Né +1200 | Bản thân · Né +1200 | Hoạt động |
| +7 | `10370000` | HP của tất cả Tướng +2000 | Đội xuất trận · HP +2000 | Hoạt động |
| +8 | `10380000` | Đỡ +3000 | Bản thân · Đỡ +3000 | Hoạt động |
| +9 | `10390000` | Tất cả thuộc tính của Tướng +5% | Đội xuất trận · % Công +5%, % HP +5%, % Thủ +5% | Hoạt động |
| +10 | `10400000` | Bạo Kích +3000 | Bản thân · Bạo +3000 | Hoạt động |
| +11 | `10590000` | Sát thương tất cả Tướng gây ra +2000 , miễn giảm sát thương +2000 | Đội xuất trận · ST cộng +2000, Miễn giảm ST +2000 | Hoạt động |
| +12 | `10600000` | HP+15000 | Bản thân · HP +15000 | Hoạt động |
| +13 | `10610000` | Chính Xác+1500 | Bản thân · Chính Xác +1500 | Hoạt động |
| +14 | `10620000` | Công+2100 | Bản thân · Công +2100 | Hoạt động |
| +15 | `10630000` | Tất cả các thuộc tính +10% | Bản thân · % Công +10%, % HP +10%, % Thủ +10% | Hoạt động |

## 5主角女橙15 (`12010006`)

Bậc tối đa từ HeroStepRelation +15. Bậc tài năng cao nhất trong bảng +15.

| Bậc | TAL | Hiệu ứng VN | Dữ liệu áp dụng | R7.16 |
|---:|---:|---|---|---|
| +1 | `10320000` | Mục tiêu Kỹ Năng Nộ từ 1 thành 3 ngẫu nhiên | Chỉ có mô tả | Chưa áp dụng |
| +2 | `10330000` | Công +100 | Bản thân · Công +100 | Hoạt động |
| +3 | `10010000` | Mới bắt đầu tăng 50đ Nộ, lượt đầu có thể Nộ Công | Bản thân · Nộ +50 | Hoạt động |
| +4 | `10340000` | HP của tất cả Tướng +500 | Đội xuất trận · HP +500 | Hoạt động |
| +5 | `10350000` | Công của tất cả Tướng +200 | Đội xuất trận · Công +200 | Hoạt động |
| +6 | `10360000` | Né +1200 | Bản thân · Né +1200 | Hoạt động |
| +7 | `10370000` | HP của tất cả Tướng +2000 | Đội xuất trận · HP +2000 | Hoạt động |
| +8 | `10380000` | Đỡ +3000 | Bản thân · Đỡ +3000 | Hoạt động |
| +9 | `10390000` | Tất cả thuộc tính của Tướng +5% | Đội xuất trận · % Công +5%, % HP +5%, % Thủ +5% | Hoạt động |
| +10 | `10400000` | Bạo Kích +3000 | Bản thân · Bạo +3000 | Hoạt động |
| +11 | `10590000` | Sát thương tất cả Tướng gây ra +2000 , miễn giảm sát thương +2000 | Đội xuất trận · ST cộng +2000, Miễn giảm ST +2000 | Hoạt động |
| +12 | `10600000` | HP+15000 | Bản thân · HP +15000 | Hoạt động |
| +13 | `10610000` | Chính Xác+1500 | Bản thân · Chính Xác +1500 | Hoạt động |
| +14 | `10620000` | Công+2100 | Bản thân · Công +2100 | Hoạt động |
| +15 | `10630000` | Tất cả các thuộc tính +10% | Bản thân · % Công +10%, % HP +10%, % Thủ +10% | Hoạt động |

## luckboss1 (`12010050`)

Bậc tối đa từ HeroStepRelation +15. Bậc tài năng cao nhất trong bảng +15.

| Bậc | TAL | Hiệu ứng VN | Dữ liệu áp dụng | R7.16 |
|---:|---:|---|---|---|
| +1 | `20910000` | Miễn dịch Choáng; miễn dịch Im Lặng; miễn dịch Giảm Nộ; miễn dịch Phản ST | Buff `10010000`, `10020000`, `10060000`, `10070000` | Chưa áp dụng |
| +2 | `10130160` | Công +80 | Bản thân · Công +80 | Hoạt động |
| +3 | `10130160` | Công +80 | Bản thân · Công +80 | Hoạt động |
| +4 | `10131000` | Công +500 | Bản thân · Công +500 | Hoạt động |
| +5 | `10130400` | Công +200 | Bản thân · Công +200 | Hoạt động |
| +6 | `10131000` | Công +500 | Bản thân · Công +500 | Hoạt động |
| +7 | `10131000` | Công +500 | Bản thân · Công +500 | Hoạt động |
| +11 | `10480800` | Sát thương tất cả Tướng gây ra +8000 , miễn giảm sát thương +8000 | Đội xuất trận · ST cộng +8000, Miễn giảm ST +8000 | Hoạt động |
| +12 | `10490480` | HP+28800 | Bản thân · HP +28800 | Hoạt động |
| +13 | `10080870` | Chính Xác +4350 | Bản thân · Chính Xác +4350 | Hoạt động |
| +14 | `10500800` | Công+4800 | Bản thân · Công +4800 | Hoạt động |
| +15 | `20660830` | Khi Nộ Công, bỏ qua 83% Thủ của mục tiêu | Buff `10560830` | Chưa áp dụng |

## luckboss2 (`12010051`)

Bậc tối đa từ HeroStepRelation +15. Bậc tài năng cao nhất trong bảng +15.

| Bậc | TAL | Hiệu ứng VN | Dữ liệu áp dụng | R7.16 |
|---:|---:|---|---|---|
| +1 | `20910000` | Miễn dịch Choáng; miễn dịch Im Lặng; miễn dịch Giảm Nộ; miễn dịch Phản ST | Buff `10010000`, `10020000`, `10060000`, `10070000` | Chưa áp dụng |
| +2 | `10130160` | Công +80 | Bản thân · Công +80 | Hoạt động |
| +3 | `10130160` | Công +80 | Bản thân · Công +80 | Hoạt động |
| +4 | `10131000` | Công +500 | Bản thân · Công +500 | Hoạt động |
| +5 | `10130400` | Công +200 | Bản thân · Công +200 | Hoạt động |
| +6 | `10131000` | Công +500 | Bản thân · Công +500 | Hoạt động |
| +7 | `10131000` | Công +500 | Bản thân · Công +500 | Hoạt động |
| +11 | `10480800` | Sát thương tất cả Tướng gây ra +8000 , miễn giảm sát thương +8000 | Đội xuất trận · ST cộng +8000, Miễn giảm ST +8000 | Hoạt động |
| +12 | `10490480` | HP+28800 | Bản thân · HP +28800 | Hoạt động |
| +13 | `10080870` | Chính Xác +4350 | Bản thân · Chính Xác +4350 | Hoạt động |
| +14 | `10500800` | Công+4800 | Bản thân · Công +4800 | Hoạt động |
| +15 | `20660830` | Khi Nộ Công, bỏ qua 83% Thủ của mục tiêu | Buff `10560830` | Chưa áp dụng |

## luckboss3 (`12010052`)

Bậc tối đa từ HeroStepRelation +15. Bậc tài năng cao nhất trong bảng +15.

| Bậc | TAL | Hiệu ứng VN | Dữ liệu áp dụng | R7.16 |
|---:|---:|---|---|---|
| +1 | `20910000` | Miễn dịch Choáng; miễn dịch Im Lặng; miễn dịch Giảm Nộ; miễn dịch Phản ST | Buff `10010000`, `10020000`, `10060000`, `10070000` | Chưa áp dụng |
| +2 | `10130160` | Công +80 | Bản thân · Công +80 | Hoạt động |
| +3 | `10130160` | Công +80 | Bản thân · Công +80 | Hoạt động |
| +4 | `10131000` | Công +500 | Bản thân · Công +500 | Hoạt động |
| +5 | `10130400` | Công +200 | Bản thân · Công +200 | Hoạt động |
| +6 | `10131000` | Công +500 | Bản thân · Công +500 | Hoạt động |
| +7 | `10131000` | Công +500 | Bản thân · Công +500 | Hoạt động |
| +11 | `10480800` | Sát thương tất cả Tướng gây ra +8000 , miễn giảm sát thương +8000 | Đội xuất trận · ST cộng +8000, Miễn giảm ST +8000 | Hoạt động |
| +12 | `10490480` | HP+28800 | Bản thân · HP +28800 | Hoạt động |
| +13 | `10080870` | Chính Xác +4350 | Bản thân · Chính Xác +4350 | Hoạt động |
| +14 | `10500800` | Công+4800 | Bản thân · Công +4800 | Hoạt động |
| +15 | `20660830` | Khi Nộ Công, bỏ qua 83% Thủ của mục tiêu | Buff `10560830` | Chưa áp dụng |

## luckboss4 (`12010053`)

Bậc tối đa từ HeroStepRelation +15. Bậc tài năng cao nhất trong bảng +15.

| Bậc | TAL | Hiệu ứng VN | Dữ liệu áp dụng | R7.16 |
|---:|---:|---|---|---|
| +1 | `20910000` | Miễn dịch Choáng; miễn dịch Im Lặng; miễn dịch Giảm Nộ; miễn dịch Phản ST | Buff `10010000`, `10020000`, `10060000`, `10070000` | Chưa áp dụng |
| +2 | `10130160` | Công +80 | Bản thân · Công +80 | Hoạt động |
| +3 | `10130160` | Công +80 | Bản thân · Công +80 | Hoạt động |
| +4 | `10131000` | Công +500 | Bản thân · Công +500 | Hoạt động |
| +5 | `10130400` | Công +200 | Bản thân · Công +200 | Hoạt động |
| +6 | `10131000` | Công +500 | Bản thân · Công +500 | Hoạt động |
| +7 | `10131000` | Công +500 | Bản thân · Công +500 | Hoạt động |
| +11 | `10480800` | Sát thương tất cả Tướng gây ra +8000 , miễn giảm sát thương +8000 | Đội xuất trận · ST cộng +8000, Miễn giảm ST +8000 | Hoạt động |
| +12 | `10490480` | HP+28800 | Bản thân · HP +28800 | Hoạt động |
| +13 | `10080870` | Chính Xác +4350 | Bản thân · Chính Xác +4350 | Hoạt động |
| +14 | `10500800` | Công+4800 | Bản thân · Công +4800 | Hoạt động |
| +15 | `20660830` | Khi Nộ Công, bỏ qua 83% Thủ của mục tiêu | Buff `10560830` | Chưa áp dụng |

## luckboss5 (`12010054`)

Bậc tối đa từ HeroStepRelation +15. Bậc tài năng cao nhất trong bảng +15.

| Bậc | TAL | Hiệu ứng VN | Dữ liệu áp dụng | R7.16 |
|---:|---:|---|---|---|
| +1 | `20910000` | Miễn dịch Choáng; miễn dịch Im Lặng; miễn dịch Giảm Nộ; miễn dịch Phản ST | Buff `10010000`, `10020000`, `10060000`, `10070000` | Chưa áp dụng |
| +2 | `10130160` | Công +80 | Bản thân · Công +80 | Hoạt động |
| +3 | `10130160` | Công +80 | Bản thân · Công +80 | Hoạt động |
| +4 | `10131000` | Công +500 | Bản thân · Công +500 | Hoạt động |
| +5 | `10130400` | Công +200 | Bản thân · Công +200 | Hoạt động |
| +6 | `10131000` | Công +500 | Bản thân · Công +500 | Hoạt động |
| +7 | `10131000` | Công +500 | Bản thân · Công +500 | Hoạt động |
| +11 | `10480800` | Sát thương tất cả Tướng gây ra +8000 , miễn giảm sát thương +8000 | Đội xuất trận · ST cộng +8000, Miễn giảm ST +8000 | Hoạt động |
| +12 | `10490480` | HP+28800 | Bản thân · HP +28800 | Hoạt động |
| +13 | `10080870` | Chính Xác +4350 | Bản thân · Chính Xác +4350 | Hoạt động |
| +14 | `10500800` | Công+4800 | Bản thân · Công +4800 | Hoạt động |
| +15 | `20660830` | Khi Nộ Công, bỏ qua 83% Thủ của mục tiêu | Buff `10560830` | Chưa áp dụng |

## LuckBoss6 (`12010055`)

Bậc tối đa từ HeroStepRelation +15. Bậc tài năng cao nhất trong bảng +15.

| Bậc | TAL | Hiệu ứng VN | Dữ liệu áp dụng | R7.16 |
|---:|---:|---|---|---|
| +1 | `20910000` | Miễn dịch Choáng; miễn dịch Im Lặng; miễn dịch Giảm Nộ; miễn dịch Phản ST | Buff `10010000`, `10020000`, `10060000`, `10070000` | Chưa áp dụng |
| +2 | `10130160` | Công +80 | Bản thân · Công +80 | Hoạt động |
| +3 | `10130160` | Công +80 | Bản thân · Công +80 | Hoạt động |
| +4 | `10131000` | Công +500 | Bản thân · Công +500 | Hoạt động |
| +5 | `10130400` | Công +200 | Bản thân · Công +200 | Hoạt động |
| +6 | `10131000` | Công +500 | Bản thân · Công +500 | Hoạt động |
| +7 | `10131000` | Công +500 | Bản thân · Công +500 | Hoạt động |
| +11 | `10480800` | Sát thương tất cả Tướng gây ra +8000 , miễn giảm sát thương +8000 | Đội xuất trận · ST cộng +8000, Miễn giảm ST +8000 | Hoạt động |
| +12 | `10490480` | HP+28800 | Bản thân · HP +28800 | Hoạt động |
| +13 | `10080870` | Chính Xác +4350 | Bản thân · Chính Xác +4350 | Hoạt động |
| +14 | `10500800` | Công+4800 | Bản thân · Công +4800 | Hoạt động |
| +15 | `20660830` | Khi Nộ Công, bỏ qua 83% Thủ của mục tiêu | Buff `10560830` | Chưa áp dụng |

## Abi (`12012019`)

Bậc tối đa từ HeroStepRelation +15. Bậc tài năng cao nhất trong bảng +15.

| Bậc | TAL | Hiệu ứng VN | Dữ liệu áp dụng | R7.16 |
|---:|---:|---|---|---|
| +2 | `10090160` | Điểm Trị Liệu +200 | Bản thân · Trị Liệu +200 | Hoạt động |
| +3 | `10060160` | Né +640 | Bản thân · Né +640 | Hoạt động |
| +4 | `10220000` | Công của tất cả Tướng +125 | Đội xuất trận · Công +125 | Hoạt động |
| +5 | `10100400` | Điểm Trị Liệu +12% | Bản thân · % Trị Liệu +20% | Hoạt động |
| +6 | `10010000` | Mới bắt đầu tăng 50đ Nộ, lượt đầu có thể Nộ Công | Bản thân · Nộ +50 | Hoạt động |
| +7 | `10230000` | HP của tất cả Tướng +1250 | Đội xuất trận · HP +1250 | Hoạt động |
| +8 | `20620400` | Khi tử vong, hồi HP bằng 30% Công cho mục tiêu đồng đội tối đa đã mất máu | Buff `10330400` | Chưa áp dụng |
| +9 | `10240000` | Tất cả thuộc tính của Tướng +2% | Đội xuất trận · % Công +2%, % HP +2%, % Thủ +2% | Hoạt động |
| +10 | `20190600` | Khi tấn công thường, 45% tăng 25đ Nộ cho mục tiêu đồng đội có Nộ thấp nhất | Buff `10530600` | Chưa áp dụng |
| +11 | `10480500` | Sát thương tất cả Tướng gây ra +5000 , miễn giảm sát thương +5000 | Đội xuất trận · ST cộng +5000, Miễn giảm ST +5000 | Hoạt động |
| +12 | `10490300` | HP+18000 | Bản thân · HP +18000 | Hoạt động |
| +13 | `10650600` | Kháng Bạo+3000 | Bản thân · Kháng Bạo +3000 | Hoạt động |
| +14 | `10500500` | Công+3000 | Bản thân · Công +3000 | Hoạt động |
| +15 | `20640500` | Ra trận lần 1,2,3, khi bản thân chịu ST giảm 38% | Buff `10140500` | Chưa áp dụng |

## A-Un (`12012012`)

Bậc tối đa từ HeroStepRelation +15. Bậc tài năng cao nhất trong bảng +15.

| Bậc | TAL | Hiệu ứng VN | Dữ liệu áp dụng | R7.16 |
|---:|---:|---|---|---|
| +2 | `10140160` | Thủ +80 | Bản thân · Thủ +80 | Hoạt động |
| +3 | `10040160` | Đỡ +800 | Bản thân · Đỡ +800 | Hoạt động |
| +4 | `10190000` | Công của tất cả Tướng +200 | Đội xuất trận · Công +200 | Hoạt động |
| +5 | `10040400` | Đỡ +2000 | Bản thân · Đỡ +2000 | Hoạt động |
| +6 | `10010000` | Mới bắt đầu tăng 50đ Nộ, lượt đầu có thể Nộ Công | Bản thân · Nộ +50 | Hoạt động |
| +7 | `10200000` | HP của tất cả Tướng +2000 | Đội xuất trận · HP +2000 | Hoạt động |
| +8 | `20730600` | Đỡ phản kích, gây ST bằng 75% Công | Buff `20050600` | Chưa áp dụng |
| +9 | `10210000` | Tất cả thuộc tính của Tướng +3% | Đội xuất trận · % Công +3%, % HP +3%, % Thủ +3% | Hoạt động |
| +10 | `20450600` | Khi bị tấn công, nếu HP cao hơn kẻ công kích, nhận ST giảm 30% | Buff `10150600` | Chưa áp dụng |
| +11 | `10480800` | Sát thương tất cả Tướng gây ra +8000 , miễn giảm sát thương +8000 | Đội xuất trận · ST cộng +8000, Miễn giảm ST +8000 | Hoạt động |
| +12 | `10490480` | HP+28800 | Bản thân · HP +28800 | Hoạt động |
| +13 | `10040870` | Đỡ +4350 | Bản thân · Đỡ +4350 | Hoạt động |
| +14 | `10500800` | Công+4800 | Bản thân · Công +4800 | Hoạt động |
| +15 | `20080830` | Khi bị tấn công thường, gây 25% [Choáng] 1 lượt đối với kẻ công kích | Buff `20140830` | Chưa áp dụng |

## Hachiemon (`12012013`)

Bậc tối đa từ HeroStepRelation +15. Bậc tài năng cao nhất trong bảng +15.

| Bậc | TAL | Hiệu ứng VN | Dữ liệu áp dụng | R7.16 |
|---:|---:|---|---|---|
| +2 | `10150160` | HP +800 | Bản thân · HP +800 | Hoạt động |
| +3 | `10080160` | Chính Xác +800 | Bản thân · Chính Xác +800 | Hoạt động |
| +4 | `10220000` | Công của tất cả Tướng +125 | Đội xuất trận · Công +125 | Hoạt động |
| +5 | `10030400` | Bạo Kích +2000 | Bản thân · Bạo +2000 | Hoạt động |
| +6 | `10010000` | Mới bắt đầu tăng 50đ Nộ, lượt đầu có thể Nộ Công | Bản thân · Nộ +50 | Hoạt động |
| +7 | `10230000` | HP của tất cả Tướng +1250 | Đội xuất trận · HP +1250 | Hoạt động |
| +8 | `20150400` | Khi tấn công thường, hồi HP bằng 30% ST cho bản thân | Buff `10710400` | Chưa áp dụng |
| +9 | `10240000` | Tất cả thuộc tính của Tướng +2% | Đội xuất trận · % Công +2%, % HP +2%, % Thủ +2% | Hoạt động |
| +10 | `20120600` | Bản thân giảm 10% HP, ST gây ra tăng 6% | Buff `10110600` | Chưa áp dụng |
| +11 | `10480500` | Sát thương tất cả Tướng gây ra +5000 , miễn giảm sát thương +5000 | Đội xuất trận · ST cộng +5000, Miễn giảm ST +5000 | Hoạt động |
| +12 | `10490300` | HP+18000 | Bản thân · HP +18000 | Hoạt động |
| +13 | `10640600` | Phá Kích+3000 | Bản thân · Phá Kích +3000 | Hoạt động |
| +14 | `10500500` | Công+3000 | Bản thân · Công +3000 | Hoạt động |
| +15 | `21070500` | Kỹ Năng ST tăng 25% | Buff `10590500` | Chưa áp dụng |

## Byakko (`12012027`)

Bậc tối đa từ HeroStepRelation +8. Bậc tài năng cao nhất trong bảng +8.

| Bậc | TAL | Hiệu ứng VN | Dữ liệu áp dụng | R7.16 |
|---:|---:|---|---|---|
| +2 | `10140120` | Thủ +60 | Bản thân · Thủ +60 | Hoạt động |
| +3 | `10040120` | Đỡ +600 | Bản thân · Đỡ +600 | Hoạt động |
| +4 | `10250000` | Công của tất cả Tướng +80 | Đội xuất trận · Công +80 | Hoạt động |
| +5 | `20460400` | Khi bị tấn công, nếu HP thấp hơn kẻ công kích, chịu ST giảm 20% | Buff `10160400` | Chưa áp dụng |
| +6 | `10010000` | Mới bắt đầu tăng 50đ Nộ, lượt đầu có thể Nộ Công | Bản thân · Nộ +50 | Hoạt động |
| +7 | `10260000` | HP của tất cả Tướng +800 | Đội xuất trận · HP +800 | Hoạt động |
| +8 | `10040400` | Đỡ +2000 | Bản thân · Đỡ +2000 | Hoạt động |

## Hakudoushi (`12013009`)

Bậc tối đa từ HeroStepRelation +15. Bậc tài năng cao nhất trong bảng +15.

| Bậc | TAL | Hiệu ứng VN | Dữ liệu áp dụng | R7.16 |
|---:|---:|---|---|---|
| +2 | `10150160` | HP +800 | Bản thân · HP +800 | Hoạt động |
| +3 | `10080160` | Chính Xác +800 | Bản thân · Chính Xác +800 | Hoạt động |
| +4 | `10190000` | Công của tất cả Tướng +200 | Đội xuất trận · Công +200 | Hoạt động |
| +5 | `10030400` | Bạo Kích +2000 | Bản thân · Bạo +2000 | Hoạt động |
| +6 | `10010000` | Mới bắt đầu tăng 50đ Nộ, lượt đầu có thể Nộ Công | Bản thân · Nộ +50 | Hoạt động |
| +7 | `10200000` | HP của tất cả Tướng +2000 | Đội xuất trận · HP +2000 | Hoạt động |
| +8 | `20530600` | Khi HP của bản thân cao hơn 50%, gây ST tăng 30% | Buff `10230600` | Chưa áp dụng |
| +9 | `10210000` | Tất cả thuộc tính của Tướng +3% | Đội xuất trận · % Công +3%, % HP +3%, % Thủ +3% | Hoạt động |
| +10 | `20350806` | Khi Nộ Công, 80% khiến mục tiêu [Trúng Độc] 2 lượt | Buff `20440806` | Chưa áp dụng |
| +11 | `10480800` | Sát thương tất cả Tướng gây ra +8000 , miễn giảm sát thương +8000 | Đội xuất trận · ST cộng +8000, Miễn giảm ST +8000 | Hoạt động |
| +12 | `10490480` | HP+28800 | Bản thân · HP +28800 | Hoạt động |
| +13 | `10030870` | Bạo Kích +4350 | Bản thân · Bạo +4350 | Hoạt động |
| +14 | `10500800` | Công+4800 | Bản thân · Công +4800 | Hoạt động |
| +15 | `10020830` | Chịu ST giảm 25% | Bản thân · % miễn giảm ST +24.9% | Hoạt động |

## Byakuya (`12013010`)

Bậc tối đa từ HeroStepRelation +15. Bậc tài năng cao nhất trong bảng +15.

| Bậc | TAL | Hiệu ứng VN | Dữ liệu áp dụng | R7.16 |
|---:|---:|---|---|---|
| +2 | `10150160` | HP +800 | Bản thân · HP +800 | Hoạt động |
| +3 | `10080160` | Chính Xác +800 | Bản thân · Chính Xác +800 | Hoạt động |
| +4 | `10220000` | Công của tất cả Tướng +125 | Đội xuất trận · Công +125 | Hoạt động |
| +5 | `20040000` | Khi tiêu diệt mục tiêu, tăng thêm 25đ Nộ | Buff `10280000` | Chưa áp dụng |
| +6 | `10010000` | Mới bắt đầu tăng 50đ Nộ, lượt đầu có thể Nộ Công | Bản thân · Nộ +50 | Hoạt động |
| +7 | `10230000` | HP của tất cả Tướng +1250 | Đội xuất trận · HP +1250 | Hoạt động |
| +8 | `20500400` | Khi HP của mục tiêu thấp hơn 50%, gây ST tăng 20% | Buff `10200400` | Chưa áp dụng |
| +9 | `10240000` | Tất cả thuộc tính của Tướng +2% | Đội xuất trận · % Công +2%, % HP +2%, % Thủ +2% | Hoạt động |
| +10 | `20190600` | Khi tấn công thường, 45% tăng 25đ Nộ cho mục tiêu đồng đội có Nộ thấp nhất | Buff `10530600` | Chưa áp dụng |
| +11 | `10480500` | Sát thương tất cả Tướng gây ra +5000 , miễn giảm sát thương +5000 | Đội xuất trận · ST cộng +5000, Miễn giảm ST +5000 | Hoạt động |
| +12 | `10490300` | HP+18000 | Bản thân · HP +18000 | Hoạt động |
| +13 | `10640600` | Phá Kích+3000 | Bản thân · Phá Kích +3000 | Hoạt động |
| +14 | `10500500` | Công+3000 | Bản thân · Công +3000 | Hoạt động |
| +15 | `10020500` | Chịu ST giảm 15% | Bản thân · % miễn giảm ST +15% | Hoạt động |

## Omukade (`12011026`)

Bậc tối đa từ HeroStepRelation +8. Bậc tài năng cao nhất trong bảng +8.

| Bậc | TAL | Hiệu ứng VN | Dữ liệu áp dụng | R7.16 |
|---:|---:|---|---|---|
| +2 | `10150120` | HP +600 | Bản thân · HP +600 | Hoạt động |
| +3 | `10060120` | Né +480 | Bản thân · Né +480 | Hoạt động |
| +4 | `10250000` | Công của tất cả Tướng +80 | Đội xuất trận · Công +80 | Hoạt động |
| +5 | `20360401` | Khi Nộ Công, 40% khiến mục tiêu bị [Choáng] 1 lượt | Buff `20210401` | Chưa áp dụng |
| +6 | `10010000` | Mới bắt đầu tăng 50đ Nộ, lượt đầu có thể Nộ Công | Bản thân · Nộ +50 | Hoạt động |
| +7 | `10260000` | HP của tất cả Tướng +800 | Đội xuất trận · HP +800 | Hoạt động |
| +8 | `20230406` | Khi tấn công thường, 15% giảm 25đ Nộ của mục tiêu | Buff `10500406` | Chưa áp dụng |

## Hosenki (`12011020`)

Bậc tối đa từ HeroStepRelation +15. Bậc tài năng cao nhất trong bảng +15.

| Bậc | TAL | Hiệu ứng VN | Dữ liệu áp dụng | R7.16 |
|---:|---:|---|---|---|
| +2 | `10150160` | HP +800 | Bản thân · HP +800 | Hoạt động |
| +3 | `10080160` | Chính Xác +800 | Bản thân · Chính Xác +800 | Hoạt động |
| +4 | `10190000` | Công của tất cả Tướng +200 | Đội xuất trận · Công +200 | Hoạt động |
| +5 | `20480400` | Mục tiêu của bản thân khi lượng máu cao,gây ST tăng 20% | Buff `10180400` | Chưa áp dụng |
| +6 | `10010000` | Mới bắt đầu tăng 50đ Nộ, lượt đầu có thể Nộ Công | Bản thân · Nộ +50 | Hoạt động |
| +7 | `10200000` | HP của tất cả Tướng +2000 | Đội xuất trận · HP +2000 | Hoạt động |
| +8 | `20630600` | Ra trận lần 1 khi tấn công, ST gây ra tăng 75% | Buff `10130600` | Chưa áp dụng |
| +9 | `10210000` | Tất cả thuộc tính của Tướng +3% | Đội xuất trận · % Công +3%, % HP +3%, % Thủ +3% | Hoạt động |
| +10 | `20190600` | Khi tấn công thường, 45% tăng 25đ Nộ cho mục tiêu đồng đội có Nộ thấp nhất | Buff `10530600` | Chưa áp dụng |
| +11 | `10480800` | Sát thương tất cả Tướng gây ra +8000 , miễn giảm sát thương +8000 | Đội xuất trận · ST cộng +8000, Miễn giảm ST +8000 | Hoạt động |
| +12 | `10490480` | HP+28800 | Bản thân · HP +28800 | Hoạt động |
| +13 | `10650870` | Kháng Bạo+4350 | Bản thân · Kháng Bạo +4350 | Hoạt động |
| +14 | `10500800` | Công+4800 | Bản thân · Công +4800 | Hoạt động |
| +15 | `20640830` | Ra trận lần 1,2,3, khi bản thân chịu ST giảm 62% | Buff `10140830` | Chưa áp dụng |

## Bunza (`12011028`)

Bậc tối đa từ HeroStepRelation +8. Bậc tài năng cao nhất trong bảng +8.

| Bậc | TAL | Hiệu ứng VN | Dữ liệu áp dụng | R7.16 |
|---:|---:|---|---|---|
| +2 | `10130120` | Công +60 | Bản thân · Công +60 | Hoạt động |
| +3 | `10030120` | Bạo Kích +600 | Bản thân · Bạo +600 | Hoạt động |
| +4 | `10250000` | Công của tất cả Tướng +80 | Đội xuất trận · Công +80 | Hoạt động |
| +5 | `20480400` | Mục tiêu của bản thân khi lượng máu cao,gây ST tăng 20% | Buff `10180400` | Chưa áp dụng |
| +6 | `10010000` | Mới bắt đầu tăng 50đ Nộ, lượt đầu có thể Nộ Công | Bản thân · Nộ +50 | Hoạt động |
| +7 | `10260000` | HP của tất cả Tướng +800 | Đội xuất trận · HP +800 | Hoạt động |
| +8 | `20440401` | Khi tấn công bị Đỡ, lần ST kế tiếp tăng 40% | Buff `20100401` | Chưa áp dụng |

## Soten (`12011030`)

Bậc tối đa từ HeroStepRelation +8. Bậc tài năng cao nhất trong bảng +8.

| Bậc | TAL | Hiệu ứng VN | Dữ liệu áp dụng | R7.16 |
|---:|---:|---|---|---|
| +2 | `10150120` | HP +600 | Bản thân · HP +600 | Hoạt động |
| +3 | `10040120` | Đỡ +600 | Bản thân · Đỡ +600 | Hoạt động |
| +4 | `10250000` | Công của tất cả Tướng +80 | Đội xuất trận · Công +80 | Hoạt động |
| +5 | `10100400` | Điểm Trị Liệu +12% | Bản thân · % Trị Liệu +20% | Hoạt động |
| +6 | `10010000` | Mới bắt đầu tăng 50đ Nộ, lượt đầu có thể Nộ Công | Bản thân · Nộ +50 | Hoạt động |
| +7 | `10260000` | HP của tất cả Tướng +800 | Đội xuất trận · HP +800 | Hoạt động |
| +8 | `10100400` | Điểm Trị Liệu +12% | Bản thân · % Trị Liệu +20% | Hoạt động |

## Takemaru (`12013003`)

Bậc tối đa từ HeroStepRelation +15. Bậc tài năng cao nhất trong bảng +15.

| Bậc | TAL | Hiệu ứng VN | Dữ liệu áp dụng | R7.16 |
|---:|---:|---|---|---|
| +2 | `10150200` | HP +1000 | Bản thân · HP +1000 | Hoạt động |
| +3 | `10040200` | Đỡ +1000 | Bản thân · Đỡ +1000 | Hoạt động |
| +4 | `10160000` | Công của tất cả Tướng +250 | Đội xuất trận · Công +250 | Hoạt động |
| +5 | `20740600` | Khi bị tấn công, phản 18% ST | Buff `20070600` | Chưa áp dụng |
| +6 | `10010000` | Mới bắt đầu tăng 50đ Nộ, lượt đầu có thể Nộ Công | Bản thân · Nộ +50 | Hoạt động |
| +7 | `10170000` | HP của tất cả Tướng +2500 | Đội xuất trận · HP +2500 | Hoạt động |
| +8 | `20150600` | Khi tấn công thường, hồi HP bằng 45% ST cho bản thân | Buff `10710600` | Chưa áp dụng |
| +9 | `10180000` | Tất cả thuộc tính của Tướng +4% | Đội xuất trận · % Công +4%, % HP +4%, % Thủ +4% | Hoạt động |
| +10 | `20521000` | Khi HP của bản thân thấp hơn 50%, gây ST tăng 50% | Buff `10221000` | Chưa áp dụng |
| +11 | `10481000` | Sát thương tất cả Tướng gây ra +10000 , miễn giảm sát thương +10000 | Đội xuất trận · ST cộng +10000, Miễn giảm ST +10000 | Hoạt động |
| +12 | `10490600` | HP+36000 | Bản thân · HP +36000 | Hoạt động |
| +13 | `10041000` | Đỡ +5000 | Bản thân · Đỡ +5000 | Hoạt động |
| +14 | `10501000` | Công+6000 | Bản thân · Công +6000 | Hoạt động |
| +15 | `10021000` | Chịu ST giảm 30% | Bản thân · % miễn giảm ST +30% | Hoạt động |

## Ayame (`12011014`)

Bậc tối đa từ HeroStepRelation +15. Bậc tài năng cao nhất trong bảng +15.

| Bậc | TAL | Hiệu ứng VN | Dữ liệu áp dụng | R7.16 |
|---:|---:|---|---|---|
| +2 | `10130160` | Công +80 | Bản thân · Công +80 | Hoạt động |
| +3 | `10030160` | Bạo Kích +800 | Bản thân · Bạo +800 | Hoạt động |
| +4 | `10220000` | Công của tất cả Tướng +125 | Đội xuất trận · Công +125 | Hoạt động |
| +5 | `20660400` | Khi Nộ Công, bỏ qua 40% Thủ của mục tiêu | Buff `10560400` | Chưa áp dụng |
| +6 | `10010000` | Mới bắt đầu tăng 50đ Nộ, lượt đầu có thể Nộ Công | Bản thân · Nộ +50 | Hoạt động |
| +7 | `10230000` | HP của tất cả Tướng +1250 | Đội xuất trận · HP +1250 | Hoạt động |
| +8 | `20440402` | Khi tấn công bị Đỡ, lần ST kế tiếp tăng 33% | Buff `20100402` | Chưa áp dụng |
| +9 | `10240000` | Tất cả thuộc tính của Tướng +2% | Đội xuất trận · % Công +2%, % HP +2%, % Thủ +2% | Hoạt động |
| +10 | `20120600` | Bản thân giảm 10% HP, ST gây ra tăng 6% | Buff `10110600` | Chưa áp dụng |
| +11 | `10480500` | Sát thương tất cả Tướng gây ra +5000 , miễn giảm sát thương +5000 | Đội xuất trận · ST cộng +5000, Miễn giảm ST +5000 | Hoạt động |
| +12 | `10490300` | HP+18000 | Bản thân · HP +18000 | Hoạt động |
| +13 | `10070600` | Bạo Kích +1500, ST Bạo +3000 | Bản thân · Bạo +1500, Tất Sát +3000 | Hoạt động |
| +14 | `10500500` | Công+3000 | Bản thân · Công +3000 | Hoạt động |
| +15 | `20480500` | Mục tiêu của bản thân khi lượng máu cao,gây ST tăng 25% | Buff `10180500` | Chưa áp dụng |

## Shunran (`12013020`)

Bậc tối đa từ HeroStepRelation +15. Bậc tài năng cao nhất trong bảng +15.

| Bậc | TAL | Hiệu ứng VN | Dữ liệu áp dụng | R7.16 |
|---:|---:|---|---|---|
| +2 | `10130160` | Công +80 | Bản thân · Công +80 | Hoạt động |
| +3 | `10030160` | Bạo Kích +800 | Bản thân · Bạo +800 | Hoạt động |
| +4 | `10220000` | Công của tất cả Tướng +125 | Đội xuất trận · Công +125 | Hoạt động |
| +5 | `20720400` | Khi tấn công thường, gây thêm 40% ST cho mục tiêu lân cận | Buff `20590400` | Chưa áp dụng |
| +6 | `10010000` | Mới bắt đầu tăng 50đ Nộ, lượt đầu có thể Nộ Công | Bản thân · Nộ +50 | Hoạt động |
| +7 | `10230000` | HP của tất cả Tướng +1250 | Đội xuất trận · HP +1250 | Hoạt động |
| +8 | `20530400` | Khi HP của bản thân cao hơn 50%, gây ST tăng 20% | Buff `10230400` | Chưa áp dụng |
| +9 | `10240000` | Tất cả thuộc tính của Tướng +2% | Đội xuất trận · % Công +2%, % HP +2%, % Thủ +2% | Hoạt động |
| +10 | `20580600` | Khi Nộ Công, nếu mục tiêu trong trạng thái [Trúng Độc], 100% giảm 45đ Nộ | Buff `10620600` | Chưa áp dụng |
| +11 | `10480500` | Sát thương tất cả Tướng gây ra +5000 , miễn giảm sát thương +5000 | Đội xuất trận · ST cộng +5000, Miễn giảm ST +5000 | Hoạt động |
| +12 | `10490300` | HP+18000 | Bản thân · HP +18000 | Hoạt động |
| +13 | `10080600` | Chính Xác +3000 | Bản thân · Chính Xác +3000 | Hoạt động |
| +14 | `10500500` | Công+3000 | Bản thân · Công +3000 | Hoạt động |
| +15 | `20660500` | Khi Nộ Công, bỏ qua 50% Thủ của mục tiêu | Buff `10560500` | Chưa áp dụng |

## Tsubaki (`12013018`)

Bậc tối đa từ HeroStepRelation +15. Bậc tài năng cao nhất trong bảng +15.

| Bậc | TAL | Hiệu ứng VN | Dữ liệu áp dụng | R7.16 |
|---:|---:|---|---|---|
| +2 | `10090160` | Điểm Trị Liệu +200 | Bản thân · Trị Liệu +200 | Hoạt động |
| +3 | `10060160` | Né +640 | Bản thân · Né +640 | Hoạt động |
| +4 | `10220000` | Công của tất cả Tướng +125 | Đội xuất trận · Công +125 | Hoạt động |
| +5 | `10100400` | Điểm Trị Liệu +12% | Bản thân · % Trị Liệu +20% | Hoạt động |
| +6 | `10010000` | Mới bắt đầu tăng 50đ Nộ, lượt đầu có thể Nộ Công | Bản thân · Nộ +50 | Hoạt động |
| +7 | `10230000` | HP của tất cả Tướng +1250 | Đội xuất trận · HP +1250 | Hoạt động |
| +8 | `20610400` | Khi tử vong, hồi HP bằng 100% Công cho mục tiêu đồng đội tối đa đã mất máu | Buff `10320400` | Chưa áp dụng |
| +9 | `10240000` | Tất cả thuộc tính của Tướng +2% | Đội xuất trận · % Công +2%, % HP +2%, % Thủ +2% | Hoạt động |
| +10 | `20190600` | Khi tấn công thường, 45% tăng 25đ Nộ cho mục tiêu đồng đội có Nộ thấp nhất | Buff `10530600` | Chưa áp dụng |
| +11 | `10480500` | Sát thương tất cả Tướng gây ra +5000 , miễn giảm sát thương +5000 | Đội xuất trận · ST cộng +5000, Miễn giảm ST +5000 | Hoạt động |
| +12 | `10490300` | HP+18000 | Bản thân · HP +18000 | Hoạt động |
| +13 | `10040600` | Đỡ +3000 | Bản thân · Đỡ +3000 | Hoạt động |
| +14 | `10500500` | Công+3000 | Bản thân · Công +3000 | Hoạt động |
| +15 | `20070500` | Khi bị tấn công, 25% giảm 25đ Nộ của kẻ công kích | Buff `10400500` | Chưa áp dụng |

## Midoriko (`12012004`)

Bậc tối đa từ HeroStepRelation +15. Bậc tài năng cao nhất trong bảng +15.

| Bậc | TAL | Hiệu ứng VN | Dữ liệu áp dụng | R7.16 |
|---:|---:|---|---|---|
| +2 | `10130200` | Công +100 | Bản thân · Công +100 | Hoạt động |
| +3 | `10030200` | Bạo Kích +1000 | Bản thân · Bạo +1000 | Hoạt động |
| +4 | `10160000` | Công của tất cả Tướng +250 | Đội xuất trận · Công +250 | Hoạt động |
| +5 | `20010000` | Khi Công, Chính Xác tăng 100% | Buff `20010000` | Chưa áp dụng |
| +6 | `10010000` | Mới bắt đầu tăng 50đ Nộ, lượt đầu có thể Nộ Công | Bản thân · Nộ +50 | Hoạt động |
| +7 | `10170000` | HP của tất cả Tướng +2500 | Đội xuất trận · HP +2500 | Hoạt động |
| +8 | `20750000` | Khi tiêu diệt mục tiêu, tiếp tục tấn công mục tiêu kế | Buff `20060000` | Chưa áp dụng |
| +9 | `10180000` | Tất cả thuộc tính của Tướng +4% | Đội xuất trận · % Công +4%, % HP +4%, % Thủ +4% | Hoạt động |
| +10 | `20501000` | Khi HP của mục tiêu thấp hơn 50%, gây ST tăng 50% | Buff `10201000` | Chưa áp dụng |
| +11 | `10481000` | Sát thương tất cả Tướng gây ra +10000 , miễn giảm sát thương +10000 | Đội xuất trận · ST cộng +10000, Miễn giảm ST +10000 | Hoạt động |
| +12 | `10490600` | HP+36000 | Bản thân · HP +36000 | Hoạt động |
| +13 | `10081000` | Chính Xác +5000 | Bản thân · Chính Xác +5000 | Hoạt động |
| +14 | `10501000` | Công+6000 | Bản thân · Công +6000 | Hoạt động |
| +15 | `20111000` | Sau mỗi lần bị tấn công, Công tăng 10%, tối đa 30% | Buff `20171000` | Chưa áp dụng |

## Taigokumaru (`12011025`)

Bậc tối đa từ HeroStepRelation +8. Bậc tài năng cao nhất trong bảng +8.

| Bậc | TAL | Hiệu ứng VN | Dữ liệu áp dụng | R7.16 |
|---:|---:|---|---|---|
| +2 | `10130120` | Công +60 | Bản thân · Công +60 | Hoạt động |
| +3 | `10030120` | Bạo Kích +600 | Bản thân · Bạo +600 | Hoạt động |
| +4 | `10250000` | Công của tất cả Tướng +80 | Đội xuất trận · Công +80 | Hoạt động |
| +5 | `20480400` | Mục tiêu của bản thân khi lượng máu cao,gây ST tăng 20% | Buff `10180400` | Chưa áp dụng |
| +6 | `10010000` | Mới bắt đầu tăng 50đ Nộ, lượt đầu có thể Nộ Công | Bản thân · Nộ +50 | Hoạt động |
| +7 | `10260000` | HP của tất cả Tướng +800 | Đội xuất trận · HP +800 | Hoạt động |
| +8 | `20440401` | Khi tấn công bị Đỡ, lần ST kế tiếp tăng 40% | Buff `20100401` | Chưa áp dụng |

## Toutousai (`12011019`)

Bậc tối đa từ HeroStepRelation +15. Bậc tài năng cao nhất trong bảng +15.

| Bậc | TAL | Hiệu ứng VN | Dữ liệu áp dụng | R7.16 |
|---:|---:|---|---|---|
| +2 | `10140160` | Thủ +80 | Bản thân · Thủ +80 | Hoạt động |
| +3 | `10040160` | Đỡ +800 | Bản thân · Đỡ +800 | Hoạt động |
| +4 | `10190000` | Công của tất cả Tướng +200 | Đội xuất trận · Công +200 | Hoạt động |
| +5 | `20050400` | Khi bị tấn công thường, gây 20% [Choáng] 1 lượt đối với kẻ công kích | Buff `20130400` | Chưa áp dụng |
| +6 | `10010000` | Mới bắt đầu tăng 50đ Nộ, lượt đầu có thể Nộ Công | Bản thân · Nộ +50 | Hoạt động |
| +7 | `10200000` | HP của tất cả Tướng +2000 | Đội xuất trận · HP +2000 | Hoạt động |
| +8 | `20550600` | Khi HP của bản thân thấp hơn 50%, chịu ST giảm 30% | Buff `10250600` | Chưa áp dụng |
| +9 | `10210000` | Tất cả thuộc tính của Tướng +3% | Đội xuất trận · % Công +3%, % HP +3%, % Thủ +3% | Hoạt động |
| +10 | `20180600` | Khi Nộ Công,  hồi HP bằng 30% ST cho bản thân | Buff `10700600` | Chưa áp dụng |
| +11 | `10480800` | Sát thương tất cả Tướng gây ra +8000 , miễn giảm sát thương +8000 | Đội xuất trận · ST cộng +8000, Miễn giảm ST +8000 | Hoạt động |
| +12 | `10490480` | HP+28800 | Bản thân · HP +28800 | Hoạt động |
| +13 | `10650870` | Kháng Bạo+4350 | Bản thân · Kháng Bạo +4350 | Hoạt động |
| +14 | `10500800` | Công+4800 | Bản thân · Công +4800 | Hoạt động |
| +15 | `20070830` | Khi bị tấn công, 42% giảm 25đ Nộ của kẻ công kích | Buff `10400830` | Chưa áp dụng |

## Jinenji (`12011013`)

Bậc tối đa từ HeroStepRelation +15. Bậc tài năng cao nhất trong bảng +15.

| Bậc | TAL | Hiệu ứng VN | Dữ liệu áp dụng | R7.16 |
|---:|---:|---|---|---|
| +2 | `10140160` | Thủ +80 | Bản thân · Thủ +80 | Hoạt động |
| +3 | `10040160` | Đỡ +800 | Bản thân · Đỡ +800 | Hoạt động |
| +4 | `10220000` | Công của tất cả Tướng +125 | Đội xuất trận · Công +125 | Hoạt động |
| +5 | `10040400` | Đỡ +2000 | Bản thân · Đỡ +2000 | Hoạt động |
| +6 | `10010000` | Mới bắt đầu tăng 50đ Nộ, lượt đầu có thể Nộ Công | Bản thân · Nộ +50 | Hoạt động |
| +7 | `10230000` | HP của tất cả Tướng +1250 | Đội xuất trận · HP +1250 | Hoạt động |
| +8 | `20450400` | Khi bị tấn công, nếu HP cao hơn kẻ công kích, nhận ST giảm 20% | Buff `10150400` | Chưa áp dụng |
| +9 | `10240000` | Tất cả thuộc tính của Tướng +2% | Đội xuất trận · % Công +2%, % HP +2%, % Thủ +2% | Hoạt động |
| +10 | `20180600` | Khi Nộ Công,  hồi HP bằng 30% ST cho bản thân | Buff `10700600` | Chưa áp dụng |
| +11 | `10480500` | Sát thương tất cả Tướng gây ra +5000 , miễn giảm sát thương +5000 | Đội xuất trận · ST cộng +5000, Miễn giảm ST +5000 | Hoạt động |
| +12 | `10490300` | HP+18000 | Bản thân · HP +18000 | Hoạt động |
| +13 | `10650600` | Kháng Bạo+3000 | Bản thân · Kháng Bạo +3000 | Hoạt động |
| +14 | `10500500` | Công+3000 | Bản thân · Công +3000 | Hoạt động |
| +15 | `20660500` | Khi Nộ Công, bỏ qua 50% Thủ của mục tiêu | Buff `10560500` | Chưa áp dụng |

## Toran (`12013021`)

Bậc tối đa từ HeroStepRelation +15. Bậc tài năng cao nhất trong bảng +15.

| Bậc | TAL | Hiệu ứng VN | Dữ liệu áp dụng | R7.16 |
|---:|---:|---|---|---|
| +2 | `10130160` | Công +80 | Bản thân · Công +80 | Hoạt động |
| +3 | `10080160` | Chính Xác +800 | Bản thân · Chính Xác +800 | Hoạt động |
| +4 | `10190000` | Công của tất cả Tướng +200 | Đội xuất trận · Công +200 | Hoạt động |
| +5 | `20480400` | Mục tiêu của bản thân khi lượng máu cao,gây ST tăng 20% | Buff `10180400` | Chưa áp dụng |
| +6 | `10010000` | Mới bắt đầu tăng 50đ Nộ, lượt đầu có thể Nộ Công | Bản thân · Nộ +50 | Hoạt động |
| +7 | `10200000` | HP của tất cả Tướng +2000 | Đội xuất trận · HP +2000 | Hoạt động |
| +8 | `20570600` | Đối với mục tiêu bị [Trúng Độc] gây ST tăng 36% | Buff `10270600` | Chưa áp dụng |
| +9 | `10210000` | Tất cả thuộc tính của Tướng +3% | Đội xuất trận · % Công +3%, % HP +3%, % Thủ +3% | Hoạt động |
| +10 | `20470600` | Khi HP của bản thân thấp hơn mục tiêu, gây ST tăng 30% | Buff `10170600` | Chưa áp dụng |
| +11 | `10480800` | Sát thương tất cả Tướng gây ra +8000 , miễn giảm sát thương +8000 | Đội xuất trận · ST cộng +8000, Miễn giảm ST +8000 | Hoạt động |
| +12 | `10490480` | HP+28800 | Bản thân · HP +28800 | Hoạt động |
| +13 | `10080870` | Chính Xác +4350 | Bản thân · Chính Xác +4350 | Hoạt động |
| +14 | `10500800` | Công+4800 | Bản thân · Công +4800 | Hoạt động |
| +15 | `20330834` | Khi Nộ Công, 83% giảm 50đ Nộ của mục tiêu | Buff `10450834` | Chưa áp dụng |

## Inu no Taishou (`12011002`)

Bậc tối đa từ HeroStepRelation +15. Bậc tài năng cao nhất trong bảng +15.

| Bậc | TAL | Hiệu ứng VN | Dữ liệu áp dụng | R7.16 |
|---:|---:|---|---|---|
| +2 | `10140200` | Thủ +100 | Bản thân · Thủ +100 | Hoạt động |
| +3 | `10040200` | Đỡ +1000 | Bản thân · Đỡ +1000 | Hoạt động |
| +4 | `10160000` | Công của tất cả Tướng +250 | Đội xuất trận · Công +250 | Hoạt động |
| +5 | `20730600` | Đỡ phản kích, gây ST bằng 75% Công | Buff `20050600` | Chưa áp dụng |
| +6 | `10010000` | Mới bắt đầu tăng 50đ Nộ, lượt đầu có thể Nộ Công | Bản thân · Nộ +50 | Hoạt động |
| +7 | `10170000` | HP của tất cả Tướng +2500 | Đội xuất trận · HP +2500 | Hoạt động |
| +8 | `20550600` | Khi HP của bản thân thấp hơn 50%, chịu ST giảm 30% | Buff `10250600` | Chưa áp dụng |
| +9 | `10180000` | Tất cả thuộc tính của Tướng +4% | Đội xuất trận · % Công +4%, % HP +4%, % Thủ +4% | Hoạt động |
| +10 | `20700000` | Hồi Sinh sau khi lần đầu Tử Vong, bản thân hồi HP bằng 150% Công | Buff `10290000` | Chưa áp dụng |
| +11 | `10481000` | Sát thương tất cả Tướng gây ra +10000 , miễn giảm sát thương +10000 | Đội xuất trận · ST cộng +10000, Miễn giảm ST +10000 | Hoạt động |
| +12 | `10490600` | HP+36000 | Bản thân · HP +36000 | Hoạt động |
| +13 | `10041000` | Đỡ +5000 | Bản thân · Đỡ +5000 | Hoạt động |
| +14 | `10501000` | Công+6000 | Bản thân · Công +6000 | Hoạt động |
| +15 | `20071000` | Khi bị tấn công, 50% giảm 25đ Nộ của kẻ công kích | Buff `10401000` | Chưa áp dụng |

## Gatenmaru (`12013031`)

Bậc tối đa từ HeroStepRelation +8. Bậc tài năng cao nhất trong bảng +8.

| Bậc | TAL | Hiệu ứng VN | Dữ liệu áp dụng | R7.16 |
|---:|---:|---|---|---|
| +2 | `10150120` | HP +600 | Bản thân · HP +600 | Hoạt động |
| +3 | `10060120` | Né +480 | Bản thân · Né +480 | Hoạt động |
| +4 | `10250000` | Công của tất cả Tướng +80 | Đội xuất trận · Công +80 | Hoạt động |
| +5 | `20360401` | Khi Nộ Công, 40% khiến mục tiêu bị [Choáng] 1 lượt | Buff `20210401` | Chưa áp dụng |
| +6 | `10010000` | Mới bắt đầu tăng 50đ Nộ, lượt đầu có thể Nộ Công | Bản thân · Nộ +50 | Hoạt động |
| +7 | `10260000` | HP của tất cả Tướng +800 | Đội xuất trận · HP +800 | Hoạt động |
| +8 | `20230401` | Khi tấn công thường, 30% giảm 25đ Nộ của mục tiêu | Buff `10500401` | Chưa áp dụng |

## Nikosen (`12012031`)

Bậc tối đa từ HeroStepRelation +8. Bậc tài năng cao nhất trong bảng +8.

| Bậc | TAL | Hiệu ứng VN | Dữ liệu áp dụng | R7.16 |
|---:|---:|---|---|---|
| +2 | `10130120` | Công +60 | Bản thân · Công +60 | Hoạt động |
| +3 | `10030120` | Bạo Kích +600 | Bản thân · Bạo +600 | Hoạt động |
| +4 | `10250000` | Công của tất cả Tướng +80 | Đội xuất trận · Công +80 | Hoạt động |
| +5 | `20480400` | Mục tiêu của bản thân khi lượng máu cao,gây ST tăng 20% | Buff `10180400` | Chưa áp dụng |
| +6 | `10010000` | Mới bắt đầu tăng 50đ Nộ, lượt đầu có thể Nộ Công | Bản thân · Nộ +50 | Hoạt động |
| +7 | `10260000` | HP của tất cả Tướng +800 | Đội xuất trận · HP +800 | Hoạt động |
| +8 | `20440404` | Khi tấn công bị Đỡ, lần ST kế tiếp tăng 27% | Buff `20100404` | Chưa áp dụng |

## Hiten (`12012015`)

Bậc tối đa từ HeroStepRelation +15. Bậc tài năng cao nhất trong bảng +15.

| Bậc | TAL | Hiệu ứng VN | Dữ liệu áp dụng | R7.16 |
|---:|---:|---|---|---|
| +2 | `10130160` | Công +80 | Bản thân · Công +80 | Hoạt động |
| +3 | `10080160` | Chính Xác +800 | Bản thân · Chính Xác +800 | Hoạt động |
| +4 | `10190000` | Công của tất cả Tướng +200 | Đội xuất trận · Công +200 | Hoạt động |
| +5 | `10030400` | Bạo Kích +2000 | Bản thân · Bạo +2000 | Hoạt động |
| +6 | `10010000` | Mới bắt đầu tăng 50đ Nộ, lượt đầu có thể Nộ Công | Bản thân · Nộ +50 | Hoạt động |
| +7 | `10200000` | HP của tất cả Tướng +2000 | Đội xuất trận · HP +2000 | Hoạt động |
| +8 | `20110600` | Sau mỗi lần bị tấn công, Công tăng 6%, tối đa 18% | Buff `20170600` | Chưa áp dụng |
| +9 | `10210000` | Tất cả thuộc tính của Tướng +3% | Đội xuất trận · % Công +3%, % HP +3%, % Thủ +3% | Hoạt động |
| +10 | `20470600` | Khi HP của bản thân thấp hơn mục tiêu, gây ST tăng 30% | Buff `10170600` | Chưa áp dụng |
| +11 | `10480800` | Sát thương tất cả Tướng gây ra +8000 , miễn giảm sát thương +8000 | Đội xuất trận · ST cộng +8000, Miễn giảm ST +8000 | Hoạt động |
| +12 | `10490480` | HP+28800 | Bản thân · HP +28800 | Hoạt động |
| +13 | `10030870` | Bạo Kích +4350 | Bản thân · Bạo +4350 | Hoạt động |
| +14 | `10500800` | Công+4800 | Bản thân · Công +4800 | Hoạt động |
| +15 | `20320836` | Khi Nộ Công, 31% giảm 50đ Nộ của mục tiêu | Buff `10510836` | Chưa áp dụng |

## Bà Kaede (`12011012`)

Bậc tối đa từ HeroStepRelation +15. Bậc tài năng cao nhất trong bảng +15.

| Bậc | TAL | Hiệu ứng VN | Dữ liệu áp dụng | R7.16 |
|---:|---:|---|---|---|
| +2 | `10090160` | Điểm Trị Liệu +200 | Bản thân · Trị Liệu +200 | Hoạt động |
| +3 | `10060160` | Né +640 | Bản thân · Né +640 | Hoạt động |
| +4 | `10220000` | Công của tất cả Tướng +125 | Đội xuất trận · Công +125 | Hoạt động |
| +5 | `20640400` | Ra trận lần 1,2,3, khi bản thân chịu ST giảm 30% | Buff `10140400` | Chưa áp dụng |
| +6 | `10010000` | Mới bắt đầu tăng 50đ Nộ, lượt đầu có thể Nộ Công | Bản thân · Nộ +50 | Hoạt động |
| +7 | `10230000` | HP của tất cả Tướng +1250 | Đội xuất trận · HP +1250 | Hoạt động |
| +8 | `10100400` | Điểm Trị Liệu +12% | Bản thân · % Trị Liệu +20% | Hoạt động |
| +9 | `10240000` | Tất cả thuộc tính của Tướng +2% | Đội xuất trận · % Công +2%, % HP +2%, % Thủ +2% | Hoạt động |
| +10 | `20620600` | Khi tử vong, hồi HP bằng 45% Công cho mục tiêu đồng đội tối đa đã mất máu | Buff `10330600` | Chưa áp dụng |
| +11 | `10480500` | Sát thương tất cả Tướng gây ra +5000 , miễn giảm sát thương +5000 | Đội xuất trận · ST cộng +5000, Miễn giảm ST +5000 | Hoạt động |
| +12 | `10490300` | HP+18000 | Bản thân · HP +18000 | Hoạt động |
| +13 | `10650600` | Kháng Bạo+3000 | Bản thân · Kháng Bạo +3000 | Hoạt động |
| +14 | `10500500` | Công+3000 | Bản thân · Công +3000 | Hoạt động |
| +15 | `10020500` | Chịu ST giảm 15% | Bản thân · % miễn giảm ST +15% | Hoạt động |

## Gora (`12012023`)

Bậc tối đa từ HeroStepRelation +15. Bậc tài năng cao nhất trong bảng +15.

| Bậc | TAL | Hiệu ứng VN | Dữ liệu áp dụng | R7.16 |
|---:|---:|---|---|---|
| +2 | `10130160` | Công +80 | Bản thân · Công +80 | Hoạt động |
| +3 | `10080160` | Chính Xác +800 | Bản thân · Chính Xác +800 | Hoạt động |
| +4 | `10220000` | Công của tất cả Tướng +125 | Đội xuất trận · Công +125 | Hoạt động |
| +5 | `10030400` | Bạo Kích +2000 | Bản thân · Bạo +2000 | Hoạt động |
| +6 | `10010000` | Mới bắt đầu tăng 50đ Nộ, lượt đầu có thể Nộ Công | Bản thân · Nộ +50 | Hoạt động |
| +7 | `10230000` | HP của tất cả Tướng +1250 | Đội xuất trận · HP +1250 | Hoạt động |
| +8 | `20280401` | Khi tấn công thường, 20% khiến mục tiêu [Tê Liệt] 1 lượt | Buff `20510401` | Chưa áp dụng |
| +9 | `10240000` | Tất cả thuộc tính của Tướng +2% | Đội xuất trận · % Công +2%, % HP +2%, % Thủ +2% | Hoạt động |
| +10 | `20480600` | Mục tiêu của bản thân khi lượng máu cao,gây ST tăng 30% | Buff `10180600` | Chưa áp dụng |
| +11 | `10480500` | Sát thương tất cả Tướng gây ra +5000 , miễn giảm sát thương +5000 | Đội xuất trận · ST cộng +5000, Miễn giảm ST +5000 | Hoạt động |
| +12 | `10490300` | HP+18000 | Bản thân · HP +18000 | Hoạt động |
| +13 | `10080600` | Chính Xác +3000 | Bản thân · Chính Xác +3000 | Hoạt động |
| +14 | `10500500` | Công+3000 | Bản thân · Công +3000 | Hoạt động |
| +15 | `20110500` | Sau mỗi lần bị tấn công, Công tăng 5%, tối đa 15% | Buff `20170500` | Chưa áp dụng |

## Kouga (`12011008`)

Bậc tối đa từ HeroStepRelation +15. Bậc tài năng cao nhất trong bảng +15.

| Bậc | TAL | Hiệu ứng VN | Dữ liệu áp dụng | R7.16 |
|---:|---:|---|---|---|
| +2 | `10150160` | HP +800 | Bản thân · HP +800 | Hoạt động |
| +3 | `10060160` | Né +640 | Bản thân · Né +640 | Hoạt động |
| +4 | `10190000` | Công của tất cả Tướng +200 | Đội xuất trận · Công +200 | Hoạt động |
| +5 | `20170400` | Khi Nộ Công, hồi HP bằng 20% ST cho mục tiêu đồng đội tối đa đã mất máu | Buff `10670400` | Chưa áp dụng |
| +6 | `10010000` | Mới bắt đầu tăng 50đ Nộ, lượt đầu có thể Nộ Công | Bản thân · Nộ +50 | Hoạt động |
| +7 | `10200000` | HP của tất cả Tướng +2000 | Đội xuất trận · HP +2000 | Hoạt động |
| +8 | `20230601` | Khi tấn công thường, 45% giảm 25đ Nộ của mục tiêu | Buff `10500601` | Chưa áp dụng |
| +9 | `10210000` | Tất cả thuộc tính của Tướng +3% | Đội xuất trận · % Công +3%, % HP +3%, % Thủ +3% | Hoạt động |
| +10 | `20430800` | Khi Né, 40% tăng 25đ Nộ cho tất cả đồng đội | Buff `10380800` | Chưa áp dụng |
| +11 | `10480800` | Sát thương tất cả Tướng gây ra +8000 , miễn giảm sát thương +8000 | Đội xuất trận · ST cộng +8000, Miễn giảm ST +8000 | Hoạt động |
| +12 | `10490480` | HP+28800 | Bản thân · HP +28800 | Hoạt động |
| +13 | `10030870` | Bạo Kích +4350 | Bản thân · Bạo +4350 | Hoạt động |
| +14 | `10500800` | Công+4800 | Bản thân · Công +4800 | Hoạt động |
| +15 | `10020830` | Chịu ST giảm 25% | Bản thân · % miễn giảm ST +24.9% | Hoạt động |

## Kohaku (`12012008`)

Bậc tối đa từ HeroStepRelation +15. Bậc tài năng cao nhất trong bảng +15.

| Bậc | TAL | Hiệu ứng VN | Dữ liệu áp dụng | R7.16 |
|---:|---:|---|---|---|
| +2 | `10130160` | Công +80 | Bản thân · Công +80 | Hoạt động |
| +3 | `10030160` | Bạo Kích +800 | Bản thân · Bạo +800 | Hoạt động |
| +4 | `10190000` | Công của tất cả Tướng +200 | Đội xuất trận · Công +200 | Hoạt động |
| +5 | `20480400` | Mục tiêu của bản thân khi lượng máu cao,gây ST tăng 20% | Buff `10180400` | Chưa áp dụng |
| +6 | `10010000` | Mới bắt đầu tăng 50đ Nộ, lượt đầu có thể Nộ Công | Bản thân · Nộ +50 | Hoạt động |
| +7 | `10200000` | HP của tất cả Tướng +2000 | Đội xuất trận · HP +2000 | Hoạt động |
| +8 | `10070600` | Bạo Kích +1500, ST Bạo +3000 | Bản thân · Bạo +1500, Tất Sát +3000 | Hoạt động |
| +9 | `10210000` | Tất cả thuộc tính của Tướng +3% | Đội xuất trận · % Công +3%, % HP +3%, % Thủ +3% | Hoạt động |
| +10 | `20390000` | Khi Bạo Kích, tăng thêm 25đ Nộ | Buff `10350000` | Hoạt động |
| +11 | `10480800` | Sát thương tất cả Tướng gây ra +8000 , miễn giảm sát thương +8000 | Đội xuất trận · ST cộng +8000, Miễn giảm ST +8000 | Hoạt động |
| +12 | `10490480` | HP+28800 | Bản thân · HP +28800 | Hoạt động |
| +13 | `10080870` | Chính Xác +4350 | Bản thân · Chính Xác +4350 | Hoạt động |
| +14 | `10500800` | Công+4800 | Bản thân · Công +4800 | Hoạt động |
| +15 | `21220830` | Khi đánh kỹ năng Nộ, 66% tăng 50đ Nộ cho bản thân | Buff `11110830` | Chưa áp dụng |

## Kao (`12012032`)

Bậc tối đa từ HeroStepRelation +8. Bậc tài năng cao nhất trong bảng +8.

| Bậc | TAL | Hiệu ứng VN | Dữ liệu áp dụng | R7.16 |
|---:|---:|---|---|---|
| +2 | `10140120` | Thủ +60 | Bản thân · Thủ +60 | Hoạt động |
| +3 | `10060120` | Né +480 | Bản thân · Né +480 | Hoạt động |
| +4 | `10250000` | Công của tất cả Tướng +80 | Đội xuất trận · Công +80 | Hoạt động |
| +5 | `20650000` | Lần đầu bị tấn công, tỷ lệ Né +100% | Buff `10120000` | Chưa áp dụng |
| +6 | `10010000` | Mới bắt đầu tăng 50đ Nộ, lượt đầu có thể Nộ Công | Bản thân · Nộ +50 | Hoạt động |
| +7 | `10260000` | HP của tất cả Tướng +800 | Đội xuất trận · HP +800 | Hoạt động |
| +8 | `20420400` | Khi Né, 60% tăng 25đ Nộ | Buff `10370400` | Chưa áp dụng |

## Kaijinbo (`12012028`)

Bậc tối đa từ HeroStepRelation +8. Bậc tài năng cao nhất trong bảng +8.

| Bậc | TAL | Hiệu ứng VN | Dữ liệu áp dụng | R7.16 |
|---:|---:|---|---|---|
| +2 | `10150120` | HP +600 | Bản thân · HP +600 | Hoạt động |
| +3 | `10060120` | Né +480 | Bản thân · Né +480 | Hoạt động |
| +4 | `10250000` | Công của tất cả Tướng +80 | Đội xuất trận · Công +80 | Hoạt động |
| +5 | `20360401` | Khi Nộ Công, 40% khiến mục tiêu bị [Choáng] 1 lượt | Buff `20210401` | Chưa áp dụng |
| +6 | `10010000` | Mới bắt đầu tăng 50đ Nộ, lượt đầu có thể Nộ Công | Bản thân · Nộ +50 | Hoạt động |
| +7 | `10260000` | HP của tất cả Tướng +800 | Đội xuất trận · HP +800 | Hoạt động |
| +8 | `20230401` | Khi tấn công thường, 30% giảm 25đ Nộ của mục tiêu | Buff `10500401` | Chưa áp dụng |

## Kinka (`12012029`)

Bậc tối đa từ HeroStepRelation +8. Bậc tài năng cao nhất trong bảng +8.

| Bậc | TAL | Hiệu ứng VN | Dữ liệu áp dụng | R7.16 |
|---:|---:|---|---|---|
| +2 | `10150120` | HP +600 | Bản thân · HP +600 | Hoạt động |
| +3 | `10060120` | Né +480 | Bản thân · Né +480 | Hoạt động |
| +4 | `10250000` | Công của tất cả Tướng +80 | Đội xuất trận · Công +80 | Hoạt động |
| +5 | `20460400` | Khi bị tấn công, nếu HP thấp hơn kẻ công kích, chịu ST giảm 20% | Buff `10160400` | Chưa áp dụng |
| +6 | `10010000` | Mới bắt đầu tăng 50đ Nộ, lượt đầu có thể Nộ Công | Bản thân · Nộ +50 | Hoạt động |
| +7 | `10260000` | HP của tất cả Tướng +800 | Đội xuất trận · HP +800 | Hoạt động |
| +8 | `10100400` | Điểm Trị Liệu +12% | Bản thân · % Trị Liệu +20% | Hoạt động |

## Kikyo (`12011003`)

Bậc tối đa từ HeroStepRelation +15. Bậc tài năng cao nhất trong bảng +15.

| Bậc | TAL | Hiệu ứng VN | Dữ liệu áp dụng | R7.16 |
|---:|---:|---|---|---|
| +2 | `10130200` | Công +100 | Bản thân · Công +100 | Hoạt động |
| +3 | `10080200` | Chính Xác +1000 | Bản thân · Chính Xác +1000 | Hoạt động |
| +4 | `10160000` | Công của tất cả Tướng +250 | Đội xuất trận · Công +250 | Hoạt động |
| +5 | `10030600` | Bạo Kích +3000 | Bản thân · Bạo +3000 | Hoạt động |
| +6 | `10010000` | Mới bắt đầu tăng 50đ Nộ, lượt đầu có thể Nộ Công | Bản thân · Nộ +50 | Hoạt động |
| +7 | `10170000` | HP của tất cả Tướng +2500 | Đội xuất trận · HP +2500 | Hoạt động |
| +8 | `20530600` | Khi HP của bản thân cao hơn 50%, gây ST tăng 30% | Buff `10230600` | Chưa áp dụng |
| +9 | `10180000` | Tất cả thuộc tính của Tướng +4% | Đội xuất trận · % Công +4%, % HP +4%, % Thủ +4% | Hoạt động |
| +10 | `10051000` | Né +3000 | Bản thân · Né +3000 | Hoạt động |
| +11 | `10481000` | Sát thương tất cả Tướng gây ra +10000 , miễn giảm sát thương +10000 | Đội xuất trận · ST cộng +10000, Miễn giảm ST +10000 | Hoạt động |
| +12 | `10490600` | HP+36000 | Bản thân · HP +36000 | Hoạt động |
| +13 | `10641000` | Phá Kích+5000 | Bản thân · Phá Kích +5000 | Hoạt động |
| +14 | `10501000` | Công+6000 | Bản thân · Công +6000 | Hoạt động |
| +15 | `10021000` | Chịu ST giảm 30% | Bản thân · % miễn giảm ST +30% | Hoạt động |

## Renkotsu (`12013015`)

Bậc tối đa từ HeroStepRelation +15. Bậc tài năng cao nhất trong bảng +15.

| Bậc | TAL | Hiệu ứng VN | Dữ liệu áp dụng | R7.16 |
|---:|---:|---|---|---|
| +2 | `10130160` | Công +80 | Bản thân · Công +80 | Hoạt động |
| +3 | `10030160` | Bạo Kích +800 | Bản thân · Bạo +800 | Hoạt động |
| +4 | `10220000` | Công của tất cả Tướng +125 | Đội xuất trận · Công +125 | Hoạt động |
| +5 | `20480400` | Mục tiêu của bản thân khi lượng máu cao,gây ST tăng 20% | Buff `10180400` | Chưa áp dụng |
| +6 | `10010000` | Mới bắt đầu tăng 50đ Nộ, lượt đầu có thể Nộ Công | Bản thân · Nộ +50 | Hoạt động |
| +7 | `10230000` | HP của tất cả Tướng +1250 | Đội xuất trận · HP +1250 | Hoạt động |
| +8 | `20630400` | Ra trận lần 1 khi tấn công, ST gây ra tăng 50% | Buff `10130400` | Chưa áp dụng |
| +9 | `10240000` | Tất cả thuộc tính của Tướng +2% | Đội xuất trận · % Công +2%, % HP +2%, % Thủ +2% | Hoạt động |
| +10 | `10030600` | Bạo Kích +3000 | Bản thân · Bạo +3000 | Hoạt động |
| +11 | `10480500` | Sát thương tất cả Tướng gây ra +5000 , miễn giảm sát thương +5000 | Đội xuất trận · ST cộng +5000, Miễn giảm ST +5000 | Hoạt động |
| +12 | `10490300` | HP+18000 | Bản thân · HP +18000 | Hoạt động |
| +13 | `10640600` | Phá Kích+3000 | Bản thân · Phá Kích +3000 | Hoạt động |
| +14 | `10500500` | Công+3000 | Bản thân · Công +3000 | Hoạt động |
| +15 | `21070500` | Kỹ Năng ST tăng 25% | Buff `10590500` | Chưa áp dụng |

## Ryukotsusei (`12012018`)

Bậc tối đa từ HeroStepRelation +15. Bậc tài năng cao nhất trong bảng +15.

| Bậc | TAL | Hiệu ứng VN | Dữ liệu áp dụng | R7.16 |
|---:|---:|---|---|---|
| +2 | `10130160` | Công +80 | Bản thân · Công +80 | Hoạt động |
| +3 | `10030160` | Bạo Kích +800 | Bản thân · Bạo +800 | Hoạt động |
| +4 | `10220000` | Công của tất cả Tướng +125 | Đội xuất trận · Công +125 | Hoạt động |
| +5 | `10030400` | Bạo Kích +2000 | Bản thân · Bạo +2000 | Hoạt động |
| +6 | `10010000` | Mới bắt đầu tăng 50đ Nộ, lượt đầu có thể Nộ Công | Bản thân · Nộ +50 | Hoạt động |
| +7 | `10230000` | HP của tất cả Tướng +1250 | Đội xuất trận · HP +1250 | Hoạt động |
| +8 | `20720400` | Khi tấn công thường, gây thêm 40% ST cho mục tiêu lân cận | Buff `20590400` | Chưa áp dụng |
| +9 | `10240000` | Tất cả thuộc tính của Tướng +2% | Đội xuất trận · % Công +2%, % HP +2%, % Thủ +2% | Hoạt động |
| +10 | `20630600` | Ra trận lần 1 khi tấn công, ST gây ra tăng 75% | Buff `10130600` | Chưa áp dụng |
| +11 | `10480500` | Sát thương tất cả Tướng gây ra +5000 , miễn giảm sát thương +5000 | Đội xuất trận · ST cộng +5000, Miễn giảm ST +5000 | Hoạt động |
| +12 | `10490300` | HP+18000 | Bản thân · HP +18000 | Hoạt động |
| +13 | `10070600` | Bạo Kích +1500, ST Bạo +3000 | Bản thân · Bạo +1500, Tất Sát +3000 | Hoạt động |
| +14 | `10500500` | Công+3000 | Bản thân · Công +3000 | Hoạt động |
| +15 | `21240500` | Bỏ qua 30% Thủ của mục tiêu | Buff `11130500` | Chưa áp dụng |

## Ryura (`12012020`)

Bậc tối đa từ HeroStepRelation +15. Bậc tài năng cao nhất trong bảng +15.

| Bậc | TAL | Hiệu ứng VN | Dữ liệu áp dụng | R7.16 |
|---:|---:|---|---|---|
| +2 | `10140160` | Thủ +80 | Bản thân · Thủ +80 | Hoạt động |
| +3 | `10040160` | Đỡ +800 | Bản thân · Đỡ +800 | Hoạt động |
| +4 | `10190000` | Công của tất cả Tướng +200 | Đội xuất trận · Công +200 | Hoạt động |
| +5 | `10040400` | Đỡ +2000 | Bản thân · Đỡ +2000 | Hoạt động |
| +6 | `10010000` | Mới bắt đầu tăng 50đ Nộ, lượt đầu có thể Nộ Công | Bản thân · Nộ +50 | Hoạt động |
| +7 | `10200000` | HP của tất cả Tướng +2000 | Đội xuất trận · HP +2000 | Hoạt động |
| +8 | `20730600` | Đỡ phản kích, gây ST bằng 75% Công | Buff `20050600` | Chưa áp dụng |
| +9 | `10210000` | Tất cả thuộc tính của Tướng +3% | Đội xuất trận · % Công +3%, % HP +3%, % Thủ +3% | Hoạt động |
| +10 | `10020800` | Chịu ST giảm 24% | Bản thân · % miễn giảm ST +24% | Hoạt động |
| +11 | `10480800` | Sát thương tất cả Tướng gây ra +8000 , miễn giảm sát thương +8000 | Đội xuất trận · ST cộng +8000, Miễn giảm ST +8000 | Hoạt động |
| +12 | `10490480` | HP+28800 | Bản thân · HP +28800 | Hoạt động |
| +13 | `10040870` | Đỡ +4350 | Bản thân · Đỡ +4350 | Hoạt động |
| +14 | `10500800` | Công+4800 | Bản thân · Công +4800 | Hoạt động |
| +15 | `20080830` | Khi bị tấn công thường, gây 25% [Choáng] 1 lượt đối với kẻ công kích | Buff `20140830` | Chưa áp dụng |

## Ryujin (`12013032`)

Bậc tối đa từ HeroStepRelation +8. Bậc tài năng cao nhất trong bảng +8.

| Bậc | TAL | Hiệu ứng VN | Dữ liệu áp dụng | R7.16 |
|---:|---:|---|---|---|
| +2 | `10150120` | HP +600 | Bản thân · HP +600 | Hoạt động |
| +3 | `10060120` | Né +480 | Bản thân · Né +480 | Hoạt động |
| +4 | `10250000` | Công của tất cả Tướng +80 | Đội xuất trận · Công +80 | Hoạt động |
| +5 | `10030400` | Bạo Kích +2000 | Bản thân · Bạo +2000 | Hoạt động |
| +6 | `10010000` | Mới bắt đầu tăng 50đ Nộ, lượt đầu có thể Nộ Công | Bản thân · Nộ +50 | Hoạt động |
| +7 | `10260000` | HP của tất cả Tướng +800 | Đội xuất trận · HP +800 | Hoạt động |
| +8 | `10100400` | Điểm Trị Liệu +12% | Bản thân · % Trị Liệu +20% | Hoạt động |

## Menomaru (`12013022`)

Bậc tối đa từ HeroStepRelation +15. Bậc tài năng cao nhất trong bảng +15.

| Bậc | TAL | Hiệu ứng VN | Dữ liệu áp dụng | R7.16 |
|---:|---:|---|---|---|
| +2 | `10130160` | Công +80 | Bản thân · Công +80 | Hoạt động |
| +3 | `10030160` | Bạo Kích +800 | Bản thân · Bạo +800 | Hoạt động |
| +4 | `10220000` | Công của tất cả Tướng +125 | Đội xuất trận · Công +125 | Hoạt động |
| +5 | `20630400` | Ra trận lần 1 khi tấn công, ST gây ra tăng 50% | Buff `10130400` | Chưa áp dụng |
| +6 | `10010000` | Mới bắt đầu tăng 50đ Nộ, lượt đầu có thể Nộ Công | Bản thân · Nộ +50 | Hoạt động |
| +7 | `10230000` | HP của tất cả Tướng +1250 | Đội xuất trận · HP +1250 | Hoạt động |
| +8 | `10070400` | Bạo Kích +1000, ST Bạo +2000 | Bản thân · Bạo +1000, Tất Sát +2000 | Hoạt động |
| +9 | `10240000` | Tất cả thuộc tính của Tướng +2% | Đội xuất trận · % Công +2%, % HP +2%, % Thủ +2% | Hoạt động |
| +10 | `20520600` | Khi HP của bản thân thấp hơn 50%, gây ST tăng 30% | Buff `10220600` | Chưa áp dụng |
| +11 | `10480500` | Sát thương tất cả Tướng gây ra +5000 , miễn giảm sát thương +5000 | Đội xuất trận · ST cộng +5000, Miễn giảm ST +5000 | Hoạt động |
| +12 | `10490300` | HP+18000 | Bản thân · HP +18000 | Hoạt động |
| +13 | `10650600` | Kháng Bạo+3000 | Bản thân · Kháng Bạo +3000 | Hoạt động |
| +14 | `10500500` | Công+3000 | Bản thân · Công +3000 | Hoạt động |
| +15 | `20640500` | Ra trận lần 1,2,3, khi bản thân chịu ST giảm 38% | Buff `10140500` | Chưa áp dụng |

## Bankotsu (`12013016`)

Bậc tối đa từ HeroStepRelation +15. Bậc tài năng cao nhất trong bảng +15.

| Bậc | TAL | Hiệu ứng VN | Dữ liệu áp dụng | R7.16 |
|---:|---:|---|---|---|
| +2 | `10130160` | Công +80 | Bản thân · Công +80 | Hoạt động |
| +3 | `10030160` | Bạo Kích +800 | Bản thân · Bạo +800 | Hoạt động |
| +4 | `10190000` | Công của tất cả Tướng +200 | Đội xuất trận · Công +200 | Hoạt động |
| +5 | `10030400` | Bạo Kích +2000 | Bản thân · Bạo +2000 | Hoạt động |
| +6 | `10010000` | Mới bắt đầu tăng 50đ Nộ, lượt đầu có thể Nộ Công | Bản thân · Nộ +50 | Hoạt động |
| +7 | `10200000` | HP của tất cả Tướng +2000 | Đội xuất trận · HP +2000 | Hoạt động |
| +8 | `20440602` | Khi tấn công bị Đỡ, lần ST kế tiếp tăng 50% | Buff `20100602` | Chưa áp dụng |
| +9 | `10210000` | Tất cả thuộc tính của Tướng +3% | Đội xuất trận · % Công +3%, % HP +3%, % Thủ +3% | Hoạt động |
| +10 | `20520600` | Khi HP của bản thân thấp hơn 50%, gây ST tăng 30% | Buff `10220600` | Chưa áp dụng |
| +11 | `10480800` | Sát thương tất cả Tướng gây ra +8000 , miễn giảm sát thương +8000 | Đội xuất trận · ST cộng +8000, Miễn giảm ST +8000 | Hoạt động |
| +12 | `10490480` | HP+28800 | Bản thân · HP +28800 | Hoạt động |
| +13 | `10080870` | Chính Xác +4350 | Bản thân · Chính Xác +4350 | Hoạt động |
| +14 | `10500800` | Công+4800 | Bản thân · Công +4800 | Hoạt động |
| +15 | `20660830` | Khi Nộ Công, bỏ qua 83% Thủ của mục tiêu | Buff `10560830` | Chưa áp dụng |

## Manten (`12012014`)

Bậc tối đa từ HeroStepRelation +15. Bậc tài năng cao nhất trong bảng +15.

| Bậc | TAL | Hiệu ứng VN | Dữ liệu áp dụng | R7.16 |
|---:|---:|---|---|---|
| +2 | `10130160` | Công +80 | Bản thân · Công +80 | Hoạt động |
| +3 | `10030160` | Bạo Kích +800 | Bản thân · Bạo +800 | Hoạt động |
| +4 | `10190000` | Công của tất cả Tướng +200 | Đội xuất trận · Công +200 | Hoạt động |
| +5 | `20040000` | Khi tiêu diệt mục tiêu, tăng thêm 25đ Nộ | Buff `10280000` | Chưa áp dụng |
| +6 | `10010000` | Mới bắt đầu tăng 50đ Nộ, lượt đầu có thể Nộ Công | Bản thân · Nộ +50 | Hoạt động |
| +7 | `10200000` | HP của tất cả Tướng +2000 | Đội xuất trận · HP +2000 | Hoạt động |
| +8 | `20630600` | Ra trận lần 1 khi tấn công, ST gây ra tăng 75% | Buff `10130600` | Chưa áp dụng |
| +9 | `10210000` | Tất cả thuộc tính của Tướng +3% | Đội xuất trận · % Công +3%, % HP +3%, % Thủ +3% | Hoạt động |
| +10 | `20480600` | Mục tiêu của bản thân khi lượng máu cao,gây ST tăng 30% | Buff `10180600` | Chưa áp dụng |
| +11 | `10480800` | Sát thương tất cả Tướng gây ra +8000 , miễn giảm sát thương +8000 | Đội xuất trận · ST cộng +8000, Miễn giảm ST +8000 | Hoạt động |
| +12 | `10490480` | HP+28800 | Bản thân · HP +28800 | Hoạt động |
| +13 | `10030870` | Bạo Kích +4350 | Bản thân · Bạo +4350 | Hoạt động |
| +14 | `10500800` | Công+4800 | Bản thân · Công +4800 | Hoạt động |
| +15 | `20980834` | Khi đánh kỹ năng Nộ, 100% khiến mục tiêu nhận thêm 55% ST trong 1 lượt | Buff `20540834` | Chưa áp dụng |

## Mushin (`12011016`)

Bậc tối đa từ HeroStepRelation +15. Bậc tài năng cao nhất trong bảng +15.

| Bậc | TAL | Hiệu ứng VN | Dữ liệu áp dụng | R7.16 |
|---:|---:|---|---|---|
| +2 | `10140160` | Thủ +80 | Bản thân · Thủ +80 | Hoạt động |
| +3 | `10040160` | Đỡ +800 | Bản thân · Đỡ +800 | Hoạt động |
| +4 | `10220000` | Công của tất cả Tướng +125 | Đội xuất trận · Công +125 | Hoạt động |
| +5 | `20450400` | Khi bị tấn công, nếu HP cao hơn kẻ công kích, nhận ST giảm 20% | Buff `10150400` | Chưa áp dụng |
| +6 | `10010000` | Mới bắt đầu tăng 50đ Nộ, lượt đầu có thể Nộ Công | Bản thân · Nộ +50 | Hoạt động |
| +7 | `10230000` | HP của tất cả Tướng +1250 | Đội xuất trận · HP +1250 | Hoạt động |
| +8 | `10040400` | Đỡ +2000 | Bản thân · Đỡ +2000 | Hoạt động |
| +9 | `10240000` | Tất cả thuộc tính của Tướng +2% | Đội xuất trận · % Công +2%, % HP +2%, % Thủ +2% | Hoạt động |
| +10 | `20150600` | Khi tấn công thường, hồi HP bằng 45% ST cho bản thân | Buff `10710600` | Chưa áp dụng |
| +11 | `10480500` | Sát thương tất cả Tướng gây ra +5000 , miễn giảm sát thương +5000 | Đội xuất trận · ST cộng +5000, Miễn giảm ST +5000 | Hoạt động |
| +12 | `10490300` | HP+18000 | Bản thân · HP +18000 | Hoạt động |
| +13 | `10040600` | Đỡ +3000 | Bản thân · Đỡ +3000 | Hoạt động |
| +14 | `10500500` | Công+3000 | Bản thân · Công +3000 | Hoạt động |
| +15 | `10020500` | Chịu ST giảm 15% | Bản thân · % miễn giảm ST +15% | Hoạt động |

## Miroku (`12011006`)

Bậc tối đa từ HeroStepRelation +15. Bậc tài năng cao nhất trong bảng +15.

| Bậc | TAL | Hiệu ứng VN | Dữ liệu áp dụng | R7.16 |
|---:|---:|---|---|---|
| +2 | `10140160` | Thủ +80 | Bản thân · Thủ +80 | Hoạt động |
| +3 | `10040160` | Đỡ +800 | Bản thân · Đỡ +800 | Hoạt động |
| +4 | `10190000` | Công của tất cả Tướng +200 | Đội xuất trận · Công +200 | Hoạt động |
| +5 | `20360401` | Khi Nộ Công, 40% khiến mục tiêu bị [Choáng] 1 lượt | Buff `20210401` | Chưa áp dụng |
| +6 | `10010000` | Mới bắt đầu tăng 50đ Nộ, lượt đầu có thể Nộ Công | Bản thân · Nộ +50 | Hoạt động |
| +7 | `10200000` | HP của tất cả Tướng +2000 | Đội xuất trận · HP +2000 | Hoạt động |
| +8 | `20730600` | Đỡ phản kích, gây ST bằng 75% Công | Buff `20050600` | Chưa áp dụng |
| +9 | `10210000` | Tất cả thuộc tính của Tướng +3% | Đội xuất trận · % Công +3%, % HP +3%, % Thủ +3% | Hoạt động |
| +10 | `20450800` | Khi bị tấn công, nếu HP cao hơn kẻ công kích, nhận ST giảm 40% | Buff `10150800` | Chưa áp dụng |
| +11 | `10480800` | Sát thương tất cả Tướng gây ra +8000 , miễn giảm sát thương +8000 | Đội xuất trận · ST cộng +8000, Miễn giảm ST +8000 | Hoạt động |
| +12 | `10490480` | HP+28800 | Bản thân · HP +28800 | Hoạt động |
| +13 | `10650870` | Kháng Bạo+4350 | Bản thân · Kháng Bạo +4350 | Hoạt động |
| +14 | `10500800` | Công+4800 | Bản thân · Công +4800 | Hoạt động |
| +15 | `20070830` | Khi bị tấn công, 42% giảm 25đ Nộ của kẻ công kích | Buff `10400830` | Chưa áp dụng |

## Ông Myoga (`12011010`)

Bậc tối đa từ HeroStepRelation +15. Bậc tài năng cao nhất trong bảng +15.

| Bậc | TAL | Hiệu ứng VN | Dữ liệu áp dụng | R7.16 |
|---:|---:|---|---|---|
| +2 | `10130160` | Công +80 | Bản thân · Công +80 | Hoạt động |
| +3 | `10030160` | Bạo Kích +800 | Bản thân · Bạo +800 | Hoạt động |
| +4 | `10190000` | Công của tất cả Tướng +200 | Đội xuất trận · Công +200 | Hoạt động |
| +5 | `20630400` | Ra trận lần 1 khi tấn công, ST gây ra tăng 50% | Buff `10130400` | Chưa áp dụng |
| +6 | `10010000` | Mới bắt đầu tăng 50đ Nộ, lượt đầu có thể Nộ Công | Bản thân · Nộ +50 | Hoạt động |
| +7 | `10200000` | HP của tất cả Tướng +2000 | Đội xuất trận · HP +2000 | Hoạt động |
| +8 | `20470600` | Khi HP của bản thân thấp hơn mục tiêu, gây ST tăng 30% | Buff `10170600` | Chưa áp dụng |
| +9 | `10210000` | Tất cả thuộc tính của Tướng +3% | Đội xuất trận · % Công +3%, % HP +3%, % Thủ +3% | Hoạt động |
| +10 | `20600600` | Khi tử vong, gây ST bằng 60% Công cho toàn bộ địch | Buff `10310600` | Chưa áp dụng |
| +11 | `10480800` | Sát thương tất cả Tướng gây ra +8000 , miễn giảm sát thương +8000 | Đội xuất trận · ST cộng +8000, Miễn giảm ST +8000 | Hoạt động |
| +12 | `10490480` | HP+28800 | Bản thân · HP +28800 | Hoạt động |
| +13 | `10080870` | Chính Xác +4350 | Bản thân · Chính Xác +4350 | Hoạt động |
| +14 | `10500800` | Công+4800 | Bản thân · Công +4800 | Hoạt động |
| +15 | `21070830` | Kỹ Năng ST tăng 42% | Buff `10590830` | Chưa áp dụng |

## Meioju (`12013033`)

Bậc tối đa từ HeroStepRelation +8. Bậc tài năng cao nhất trong bảng +8.

| Bậc | TAL | Hiệu ứng VN | Dữ liệu áp dụng | R7.16 |
|---:|---:|---|---|---|
| +2 | `10140120` | Thủ +60 | Bản thân · Thủ +60 | Hoạt động |
| +3 | `10040120` | Đỡ +600 | Bản thân · Đỡ +600 | Hoạt động |
| +4 | `10250000` | Công của tất cả Tướng +80 | Đội xuất trận · Công +80 | Hoạt động |
| +5 | `20270401` | Khi tấn công thường, 50% khiến mục tiêu [Im Lặng] 1 lượt | Buff `20280401` | Chưa áp dụng |
| +6 | `10010000` | Mới bắt đầu tăng 50đ Nộ, lượt đầu có thể Nộ Công | Bản thân · Nộ +50 | Hoạt động |
| +7 | `10260000` | HP của tất cả Tướng +800 | Đội xuất trận · HP +800 | Hoạt động |
| +8 | `10040400` | Đỡ +2000 | Bản thân · Đỡ +2000 | Hoạt động |

## Naraku (`12013005`)

Bậc tối đa từ HeroStepRelation +15. Bậc tài năng cao nhất trong bảng +15.

| Bậc | TAL | Hiệu ứng VN | Dữ liệu áp dụng | R7.16 |
|---:|---:|---|---|---|
| +2 | `10150200` | HP +1000 | Bản thân · HP +1000 | Hoạt động |
| +3 | `10080200` | Chính Xác +1000 | Bản thân · Chính Xác +1000 | Hoạt động |
| +4 | `10160000` | Công của tất cả Tướng +250 | Đội xuất trận · Công +250 | Hoạt động |
| +5 | `20020000` | Khi bị Công, Kháng Bạo tăng 100% | Buff `20020000` | Chưa áp dụng |
| +6 | `10010000` | Mới bắt đầu tăng 50đ Nộ, lượt đầu có thể Nộ Công | Bản thân · Nộ +50 | Hoạt động |
| +7 | `10170000` | HP của tất cả Tướng +2500 | Đội xuất trận · HP +2500 | Hoạt động |
| +8 | `20570600` | Đối với mục tiêu bị [Trúng Độc] gây ST tăng 36% | Buff `10270600` | Chưa áp dụng |
| +9 | `10180000` | Tất cả thuộc tính của Tướng +4% | Đội xuất trận · % Công +4%, % HP +4%, % Thủ +4% | Hoạt động |
| +10 | `20561000` | Khi bị tấn công, nếu kẻ công kích trong trạng thái [Trúng Độc], chịu ST giảm 50% | Buff `10261000` | Chưa áp dụng |
| +11 | `10481000` | Sát thương tất cả Tướng gây ra +10000 , miễn giảm sát thương +10000 | Đội xuất trận · ST cộng +10000, Miễn giảm ST +10000 | Hoạt động |
| +12 | `10490600` | HP+36000 | Bản thân · HP +36000 | Hoạt động |
| +13 | `10031000` | Bạo Kích +5000 | Bản thân · Bạo +5000 | Hoạt động |
| +14 | `10501000` | Công+6000 | Bản thân · Công +6000 | Hoạt động |
| +15 | `20321006` | Khi Nộ Công, 38 giảm 50đ Nộ của mục tiêu | Buff `10511006` | Chưa áp dụng |

## Yura (`12011022`)

Bậc tối đa từ HeroStepRelation +15. Bậc tài năng cao nhất trong bảng +15.

| Bậc | TAL | Hiệu ứng VN | Dữ liệu áp dụng | R7.16 |
|---:|---:|---|---|---|
| +2 | `10130160` | Công +80 | Bản thân · Công +80 | Hoạt động |
| +3 | `10030160` | Bạo Kích +800 | Bản thân · Bạo +800 | Hoạt động |
| +4 | `10190000` | Công của tất cả Tướng +200 | Đội xuất trận · Công +200 | Hoạt động |
| +5 | `20630400` | Ra trận lần 1 khi tấn công, ST gây ra tăng 50% | Buff `10130400` | Chưa áp dụng |
| +6 | `10010000` | Mới bắt đầu tăng 50đ Nộ, lượt đầu có thể Nộ Công | Bản thân · Nộ +50 | Hoạt động |
| +7 | `10200000` | HP của tất cả Tướng +2000 | Đội xuất trận · HP +2000 | Hoạt động |
| +8 | `10070600` | Bạo Kích +1500, ST Bạo +3000 | Bản thân · Bạo +1500, Tất Sát +3000 | Hoạt động |
| +9 | `10210000` | Tất cả thuộc tính của Tướng +3% | Đội xuất trận · % Công +3%, % HP +3%, % Thủ +3% | Hoạt động |
| +10 | `20480600` | Mục tiêu của bản thân khi lượng máu cao,gây ST tăng 30% | Buff `10180600` | Chưa áp dụng |
| +11 | `10480800` | Sát thương tất cả Tướng gây ra +8000 , miễn giảm sát thương +8000 | Đội xuất trận · ST cộng +8000, Miễn giảm ST +8000 | Hoạt động |
| +12 | `10490480` | HP+28800 | Bản thân · HP +28800 | Hoạt động |
| +13 | `10080870` | Chính Xác +4350 | Bản thân · Chính Xác +4350 | Hoạt động |
| +14 | `10500800` | Công+4800 | Bản thân · Công +4800 | Hoạt động |
| +15 | `20110830` | Sau mỗi lần bị tấn công, Công tăng 8%, tối đa 25% | Buff `20170830` | Chưa áp dụng |

## Shippo (`12011009`)

Bậc tối đa từ HeroStepRelation +15. Bậc tài năng cao nhất trong bảng +15.

| Bậc | TAL | Hiệu ứng VN | Dữ liệu áp dụng | R7.16 |
|---:|---:|---|---|---|
| +2 | `10150160` | HP +800 | Bản thân · HP +800 | Hoạt động |
| +3 | `10080160` | Chính Xác +800 | Bản thân · Chính Xác +800 | Hoạt động |
| +4 | `10220000` | Công của tất cả Tướng +125 | Đội xuất trận · Công +125 | Hoạt động |
| +5 | `20490400` | Khi HP của mục tiêu cao hơn 50%, gây ST tăng 20% | Buff `10190400` | Chưa áp dụng |
| +6 | `10010000` | Mới bắt đầu tăng 50đ Nộ, lượt đầu có thể Nộ Công | Bản thân · Nộ +50 | Hoạt động |
| +7 | `10230000` | HP của tất cả Tướng +1250 | Đội xuất trận · HP +1250 | Hoạt động |
| +8 | `20190400` | Khi tấn công thường, 30% tăng 25đ Nộ cho mục tiêu đồng đội có Nộ thấp nhất | Buff `10530400` | Chưa áp dụng |
| +9 | `10240000` | Tất cả thuộc tính của Tướng +2% | Đội xuất trận · % Công +2%, % HP +2%, % Thủ +2% | Hoạt động |
| +10 | `20170600` | Khi Nộ Công, hồi HP bằng 30% ST cho mục tiêu đồng đội tối đa đã mất máu | Buff `10670600` | Chưa áp dụng |
| +11 | `10480500` | Sát thương tất cả Tướng gây ra +5000 , miễn giảm sát thương +5000 | Đội xuất trận · ST cộng +5000, Miễn giảm ST +5000 | Hoạt động |
| +12 | `10490300` | HP+18000 | Bản thân · HP +18000 | Hoạt động |
| +13 | `10080600` | Chính Xác +3000 | Bản thân · Chính Xác +3000 | Hoạt động |
| +14 | `10500500` | Công+3000 | Bản thân · Công +3000 | Hoạt động |
| +15 | `20330507` | Khi Nộ Công, 30% giảm 50đ Nộ của mục tiêu | Buff `10450507` | Chưa áp dụng |

## Oyakata (`12013019`)

Bậc tối đa từ HeroStepRelation +15. Bậc tài năng cao nhất trong bảng +15.

| Bậc | TAL | Hiệu ứng VN | Dữ liệu áp dụng | R7.16 |
|---:|---:|---|---|---|
| +2 | `10140160` | Thủ +80 | Bản thân · Thủ +80 | Hoạt động |
| +3 | `10060160` | Né +640 | Bản thân · Né +640 | Hoạt động |
| +4 | `10220000` | Công của tất cả Tướng +125 | Đội xuất trận · Công +125 | Hoạt động |
| +5 | `20640400` | Ra trận lần 1,2,3, khi bản thân chịu ST giảm 30% | Buff `10140400` | Chưa áp dụng |
| +6 | `10010000` | Mới bắt đầu tăng 50đ Nộ, lượt đầu có thể Nộ Công | Bản thân · Nộ +50 | Hoạt động |
| +7 | `10230000` | HP của tất cả Tướng +1250 | Đội xuất trận · HP +1250 | Hoạt động |
| +8 | `20450400` | Khi bị tấn công, nếu HP cao hơn kẻ công kích, nhận ST giảm 20% | Buff `10150400` | Chưa áp dụng |
| +9 | `10240000` | Tất cả thuộc tính của Tướng +2% | Đội xuất trận · % Công +2%, % HP +2%, % Thủ +2% | Hoạt động |
| +10 | `20050600` | Khi bị tấn công thường, gây 30% [Choáng] 1 lượt đối với kẻ công kích | Buff `20130600` | Chưa áp dụng |
| +11 | `10480500` | Sát thương tất cả Tướng gây ra +5000 , miễn giảm sát thương +5000 | Đội xuất trận · ST cộng +5000, Miễn giảm ST +5000 | Hoạt động |
| +12 | `10490300` | HP+18000 | Bản thân · HP +18000 | Hoạt động |
| +13 | `10650600` | Kháng Bạo+3000 | Bản thân · Kháng Bạo +3000 | Hoạt động |
| +14 | `10500500` | Công+3000 | Bản thân · Công +3000 | Hoạt động |
| +15 | `20660500` | Khi Nộ Công, bỏ qua 50% Thủ của mục tiêu | Buff `10560500` | Chưa áp dụng |

## Seiryu (`12012026`)

Bậc tối đa từ HeroStepRelation +8. Bậc tài năng cao nhất trong bảng +8.

| Bậc | TAL | Hiệu ứng VN | Dữ liệu áp dụng | R7.16 |
|---:|---:|---|---|---|
| +2 | `10130120` | Công +60 | Bản thân · Công +60 | Hoạt động |
| +3 | `10030120` | Bạo Kích +600 | Bản thân · Bạo +600 | Hoạt động |
| +4 | `10250000` | Công của tất cả Tướng +80 | Đội xuất trận · Công +80 | Hoạt động |
| +5 | `20220401` | Khi tấn công thường, 80% giảm 45% Thủ 1 lượt của mục tiêu | Buff `20420401` | Chưa áp dụng |
| +6 | `10010000` | Mới bắt đầu tăng 50đ Nộ, lượt đầu có thể Nộ Công | Bản thân · Nộ +50 | Hoạt động |
| +7 | `10260000` | HP của tất cả Tướng +800 | Đội xuất trận · HP +800 | Hoạt động |
| +8 | `20340408` | Khi Nộ Công, 17% giảm 75% hiệu quả trị liệu 2 lượt của mục tiêu | Buff `20300408` | Chưa áp dụng |

## Shuran (`12013029`)

Bậc tối đa từ HeroStepRelation +8. Bậc tài năng cao nhất trong bảng +8.

| Bậc | TAL | Hiệu ứng VN | Dữ liệu áp dụng | R7.16 |
|---:|---:|---|---|---|
| +2 | `10140120` | Thủ +60 | Bản thân · Thủ +60 | Hoạt động |
| +3 | `10060120` | Né +480 | Bản thân · Né +480 | Hoạt động |
| +4 | `10250000` | Công của tất cả Tướng +80 | Đội xuất trận · Công +80 | Hoạt động |
| +5 | `20650000` | Lần đầu bị tấn công, tỷ lệ Né +100% | Buff `10120000` | Chưa áp dụng |
| +6 | `10010000` | Mới bắt đầu tăng 50đ Nộ, lượt đầu có thể Nộ Công | Bản thân · Nộ +50 | Hoạt động |
| +7 | `10260000` | HP của tất cả Tướng +800 | Đội xuất trận · HP +800 | Hoạt động |
| +8 | `20420400` | Khi Né, 60% tăng 25đ Nộ | Buff `10370400` | Chưa áp dụng |

## InuYasha (`12011004`)

Bậc tối đa từ HeroStepRelation +15. Bậc tài năng cao nhất trong bảng +15.

| Bậc | TAL | Hiệu ứng VN | Dữ liệu áp dụng | R7.16 |
|---:|---:|---|---|---|
| +2 | `10130200` | Công +100 | Bản thân · Công +100 | Hoạt động |
| +3 | `10030200` | Bạo Kích +1000 | Bản thân · Bạo +1000 | Hoạt động |
| +4 | `10160000` | Công của tất cả Tướng +250 | Đội xuất trận · Công +250 | Hoạt động |
| +5 | `20390000` | Khi Bạo Kích, tăng thêm 25đ Nộ | Buff `10350000` | Hoạt động |
| +6 | `10010000` | Mới bắt đầu tăng 50đ Nộ, lượt đầu có thể Nộ Công | Bản thân · Nộ +50 | Hoạt động |
| +7 | `10170000` | HP của tất cả Tướng +2500 | Đội xuất trận · HP +2500 | Hoạt động |
| +8 | `20720600` | Khi tấn công thường, gây thêm 60% ST cho mục tiêu lân cận | Buff `20590600` | Chưa áp dụng |
| +9 | `10180000` | Tất cả thuộc tính của Tướng +4% | Đội xuất trận · % Công +4%, % HP +4%, % Thủ +4% | Hoạt động |
| +10 | `20111000` | Sau mỗi lần bị tấn công, Công tăng 10%, tối đa 30% | Buff `20171000` | Chưa áp dụng |
| +11 | `10481000` | Sát thương tất cả Tướng gây ra +10000 , miễn giảm sát thương +10000 | Đội xuất trận · ST cộng +10000, Miễn giảm ST +10000 | Hoạt động |
| +12 | `10490600` | HP+36000 | Bản thân · HP +36000 | Hoạt động |
| +13 | `10081000` | Chính Xác +5000 | Bản thân · Chính Xác +5000 | Hoạt động |
| +14 | `10501000` | Công+6000 | Bản thân · Công +6000 | Hoạt động |
| +15 | `21221000` | Khi đánh kỹ năng Nộ, 80% tăng 50đ Nộ cho bản thân | Buff `11111000` | Chưa áp dụng |

## Kagome (`12011005`)

Bậc tối đa từ HeroStepRelation +15. Bậc tài năng cao nhất trong bảng +15.

| Bậc | TAL | Hiệu ứng VN | Dữ liệu áp dụng | R7.16 |
|---:|---:|---|---|---|
| +2 | `10150160` | HP +800 | Bản thân · HP +800 | Hoạt động |
| +3 | `10060160` | Né +640 | Bản thân · Né +640 | Hoạt động |
| +4 | `10190000` | Công của tất cả Tướng +200 | Đội xuất trận · Công +200 | Hoạt động |
| +5 | `20450400` | Khi bị tấn công, nếu HP cao hơn kẻ công kích, nhận ST giảm 20% | Buff `10150400` | Chưa áp dụng |
| +6 | `10010000` | Mới bắt đầu tăng 50đ Nộ, lượt đầu có thể Nộ Công | Bản thân · Nộ +50 | Hoạt động |
| +7 | `10200000` | HP của tất cả Tướng +2000 | Đội xuất trận · HP +2000 | Hoạt động |
| +8 | `10030600` | Bạo Kích +3000 | Bản thân · Bạo +3000 | Hoạt động |
| +9 | `10210000` | Tất cả thuộc tính của Tướng +3% | Đội xuất trận · % Công +3%, % HP +3%, % Thủ +3% | Hoạt động |
| +10 | `20480800` | Mục tiêu của bản thân khi lượng máu cao,gây ST tăng 40% | Buff `10180800` | Chưa áp dụng |
| +11 | `10480800` | Sát thương tất cả Tướng gây ra +8000 , miễn giảm sát thương +8000 | Đội xuất trận · ST cộng +8000, Miễn giảm ST +8000 | Hoạt động |
| +12 | `10490480` | HP+28800 | Bản thân · HP +28800 | Hoạt động |
| +13 | `10030870` | Bạo Kích +4350 | Bản thân · Bạo +4350 | Hoạt động |
| +14 | `10500800` | Công+4800 | Bản thân · Công +4800 | Hoạt động |
| +15 | `20330836` | Khi Nộ Công, 62% giảm 50đ Nộ của mục tiêu | Buff `10450836` | Chưa áp dụng |

## Sesshomaru (`12012005`)

Bậc tối đa từ HeroStepRelation +15. Bậc tài năng cao nhất trong bảng +15.

| Bậc | TAL | Hiệu ứng VN | Dữ liệu áp dụng | R7.16 |
|---:|---:|---|---|---|
| +2 | `10130200` | Công +100 | Bản thân · Công +100 | Hoạt động |
| +3 | `10030200` | Bạo Kích +1000 | Bản thân · Bạo +1000 | Hoạt động |
| +4 | `10160000` | Công của tất cả Tướng +250 | Đội xuất trận · Công +250 | Hoạt động |
| +5 | `10070600` | Bạo Kích +1500, ST Bạo +3000 | Bản thân · Bạo +1500, Tất Sát +3000 | Hoạt động |
| +6 | `10010000` | Mới bắt đầu tăng 50đ Nộ, lượt đầu có thể Nộ Công | Bản thân · Nộ +50 | Hoạt động |
| +7 | `10170000` | HP của tất cả Tướng +2500 | Đội xuất trận · HP +2500 | Hoạt động |
| +8 | `20480600` | Mục tiêu của bản thân khi lượng máu cao,gây ST tăng 30% | Buff `10180600` | Chưa áp dụng |
| +9 | `10180000` | Tất cả thuộc tính của Tướng +4% | Đội xuất trận · % Công +4%, % HP +4%, % Thủ +4% | Hoạt động |
| +10 | `20410000` | Khi Nộ Công, Bạo Kích tăng thêm 50đ Nộ | Buff `10550000` | Hoạt động |
| +11 | `10481000` | Sát thương tất cả Tướng gây ra +10000 , miễn giảm sát thương +10000 | Đội xuất trận · ST cộng +10000, Miễn giảm ST +10000 | Hoạt động |
| +12 | `10490600` | HP+36000 | Bản thân · HP +36000 | Hoạt động |
| +13 | `10641000` | Phá Kích+5000 | Bản thân · Phá Kích +5000 | Hoạt động |
| +14 | `10501000` | Công+6000 | Bản thân · Công +6000 | Hoạt động |
| +15 | `21071000` | Kỹ Năng ST tăng 50% | Buff `10591000` | Chưa áp dụng |

## Sango (`12011007`)

Bậc tối đa từ HeroStepRelation +15. Bậc tài năng cao nhất trong bảng +15.

| Bậc | TAL | Hiệu ứng VN | Dữ liệu áp dụng | R7.16 |
|---:|---:|---|---|---|
| +2 | `10130160` | Công +80 | Bản thân · Công +80 | Hoạt động |
| +3 | `10030160` | Bạo Kích +800 | Bản thân · Bạo +800 | Hoạt động |
| +4 | `10190000` | Công của tất cả Tướng +200 | Đội xuất trận · Công +200 | Hoạt động |
| +5 | `20480400` | Mục tiêu của bản thân khi lượng máu cao,gây ST tăng 20% | Buff `10180400` | Chưa áp dụng |
| +6 | `10010000` | Mới bắt đầu tăng 50đ Nộ, lượt đầu có thể Nộ Công | Bản thân · Nộ +50 | Hoạt động |
| +7 | `10200000` | HP của tất cả Tướng +2000 | Đội xuất trận · HP +2000 | Hoạt động |
| +8 | `10070600` | Bạo Kích +1500, ST Bạo +3000 | Bản thân · Bạo +1500, Tất Sát +3000 | Hoạt động |
| +9 | `10210000` | Tất cả thuộc tính của Tướng +3% | Đội xuất trận · % Công +3%, % HP +3%, % Thủ +3% | Hoạt động |
| +10 | `20390000` | Khi Bạo Kích, tăng thêm 25đ Nộ | Buff `10350000` | Hoạt động |
| +11 | `10480800` | Sát thương tất cả Tướng gây ra +8000 , miễn giảm sát thương +8000 | Đội xuất trận · ST cộng +8000, Miễn giảm ST +8000 | Hoạt động |
| +12 | `10490480` | HP+28800 | Bản thân · HP +28800 | Hoạt động |
| +13 | `10070870` | Bạo Kích +2175, ST Bạo +4350 | Bản thân · Bạo +2175, Tất Sát +4350 | Hoạt động |
| +14 | `10500800` | Công+4800 | Bản thân · Công +4800 | Hoạt động |
| +15 | `20110830` | Sau mỗi lần bị tấn công, Công tăng 8%, tối đa 25% | Buff `20170830` | Chưa áp dụng |

## Jakotsu (`12013017`)

Bậc tối đa từ HeroStepRelation +15. Bậc tài năng cao nhất trong bảng +15.

| Bậc | TAL | Hiệu ứng VN | Dữ liệu áp dụng | R7.16 |
|---:|---:|---|---|---|
| +2 | `10150160` | HP +800 | Bản thân · HP +800 | Hoạt động |
| +3 | `10080160` | Chính Xác +800 | Bản thân · Chính Xác +800 | Hoạt động |
| +4 | `10190000` | Công của tất cả Tướng +200 | Đội xuất trận · Công +200 | Hoạt động |
| +5 | `10030400` | Bạo Kích +2000 | Bản thân · Bạo +2000 | Hoạt động |
| +6 | `10010000` | Mới bắt đầu tăng 50đ Nộ, lượt đầu có thể Nộ Công | Bản thân · Nộ +50 | Hoạt động |
| +7 | `10200000` | HP của tất cả Tướng +2000 | Đội xuất trận · HP +2000 | Hoạt động |
| +8 | `20250601` | Khi tấn công thường, 100% khiến mục tiêu [Trúng Độc] 2 lượt | Buff `20310601` | Chưa áp dụng |
| +9 | `10210000` | Tất cả thuộc tính của Tướng +3% | Đội xuất trận · % Công +3%, % HP +3%, % Thủ +3% | Hoạt động |
| +10 | `20570600` | Đối với mục tiêu bị [Trúng Độc] gây ST tăng 36% | Buff `10270600` | Chưa áp dụng |
| +11 | `10480800` | Sát thương tất cả Tướng gây ra +8000 , miễn giảm sát thương +8000 | Đội xuất trận · ST cộng +8000, Miễn giảm ST +8000 | Hoạt động |
| +12 | `10490480` | HP+28800 | Bản thân · HP +28800 | Hoạt động |
| +13 | `10640870` | Phá Kích+4350 | Bản thân · Phá Kích +4350 | Hoạt động |
| +14 | `10500800` | Công+4800 | Bản thân · Công +4800 | Hoạt động |
| +15 | `21070830` | Kỹ Năng ST tăng 42% | Buff `10590830` | Chưa áp dụng |

## Kaguya (`12013004`)

Bậc tối đa từ HeroStepRelation +15. Bậc tài năng cao nhất trong bảng +15.

| Bậc | TAL | Hiệu ứng VN | Dữ liệu áp dụng | R7.16 |
|---:|---:|---|---|---|
| +2 | `10150200` | HP +1000 | Bản thân · HP +1000 | Hoạt động |
| +3 | `10080200` | Chính Xác +1000 | Bản thân · Chính Xác +1000 | Hoạt động |
| +4 | `10160000` | Công của tất cả Tướng +250 | Đội xuất trận · Công +250 | Hoạt động |
| +5 | `20250606` | Khi tấn công thường, 50% khiến mục tiêu [Trúng Độc] 2 lượt | Buff `20310606` | Chưa áp dụng |
| +6 | `10010000` | Mới bắt đầu tăng 50đ Nộ, lượt đầu có thể Nộ Công | Bản thân · Nộ +50 | Hoạt động |
| +7 | `10170000` | HP của tất cả Tướng +2500 | Đội xuất trận · HP +2500 | Hoạt động |
| +8 | `20370606` | Khi Nộ Công, 75% khiến mục tiêu [Im Lặng] 1 lượt | Buff `20290606` | Chưa áp dụng |
| +9 | `10180000` | Tất cả thuộc tính của Tướng +4% | Đội xuất trận · % Công +4%, % HP +4%, % Thủ +4% | Hoạt động |
| +10 | `20581000` | Khi Nộ Công, nếu mục tiêu trong trạng thái [Trúng Độc], 100% giảm 75đ Nộ | Buff `10621000` | Chưa áp dụng |
| +11 | `10481000` | Sát thương tất cả Tướng gây ra +10000 , miễn giảm sát thương +10000 | Đội xuất trận · ST cộng +10000, Miễn giảm ST +10000 | Hoạt động |
| +12 | `10490600` | HP+36000 | Bản thân · HP +36000 | Hoạt động |
| +13 | `10031000` | Bạo Kích +5000 | Bản thân · Bạo +5000 | Hoạt động |
| +14 | `10501000` | Công+6000 | Bản thân · Công +6000 | Hoạt động |
| +15 | `10021000` | Chịu ST giảm 30% | Bản thân · % miễn giảm ST +30% | Hoạt động |

## Kagura (`12013008`)

Bậc tối đa từ HeroStepRelation +15. Bậc tài năng cao nhất trong bảng +15.

| Bậc | TAL | Hiệu ứng VN | Dữ liệu áp dụng | R7.16 |
|---:|---:|---|---|---|
| +2 | `10130160` | Công +80 | Bản thân · Công +80 | Hoạt động |
| +3 | `10030160` | Bạo Kích +800 | Bản thân · Bạo +800 | Hoạt động |
| +4 | `10190000` | Công của tất cả Tướng +200 | Đội xuất trận · Công +200 | Hoạt động |
| +5 | `20480400` | Mục tiêu của bản thân khi lượng máu cao,gây ST tăng 20% | Buff `10180400` | Chưa áp dụng |
| +6 | `10010000` | Mới bắt đầu tăng 50đ Nộ, lượt đầu có thể Nộ Công | Bản thân · Nộ +50 | Hoạt động |
| +7 | `10200000` | HP của tất cả Tướng +2000 | Đội xuất trận · HP +2000 | Hoạt động |
| +8 | `10030600` | Bạo Kích +3000 | Bản thân · Bạo +3000 | Hoạt động |
| +9 | `10210000` | Tất cả thuộc tính của Tướng +3% | Đội xuất trận · % Công +3%, % HP +3%, % Thủ +3% | Hoạt động |
| +10 | `20170800` | Khi Nộ Công, hồi HP bằng 40% ST cho mục tiêu đồng đội tối đa đã mất máu | Buff `10670800` | Chưa áp dụng |
| +11 | `10480800` | Sát thương tất cả Tướng gây ra +8000 , miễn giảm sát thương +8000 | Đội xuất trận · ST cộng +8000, Miễn giảm ST +8000 | Hoạt động |
| +12 | `10490480` | HP+28800 | Bản thân · HP +28800 | Hoạt động |
| +13 | `10070870` | Bạo Kích +2175, ST Bạo +4350 | Bản thân · Bạo +2175, Tất Sát +4350 | Hoạt động |
| +14 | `10500800` | Công+4800 | Bản thân · Công +4800 | Hoạt động |
| +15 | `21240830` | Bỏ qua 50% Thủ của mục tiêu | Buff `11130830` | Chưa áp dụng |

## Kanna (`12013006`)

Bậc tối đa từ HeroStepRelation +15. Bậc tài năng cao nhất trong bảng +15.

| Bậc | TAL | Hiệu ứng VN | Dữ liệu áp dụng | R7.16 |
|---:|---:|---|---|---|
| +2 | `10150160` | HP +800 | Bản thân · HP +800 | Hoạt động |
| +3 | `10030160` | Bạo Kích +800 | Bản thân · Bạo +800 | Hoạt động |
| +4 | `10190000` | Công của tất cả Tướng +200 | Đội xuất trận · Công +200 | Hoạt động |
| +5 | `20640400` | Ra trận lần 1,2,3, khi bản thân chịu ST giảm 30% | Buff `10140400` | Chưa áp dụng |
| +6 | `10010000` | Mới bắt đầu tăng 50đ Nộ, lượt đầu có thể Nộ Công | Bản thân · Nộ +50 | Hoạt động |
| +7 | `10200000` | HP của tất cả Tướng +2000 | Đội xuất trận · HP +2000 | Hoạt động |
| +8 | `10020600` | Chịu ST giảm 18% | Bản thân · % miễn giảm ST +18% | Hoạt động |
| +9 | `10210000` | Tất cả thuộc tính của Tướng +3% | Đội xuất trận · % Công +3%, % HP +3%, % Thủ +3% | Hoạt động |
| +10 | `20510800` | Khi HP của mục tiêu thấp hơn 40%, tỷ lệ Bạo Kích tăng 80% | Buff `10210800` | Chưa áp dụng |
| +11 | `10480800` | Sát thương tất cả Tướng gây ra +8000 , miễn giảm sát thương +8000 | Đội xuất trận · ST cộng +8000, Miễn giảm ST +8000 | Hoạt động |
| +12 | `10490480` | HP+28800 | Bản thân · HP +28800 | Hoạt động |
| +13 | `10650870` | Kháng Bạo+4350 | Bản thân · Kháng Bạo +4350 | Hoạt động |
| +14 | `10500800` | Công+4800 | Bản thân · Công +4800 | Hoạt động |
| +15 | `20640830` | Ra trận lần 1,2,3, khi bản thân chịu ST giảm 62% | Buff `10140830` | Chưa áp dụng |

## Bà Shoga (`12011015`)

Bậc tối đa từ HeroStepRelation +15. Bậc tài năng cao nhất trong bảng +15.

| Bậc | TAL | Hiệu ứng VN | Dữ liệu áp dụng | R7.16 |
|---:|---:|---|---|---|
| +2 | `10130160` | Công +80 | Bản thân · Công +80 | Hoạt động |
| +3 | `10080160` | Chính Xác +800 | Bản thân · Chính Xác +800 | Hoạt động |
| +4 | `10220000` | Công của tất cả Tướng +125 | Đội xuất trận · Công +125 | Hoạt động |
| +5 | `20170400` | Khi Nộ Công, hồi HP bằng 20% ST cho mục tiêu đồng đội tối đa đã mất máu | Buff `10670400` | Chưa áp dụng |
| +6 | `10010000` | Mới bắt đầu tăng 50đ Nộ, lượt đầu có thể Nộ Công | Bản thân · Nộ +50 | Hoạt động |
| +7 | `10230000` | HP của tất cả Tướng +1250 | Đội xuất trận · HP +1250 | Hoạt động |
| +8 | `20470400` | Khi HP của bản thân thấp hơn mục tiêu, gây ST tăng 20% | Buff `10170400` | Chưa áp dụng |
| +9 | `10240000` | Tất cả thuộc tính của Tướng +2% | Đội xuất trận · % Công +2%, % HP +2%, % Thủ +2% | Hoạt động |
| +10 | `10030600` | Bạo Kích +3000 | Bản thân · Bạo +3000 | Hoạt động |
| +11 | `10480500` | Sát thương tất cả Tướng gây ra +5000 , miễn giảm sát thương +5000 | Đội xuất trận · ST cộng +5000, Miễn giảm ST +5000 | Hoạt động |
| +12 | `10490300` | HP+18000 | Bản thân · HP +18000 | Hoạt động |
| +13 | `10650600` | Kháng Bạo+3000 | Bản thân · Kháng Bạo +3000 | Hoạt động |
| +14 | `10500500` | Công+3000 | Bản thân · Công +3000 | Hoạt động |
| +15 | `20640500` | Ra trận lần 1,2,3, khi bản thân chịu ST giảm 38% | Buff `10140500` | Chưa áp dụng |

## Shibugarasu (`12011031`)

Bậc tối đa từ HeroStepRelation +8. Bậc tài năng cao nhất trong bảng +8.

| Bậc | TAL | Hiệu ứng VN | Dữ liệu áp dụng | R7.16 |
|---:|---:|---|---|---|
| +2 | `10130120` | Công +60 | Bản thân · Công +60 | Hoạt động |
| +3 | `10030120` | Bạo Kích +600 | Bản thân · Bạo +600 | Hoạt động |
| +4 | `10250000` | Công của tất cả Tướng +80 | Đội xuất trận · Công +80 | Hoạt động |
| +5 | `20150400` | Khi tấn công thường, hồi HP bằng 30% ST cho bản thân | Buff `10710400` | Chưa áp dụng |
| +6 | `10010000` | Mới bắt đầu tăng 50đ Nộ, lượt đầu có thể Nộ Công | Bản thân · Nộ +50 | Hoạt động |
| +7 | `10260000` | HP của tất cả Tướng +800 | Đội xuất trận · HP +800 | Hoạt động |
| +8 | `20310407` | Khi Nộ Công, 32% giảm 45%Thủ 2 lượt của mục tiêu | Buff `20430407` | Chưa áp dụng |

## Izayoi (`12011021`)

Bậc tối đa từ HeroStepRelation +15. Bậc tài năng cao nhất trong bảng +15.

| Bậc | TAL | Hiệu ứng VN | Dữ liệu áp dụng | R7.16 |
|---:|---:|---|---|---|
| +2 | `10150160` | HP +800 | Bản thân · HP +800 | Hoạt động |
| +3 | `10060160` | Né +640 | Bản thân · Né +640 | Hoạt động |
| +4 | `10190000` | Công của tất cả Tướng +200 | Đội xuất trận · Công +200 | Hoạt động |
| +5 | `20540400` | Khi HP của bản thân cao hơn 50%, chịu ST giảm 20% | Buff `10240400` | Chưa áp dụng |
| +6 | `10010000` | Mới bắt đầu tăng 50đ Nộ, lượt đầu có thể Nộ Công | Bản thân · Nộ +50 | Hoạt động |
| +7 | `10200000` | HP của tất cả Tướng +2000 | Đội xuất trận · HP +2000 | Hoạt động |
| +8 | `10050600` | Né +1800 | Bản thân · Né +1800 | Hoạt động |
| +9 | `10210000` | Tất cả thuộc tính của Tướng +3% | Đội xuất trận · % Công +3%, % HP +3%, % Thủ +3% | Hoạt động |
| +10 | `10100600` | Điểm Trị Liệu +18% | Bản thân · % Trị Liệu +30% | Hoạt động |
| +11 | `10480800` | Sát thương tất cả Tướng gây ra +8000 , miễn giảm sát thương +8000 | Đội xuất trận · ST cộng +8000, Miễn giảm ST +8000 | Hoạt động |
| +12 | `10490480` | HP+28800 | Bản thân · HP +28800 | Hoạt động |
| +13 | `10650870` | Kháng Bạo+4350 | Bản thân · Kháng Bạo +4350 | Hoạt động |
| +14 | `10500800` | Công+4800 | Bản thân · Công +4800 | Hoạt động |
| +15 | `20070830` | Khi bị tấn công, 42% giảm 25đ Nộ của kẻ công kích | Buff `10400830` | Chưa áp dụng |

## Juromaru (`12013013`)

Bậc tối đa từ HeroStepRelation +15. Bậc tài năng cao nhất trong bảng +15.

| Bậc | TAL | Hiệu ứng VN | Dữ liệu áp dụng | R7.16 |
|---:|---:|---|---|---|
| +2 | `10140160` | Thủ +80 | Bản thân · Thủ +80 | Hoạt động |
| +3 | `10040160` | Đỡ +800 | Bản thân · Đỡ +800 | Hoạt động |
| +4 | `10220000` | Công của tất cả Tướng +125 | Đội xuất trận · Công +125 | Hoạt động |
| +5 | `10120400` | Khi được Trị Liệu, tăng 40% hồi HP | Bản thân · % Nhận Trị Liệu +40% | Hoạt động |
| +6 | `10010000` | Mới bắt đầu tăng 50đ Nộ, lượt đầu có thể Nộ Công | Bản thân · Nộ +50 | Hoạt động |
| +7 | `10230000` | HP của tất cả Tướng +1250 | Đội xuất trận · HP +1250 | Hoạt động |
| +8 | `20740400` | Khi bị tấn công, phản 12% ST | Buff `20070400` | Chưa áp dụng |
| +9 | `10240000` | Tất cả thuộc tính của Tướng +2% | Đội xuất trận · % Công +2%, % HP +2%, % Thủ +2% | Hoạt động |
| +10 | `10020600` | Chịu ST giảm 18% | Bản thân · % miễn giảm ST +18% | Hoạt động |
| +11 | `10480500` | Sát thương tất cả Tướng gây ra +5000 , miễn giảm sát thương +5000 | Đội xuất trận · ST cộng +5000, Miễn giảm ST +5000 | Hoạt động |
| +12 | `10490300` | HP+18000 | Bản thân · HP +18000 | Hoạt động |
| +13 | `10040600` | Đỡ +3000 | Bản thân · Đỡ +3000 | Hoạt động |
| +14 | `10500500` | Công+3000 | Bản thân · Công +3000 | Hoạt động |
| +15 | `20070500` | Khi bị tấn công, 25% giảm 25đ Nộ của kẻ công kích | Buff `10400500` | Chưa áp dụng |

## Jura (`12012022`)

Bậc tối đa từ HeroStepRelation +15. Bậc tài năng cao nhất trong bảng +15.

| Bậc | TAL | Hiệu ứng VN | Dữ liệu áp dụng | R7.16 |
|---:|---:|---|---|---|
| +2 | `10150160` | HP +800 | Bản thân · HP +800 | Hoạt động |
| +3 | `10060160` | Né +640 | Bản thân · Né +640 | Hoạt động |
| +4 | `10220000` | Công của tất cả Tướng +125 | Đội xuất trận · Công +125 | Hoạt động |
| +5 | `20140400` | Khi tấn công thường, hồi HP bằng 30% ST cho mục tiêu đồng đội tối đa đã mất máu | Buff `10680400` | Chưa áp dụng |
| +6 | `10010000` | Mới bắt đầu tăng 50đ Nộ, lượt đầu có thể Nộ Công | Bản thân · Nộ +50 | Hoạt động |
| +7 | `10230000` | HP của tất cả Tướng +1250 | Đội xuất trận · HP +1250 | Hoạt động |
| +8 | `20320407` | Khi Nộ Công, 12% giảm 50đ Nộ của mục tiêu | Buff `10510407` | Chưa áp dụng |
| +9 | `10240000` | Tất cả thuộc tính của Tướng +2% | Đội xuất trận · % Công +2%, % HP +2%, % Thủ +2% | Hoạt động |
| +10 | `20590600` | Khi tử vong, 60% giảm 25đ Nộ của tất cả địch | Buff `10300600` | Chưa áp dụng |
| +11 | `10480500` | Sát thương tất cả Tướng gây ra +5000 , miễn giảm sát thương +5000 | Đội xuất trận · ST cộng +5000, Miễn giảm ST +5000 | Hoạt động |
| +12 | `10490300` | HP+18000 | Bản thân · HP +18000 | Hoạt động |
| +13 | `10080600` | Chính Xác +3000 | Bản thân · Chính Xác +3000 | Hoạt động |
| +14 | `10500500` | Công+3000 | Bản thân · Công +3000 | Hoạt động |
| +15 | `20480500` | Mục tiêu của bản thân khi lượng máu cao,gây ST tăng 25% | Buff `10180500` | Chưa áp dụng |

## Suikotsu (`12013024`)

Bậc tối đa từ HeroStepRelation +8. Bậc tài năng cao nhất trong bảng +8.

| Bậc | TAL | Hiệu ứng VN | Dữ liệu áp dụng | R7.16 |
|---:|---:|---|---|---|
| +2 | `10130120` | Công +60 | Bản thân · Công +60 | Hoạt động |
| +3 | `10030120` | Bạo Kích +600 | Bản thân · Bạo +600 | Hoạt động |
| +4 | `10250000` | Công của tất cả Tướng +80 | Đội xuất trận · Công +80 | Hoạt động |
| +5 | `20250401` | Khi tấn công thường, 67% khiến mục tiêu [Trúng Độc] 2 lượt | Buff `20310401` | Chưa áp dụng |
| +6 | `10010000` | Mới bắt đầu tăng 50đ Nộ, lượt đầu có thể Nộ Công | Bản thân · Nộ +50 | Hoạt động |
| +7 | `10260000` | HP của tất cả Tướng +800 | Đội xuất trận · HP +800 | Hoạt động |
| +8 | `20570400` | Đối với mục tiêu bị [Trúng Độc] gây ST tăng 24% | Buff `10270400` | Chưa áp dụng |

## Shishinki (`12013023`)

Bậc tối đa từ HeroStepRelation +15. Bậc tài năng cao nhất trong bảng +15.

| Bậc | TAL | Hiệu ứng VN | Dữ liệu áp dụng | R7.16 |
|---:|---:|---|---|---|
| +2 | `10130160` | Công +80 | Bản thân · Công +80 | Hoạt động |
| +3 | `10030160` | Bạo Kích +800 | Bản thân · Bạo +800 | Hoạt động |
| +4 | `10220000` | Công của tất cả Tướng +125 | Đội xuất trận · Công +125 | Hoạt động |
| +5 | `20480400` | Mục tiêu của bản thân khi lượng máu cao,gây ST tăng 20% | Buff `10180400` | Chưa áp dụng |
| +6 | `10010000` | Mới bắt đầu tăng 50đ Nộ, lượt đầu có thể Nộ Công | Bản thân · Nộ +50 | Hoạt động |
| +7 | `10230000` | HP của tất cả Tướng +1250 | Đội xuất trận · HP +1250 | Hoạt động |
| +8 | `10030400` | Bạo Kích +2000 | Bản thân · Bạo +2000 | Hoạt động |
| +9 | `10240000` | Tất cả thuộc tính của Tướng +2% | Đội xuất trận · % Công +2%, % HP +2%, % Thủ +2% | Hoạt động |
| +10 | `20390000` | Khi Bạo Kích, tăng thêm 25đ Nộ | Buff `10350000` | Hoạt động |
| +11 | `10480500` | Sát thương tất cả Tướng gây ra +5000 , miễn giảm sát thương +5000 | Đội xuất trận · ST cộng +5000, Miễn giảm ST +5000 | Hoạt động |
| +12 | `10490300` | HP+18000 | Bản thân · HP +18000 | Hoạt động |
| +13 | `10080600` | Chính Xác +3000 | Bản thân · Chính Xác +3000 | Hoạt động |
| +14 | `10500500` | Công+3000 | Bản thân · Công +3000 | Hoạt động |
| +15 | `20330501` | Khi Nộ Công, 75% giảm 50đ Nộ của mục tiêu | Buff `10450501` | Chưa áp dụng |

## Sara (`12012007`)

Bậc tối đa từ HeroStepRelation +15. Bậc tài năng cao nhất trong bảng +15.

| Bậc | TAL | Hiệu ứng VN | Dữ liệu áp dụng | R7.16 |
|---:|---:|---|---|---|
| +2 | `10150160` | HP +800 | Bản thân · HP +800 | Hoạt động |
| +3 | `10060160` | Né +640 | Bản thân · Né +640 | Hoạt động |
| +4 | `10190000` | Công của tất cả Tướng +200 | Đội xuất trận · Công +200 | Hoạt động |
| +5 | `20450400` | Khi bị tấn công, nếu HP cao hơn kẻ công kích, nhận ST giảm 20% | Buff `10150400` | Chưa áp dụng |
| +6 | `10010000` | Mới bắt đầu tăng 50đ Nộ, lượt đầu có thể Nộ Công | Bản thân · Nộ +50 | Hoạt động |
| +7 | `10200000` | HP của tất cả Tướng +2000 | Đội xuất trận · HP +2000 | Hoạt động |
| +8 | `20280606` | Khi tấn công thường, 15% khiến mục tiêu [Tê Liệt] 1 lượt | Buff `20510606` | Chưa áp dụng |
| +9 | `10210000` | Tất cả thuộc tính của Tướng +3% | Đội xuất trận · % Công +3%, % HP +3%, % Thủ +3% | Hoạt động |
| +10 | `20710800` | Sau khi Nộ Công, 80% nhận hiệu quả [Vô Địch] 1 lượt | Buff `20220800` | Chưa áp dụng |
| +11 | `10480800` | Sát thương tất cả Tướng gây ra +8000 , miễn giảm sát thương +8000 | Đội xuất trận · ST cộng +8000, Miễn giảm ST +8000 | Hoạt động |
| +12 | `10490480` | HP+28800 | Bản thân · HP +28800 | Hoạt động |
| +13 | `10030870` | Bạo Kích +4350 | Bản thân · Bạo +4350 | Hoạt động |
| +14 | `10500800` | Công+4800 | Bản thân · Công +4800 | Hoạt động |
| +15 | `20480830` | Mục tiêu của bản thân khi lượng máu cao,gây ST tăng 52% | Buff `10180830` | Chưa áp dụng |

## Tokajin (`12012033`)

Bậc tối đa từ HeroStepRelation +8. Bậc tài năng cao nhất trong bảng +8.

| Bậc | TAL | Hiệu ứng VN | Dữ liệu áp dụng | R7.16 |
|---:|---:|---|---|---|
| +2 | `10140120` | Thủ +60 | Bản thân · Thủ +60 | Hoạt động |
| +3 | `10040120` | Đỡ +600 | Bản thân · Đỡ +600 | Hoạt động |
| +4 | `10250000` | Công của tất cả Tướng +80 | Đội xuất trận · Công +80 | Hoạt động |
| +5 | `20270401` | Khi tấn công thường, 50% khiến mục tiêu [Im Lặng] 1 lượt | Buff `20280401` | Chưa áp dụng |
| +6 | `10010000` | Mới bắt đầu tăng 50đ Nộ, lượt đầu có thể Nộ Công | Bản thân · Nộ +50 | Hoạt động |
| +7 | `10260000` | HP của tất cả Tướng +800 | Đội xuất trận · HP +800 | Hoạt động |
| +8 | `10040400` | Đỡ +2000 | Bản thân · Đỡ +2000 | Hoạt động |

## Hitomiko (`12012009`)

Bậc tối đa từ HeroStepRelation +15. Bậc tài năng cao nhất trong bảng +15.

| Bậc | TAL | Hiệu ứng VN | Dữ liệu áp dụng | R7.16 |
|---:|---:|---|---|---|
| +2 | `10150160` | HP +800 | Bản thân · HP +800 | Hoạt động |
| +3 | `10060160` | Né +640 | Bản thân · Né +640 | Hoạt động |
| +4 | `10190000` | Công của tất cả Tướng +200 | Đội xuất trận · Công +200 | Hoạt động |
| +5 | `10020400` | Chịu ST giảm 12% | Bản thân · % miễn giảm ST +12% | Hoạt động |
| +6 | `10010000` | Mới bắt đầu tăng 50đ Nộ, lượt đầu có thể Nộ Công | Bản thân · Nộ +50 | Hoạt động |
| +7 | `10200000` | HP của tất cả Tướng +2000 | Đội xuất trận · HP +2000 | Hoạt động |
| +8 | `10100600` | Điểm Trị Liệu +18% | Bản thân · % Trị Liệu +30% | Hoạt động |
| +9 | `10210000` | Tất cả thuộc tính của Tướng +3% | Đội xuất trận · % Công +3%, % HP +3%, % Thủ +3% | Hoạt động |
| +10 | `20920808` | Khi Nộ Công, có 50% khiến mục tiêu Bất Tử trong 1 lượt | Buff `20470808` | Chưa áp dụng |
| +11 | `10480800` | Sát thương tất cả Tướng gây ra +8000 , miễn giảm sát thương +8000 | Đội xuất trận · ST cộng +8000, Miễn giảm ST +8000 | Hoạt động |
| +12 | `10490480` | HP+28800 | Bản thân · HP +28800 | Hoạt động |
| +13 | `10040870` | Đỡ +4350 | Bản thân · Đỡ +4350 | Hoạt động |
| +14 | `10500800` | Công+4800 | Bản thân · Công +4800 | Hoạt động |
| +15 | `10020830` | Chịu ST giảm 25% | Bản thân · % miễn giảm ST +24.9% | Hoạt động |

## Moryomaru (`12013007`)

Bậc tối đa từ HeroStepRelation +15. Bậc tài năng cao nhất trong bảng +15.

| Bậc | TAL | Hiệu ứng VN | Dữ liệu áp dụng | R7.16 |
|---:|---:|---|---|---|
| +2 | `10140160` | Thủ +80 | Bản thân · Thủ +80 | Hoạt động |
| +3 | `10060160` | Né +640 | Bản thân · Né +640 | Hoạt động |
| +4 | `10190000` | Công của tất cả Tướng +200 | Đội xuất trận · Công +200 | Hoạt động |
| +5 | `20450400` | Khi bị tấn công, nếu HP cao hơn kẻ công kích, nhận ST giảm 20% | Buff `10150400` | Chưa áp dụng |
| +6 | `10010000` | Mới bắt đầu tăng 50đ Nộ, lượt đầu có thể Nộ Công | Bản thân · Nộ +50 | Hoạt động |
| +7 | `10200000` | HP của tất cả Tướng +2000 | Đội xuất trận · HP +2000 | Hoạt động |
| +8 | `10020600` | Chịu ST giảm 18% | Bản thân · % miễn giảm ST +18% | Hoạt động |
| +9 | `10210000` | Tất cả thuộc tính của Tướng +3% | Đội xuất trận · % Công +3%, % HP +3%, % Thủ +3% | Hoạt động |
| +10 | `20070800` | Khi bị tấn công, 40% giảm 25đ Nộ của kẻ công kích | Buff `10400800` | Chưa áp dụng |
| +11 | `10480800` | Sát thương tất cả Tướng gây ra +8000 , miễn giảm sát thương +8000 | Đội xuất trận · ST cộng +8000, Miễn giảm ST +8000 | Hoạt động |
| +12 | `10490480` | HP+28800 | Bản thân · HP +28800 | Hoạt động |
| +13 | `10040870` | Đỡ +4350 | Bản thân · Đỡ +4350 | Hoạt động |
| +14 | `10500800` | Công+4800 | Bản thân · Công +4800 | Hoạt động |
| +15 | `20080830` | Khi bị tấn công thường, gây 25% [Choáng] 1 lượt đối với kẻ công kích | Buff `20140830` | Chưa áp dụng |

## Musou (`12013014`)

Bậc tối đa từ HeroStepRelation +15. Bậc tài năng cao nhất trong bảng +15.

| Bậc | TAL | Hiệu ứng VN | Dữ liệu áp dụng | R7.16 |
|---:|---:|---|---|---|
| +2 | `10150160` | HP +800 | Bản thân · HP +800 | Hoạt động |
| +3 | `10080160` | Chính Xác +800 | Bản thân · Chính Xác +800 | Hoạt động |
| +4 | `10190000` | Công của tất cả Tướng +200 | Đội xuất trận · Công +200 | Hoạt động |
| +5 | `10030400` | Bạo Kích +2000 | Bản thân · Bạo +2000 | Hoạt động |
| +6 | `10010000` | Mới bắt đầu tăng 50đ Nộ, lượt đầu có thể Nộ Công | Bản thân · Nộ +50 | Hoạt động |
| +7 | `10200000` | HP của tất cả Tướng +2000 | Đội xuất trận · HP +2000 | Hoạt động |
| +8 | `20620600` | Khi tử vong, hồi HP bằng 45% Công cho mục tiêu đồng đội tối đa đã mất máu | Buff `10330600` | Chưa áp dụng |
| +9 | `10210000` | Tất cả thuộc tính của Tướng +3% | Đội xuất trận · % Công +3%, % HP +3%, % Thủ +3% | Hoạt động |
| +10 | `20230601` | Khi tấn công thường, 45% giảm 25đ Nộ của mục tiêu | Buff `10500601` | Chưa áp dụng |
| +11 | `10480800` | Sát thương tất cả Tướng gây ra +8000 , miễn giảm sát thương +8000 | Đội xuất trận · ST cộng +8000, Miễn giảm ST +8000 | Hoạt động |
| +12 | `10490480` | HP+28800 | Bản thân · HP +28800 | Hoạt động |
| +13 | `10030870` | Bạo Kích +4350 | Bản thân · Bạo +4350 | Hoạt động |
| +14 | `10500800` | Công+4800 | Bản thân · Công +4800 | Hoạt động |
| +15 | `20320831` | Khi Nộ Công, 62% giảm 50đ Nộ của mục tiêu | Buff `10510831` | Chưa áp dụng |

## Goshinki (`12013011`)

Bậc tối đa từ HeroStepRelation +15. Bậc tài năng cao nhất trong bảng +15.

| Bậc | TAL | Hiệu ứng VN | Dữ liệu áp dụng | R7.16 |
|---:|---:|---|---|---|
| +2 | `10140160` | Thủ +80 | Bản thân · Thủ +80 | Hoạt động |
| +3 | `10040160` | Đỡ +800 | Bản thân · Đỡ +800 | Hoạt động |
| +4 | `10190000` | Công của tất cả Tướng +200 | Đội xuất trận · Công +200 | Hoạt động |
| +5 | `20050400` | Khi bị tấn công thường, gây 20% [Choáng] 1 lượt đối với kẻ công kích | Buff `20130400` | Chưa áp dụng |
| +6 | `10010000` | Mới bắt đầu tăng 50đ Nộ, lượt đầu có thể Nộ Công | Bản thân · Nộ +50 | Hoạt động |
| +7 | `10200000` | HP của tất cả Tướng +2000 | Đội xuất trận · HP +2000 | Hoạt động |
| +8 | `20550600` | Khi HP của bản thân thấp hơn 50%, chịu ST giảm 30% | Buff `10250600` | Chưa áp dụng |
| +9 | `10210000` | Tất cả thuộc tính của Tướng +3% | Đội xuất trận · % Công +3%, % HP +3%, % Thủ +3% | Hoạt động |
| +10 | `20180600` | Khi Nộ Công,  hồi HP bằng 30% ST cho bản thân | Buff `10700600` | Chưa áp dụng |
| +11 | `10480800` | Sát thương tất cả Tướng gây ra +8000 , miễn giảm sát thương +8000 | Đội xuất trận · ST cộng +8000, Miễn giảm ST +8000 | Hoạt động |
| +12 | `10490480` | HP+28800 | Bản thân · HP +28800 | Hoạt động |
| +13 | `10040870` | Đỡ +4350 | Bản thân · Đỡ +4350 | Hoạt động |
| +14 | `10500800` | Công+4800 | Bản thân · Công +4800 | Hoạt động |
| +15 | `10020830` | Chịu ST giảm 25% | Bản thân · % miễn giảm ST +24.9% | Hoạt động |

## Mukotsu (`12013026`)

Bậc tối đa từ HeroStepRelation +8. Bậc tài năng cao nhất trong bảng +8.

| Bậc | TAL | Hiệu ứng VN | Dữ liệu áp dụng | R7.16 |
|---:|---:|---|---|---|
| +2 | `10150120` | HP +600 | Bản thân · HP +600 | Hoạt động |
| +3 | `10060120` | Né +480 | Bản thân · Né +480 | Hoạt động |
| +4 | `10250000` | Công của tất cả Tướng +80 | Đội xuất trận · Công +80 | Hoạt động |
| +5 | `20460400` | Khi bị tấn công, nếu HP thấp hơn kẻ công kích, chịu ST giảm 20% | Buff `10160400` | Chưa áp dụng |
| +6 | `10010000` | Mới bắt đầu tăng 50đ Nộ, lượt đầu có thể Nộ Công | Bản thân · Nộ +50 | Hoạt động |
| +7 | `10260000` | HP của tất cả Tướng +800 | Đội xuất trận · HP +800 | Hoạt động |
| +8 | `10100400` | Điểm Trị Liệu +12% | Bản thân · % Trị Liệu +20% | Hoạt động |

## Karan (`12013028`)

Bậc tối đa từ HeroStepRelation +8. Bậc tài năng cao nhất trong bảng +8.

| Bậc | TAL | Hiệu ứng VN | Dữ liệu áp dụng | R7.16 |
|---:|---:|---|---|---|
| +2 | `10130120` | Công +60 | Bản thân · Công +60 | Hoạt động |
| +3 | `10030120` | Bạo Kích +600 | Bản thân · Bạo +600 | Hoạt động |
| +4 | `10250000` | Công của tất cả Tướng +80 | Đội xuất trận · Công +80 | Hoạt động |
| +5 | `20480400` | Mục tiêu của bản thân khi lượng máu cao,gây ST tăng 20% | Buff `10180400` | Chưa áp dụng |
| +6 | `10010000` | Mới bắt đầu tăng 50đ Nộ, lượt đầu có thể Nộ Công | Bản thân · Nộ +50 | Hoạt động |
| +7 | `10260000` | HP của tất cả Tướng +800 | Đội xuất trận · HP +800 | Hoạt động |
| +8 | `20440406` | Khi tấn công bị Đỡ, lần ST kế tiếp tăng 20% | Buff `20100406` | Chưa áp dụng |

## 限时Boss1 (`12010011`)

Bậc tối đa từ HeroStepRelation +15. Bậc tài năng cao nhất trong bảng +15.

| Bậc | TAL | Hiệu ứng VN | Dữ liệu áp dụng | R7.16 |
|---:|---:|---|---|---|
| +1 | `20910000` | Miễn dịch Choáng; miễn dịch Im Lặng; miễn dịch Giảm Nộ; miễn dịch Phản ST | Buff `10010000`, `10020000`, `10060000`, `10070000` | Chưa áp dụng |
| +2 | `10130160` | Công +80 | Bản thân · Công +80 | Hoạt động |
| +3 | `10130160` | Công +80 | Bản thân · Công +80 | Hoạt động |
| +4 | `10131000` | Công +500 | Bản thân · Công +500 | Hoạt động |
| +5 | `10130400` | Công +200 | Bản thân · Công +200 | Hoạt động |
| +6 | `10131000` | Công +500 | Bản thân · Công +500 | Hoạt động |
| +7 | `20351008` | Khi Nộ Công, 57% khiến mục tiêu [Trúng Độc] 2 lượt | Buff `20441008` | Chưa áp dụng |
| +11 | `10480800` | Sát thương tất cả Tướng gây ra +8000 , miễn giảm sát thương +8000 | Đội xuất trận · ST cộng +8000, Miễn giảm ST +8000 | Hoạt động |
| +12 | `10490480` | HP+28800 | Bản thân · HP +28800 | Hoạt động |
| +13 | `10080870` | Chính Xác +4350 | Bản thân · Chính Xác +4350 | Hoạt động |
| +14 | `10500800` | Công+4800 | Bản thân · Công +4800 | Hoạt động |
| +15 | `20660830` | Khi Nộ Công, bỏ qua 83% Thủ của mục tiêu | Buff `10560830` | Chưa áp dụng |

## 限时Boss2 (`12010012`)

Bậc tối đa từ HeroStepRelation +15. Bậc tài năng cao nhất trong bảng +15.

| Bậc | TAL | Hiệu ứng VN | Dữ liệu áp dụng | R7.16 |
|---:|---:|---|---|---|
| +1 | `20910000` | Miễn dịch Choáng; miễn dịch Im Lặng; miễn dịch Giảm Nộ; miễn dịch Phản ST | Buff `10010000`, `10020000`, `10060000`, `10070000` | Chưa áp dụng |
| +2 | `10130160` | Công +80 | Bản thân · Công +80 | Hoạt động |
| +3 | `10130160` | Công +80 | Bản thân · Công +80 | Hoạt động |
| +4 | `10131000` | Công +500 | Bản thân · Công +500 | Hoạt động |
| +5 | `10130400` | Công +200 | Bản thân · Công +200 | Hoạt động |
| +6 | `10131000` | Công +500 | Bản thân · Công +500 | Hoạt động |
| +7 | `10131000` | Công +500 | Bản thân · Công +500 | Hoạt động |
| +11 | `10480800` | Sát thương tất cả Tướng gây ra +8000 , miễn giảm sát thương +8000 | Đội xuất trận · ST cộng +8000, Miễn giảm ST +8000 | Hoạt động |
| +12 | `10490480` | HP+28800 | Bản thân · HP +28800 | Hoạt động |
| +13 | `10080870` | Chính Xác +4350 | Bản thân · Chính Xác +4350 | Hoạt động |
| +14 | `10500800` | Công+4800 | Bản thân · Công +4800 | Hoạt động |
| +15 | `20660830` | Khi Nộ Công, bỏ qua 83% Thủ của mục tiêu | Buff `10560830` | Chưa áp dụng |

## 限时Boss3 (`12010013`)

Bậc tối đa từ HeroStepRelation +15. Bậc tài năng cao nhất trong bảng +15.

| Bậc | TAL | Hiệu ứng VN | Dữ liệu áp dụng | R7.16 |
|---:|---:|---|---|---|
| +1 | `20910000` | Miễn dịch Choáng; miễn dịch Im Lặng; miễn dịch Giảm Nộ; miễn dịch Phản ST | Buff `10010000`, `10020000`, `10060000`, `10070000` | Chưa áp dụng |
| +2 | `10130160` | Công +80 | Bản thân · Công +80 | Hoạt động |
| +3 | `10130160` | Công +80 | Bản thân · Công +80 | Hoạt động |
| +4 | `10131000` | Công +500 | Bản thân · Công +500 | Hoạt động |
| +5 | `10130400` | Công +200 | Bản thân · Công +200 | Hoạt động |
| +6 | `10131000` | Công +500 | Bản thân · Công +500 | Hoạt động |
| +7 | `10131000` | Công +500 | Bản thân · Công +500 | Hoạt động |
| +11 | `10480800` | Sát thương tất cả Tướng gây ra +8000 , miễn giảm sát thương +8000 | Đội xuất trận · ST cộng +8000, Miễn giảm ST +8000 | Hoạt động |
| +12 | `10490480` | HP+28800 | Bản thân · HP +28800 | Hoạt động |
| +13 | `10080870` | Chính Xác +4350 | Bản thân · Chính Xác +4350 | Hoạt động |
| +14 | `10500800` | Công+4800 | Bản thân · Công +4800 | Hoạt động |
| +15 | `20660830` | Khi Nộ Công, bỏ qua 83% Thủ của mục tiêu | Buff `10560830` | Chưa áp dụng |

## 限时Boss4 (`12010014`)

Bậc tối đa từ HeroStepRelation +15. Bậc tài năng cao nhất trong bảng +15.

| Bậc | TAL | Hiệu ứng VN | Dữ liệu áp dụng | R7.16 |
|---:|---:|---|---|---|
| +1 | `20910000` | Miễn dịch Choáng; miễn dịch Im Lặng; miễn dịch Giảm Nộ; miễn dịch Phản ST | Buff `10010000`, `10020000`, `10060000`, `10070000` | Chưa áp dụng |
| +2 | `10130160` | Công +80 | Bản thân · Công +80 | Hoạt động |
| +3 | `10130160` | Công +80 | Bản thân · Công +80 | Hoạt động |
| +4 | `10131000` | Công +500 | Bản thân · Công +500 | Hoạt động |
| +5 | `10130400` | Công +200 | Bản thân · Công +200 | Hoạt động |
| +6 | `10131000` | Công +500 | Bản thân · Công +500 | Hoạt động |
| +7 | `10131000` | Công +500 | Bản thân · Công +500 | Hoạt động |
| +11 | `10480800` | Sát thương tất cả Tướng gây ra +8000 , miễn giảm sát thương +8000 | Đội xuất trận · ST cộng +8000, Miễn giảm ST +8000 | Hoạt động |
| +12 | `10490480` | HP+28800 | Bản thân · HP +28800 | Hoạt động |
| +13 | `10080870` | Chính Xác +4350 | Bản thân · Chính Xác +4350 | Hoạt động |
| +14 | `10500800` | Công+4800 | Bản thân · Công +4800 | Hoạt động |
| +15 | `20660830` | Khi Nộ Công, bỏ qua 83% Thủ của mục tiêu | Buff `10560830` | Chưa áp dụng |

## 限时Boss5 (`12010015`)

Bậc tối đa từ HeroStepRelation +15. Bậc tài năng cao nhất trong bảng +15.

| Bậc | TAL | Hiệu ứng VN | Dữ liệu áp dụng | R7.16 |
|---:|---:|---|---|---|
| +1 | `20910000` | Miễn dịch Choáng; miễn dịch Im Lặng; miễn dịch Giảm Nộ; miễn dịch Phản ST | Buff `10010000`, `10020000`, `10060000`, `10070000` | Chưa áp dụng |
| +2 | `10130160` | Công +80 | Bản thân · Công +80 | Hoạt động |
| +3 | `10130160` | Công +80 | Bản thân · Công +80 | Hoạt động |
| +4 | `10131000` | Công +500 | Bản thân · Công +500 | Hoạt động |
| +5 | `10130400` | Công +200 | Bản thân · Công +200 | Hoạt động |
| +6 | `10131000` | Công +500 | Bản thân · Công +500 | Hoạt động |
| +7 | `10131000` | Công +500 | Bản thân · Công +500 | Hoạt động |
| +11 | `10480800` | Sát thương tất cả Tướng gây ra +8000 , miễn giảm sát thương +8000 | Đội xuất trận · ST cộng +8000, Miễn giảm ST +8000 | Hoạt động |
| +12 | `10490480` | HP+28800 | Bản thân · HP +28800 | Hoạt động |
| +13 | `10080870` | Chính Xác +4350 | Bản thân · Chính Xác +4350 | Hoạt động |
| +14 | `10500800` | Công+4800 | Bản thân · Công +4800 | Hoạt động |
| +15 | `20660830` | Khi Nộ Công, bỏ qua 83% Thủ của mục tiêu | Buff `10560830` | Chưa áp dụng |

## 限时Boss6 (`12010016`)

Bậc tối đa từ HeroStepRelation +15. Bậc tài năng cao nhất trong bảng +15.

| Bậc | TAL | Hiệu ứng VN | Dữ liệu áp dụng | R7.16 |
|---:|---:|---|---|---|
| +1 | `20910000` | Miễn dịch Choáng; miễn dịch Im Lặng; miễn dịch Giảm Nộ; miễn dịch Phản ST | Buff `10010000`, `10020000`, `10060000`, `10070000` | Chưa áp dụng |
| +2 | `10130160` | Công +80 | Bản thân · Công +80 | Hoạt động |
| +3 | `10130160` | Công +80 | Bản thân · Công +80 | Hoạt động |
| +4 | `10131000` | Công +500 | Bản thân · Công +500 | Hoạt động |
| +5 | `10130400` | Công +200 | Bản thân · Công +200 | Hoạt động |
| +6 | `10131000` | Công +500 | Bản thân · Công +500 | Hoạt động |
| +7 | `10131000` | Công +500 | Bản thân · Công +500 | Hoạt động |
| +11 | `10480800` | Sát thương tất cả Tướng gây ra +8000 , miễn giảm sát thương +8000 | Đội xuất trận · ST cộng +8000, Miễn giảm ST +8000 | Hoạt động |
| +12 | `10490480` | HP+28800 | Bản thân · HP +28800 | Hoạt động |
| +13 | `10080870` | Chính Xác +4350 | Bản thân · Chính Xác +4350 | Hoạt động |
| +14 | `10500800` | Công+4800 | Bản thân · Công +4800 | Hoạt động |
| +15 | `20660830` | Khi Nộ Công, bỏ qua 83% Thủ của mục tiêu | Buff `10560830` | Chưa áp dụng |

## Rin (`12012010`)

Bậc tối đa từ HeroStepRelation +15. Bậc tài năng cao nhất trong bảng +15.

| Bậc | TAL | Hiệu ứng VN | Dữ liệu áp dụng | R7.16 |
|---:|---:|---|---|---|
| +2 | `10150160` | HP +800 | Bản thân · HP +800 | Hoạt động |
| +3 | `10080160` | Chính Xác +800 | Bản thân · Chính Xác +800 | Hoạt động |
| +4 | `10220000` | Công của tất cả Tướng +125 | Đội xuất trận · Công +125 | Hoạt động |
| +5 | `20480400` | Mục tiêu của bản thân khi lượng máu cao,gây ST tăng 20% | Buff `10180400` | Chưa áp dụng |
| +6 | `10010000` | Mới bắt đầu tăng 50đ Nộ, lượt đầu có thể Nộ Công | Bản thân · Nộ +50 | Hoạt động |
| +7 | `10230000` | HP của tất cả Tướng +1250 | Đội xuất trận · HP +1250 | Hoạt động |
| +8 | `20190400` | Khi tấn công thường, 30% tăng 25đ Nộ cho mục tiêu đồng đội có Nộ thấp nhất | Buff `10530400` | Chưa áp dụng |
| +9 | `10240000` | Tất cả thuộc tính của Tướng +2% | Đội xuất trận · % Công +2%, % HP +2%, % Thủ +2% | Hoạt động |
| +10 | `20370607` | Khi Nộ Công, 60% khiến mục tiêu [Im Lặng] 1 lượt | Buff `20290607` | Chưa áp dụng |
| +11 | `10480500` | Sát thương tất cả Tướng gây ra +5000 , miễn giảm sát thương +5000 | Đội xuất trận · ST cộng +5000, Miễn giảm ST +5000 | Hoạt động |
| +12 | `10490300` | HP+18000 | Bản thân · HP +18000 | Hoạt động |
| +13 | `10640600` | Phá Kích+3000 | Bản thân · Phá Kích +3000 | Hoạt động |
| +14 | `10500500` | Công+3000 | Bản thân · Công +3000 | Hoạt động |
| +15 | `10020500` | Chịu ST giảm 15% | Bản thân · % miễn giảm ST +15% | Hoạt động |

## Jaken (`12012006`)

Bậc tối đa từ HeroStepRelation +15. Bậc tài năng cao nhất trong bảng +15.

| Bậc | TAL | Hiệu ứng VN | Dữ liệu áp dụng | R7.16 |
|---:|---:|---|---|---|
| +2 | `10140160` | Thủ +80 | Bản thân · Thủ +80 | Hoạt động |
| +3 | `10040160` | Đỡ +800 | Bản thân · Đỡ +800 | Hoạt động |
| +4 | `10190000` | Công của tất cả Tướng +200 | Đội xuất trận · Công +200 | Hoạt động |
| +5 | `10040400` | Đỡ +2000 | Bản thân · Đỡ +2000 | Hoạt động |
| +6 | `10010000` | Mới bắt đầu tăng 50đ Nộ, lượt đầu có thể Nộ Công | Bản thân · Nộ +50 | Hoạt động |
| +7 | `10200000` | HP của tất cả Tướng +2000 | Đội xuất trận · HP +2000 | Hoạt động |
| +8 | `20540600` | Khi HP của bản thân cao hơn 50%, chịu ST giảm 30% | Buff `10240600` | Chưa áp dụng |
| +9 | `10210000` | Tất cả thuộc tính của Tướng +3% | Đội xuất trận · % Công +3%, % HP +3%, % Thủ +3% | Hoạt động |
| +10 | `20730800` | Đỡ phản kích, gây ST bằng 100% Công | Buff `20050800` | Chưa áp dụng |
| +11 | `10480800` | Sát thương tất cả Tướng gây ra +8000 , miễn giảm sát thương +8000 | Đội xuất trận · ST cộng +8000, Miễn giảm ST +8000 | Hoạt động |
| +12 | `10490480` | HP+28800 | Bản thân · HP +28800 | Hoạt động |
| +13 | `10650870` | Kháng Bạo+4350 | Bản thân · Kháng Bạo +4350 | Hoạt động |
| +14 | `10500800` | Công+4800 | Bản thân · Công +4800 | Hoạt động |
| +15 | `20070830` | Khi bị tấn công, 42% giảm 25đ Nộ của kẻ công kích | Buff `10400830` | Chưa áp dụng |

## Hoshiyomi (`12012016`)

Bậc tối đa từ HeroStepRelation +15. Bậc tài năng cao nhất trong bảng +15.

| Bậc | TAL | Hiệu ứng VN | Dữ liệu áp dụng | R7.16 |
|---:|---:|---|---|---|
| +2 | `10130160` | Công +80 | Bản thân · Công +80 | Hoạt động |
| +3 | `10030160` | Bạo Kích +800 | Bản thân · Bạo +800 | Hoạt động |
| +4 | `10190000` | Công của tất cả Tướng +200 | Đội xuất trận · Công +200 | Hoạt động |
| +5 | `10080400` | Chính Xác +2000 | Bản thân · Chính Xác +2000 | Hoạt động |
| +6 | `10010000` | Mới bắt đầu tăng 50đ Nộ, lượt đầu có thể Nộ Công | Bản thân · Nộ +50 | Hoạt động |
| +7 | `10200000` | HP của tất cả Tướng +2000 | Đội xuất trận · HP +2000 | Hoạt động |
| +8 | `10070600` | Bạo Kích +1500, ST Bạo +3000 | Bản thân · Bạo +1500, Tất Sát +3000 | Hoạt động |
| +9 | `10210000` | Tất cả thuộc tính của Tướng +3% | Đội xuất trận · % Công +3%, % HP +3%, % Thủ +3% | Hoạt động |
| +10 | `20690601` | Khi Bạo Kích, 48% công thường lần nữa | Buff `20040601` | Chưa áp dụng |
| +11 | `10480800` | Sát thương tất cả Tướng gây ra +8000 , miễn giảm sát thương +8000 | Đội xuất trận · ST cộng +8000, Miễn giảm ST +8000 | Hoạt động |
| +12 | `10490480` | HP+28800 | Bản thân · HP +28800 | Hoạt động |
| +13 | `10080870` | Chính Xác +4350 | Bản thân · Chính Xác +4350 | Hoạt động |
| +14 | `10500800` | Công+4800 | Bản thân · Công +4800 | Hoạt động |
| +15 | `20110830` | Sau mỗi lần bị tấn công, Công tăng 8%, tối đa 25% | Buff `20170830` | Chưa áp dụng |

## Kyokotsu (`12013027`)

Bậc tối đa từ HeroStepRelation +8. Bậc tài năng cao nhất trong bảng +8.

| Bậc | TAL | Hiệu ứng VN | Dữ liệu áp dụng | R7.16 |
|---:|---:|---|---|---|
| +2 | `10130120` | Công +60 | Bản thân · Công +60 | Hoạt động |
| +3 | `10030120` | Bạo Kích +600 | Bản thân · Bạo +600 | Hoạt động |
| +4 | `10250000` | Công của tất cả Tướng +80 | Đội xuất trận · Công +80 | Hoạt động |
| +5 | `20220401` | Khi tấn công thường, 80% giảm 45% Thủ 1 lượt của mục tiêu | Buff `20420401` | Chưa áp dụng |
| +6 | `10010000` | Mới bắt đầu tăng 50đ Nộ, lượt đầu có thể Nộ Công | Bản thân · Nộ +50 | Hoạt động |
| +7 | `10260000` | HP của tất cả Tướng +800 | Đội xuất trận · HP +800 | Hoạt động |
| +8 | `20340401` | Khi Nộ Công, 60% giảm 75% hiệu quả trị liệu 2 lượt của mục tiêu | Buff `20300401` | Chưa áp dụng |

## Kyora (`12012021`)

Bậc tối đa từ HeroStepRelation +15. Bậc tài năng cao nhất trong bảng +15.

| Bậc | TAL | Hiệu ứng VN | Dữ liệu áp dụng | R7.16 |
|---:|---:|---|---|---|
| +2 | `10150160` | HP +800 | Bản thân · HP +800 | Hoạt động |
| +3 | `10060160` | Né +640 | Bản thân · Né +640 | Hoạt động |
| +4 | `10220000` | Công của tất cả Tướng +125 | Đội xuất trận · Công +125 | Hoạt động |
| +5 | `20480400` | Mục tiêu của bản thân khi lượng máu cao,gây ST tăng 20% | Buff `10180400` | Chưa áp dụng |
| +6 | `10010000` | Mới bắt đầu tăng 50đ Nộ, lượt đầu có thể Nộ Công | Bản thân · Nộ +50 | Hoạt động |
| +7 | `10230000` | HP của tất cả Tướng +1250 | Đội xuất trận · HP +1250 | Hoạt động |
| +8 | `10030400` | Bạo Kích +2000 | Bản thân · Bạo +2000 | Hoạt động |
| +9 | `10240000` | Tất cả thuộc tính của Tướng +2% | Đội xuất trận · % Công +2%, % HP +2%, % Thủ +2% | Hoạt động |
| +10 | `20630600` | Ra trận lần 1 khi tấn công, ST gây ra tăng 75% | Buff `10130600` | Chưa áp dụng |
| +11 | `10480500` | Sát thương tất cả Tướng gây ra +5000 , miễn giảm sát thương +5000 | Đội xuất trận · ST cộng +5000, Miễn giảm ST +5000 | Hoạt động |
| +12 | `10490300` | HP+18000 | Bản thân · HP +18000 | Hoạt động |
| +13 | `10650600` | Kháng Bạo+3000 | Bản thân · Kháng Bạo +3000 | Hoạt động |
| +14 | `10500500` | Công+3000 | Bản thân · Công +3000 | Hoạt động |
| +15 | `20640500` | Ra trận lần 1,2,3, khi bản thân chịu ST giảm 38% | Buff `10140500` | Chưa áp dụng |

## Genbu (`12012025`)

Bậc tối đa từ HeroStepRelation +8. Bậc tài năng cao nhất trong bảng +8.

| Bậc | TAL | Hiệu ứng VN | Dữ liệu áp dụng | R7.16 |
|---:|---:|---|---|---|
| +2 | `10140120` | Thủ +60 | Bản thân · Thủ +60 | Hoạt động |
| +3 | `10040120` | Đỡ +600 | Bản thân · Đỡ +600 | Hoạt động |
| +4 | `10250000` | Công của tất cả Tướng +80 | Đội xuất trận · Công +80 | Hoạt động |
| +5 | `10040400` | Đỡ +2000 | Bản thân · Đỡ +2000 | Hoạt động |
| +6 | `10010000` | Mới bắt đầu tăng 50đ Nộ, lượt đầu có thể Nộ Công | Bản thân · Nộ +50 | Hoạt động |
| +7 | `10260000` | HP của tất cả Tướng +800 | Đội xuất trận · HP +800 | Hoạt động |
| +8 | `20550400` | Khi HP của bản thân thấp hơn 50%, chịu ST giảm 20% | Buff `10250400` | Chưa áp dụng |

## Yukionna (`12011027`)

Bậc tối đa từ HeroStepRelation +8. Bậc tài năng cao nhất trong bảng +8.

| Bậc | TAL | Hiệu ứng VN | Dữ liệu áp dụng | R7.16 |
|---:|---:|---|---|---|
| +2 | `10130120` | Công +60 | Bản thân · Công +60 | Hoạt động |
| +3 | `10030120` | Bạo Kích +600 | Bản thân · Bạo +600 | Hoạt động |
| +4 | `10250000` | Công của tất cả Tướng +80 | Đội xuất trận · Công +80 | Hoạt động |
| +5 | `20250401` | Khi tấn công thường, 67% khiến mục tiêu [Trúng Độc] 2 lượt | Buff `20310401` | Chưa áp dụng |
| +6 | `10010000` | Mới bắt đầu tăng 50đ Nộ, lượt đầu có thể Nộ Công | Bản thân · Nộ +50 | Hoạt động |
| +7 | `10260000` | HP của tất cả Tướng +800 | Đội xuất trận · HP +800 | Hoạt động |
| +8 | `20570400` | Đối với mục tiêu bị [Trúng Độc] gây ST tăng 24% | Buff `10270400` | Chưa áp dụng |

## Yoreitaisei (`12011018`)

Bậc tối đa từ HeroStepRelation +15. Bậc tài năng cao nhất trong bảng +15.

| Bậc | TAL | Hiệu ứng VN | Dữ liệu áp dụng | R7.16 |
|---:|---:|---|---|---|
| +2 | `10150160` | HP +800 | Bản thân · HP +800 | Hoạt động |
| +3 | `10060160` | Né +640 | Bản thân · Né +640 | Hoạt động |
| +4 | `10220000` | Công của tất cả Tướng +125 | Đội xuất trận · Công +125 | Hoạt động |
| +5 | `20480400` | Mục tiêu của bản thân khi lượng máu cao,gây ST tăng 20% | Buff `10180400` | Chưa áp dụng |
| +6 | `10010000` | Mới bắt đầu tăng 50đ Nộ, lượt đầu có thể Nộ Công | Bản thân · Nộ +50 | Hoạt động |
| +7 | `10230000` | HP của tất cả Tướng +1250 | Đội xuất trận · HP +1250 | Hoạt động |
| +8 | `20180400` | Khi Nộ Công,  hồi HP bằng 20% ST cho bản thân | Buff `10700400` | Chưa áp dụng |
| +9 | `10240000` | Tất cả thuộc tính của Tướng +2% | Đội xuất trận · % Công +2%, % HP +2%, % Thủ +2% | Hoạt động |
| +10 | `20590600` | Khi tử vong, 60% giảm 25đ Nộ của tất cả địch | Buff `10300600` | Chưa áp dụng |
| +11 | `10480500` | Sát thương tất cả Tướng gây ra +5000 , miễn giảm sát thương +5000 | Đội xuất trận · ST cộng +5000, Miễn giảm ST +5000 | Hoạt động |
| +12 | `10490300` | HP+18000 | Bản thân · HP +18000 | Hoạt động |
| +13 | `10030600` | Bạo Kích +3000 | Bản thân · Bạo +3000 | Hoạt động |
| +14 | `10500500` | Công+3000 | Bản thân · Công +3000 | Hoạt động |
| +15 | `20980504` | Khi đánh kỹ năng Nộ, 100% khiến mục tiêu nhận thêm 33% ST trong 1 lượt | Buff `20540504` | Chưa áp dụng |

## Yakurodokusen (`12011017`)

Bậc tối đa từ HeroStepRelation +15. Bậc tài năng cao nhất trong bảng +15.

| Bậc | TAL | Hiệu ứng VN | Dữ liệu áp dụng | R7.16 |
|---:|---:|---|---|---|
| +2 | `10130160` | Công +80 | Bản thân · Công +80 | Hoạt động |
| +3 | `10030160` | Bạo Kích +800 | Bản thân · Bạo +800 | Hoạt động |
| +4 | `10220000` | Công của tất cả Tướng +125 | Đội xuất trận · Công +125 | Hoạt động |
| +5 | `10030400` | Bạo Kích +2000 | Bản thân · Bạo +2000 | Hoạt động |
| +6 | `10010000` | Mới bắt đầu tăng 50đ Nộ, lượt đầu có thể Nộ Công | Bản thân · Nộ +50 | Hoạt động |
| +7 | `10230000` | HP của tất cả Tướng +1250 | Đội xuất trận · HP +1250 | Hoạt động |
| +8 | `20660400` | Khi Nộ Công, bỏ qua 40% Thủ của mục tiêu | Buff `10560400` | Chưa áp dụng |
| +9 | `10240000` | Tất cả thuộc tính của Tướng +2% | Đội xuất trận · % Công +2%, % HP +2%, % Thủ +2% | Hoạt động |
| +10 | `20720600` | Khi tấn công thường, gây thêm 60% ST cho mục tiêu lân cận | Buff `20590600` | Chưa áp dụng |
| +11 | `10480500` | Sát thương tất cả Tướng gây ra +5000 , miễn giảm sát thương +5000 | Đội xuất trận · ST cộng +5000, Miễn giảm ST +5000 | Hoạt động |
| +12 | `10490300` | HP+18000 | Bản thân · HP +18000 | Hoạt động |
| +13 | `10080600` | Chính Xác +3000 | Bản thân · Chính Xác +3000 | Hoạt động |
| +14 | `10500500` | Công+3000 | Bản thân · Công +3000 | Hoạt động |
| +15 | `21220500` | Khi đánh kỹ năng Nộ, 40% tăng 50đ Nộ cho bản thân | Buff `11110500` | Chưa áp dụng |

## Royakan (`12012011`)

Bậc tối đa từ HeroStepRelation +15. Bậc tài năng cao nhất trong bảng +15.

| Bậc | TAL | Hiệu ứng VN | Dữ liệu áp dụng | R7.16 |
|---:|---:|---|---|---|
| +2 | `10140160` | Thủ +80 | Bản thân · Thủ +80 | Hoạt động |
| +3 | `10060160` | Né +640 | Bản thân · Né +640 | Hoạt động |
| +4 | `10220000` | Công của tất cả Tướng +125 | Đội xuất trận · Công +125 | Hoạt động |
| +5 | `20650000` | Lần đầu bị tấn công, tỷ lệ Né +100% | Buff `10120000` | Chưa áp dụng |
| +6 | `10010000` | Mới bắt đầu tăng 50đ Nộ, lượt đầu có thể Nộ Công | Bản thân · Nộ +50 | Hoạt động |
| +7 | `10230000` | HP của tất cả Tướng +1250 | Đội xuất trận · HP +1250 | Hoạt động |
| +8 | `20100400` | Sau mỗi lần bị tấn công, ST giảm +6%, tối đa 18% | Buff `20160400` | Chưa áp dụng |
| +9 | `10240000` | Tất cả thuộc tính của Tướng +2% | Đội xuất trận · % Công +2%, % HP +2%, % Thủ +2% | Hoạt động |
| +10 | `20420600` | Khi Né, 90% tăng 25đ Nộ | Buff `10370600` | Chưa áp dụng |
| +11 | `10480500` | Sát thương tất cả Tướng gây ra +5000 , miễn giảm sát thương +5000 | Đội xuất trận · ST cộng +5000, Miễn giảm ST +5000 | Hoạt động |
| +12 | `10490300` | HP+18000 | Bản thân · HP +18000 | Hoạt động |
| +13 | `10650600` | Kháng Bạo+3000 | Bản thân · Kháng Bạo +3000 | Hoạt động |
| +14 | `10500500` | Công+3000 | Bản thân · Công +3000 | Hoạt động |
| +15 | `20660500` | Khi Nộ Công, bỏ qua 50% Thủ của mục tiêu | Buff `10560500` | Chưa áp dụng |

## Ginkotsu (`12013025`)

Bậc tối đa từ HeroStepRelation +8. Bậc tài năng cao nhất trong bảng +8.

| Bậc | TAL | Hiệu ứng VN | Dữ liệu áp dụng | R7.16 |
|---:|---:|---|---|---|
| +2 | `10140120` | Thủ +60 | Bản thân · Thủ +60 | Hoạt động |
| +3 | `10040120` | Đỡ +600 | Bản thân · Đỡ +600 | Hoạt động |
| +4 | `10250000` | Công của tất cả Tướng +80 | Đội xuất trận · Công +80 | Hoạt động |
| +5 | `20730400` | Đỡ phản kích, gây ST bằng 50% Công | Buff `20050400` | Chưa áp dụng |
| +6 | `10010000` | Mới bắt đầu tăng 50đ Nộ, lượt đầu có thể Nộ Công | Bản thân · Nộ +50 | Hoạt động |
| +7 | `10260000` | HP của tất cả Tướng +800 | Đội xuất trận · HP +800 | Hoạt động |
| +8 | `20550400` | Khi HP của bản thân thấp hơn 50%, chịu ST giảm 20% | Buff `10250400` | Chưa áp dụng |

## Ginka (`12012030`)

Bậc tối đa từ HeroStepRelation +8. Bậc tài năng cao nhất trong bảng +8.

| Bậc | TAL | Hiệu ứng VN | Dữ liệu áp dụng | R7.16 |
|---:|---:|---|---|---|
| +2 | `10130120` | Công +60 | Bản thân · Công +60 | Hoạt động |
| +3 | `10030120` | Bạo Kích +600 | Bản thân · Bạo +600 | Hoạt động |
| +4 | `10250000` | Công của tất cả Tướng +80 | Đội xuất trận · Công +80 | Hoạt động |
| +5 | `20250401` | Khi tấn công thường, 67% khiến mục tiêu [Trúng Độc] 2 lượt | Buff `20310401` | Chưa áp dụng |
| +6 | `10010000` | Mới bắt đầu tăng 50đ Nộ, lượt đầu có thể Nộ Công | Bản thân · Nộ +50 | Hoạt động |
| +7 | `10260000` | HP của tất cả Tướng +800 | Đội xuất trận · HP +800 | Hoạt động |
| +8 | `20570400` | Đối với mục tiêu bị [Trúng Độc] gây ST tăng 24% | Buff `10270400` | Chưa áp dụng |

## Kageromaru (`12013012`)

Bậc tối đa từ HeroStepRelation +15. Bậc tài năng cao nhất trong bảng +15.

| Bậc | TAL | Hiệu ứng VN | Dữ liệu áp dụng | R7.16 |
|---:|---:|---|---|---|
| +2 | `10130160` | Công +80 | Bản thân · Công +80 | Hoạt động |
| +3 | `10030160` | Bạo Kích +800 | Bản thân · Bạo +800 | Hoạt động |
| +4 | `10190000` | Công của tất cả Tướng +200 | Đội xuất trận · Công +200 | Hoạt động |
| +5 | `20480400` | Mục tiêu của bản thân khi lượng máu cao,gây ST tăng 20% | Buff `10180400` | Chưa áp dụng |
| +6 | `10010000` | Mới bắt đầu tăng 50đ Nộ, lượt đầu có thể Nộ Công | Bản thân · Nộ +50 | Hoạt động |
| +7 | `10200000` | HP của tất cả Tướng +2000 | Đội xuất trận · HP +2000 | Hoạt động |
| +8 | `20630600` | Ra trận lần 1 khi tấn công, ST gây ra tăng 75% | Buff `10130600` | Chưa áp dụng |
| +9 | `10210000` | Tất cả thuộc tính của Tướng +3% | Đội xuất trận · % Công +3%, % HP +3%, % Thủ +3% | Hoạt động |
| +10 | `20180600` | Khi Nộ Công,  hồi HP bằng 30% ST cho bản thân | Buff `10700600` | Chưa áp dụng |
| +11 | `10480800` | Sát thương tất cả Tướng gây ra +8000 , miễn giảm sát thương +8000 | Đội xuất trận · ST cộng +8000, Miễn giảm ST +8000 | Hoạt động |
| +12 | `10490480` | HP+28800 | Bản thân · HP +28800 | Hoạt động |
| +13 | `10080870` | Chính Xác +4350 | Bản thân · Chính Xác +4350 | Hoạt động |
| +14 | `10500800` | Công+4800 | Bản thân · Công +4800 | Hoạt động |
| +15 | `20330836` | Khi Nộ Công, 62% giảm 50đ Nộ của mục tiêu | Buff `10450836` | Chưa áp dụng |

## Sarugami (`12011024`)

Bậc tối đa từ HeroStepRelation +8. Bậc tài năng cao nhất trong bảng +8.

| Bậc | TAL | Hiệu ứng VN | Dữ liệu áp dụng | R7.16 |
|---:|---:|---|---|---|
| +2 | `10140120` | Thủ +60 | Bản thân · Thủ +60 | Hoạt động |
| +3 | `10060120` | Né +480 | Bản thân · Né +480 | Hoạt động |
| +4 | `10250000` | Công của tất cả Tướng +80 | Đội xuất trận · Công +80 | Hoạt động |
| +5 | `20650000` | Lần đầu bị tấn công, tỷ lệ Né +100% | Buff `10120000` | Chưa áp dụng |
| +6 | `10010000` | Mới bắt đầu tăng 50đ Nộ, lượt đầu có thể Nộ Công | Bản thân · Nộ +50 | Hoạt động |
| +7 | `10260000` | HP của tất cả Tướng +800 | Đội xuất trận · HP +800 | Hoạt động |
| +8 | `20420400` | Khi Né, 60% tăng 25đ Nộ | Buff `10370400` | Chưa áp dụng |

## Tsukiyomi (`12012017`)

Bậc tối đa từ HeroStepRelation +15. Bậc tài năng cao nhất trong bảng +15.

| Bậc | TAL | Hiệu ứng VN | Dữ liệu áp dụng | R7.16 |
|---:|---:|---|---|---|
| +2 | `10130160` | Công +80 | Bản thân · Công +80 | Hoạt động |
| +3 | `10030160` | Bạo Kích +800 | Bản thân · Bạo +800 | Hoạt động |
| +4 | `10190000` | Công của tất cả Tướng +200 | Đội xuất trận · Công +200 | Hoạt động |
| +5 | `20630400` | Ra trận lần 1 khi tấn công, ST gây ra tăng 50% | Buff `10130400` | Chưa áp dụng |
| +6 | `10010000` | Mới bắt đầu tăng 50đ Nộ, lượt đầu có thể Nộ Công | Bản thân · Nộ +50 | Hoạt động |
| +7 | `10200000` | HP của tất cả Tướng +2000 | Đội xuất trận · HP +2000 | Hoạt động |
| +8 | `10030600` | Bạo Kích +3000 | Bản thân · Bạo +3000 | Hoạt động |
| +9 | `10210000` | Tất cả thuộc tính của Tướng +3% | Đội xuất trận · % Công +3%, % HP +3%, % Thủ +3% | Hoạt động |
| +10 | `10070600` | Bạo Kích +1500, ST Bạo +3000 | Bản thân · Bạo +1500, Tất Sát +3000 | Hoạt động |
| +11 | `10480800` | Sát thương tất cả Tướng gây ra +8000 , miễn giảm sát thương +8000 | Đội xuất trận · ST cộng +8000, Miễn giảm ST +8000 | Hoạt động |
| +12 | `10490480` | HP+28800 | Bản thân · HP +28800 | Hoạt động |
| +13 | `10030870` | Bạo Kích +4350 | Bản thân · Bạo +4350 | Hoạt động |
| +14 | `10500800` | Công+4800 | Bản thân · Công +4800 | Hoạt động |
| +15 | `20480830` | Mục tiêu của bản thân khi lượng máu cao,gây ST tăng 52% | Buff `10180830` | Chưa áp dụng |

## Gakusanjin (`12011032`)

Bậc tối đa từ HeroStepRelation +8. Bậc tài năng cao nhất trong bảng +8.

| Bậc | TAL | Hiệu ứng VN | Dữ liệu áp dụng | R7.16 |
|---:|---:|---|---|---|
| +2 | `10140120` | Thủ +60 | Bản thân · Thủ +60 | Hoạt động |
| +3 | `10040120` | Đỡ +600 | Bản thân · Đỡ +600 | Hoạt động |
| +4 | `10250000` | Công của tất cả Tướng +80 | Đội xuất trận · Công +80 | Hoạt động |
| +5 | `20270401` | Khi tấn công thường, 50% khiến mục tiêu [Im Lặng] 1 lượt | Buff `20280401` | Chưa áp dụng |
| +6 | `10010000` | Mới bắt đầu tăng 50đ Nộ, lượt đầu có thể Nộ Công | Bản thân · Nộ +50 | Hoạt động |
| +7 | `10260000` | HP của tất cả Tướng +800 | Đội xuất trận · HP +800 | Hoạt động |
| +8 | `10020400` | Chịu ST giảm 12% | Bản thân · % miễn giảm ST +12% | Hoạt động |

## Kirara (`12011011`)

Bậc tối đa từ HeroStepRelation +15. Bậc tài năng cao nhất trong bảng +15.

| Bậc | TAL | Hiệu ứng VN | Dữ liệu áp dụng | R7.16 |
|---:|---:|---|---|---|
| +2 | `10130160` | Công +80 | Bản thân · Công +80 | Hoạt động |
| +3 | `10030160` | Bạo Kích +800 | Bản thân · Bạo +800 | Hoạt động |
| +4 | `10190000` | Công của tất cả Tướng +200 | Đội xuất trận · Công +200 | Hoạt động |
| +5 | `20480400` | Mục tiêu của bản thân khi lượng máu cao,gây ST tăng 20% | Buff `10180400` | Chưa áp dụng |
| +6 | `10010000` | Mới bắt đầu tăng 50đ Nộ, lượt đầu có thể Nộ Công | Bản thân · Nộ +50 | Hoạt động |
| +7 | `10200000` | HP của tất cả Tướng +2000 | Đội xuất trận · HP +2000 | Hoạt động |
| +8 | `20240606` | Khi tấn công thường, 30% giảm 80% hiệu quả trị liệu 1 lượt của mục tiêu | Buff `20250606` | Chưa áp dụng |
| +9 | `10210000` | Tất cả thuộc tính của Tướng +3% | Đội xuất trận · % Công +3%, % HP +3%, % Thủ +3% | Hoạt động |
| +10 | `10030600` | Bạo Kích +3000 | Bản thân · Bạo +3000 | Hoạt động |
| +11 | `10480800` | Sát thương tất cả Tướng gây ra +8000 , miễn giảm sát thương +8000 | Đội xuất trận · ST cộng +8000, Miễn giảm ST +8000 | Hoạt động |
| +12 | `10490480` | HP+28800 | Bản thân · HP +28800 | Hoạt động |
| +13 | `10640870` | Phá Kích+4350 | Bản thân · Phá Kích +4350 | Hoạt động |
| +14 | `10500800` | Công+4800 | Bản thân · Công +4800 | Hoạt động |
| +15 | `21070830` | Kỹ Năng ST tăng 42% | Buff `10590830` | Chưa áp dụng |

## Nhện Đầu Người (`12011029`)

Bậc tối đa từ HeroStepRelation +8. Bậc tài năng cao nhất trong bảng +8.

| Bậc | TAL | Hiệu ứng VN | Dữ liệu áp dụng | R7.16 |
|---:|---:|---|---|---|
| +2 | `10130120` | Công +60 | Bản thân · Công +60 | Hoạt động |
| +3 | `10030120` | Bạo Kích +600 | Bản thân · Bạo +600 | Hoạt động |
| +4 | `10250000` | Công của tất cả Tướng +80 | Đội xuất trận · Công +80 | Hoạt động |
| +5 | `20220401` | Khi tấn công thường, 80% giảm 45% Thủ 1 lượt của mục tiêu | Buff `20420401` | Chưa áp dụng |
| +6 | `10010000` | Mới bắt đầu tăng 50đ Nộ, lượt đầu có thể Nộ Công | Bản thân · Nộ +50 | Hoạt động |
| +7 | `10260000` | HP của tất cả Tướng +800 | Đội xuất trận · HP +800 | Hoạt động |
| +8 | `20340406` | Khi Nộ Công, 30% giảm 75% hiệu quả trị liệu 2 lượt của mục tiêu | Buff `20300406` | Chưa áp dụng |

## Suzaku (`12012024`)

Bậc tối đa từ HeroStepRelation +8. Bậc tài năng cao nhất trong bảng +8.

| Bậc | TAL | Hiệu ứng VN | Dữ liệu áp dụng | R7.16 |
|---:|---:|---|---|---|
| +2 | `10150120` | HP +600 | Bản thân · HP +600 | Hoạt động |
| +3 | `10060120` | Né +480 | Bản thân · Né +480 | Hoạt động |
| +4 | `10250000` | Công của tất cả Tướng +80 | Đội xuất trận · Công +80 | Hoạt động |
| +5 | `20460400` | Khi bị tấn công, nếu HP thấp hơn kẻ công kích, chịu ST giảm 20% | Buff `10160400` | Chưa áp dụng |
| +6 | `10010000` | Mới bắt đầu tăng 50đ Nộ, lượt đầu có thể Nộ Công | Bản thân · Nộ +50 | Hoạt động |
| +7 | `10260000` | HP của tất cả Tướng +800 | Đội xuất trận · HP +800 | Hoạt động |
| +8 | `10100400` | Điểm Trị Liệu +12% | Bản thân · % Trị Liệu +20% | Hoạt động |

## Chokyukai (`12011023`)

Bậc tối đa từ HeroStepRelation +8. Bậc tài năng cao nhất trong bảng +8.

| Bậc | TAL | Hiệu ứng VN | Dữ liệu áp dụng | R7.16 |
|---:|---:|---|---|---|
| +2 | `10140120` | Thủ +60 | Bản thân · Thủ +60 | Hoạt động |
| +3 | `10040120` | Đỡ +600 | Bản thân · Đỡ +600 | Hoạt động |
| +4 | `10250000` | Công của tất cả Tướng +80 | Đội xuất trận · Công +80 | Hoạt động |
| +5 | `20730400` | Đỡ phản kích, gây ST bằng 50% Công | Buff `20050400` | Chưa áp dụng |
| +6 | `10010000` | Mới bắt đầu tăng 50đ Nộ, lượt đầu có thể Nộ Công | Bản thân · Nộ +50 | Hoạt động |
| +7 | `10260000` | HP của tất cả Tướng +800 | Đội xuất trận · HP +800 | Hoạt động |
| +8 | `20550400` | Khi HP của bản thân thấp hơn 50%, chịu ST giảm 20% | Buff `10250400` | Chưa áp dụng |

## Kanade Hime (`12012003`)

Bậc tối đa từ HeroStepRelation +15. Bậc tài năng cao nhất trong bảng +15.

| Bậc | TAL | Hiệu ứng VN | Dữ liệu áp dụng | R7.16 |
|---:|---:|---|---|---|
| +2 | `10150200` | HP +1000 | Bản thân · HP +1000 | Hoạt động |
| +3 | `10060200` | Né +800 | Bản thân · Né +800 | Hoạt động |
| +4 | `10160000` | Công của tất cả Tướng +250 | Đội xuất trận · Công +250 | Hoạt động |
| +5 | `10050600` | Né +1800 | Bản thân · Né +1800 | Hoạt động |
| +6 | `10010000` | Mới bắt đầu tăng 50đ Nộ, lượt đầu có thể Nộ Công | Bản thân · Nộ +50 | Hoạt động |
| +7 | `10170000` | HP của tất cả Tướng +2500 | Đội xuất trận · HP +2500 | Hoạt động |
| +8 | `21040600` | Khi Nộ Công,  tăng 20% Bạo Kích 2 lượt cho hàng sau | Buff `20600600` | Chưa áp dụng |
| +9 | `10180000` | Tất cả thuộc tính của Tướng +4% | Đội xuất trận · % Công +4%, % HP +4%, % Thủ +4% | Hoạt động |
| +10 | `20641000` | Ra trận lần 1,2,3, khi bản thân chịu ST giảm 75% | Buff `10141000` | Chưa áp dụng |
| +11 | `10481000` | Sát thương tất cả Tướng gây ra +10000 , miễn giảm sát thương +10000 | Đội xuất trận · ST cộng +10000, Miễn giảm ST +10000 | Hoạt động |
| +12 | `10490600` | HP+36000 | Bản thân · HP +36000 | Hoạt động |
| +13 | `10031000` | Bạo Kích +5000 | Bản thân · Bạo +5000 | Hoạt động |
| +14 | `10501000` | Công+6000 | Bản thân · Công +6000 | Hoạt động |
| +15 | `10021000` | Chịu ST giảm 30% | Bản thân · % miễn giảm ST +30% | Hoạt động |

## Saimyosho (`12013030`)

Bậc tối đa từ HeroStepRelation +8. Bậc tài năng cao nhất trong bảng +8.

| Bậc | TAL | Hiệu ứng VN | Dữ liệu áp dụng | R7.16 |
|---:|---:|---|---|---|
| +2 | `10140120` | Thủ +60 | Bản thân · Thủ +60 | Hoạt động |
| +3 | `10040120` | Đỡ +600 | Bản thân · Đỡ +600 | Hoạt động |
| +4 | `10250000` | Công của tất cả Tướng +80 | Đội xuất trận · Công +80 | Hoạt động |
| +5 | `20460400` | Khi bị tấn công, nếu HP thấp hơn kẻ công kích, chịu ST giảm 20% | Buff `10160400` | Chưa áp dụng |
| +6 | `10010000` | Mới bắt đầu tăng 50đ Nộ, lượt đầu có thể Nộ Công | Bản thân · Nộ +50 | Hoạt động |
| +7 | `10260000` | HP của tất cả Tướng +800 | Đội xuất trận · HP +800 | Hoạt động |
| +8 | `20730400` | Đỡ phản kích, gây ST bằng 50% Công | Buff `20050400` | Chưa áp dụng |

## 万妖之王*A (`12015019`)

Bậc tối đa từ HeroStepRelation +15. Bậc tài năng cao nhất trong bảng +15.

| Bậc | TAL | Hiệu ứng VN | Dữ liệu áp dụng | R7.16 |
|---:|---:|---|---|---|
| +1 | `20361008` | Khi Nộ Công, 29% khiến mục tiêu bị [Choáng] 1 lượt | Buff `20211008` | Chưa áp dụng |
| +2 | `10030160` | Bạo Kích +800 | Bản thân · Bạo +800 | Hoạt động |
| +3 | `10030160` | Bạo Kích +800 | Bản thân · Bạo +800 | Hoạt động |
| +4 | `10460000` | Gặp Đội Hình Sesshomaru ST tăng 50% | Trận doanh 2 · % ST từ trận doanh 2 -50% | Chưa áp dụng |
| +5 | `20910000` | Miễn dịch Choáng; miễn dịch Im Lặng; miễn dịch Giảm Nộ; miễn dịch Phản ST | Buff `10010000`, `10020000`, `10060000`, `10070000` | Chưa áp dụng |
| +6 | `10010000` | Mới bắt đầu tăng 50đ Nộ, lượt đầu có thể Nộ Công | Bản thân · Nộ +50 | Hoạt động |
| +7 | `10170000` | HP của tất cả Tướng +2500 | Đội xuất trận · HP +2500 | Hoạt động |
| +8 | `20750000` | Khi tiêu diệt mục tiêu, tiếp tục tấn công mục tiêu kế | Buff `20060000` | Chưa áp dụng |
| +9 | `10180000` | Tất cả thuộc tính của Tướng +4% | Đội xuất trận · % Công +4%, % HP +4%, % Thủ +4% | Hoạt động |
| +10 | `20070800` | Khi bị tấn công, 40% giảm 25đ Nộ của kẻ công kích | Buff `10400800` | Chưa áp dụng |
| +11 | `10480800` | Sát thương tất cả Tướng gây ra +8000 , miễn giảm sát thương +8000 | Đội xuất trận · ST cộng +8000, Miễn giảm ST +8000 | Hoạt động |
| +12 | `10490480` | HP+28800 | Bản thân · HP +28800 | Hoạt động |
| +13 | `10070870` | Bạo Kích +2175, ST Bạo +4350 | Bản thân · Bạo +2175, Tất Sát +4350 | Hoạt động |
| +14 | `10500800` | Công+4800 | Bản thân · Công +4800 | Hoạt động |
| +15 | `21240830` | Bỏ qua 50% Thủ của mục tiêu | Buff `11130830` | Chưa áp dụng |

## 万妖之王*B (`12015020`)

Bậc tối đa từ HeroStepRelation +15. Bậc tài năng cao nhất trong bảng +15.

| Bậc | TAL | Hiệu ứng VN | Dữ liệu áp dụng | R7.16 |
|---:|---:|---|---|---|
| +1 | `20361008` | Khi Nộ Công, 29% khiến mục tiêu bị [Choáng] 1 lượt | Buff `20211008` | Chưa áp dụng |
| +2 | `10030160` | Bạo Kích +800 | Bản thân · Bạo +800 | Hoạt động |
| +3 | `10030160` | Bạo Kích +800 | Bản thân · Bạo +800 | Hoạt động |
| +4 | `10450000` | Gặp Đội Hình InuYasha ST tăng 50% | Trận doanh 1 · % ST từ trận doanh 1 -50% | Chưa áp dụng |
| +5 | `20910000` | Miễn dịch Choáng; miễn dịch Im Lặng; miễn dịch Giảm Nộ; miễn dịch Phản ST | Buff `10010000`, `10020000`, `10060000`, `10070000` | Chưa áp dụng |
| +6 | `10010000` | Mới bắt đầu tăng 50đ Nộ, lượt đầu có thể Nộ Công | Bản thân · Nộ +50 | Hoạt động |
| +7 | `10170000` | HP của tất cả Tướng +2500 | Đội xuất trận · HP +2500 | Hoạt động |
| +8 | `20750000` | Khi tiêu diệt mục tiêu, tiếp tục tấn công mục tiêu kế | Buff `20060000` | Chưa áp dụng |
| +9 | `10180000` | Tất cả thuộc tính của Tướng +4% | Đội xuất trận · % Công +4%, % HP +4%, % Thủ +4% | Hoạt động |
| +10 | `20070800` | Khi bị tấn công, 40% giảm 25đ Nộ của kẻ công kích | Buff `10400800` | Chưa áp dụng |
| +11 | `10480800` | Sát thương tất cả Tướng gây ra +8000 , miễn giảm sát thương +8000 | Đội xuất trận · ST cộng +8000, Miễn giảm ST +8000 | Hoạt động |
| +12 | `10490480` | HP+28800 | Bản thân · HP +28800 | Hoạt động |
| +13 | `10640870` | Phá Kích+4350 | Bản thân · Phá Kích +4350 | Hoạt động |
| +14 | `10500800` | Công+4800 | Bản thân · Công +4800 | Hoạt động |
| +15 | `21070830` | Kỹ Năng ST tăng 42% | Buff `10590830` | Chưa áp dụng |

## 万妖之王*C (`12015021`)

Bậc tối đa từ HeroStepRelation +15. Bậc tài năng cao nhất trong bảng +15.

| Bậc | TAL | Hiệu ứng VN | Dữ liệu áp dụng | R7.16 |
|---:|---:|---|---|---|
| +1 | `20361008` | Khi Nộ Công, 29% khiến mục tiêu bị [Choáng] 1 lượt | Buff `20211008` | Chưa áp dụng |
| +2 | `10030160` | Bạo Kích +800 | Bản thân · Bạo +800 | Hoạt động |
| +3 | `10030160` | Bạo Kích +800 | Bản thân · Bạo +800 | Hoạt động |
| +4 | `10470000` | Gặp Đội Hình Naraku ST tăng 50% | Trận doanh 3 · % ST từ trận doanh 3 -50% | Chưa áp dụng |
| +5 | `20910000` | Miễn dịch Choáng; miễn dịch Im Lặng; miễn dịch Giảm Nộ; miễn dịch Phản ST | Buff `10010000`, `10020000`, `10060000`, `10070000` | Chưa áp dụng |
| +6 | `10010000` | Mới bắt đầu tăng 50đ Nộ, lượt đầu có thể Nộ Công | Bản thân · Nộ +50 | Hoạt động |
| +7 | `10170000` | HP của tất cả Tướng +2500 | Đội xuất trận · HP +2500 | Hoạt động |
| +8 | `20750000` | Khi tiêu diệt mục tiêu, tiếp tục tấn công mục tiêu kế | Buff `20060000` | Chưa áp dụng |
| +9 | `10180000` | Tất cả thuộc tính của Tướng +4% | Đội xuất trận · % Công +4%, % HP +4%, % Thủ +4% | Hoạt động |
| +10 | `20070800` | Khi bị tấn công, 40% giảm 25đ Nộ của kẻ công kích | Buff `10400800` | Chưa áp dụng |
| +11 | `10480800` | Sát thương tất cả Tướng gây ra +8000 , miễn giảm sát thương +8000 | Đội xuất trận · ST cộng +8000, Miễn giảm ST +8000 | Hoạt động |
| +12 | `10490480` | HP+28800 | Bản thân · HP +28800 | Hoạt động |
| +13 | `10070870` | Bạo Kích +2175, ST Bạo +4350 | Bản thân · Bạo +2175, Tất Sát +4350 | Hoạt động |
| +14 | `10500800` | Công+4800 | Bản thân · Công +4800 | Hoạt động |
| +15 | `21240830` | Bỏ qua 50% Thủ của mục tiêu | Buff `11130830` | Chưa áp dụng |

## Kagome Yokai (`12015001`)

Bậc tối đa từ HeroStepRelation +15. Bậc tài năng cao nhất trong bảng +15.

| Bậc | TAL | Hiệu ứng VN | Dữ liệu áp dụng | R7.16 |
|---:|---:|---|---|---|
| +1 | `21211000` | Khi mở trận bản thân thêm Khiên có 240% Thủ | Buff `20121000` | Chưa áp dụng |
| +2 | `10150160` | HP +800 | Bản thân · HP +800 | Hoạt động |
| +3 | `10060160` | Né +640 | Bản thân · Né +640 | Hoạt động |
| +4 | `10190000` | Công của tất cả Tướng +200 | Đội xuất trận · Công +200 | Hoạt động |
| +5 | `20450400` | Khi bị tấn công, nếu HP cao hơn kẻ công kích, nhận ST giảm 20% | Buff `10150400` | Chưa áp dụng |
| +6 | `10010000` | Mới bắt đầu tăng 50đ Nộ, lượt đầu có thể Nộ Công | Bản thân · Nộ +50 | Hoạt động |
| +7 | `10200000` | HP của tất cả Tướng +2000 | Đội xuất trận · HP +2000 | Hoạt động |
| +8 | `10030600` | Bạo Kích +3000 | Bản thân · Bạo +3000 | Hoạt động |
| +9 | `10210000` | Tất cả thuộc tính của Tướng +3% | Đội xuất trận · % Công +3%, % HP +3%, % Thủ +3% | Hoạt động |
| +10 | `20480800` | Mục tiêu của bản thân khi lượng máu cao,gây ST tăng 40% | Buff `10180800` | Chưa áp dụng |
| +11 | `10480800` | Sát thương tất cả Tướng gây ra +8000 , miễn giảm sát thương +8000 | Đội xuất trận · ST cộng +8000, Miễn giảm ST +8000 | Hoạt động |
| +12 | `10490480` | HP+28800 | Bản thân · HP +28800 | Hoạt động |
| +13 | `10080870` | Chính Xác +4350 | Bản thân · Chính Xác +4350 | Hoạt động |
| +14 | `10500800` | Công+4800 | Bản thân · Công +4800 | Hoạt động |
| +15 | `20660830` | Khi Nộ Công, bỏ qua 83% Thủ của mục tiêu | Buff `10560830` | Chưa áp dụng |

## Kouga Yokai (`12015002`)

Bậc tối đa từ HeroStepRelation +15. Bậc tài năng cao nhất trong bảng +15.

| Bậc | TAL | Hiệu ứng VN | Dữ liệu áp dụng | R7.16 |
|---:|---:|---|---|---|
| +1 | `21211000` | Khi mở trận bản thân thêm Khiên có 240% Thủ | Buff `20121000` | Chưa áp dụng |
| +2 | `10150160` | HP +800 | Bản thân · HP +800 | Hoạt động |
| +3 | `10060160` | Né +640 | Bản thân · Né +640 | Hoạt động |
| +4 | `10190000` | Công của tất cả Tướng +200 | Đội xuất trận · Công +200 | Hoạt động |
| +5 | `20170400` | Khi Nộ Công, hồi HP bằng 20% ST cho mục tiêu đồng đội tối đa đã mất máu | Buff `10670400` | Chưa áp dụng |
| +6 | `10010000` | Mới bắt đầu tăng 50đ Nộ, lượt đầu có thể Nộ Công | Bản thân · Nộ +50 | Hoạt động |
| +7 | `10200000` | HP của tất cả Tướng +2000 | Đội xuất trận · HP +2000 | Hoạt động |
| +8 | `20230601` | Khi tấn công thường, 45% giảm 25đ Nộ của mục tiêu | Buff `10500601` | Chưa áp dụng |
| +9 | `10210000` | Tất cả thuộc tính của Tướng +3% | Đội xuất trận · % Công +3%, % HP +3%, % Thủ +3% | Hoạt động |
| +10 | `20430800` | Khi Né, 40% tăng 25đ Nộ cho tất cả đồng đội | Buff `10380800` | Chưa áp dụng |
| +11 | `10480800` | Sát thương tất cả Tướng gây ra +8000 , miễn giảm sát thương +8000 | Đội xuất trận · ST cộng +8000, Miễn giảm ST +8000 | Hoạt động |
| +12 | `10490480` | HP+28800 | Bản thân · HP +28800 | Hoạt động |
| +13 | `10080870` | Chính Xác +4350 | Bản thân · Chính Xác +4350 | Hoạt động |
| +14 | `10500800` | Công+4800 | Bản thân · Công +4800 | Hoạt động |
| +15 | `20660830` | Khi Nộ Công, bỏ qua 83% Thủ của mục tiêu | Buff `10560830` | Chưa áp dụng |

## Jinenji Yokai (`12015003`)

Bậc tối đa từ HeroStepRelation +15. Bậc tài năng cao nhất trong bảng +15.

| Bậc | TAL | Hiệu ứng VN | Dữ liệu áp dụng | R7.16 |
|---:|---:|---|---|---|
| +1 | `21211000` | Khi mở trận bản thân thêm Khiên có 240% Thủ | Buff `20121000` | Chưa áp dụng |
| +2 | `10140160` | Thủ +80 | Bản thân · Thủ +80 | Hoạt động |
| +3 | `10040160` | Đỡ +800 | Bản thân · Đỡ +800 | Hoạt động |
| +4 | `10190000` | Công của tất cả Tướng +200 | Đội xuất trận · Công +200 | Hoạt động |
| +5 | `10040400` | Đỡ +2000 | Bản thân · Đỡ +2000 | Hoạt động |
| +6 | `10010000` | Mới bắt đầu tăng 50đ Nộ, lượt đầu có thể Nộ Công | Bản thân · Nộ +50 | Hoạt động |
| +7 | `10200000` | HP của tất cả Tướng +2000 | Đội xuất trận · HP +2000 | Hoạt động |
| +8 | `20450600` | Khi bị tấn công, nếu HP cao hơn kẻ công kích, nhận ST giảm 30% | Buff `10150600` | Chưa áp dụng |
| +9 | `10210000` | Tất cả thuộc tính của Tướng +3% | Đội xuất trận · % Công +3%, % HP +3%, % Thủ +3% | Hoạt động |
| +10 | `20180800` | Khi Nộ Công,  hồi HP bằng 40% ST cho bản thân | Buff `10700800` | Chưa áp dụng |
| +11 | `10480800` | Sát thương tất cả Tướng gây ra +8000 , miễn giảm sát thương +8000 | Đội xuất trận · ST cộng +8000, Miễn giảm ST +8000 | Hoạt động |
| +12 | `10490480` | HP+28800 | Bản thân · HP +28800 | Hoạt động |
| +13 | `10080870` | Chính Xác +4350 | Bản thân · Chính Xác +4350 | Hoạt động |
| +14 | `10500800` | Công+4800 | Bản thân · Công +4800 | Hoạt động |
| +15 | `20660830` | Khi Nộ Công, bỏ qua 83% Thủ của mục tiêu | Buff `10560830` | Chưa áp dụng |

## Moryomaru Yokai (`12015004`)

Bậc tối đa từ HeroStepRelation +15. Bậc tài năng cao nhất trong bảng +15.

| Bậc | TAL | Hiệu ứng VN | Dữ liệu áp dụng | R7.16 |
|---:|---:|---|---|---|
| +1 | `21211000` | Khi mở trận bản thân thêm Khiên có 240% Thủ | Buff `20121000` | Chưa áp dụng |
| +2 | `10140160` | Thủ +80 | Bản thân · Thủ +80 | Hoạt động |
| +3 | `10040160` | Đỡ +800 | Bản thân · Đỡ +800 | Hoạt động |
| +4 | `10190000` | Công của tất cả Tướng +200 | Đội xuất trận · Công +200 | Hoạt động |
| +5 | `10040400` | Đỡ +2000 | Bản thân · Đỡ +2000 | Hoạt động |
| +6 | `10010000` | Mới bắt đầu tăng 50đ Nộ, lượt đầu có thể Nộ Công | Bản thân · Nộ +50 | Hoạt động |
| +7 | `10200000` | HP của tất cả Tướng +2000 | Đội xuất trận · HP +2000 | Hoạt động |
| +8 | `20540600` | Khi HP của bản thân cao hơn 50%, chịu ST giảm 30% | Buff `10240600` | Chưa áp dụng |
| +9 | `10210000` | Tất cả thuộc tính của Tướng +3% | Đội xuất trận · % Công +3%, % HP +3%, % Thủ +3% | Hoạt động |
| +10 | `20730800` | Đỡ phản kích, gây ST bằng 100% Công | Buff `20050800` | Chưa áp dụng |
| +11 | `10480800` | Sát thương tất cả Tướng gây ra +8000 , miễn giảm sát thương +8000 | Đội xuất trận · ST cộng +8000, Miễn giảm ST +8000 | Hoạt động |
| +12 | `10490480` | HP+28800 | Bản thân · HP +28800 | Hoạt động |
| +13 | `10080870` | Chính Xác +4350 | Bản thân · Chính Xác +4350 | Hoạt động |
| +14 | `10500800` | Công+4800 | Bản thân · Công +4800 | Hoạt động |
| +15 | `20660830` | Khi Nộ Công, bỏ qua 83% Thủ của mục tiêu | Buff `10560830` | Chưa áp dụng |

## Inu no Taishou Yokai (`12015005`)

Bậc tối đa từ HeroStepRelation +15. Bậc tài năng cao nhất trong bảng +15.

| Bậc | TAL | Hiệu ứng VN | Dữ liệu áp dụng | R7.16 |
|---:|---:|---|---|---|
| +1 | `21211000` | Khi mở trận bản thân thêm Khiên có 240% Thủ | Buff `20121000` | Chưa áp dụng |
| +2 | `10140160` | Thủ +80 | Bản thân · Thủ +80 | Hoạt động |
| +3 | `10040160` | Đỡ +800 | Bản thân · Đỡ +800 | Hoạt động |
| +4 | `10160000` | Công của tất cả Tướng +250 | Đội xuất trận · Công +250 | Hoạt động |
| +5 | `20730400` | Đỡ phản kích, gây ST bằng 50% Công | Buff `20050400` | Chưa áp dụng |
| +6 | `10010000` | Mới bắt đầu tăng 50đ Nộ, lượt đầu có thể Nộ Công | Bản thân · Nộ +50 | Hoạt động |
| +7 | `10170000` | HP của tất cả Tướng +2500 | Đội xuất trận · HP +2500 | Hoạt động |
| +8 | `20550600` | Khi HP của bản thân thấp hơn 50%, chịu ST giảm 30% | Buff `10250600` | Chưa áp dụng |
| +9 | `10180000` | Tất cả thuộc tính của Tướng +4% | Đội xuất trận · % Công +4%, % HP +4%, % Thủ +4% | Hoạt động |
| +10 | `20700000` | Hồi Sinh sau khi lần đầu Tử Vong, bản thân hồi HP bằng 150% Công | Buff `10290000` | Chưa áp dụng |
| +11 | `10480800` | Sát thương tất cả Tướng gây ra +8000 , miễn giảm sát thương +8000 | Đội xuất trận · ST cộng +8000, Miễn giảm ST +8000 | Hoạt động |
| +12 | `10490480` | HP+28800 | Bản thân · HP +28800 | Hoạt động |
| +13 | `10080870` | Chính Xác +4350 | Bản thân · Chính Xác +4350 | Hoạt động |
| +14 | `10500800` | Công+4800 | Bản thân · Công +4800 | Hoạt động |
| +15 | `20660830` | Khi Nộ Công, bỏ qua 83% Thủ của mục tiêu | Buff `10560830` | Chưa áp dụng |

## Hakudoushi Yokai (`12015006`)

Bậc tối đa từ HeroStepRelation +15. Bậc tài năng cao nhất trong bảng +15.

| Bậc | TAL | Hiệu ứng VN | Dữ liệu áp dụng | R7.16 |
|---:|---:|---|---|---|
| +1 | `21211000` | Khi mở trận bản thân thêm Khiên có 240% Thủ | Buff `20121000` | Chưa áp dụng |
| +2 | `10150160` | HP +800 | Bản thân · HP +800 | Hoạt động |
| +3 | `10060160` | Né +640 | Bản thân · Né +640 | Hoạt động |
| +4 | `10190000` | Công của tất cả Tướng +200 | Đội xuất trận · Công +200 | Hoạt động |
| +5 | `20450400` | Khi bị tấn công, nếu HP cao hơn kẻ công kích, nhận ST giảm 20% | Buff `10150400` | Chưa áp dụng |
| +6 | `10010000` | Mới bắt đầu tăng 50đ Nộ, lượt đầu có thể Nộ Công | Bản thân · Nộ +50 | Hoạt động |
| +7 | `10200000` | HP của tất cả Tướng +2000 | Đội xuất trận · HP +2000 | Hoạt động |
| +8 | `20280606` | Khi tấn công thường, 15% khiến mục tiêu [Tê Liệt] 1 lượt | Buff `20510606` | Chưa áp dụng |
| +9 | `10210000` | Tất cả thuộc tính của Tướng +3% | Đội xuất trận · % Công +3%, % HP +3%, % Thủ +3% | Hoạt động |
| +10 | `20710800` | Sau khi Nộ Công, 80% nhận hiệu quả [Vô Địch] 1 lượt | Buff `20220800` | Chưa áp dụng |
| +11 | `10480800` | Sát thương tất cả Tướng gây ra +8000 , miễn giảm sát thương +8000 | Đội xuất trận · ST cộng +8000, Miễn giảm ST +8000 | Hoạt động |
| +12 | `10490480` | HP+28800 | Bản thân · HP +28800 | Hoạt động |
| +13 | `10080870` | Chính Xác +4350 | Bản thân · Chính Xác +4350 | Hoạt động |
| +14 | `10500800` | Công+4800 | Bản thân · Công +4800 | Hoạt động |
| +15 | `20660830` | Khi Nộ Công, bỏ qua 83% Thủ của mục tiêu | Buff `10560830` | Chưa áp dụng |

## Ông Myoga Yokai (`12015007`)

Bậc tối đa từ HeroStepRelation +15. Bậc tài năng cao nhất trong bảng +15.

| Bậc | TAL | Hiệu ứng VN | Dữ liệu áp dụng | R7.16 |
|---:|---:|---|---|---|
| +1 | `21211000` | Khi mở trận bản thân thêm Khiên có 240% Thủ | Buff `20121000` | Chưa áp dụng |
| +2 | `10130160` | Công +80 | Bản thân · Công +80 | Hoạt động |
| +3 | `10030160` | Bạo Kích +800 | Bản thân · Bạo +800 | Hoạt động |
| +4 | `10190000` | Công của tất cả Tướng +200 | Đội xuất trận · Công +200 | Hoạt động |
| +5 | `20630400` | Ra trận lần 1 khi tấn công, ST gây ra tăng 50% | Buff `10130400` | Chưa áp dụng |
| +6 | `10010000` | Mới bắt đầu tăng 50đ Nộ, lượt đầu có thể Nộ Công | Bản thân · Nộ +50 | Hoạt động |
| +7 | `10200000` | HP của tất cả Tướng +2000 | Đội xuất trận · HP +2000 | Hoạt động |
| +8 | `20470600` | Khi HP của bản thân thấp hơn mục tiêu, gây ST tăng 30% | Buff `10170600` | Chưa áp dụng |
| +9 | `10210000` | Tất cả thuộc tính của Tướng +3% | Đội xuất trận · % Công +3%, % HP +3%, % Thủ +3% | Hoạt động |
| +10 | `20600800` | Khi tử vong, gây ST bằng 80% Công cho toàn bộ địch | Buff `10310800` | Chưa áp dụng |
| +11 | `10480800` | Sát thương tất cả Tướng gây ra +8000 , miễn giảm sát thương +8000 | Đội xuất trận · ST cộng +8000, Miễn giảm ST +8000 | Hoạt động |
| +12 | `10490480` | HP+28800 | Bản thân · HP +28800 | Hoạt động |
| +13 | `10080870` | Chính Xác +4350 | Bản thân · Chính Xác +4350 | Hoạt động |
| +14 | `10500800` | Công+4800 | Bản thân · Công +4800 | Hoạt động |
| +15 | `20660830` | Khi Nộ Công, bỏ qua 83% Thủ của mục tiêu | Buff `10560830` | Chưa áp dụng |

## Miroku Yokai (`12015008`)

Bậc tối đa từ HeroStepRelation +15. Bậc tài năng cao nhất trong bảng +15.

| Bậc | TAL | Hiệu ứng VN | Dữ liệu áp dụng | R7.16 |
|---:|---:|---|---|---|
| +1 | `21211000` | Khi mở trận bản thân thêm Khiên có 240% Thủ | Buff `20121000` | Chưa áp dụng |
| +2 | `10130160` | Công +80 | Bản thân · Công +80 | Hoạt động |
| +3 | `10030160` | Bạo Kích +800 | Bản thân · Bạo +800 | Hoạt động |
| +4 | `10190000` | Công của tất cả Tướng +200 | Đội xuất trận · Công +200 | Hoạt động |
| +5 | `20360401` | Khi Nộ Công, 40% khiến mục tiêu bị [Choáng] 1 lượt | Buff `20210401` | Chưa áp dụng |
| +6 | `10010000` | Mới bắt đầu tăng 50đ Nộ, lượt đầu có thể Nộ Công | Bản thân · Nộ +50 | Hoạt động |
| +7 | `10200000` | HP của tất cả Tướng +2000 | Đội xuất trận · HP +2000 | Hoạt động |
| +8 | `10030600` | Bạo Kích +3000 | Bản thân · Bạo +3000 | Hoạt động |
| +9 | `10210000` | Tất cả thuộc tính của Tướng +3% | Đội xuất trận · % Công +3%, % HP +3%, % Thủ +3% | Hoạt động |
| +10 | `20470800` | Khi HP của bản thân thấp hơn mục tiêu, gây ST tăng 40% | Buff `10170800` | Chưa áp dụng |
| +11 | `10480800` | Sát thương tất cả Tướng gây ra +8000 , miễn giảm sát thương +8000 | Đội xuất trận · ST cộng +8000, Miễn giảm ST +8000 | Hoạt động |
| +12 | `10490480` | HP+28800 | Bản thân · HP +28800 | Hoạt động |
| +13 | `10080870` | Chính Xác +4350 | Bản thân · Chính Xác +4350 | Hoạt động |
| +14 | `10500800` | Công+4800 | Bản thân · Công +4800 | Hoạt động |
| +15 | `20660830` | Khi Nộ Công, bỏ qua 83% Thủ của mục tiêu | Buff `10560830` | Chưa áp dụng |

## Kirara Yokai (`12015009`)

Bậc tối đa từ HeroStepRelation +15. Bậc tài năng cao nhất trong bảng +15.

| Bậc | TAL | Hiệu ứng VN | Dữ liệu áp dụng | R7.16 |
|---:|---:|---|---|---|
| +1 | `21211000` | Khi mở trận bản thân thêm Khiên có 240% Thủ | Buff `20121000` | Chưa áp dụng |
| +2 | `10130160` | Công +80 | Bản thân · Công +80 | Hoạt động |
| +3 | `10030160` | Bạo Kích +800 | Bản thân · Bạo +800 | Hoạt động |
| +4 | `10190000` | Công của tất cả Tướng +200 | Đội xuất trận · Công +200 | Hoạt động |
| +5 | `20480400` | Mục tiêu của bản thân khi lượng máu cao,gây ST tăng 20% | Buff `10180400` | Chưa áp dụng |
| +6 | `10010000` | Mới bắt đầu tăng 50đ Nộ, lượt đầu có thể Nộ Công | Bản thân · Nộ +50 | Hoạt động |
| +7 | `10200000` | HP của tất cả Tướng +2000 | Đội xuất trận · HP +2000 | Hoạt động |
| +8 | `20240606` | Khi tấn công thường, 30% giảm 80% hiệu quả trị liệu 1 lượt của mục tiêu | Buff `20250606` | Chưa áp dụng |
| +9 | `10210000` | Tất cả thuộc tính của Tướng +3% | Đội xuất trận · % Công +3%, % HP +3%, % Thủ +3% | Hoạt động |
| +10 | `10030800` | Bạo Kích +4000 | Bản thân · Bạo +4000 | Hoạt động |
| +11 | `10480800` | Sát thương tất cả Tướng gây ra +8000 , miễn giảm sát thương +8000 | Đội xuất trận · ST cộng +8000, Miễn giảm ST +8000 | Hoạt động |
| +12 | `10490480` | HP+28800 | Bản thân · HP +28800 | Hoạt động |
| +13 | `10080870` | Chính Xác +4350 | Bản thân · Chính Xác +4350 | Hoạt động |
| +14 | `10500800` | Công+4800 | Bản thân · Công +4800 | Hoạt động |
| +15 | `20660830` | Khi Nộ Công, bỏ qua 83% Thủ của mục tiêu | Buff `10560830` | Chưa áp dụng |

## Ryukotsusei Yokai (`12015010`)

Bậc tối đa từ HeroStepRelation +15. Bậc tài năng cao nhất trong bảng +15.

| Bậc | TAL | Hiệu ứng VN | Dữ liệu áp dụng | R7.16 |
|---:|---:|---|---|---|
| +1 | `21211000` | Khi mở trận bản thân thêm Khiên có 240% Thủ | Buff `20121000` | Chưa áp dụng |
| +2 | `10130160` | Công +80 | Bản thân · Công +80 | Hoạt động |
| +3 | `10030160` | Bạo Kích +800 | Bản thân · Bạo +800 | Hoạt động |
| +4 | `10220000` | Công của tất cả Tướng +125 | Đội xuất trận · Công +125 | Hoạt động |
| +5 | `20720400` | Khi tấn công thường, gây thêm 40% ST cho mục tiêu lân cận | Buff `20590400` | Chưa áp dụng |
| +6 | `10010000` | Mới bắt đầu tăng 50đ Nộ, lượt đầu có thể Nộ Công | Bản thân · Nộ +50 | Hoạt động |
| +7 | `10230000` | HP của tất cả Tướng +1250 | Đội xuất trận · HP +1250 | Hoạt động |
| +8 | `20530600` | Khi HP của bản thân cao hơn 50%, gây ST tăng 30% | Buff `10230600` | Chưa áp dụng |
| +9 | `10240000` | Tất cả thuộc tính của Tướng +2% | Đội xuất trận · % Công +2%, % HP +2%, % Thủ +2% | Hoạt động |
| +10 | `20580800` | Khi Nộ Công, nếu mục tiêu trong trạng thái [Trúng Độc], 100% giảm 60đ Nộ | Buff `10620800` | Chưa áp dụng |
| +11 | `10480800` | Sát thương tất cả Tướng gây ra +8000 , miễn giảm sát thương +8000 | Đội xuất trận · ST cộng +8000, Miễn giảm ST +8000 | Hoạt động |
| +12 | `10490480` | HP+28800 | Bản thân · HP +28800 | Hoạt động |
| +13 | `10080870` | Chính Xác +4350 | Bản thân · Chính Xác +4350 | Hoạt động |
| +14 | `10500800` | Công+4800 | Bản thân · Công +4800 | Hoạt động |
| +15 | `20660830` | Khi Nộ Công, bỏ qua 83% Thủ của mục tiêu | Buff `10560830` | Chưa áp dụng |

## Hiten Yokai (`12015011`)

Bậc tối đa từ HeroStepRelation +15. Bậc tài năng cao nhất trong bảng +15.

| Bậc | TAL | Hiệu ứng VN | Dữ liệu áp dụng | R7.16 |
|---:|---:|---|---|---|
| +1 | `21211000` | Khi mở trận bản thân thêm Khiên có 240% Thủ | Buff `20121000` | Chưa áp dụng |
| +2 | `10130160` | Công +80 | Bản thân · Công +80 | Hoạt động |
| +3 | `10030160` | Bạo Kích +800 | Bản thân · Bạo +800 | Hoạt động |
| +4 | `10190000` | Công của tất cả Tướng +200 | Đội xuất trận · Công +200 | Hoạt động |
| +5 | `10030400` | Bạo Kích +2000 | Bản thân · Bạo +2000 | Hoạt động |
| +6 | `10010000` | Mới bắt đầu tăng 50đ Nộ, lượt đầu có thể Nộ Công | Bản thân · Nộ +50 | Hoạt động |
| +7 | `10200000` | HP của tất cả Tướng +2000 | Đội xuất trận · HP +2000 | Hoạt động |
| +8 | `20440602` | Khi tấn công bị Đỡ, lần ST kế tiếp tăng 50% | Buff `20100602` | Chưa áp dụng |
| +9 | `10210000` | Tất cả thuộc tính của Tướng +3% | Đội xuất trận · % Công +3%, % HP +3%, % Thủ +3% | Hoạt động |
| +10 | `20520800` | Khi HP của bản thân thấp hơn 50%, gây ST tăng 40% | Buff `10220800` | Chưa áp dụng |
| +11 | `10480800` | Sát thương tất cả Tướng gây ra +8000 , miễn giảm sát thương +8000 | Đội xuất trận · ST cộng +8000, Miễn giảm ST +8000 | Hoạt động |
| +12 | `10490480` | HP+28800 | Bản thân · HP +28800 | Hoạt động |
| +13 | `10080870` | Chính Xác +4350 | Bản thân · Chính Xác +4350 | Hoạt động |
| +14 | `10500800` | Công+4800 | Bản thân · Công +4800 | Hoạt động |
| +15 | `20660830` | Khi Nộ Công, bỏ qua 83% Thủ của mục tiêu | Buff `10560830` | Chưa áp dụng |

## Kanade Hime Yokai (`12015012`)

Bậc tối đa từ HeroStepRelation +15. Bậc tài năng cao nhất trong bảng +15.

| Bậc | TAL | Hiệu ứng VN | Dữ liệu áp dụng | R7.16 |
|---:|---:|---|---|---|
| +1 | `21211000` | Khi mở trận bản thân thêm Khiên có 240% Thủ | Buff `20121000` | Chưa áp dụng |
| +2 | `10150160` | HP +800 | Bản thân · HP +800 | Hoạt động |
| +3 | `10080160` | Chính Xác +800 | Bản thân · Chính Xác +800 | Hoạt động |
| +4 | `10160000` | Công của tất cả Tướng +250 | Đội xuất trận · Công +250 | Hoạt động |
| +5 | `20250406` | Khi tấn công thường, 33% khiến mục tiêu [Trúng Độc] 2 lượt | Buff `20310406` | Chưa áp dụng |
| +6 | `10010000` | Mới bắt đầu tăng 50đ Nộ, lượt đầu có thể Nộ Công | Bản thân · Nộ +50 | Hoạt động |
| +7 | `10170000` | HP của tất cả Tướng +2500 | Đội xuất trận · HP +2500 | Hoạt động |
| +8 | `20370608` | Khi Nộ Công, 43% khiến mục tiêu [Im Lặng] 1 lượt | Buff `20290608` | Chưa áp dụng |
| +9 | `10180000` | Tất cả thuộc tính của Tướng +4% | Đội xuất trận · % Công +4%, % HP +4%, % Thủ +4% | Hoạt động |
| +10 | `20580800` | Khi Nộ Công, nếu mục tiêu trong trạng thái [Trúng Độc], 100% giảm 60đ Nộ | Buff `10620800` | Chưa áp dụng |
| +11 | `10480800` | Sát thương tất cả Tướng gây ra +8000 , miễn giảm sát thương +8000 | Đội xuất trận · ST cộng +8000, Miễn giảm ST +8000 | Hoạt động |
| +12 | `10490480` | HP+28800 | Bản thân · HP +28800 | Hoạt động |
| +13 | `10080870` | Chính Xác +4350 | Bản thân · Chính Xác +4350 | Hoạt động |
| +14 | `10500800` | Công+4800 | Bản thân · Công +4800 | Hoạt động |
| +15 | `20660830` | Khi Nộ Công, bỏ qua 83% Thủ của mục tiêu | Buff `10560830` | Chưa áp dụng |

## Kohaku Yokai (`12015013`)

Bậc tối đa từ HeroStepRelation +15. Bậc tài năng cao nhất trong bảng +15.

| Bậc | TAL | Hiệu ứng VN | Dữ liệu áp dụng | R7.16 |
|---:|---:|---|---|---|
| +1 | `21211000` | Khi mở trận bản thân thêm Khiên có 240% Thủ | Buff `20121000` | Chưa áp dụng |
| +2 | `10130160` | Công +80 | Bản thân · Công +80 | Hoạt động |
| +3 | `10030160` | Bạo Kích +800 | Bản thân · Bạo +800 | Hoạt động |
| +4 | `10190000` | Công của tất cả Tướng +200 | Đội xuất trận · Công +200 | Hoạt động |
| +5 | `20480400` | Mục tiêu của bản thân khi lượng máu cao,gây ST tăng 20% | Buff `10180400` | Chưa áp dụng |
| +6 | `10010000` | Mới bắt đầu tăng 50đ Nộ, lượt đầu có thể Nộ Công | Bản thân · Nộ +50 | Hoạt động |
| +7 | `10200000` | HP của tất cả Tướng +2000 | Đội xuất trận · HP +2000 | Hoạt động |
| +8 | `10030600` | Bạo Kích +3000 | Bản thân · Bạo +3000 | Hoạt động |
| +9 | `10210000` | Tất cả thuộc tính của Tướng +3% | Đội xuất trận · % Công +3%, % HP +3%, % Thủ +3% | Hoạt động |
| +10 | `20170800` | Khi Nộ Công, hồi HP bằng 40% ST cho mục tiêu đồng đội tối đa đã mất máu | Buff `10670800` | Chưa áp dụng |
| +11 | `10480800` | Sát thương tất cả Tướng gây ra +8000 , miễn giảm sát thương +8000 | Đội xuất trận · ST cộng +8000, Miễn giảm ST +8000 | Hoạt động |
| +12 | `10490480` | HP+28800 | Bản thân · HP +28800 | Hoạt động |
| +13 | `10080870` | Chính Xác +4350 | Bản thân · Chính Xác +4350 | Hoạt động |
| +14 | `10500800` | Công+4800 | Bản thân · Công +4800 | Hoạt động |
| +15 | `20660830` | Khi Nộ Công, bỏ qua 83% Thủ của mục tiêu | Buff `10560830` | Chưa áp dụng |

## Sango Yokai (`12015014`)

Bậc tối đa từ HeroStepRelation +15. Bậc tài năng cao nhất trong bảng +15.

| Bậc | TAL | Hiệu ứng VN | Dữ liệu áp dụng | R7.16 |
|---:|---:|---|---|---|
| +1 | `21211000` | Khi mở trận bản thân thêm Khiên có 240% Thủ | Buff `20121000` | Chưa áp dụng |
| +2 | `10130160` | Công +80 | Bản thân · Công +80 | Hoạt động |
| +3 | `10030160` | Bạo Kích +800 | Bản thân · Bạo +800 | Hoạt động |
| +4 | `10190000` | Công của tất cả Tướng +200 | Đội xuất trận · Công +200 | Hoạt động |
| +5 | `20480400` | Mục tiêu của bản thân khi lượng máu cao,gây ST tăng 20% | Buff `10180400` | Chưa áp dụng |
| +6 | `10010000` | Mới bắt đầu tăng 50đ Nộ, lượt đầu có thể Nộ Công | Bản thân · Nộ +50 | Hoạt động |
| +7 | `10200000` | HP của tất cả Tướng +2000 | Đội xuất trận · HP +2000 | Hoạt động |
| +8 | `10070600` | Bạo Kích +1500, ST Bạo +3000 | Bản thân · Bạo +1500, Tất Sát +3000 | Hoạt động |
| +9 | `10210000` | Tất cả thuộc tính của Tướng +3% | Đội xuất trận · % Công +3%, % HP +3%, % Thủ +3% | Hoạt động |
| +10 | `20390000` | Khi Bạo Kích, tăng thêm 25đ Nộ | Buff `10350000` | Hoạt động |
| +11 | `10480800` | Sát thương tất cả Tướng gây ra +8000 , miễn giảm sát thương +8000 | Đội xuất trận · ST cộng +8000, Miễn giảm ST +8000 | Hoạt động |
| +12 | `10490480` | HP+28800 | Bản thân · HP +28800 | Hoạt động |
| +13 | `10080870` | Chính Xác +4350 | Bản thân · Chính Xác +4350 | Hoạt động |
| +14 | `10500800` | Công+4800 | Bản thân · Công +4800 | Hoạt động |
| +15 | `20660830` | Khi Nộ Công, bỏ qua 83% Thủ của mục tiêu | Buff `10560830` | Chưa áp dụng |

## InuYasha Yokai (`12015015`)

Bậc tối đa từ HeroStepRelation +15. Bậc tài năng cao nhất trong bảng +15.

| Bậc | TAL | Hiệu ứng VN | Dữ liệu áp dụng | R7.16 |
|---:|---:|---|---|---|
| +1 | `21211000` | Khi mở trận bản thân thêm Khiên có 240% Thủ | Buff `20121000` | Chưa áp dụng |
| +2 | `10130160` | Công +80 | Bản thân · Công +80 | Hoạt động |
| +3 | `10030160` | Bạo Kích +800 | Bản thân · Bạo +800 | Hoạt động |
| +4 | `10160000` | Công của tất cả Tướng +250 | Đội xuất trận · Công +250 | Hoạt động |
| +5 | `20390000` | Khi Bạo Kích, tăng thêm 25đ Nộ | Buff `10350000` | Hoạt động |
| +6 | `10010000` | Mới bắt đầu tăng 50đ Nộ, lượt đầu có thể Nộ Công | Bản thân · Nộ +50 | Hoạt động |
| +7 | `10170000` | HP của tất cả Tướng +2500 | Đội xuất trận · HP +2500 | Hoạt động |
| +8 | `20720600` | Khi tấn công thường, gây thêm 60% ST cho mục tiêu lân cận | Buff `20590600` | Chưa áp dụng |
| +9 | `10180000` | Tất cả thuộc tính của Tướng +4% | Đội xuất trận · % Công +4%, % HP +4%, % Thủ +4% | Hoạt động |
| +10 | `20110800` | Sau mỗi lần bị tấn công, Công tăng 8%, tối đa 24% | Buff `20170800` | Chưa áp dụng |
| +11 | `10480800` | Sát thương tất cả Tướng gây ra +8000 , miễn giảm sát thương +8000 | Đội xuất trận · ST cộng +8000, Miễn giảm ST +8000 | Hoạt động |
| +12 | `10490480` | HP+28800 | Bản thân · HP +28800 | Hoạt động |
| +13 | `10080870` | Chính Xác +4350 | Bản thân · Chính Xác +4350 | Hoạt động |
| +14 | `10500800` | Công+4800 | Bản thân · Công +4800 | Hoạt động |
| +15 | `20660830` | Khi Nộ Công, bỏ qua 83% Thủ của mục tiêu | Buff `10560830` | Chưa áp dụng |

## Hoshiyomi Yokai (`12015016`)

Bậc tối đa từ HeroStepRelation +15. Bậc tài năng cao nhất trong bảng +15.

| Bậc | TAL | Hiệu ứng VN | Dữ liệu áp dụng | R7.16 |
|---:|---:|---|---|---|
| +1 | `21211000` | Khi mở trận bản thân thêm Khiên có 240% Thủ | Buff `20121000` | Chưa áp dụng |
| +2 | `10130160` | Công +80 | Bản thân · Công +80 | Hoạt động |
| +3 | `10030160` | Bạo Kích +800 | Bản thân · Bạo +800 | Hoạt động |
| +4 | `10190000` | Công của tất cả Tướng +200 | Đội xuất trận · Công +200 | Hoạt động |
| +5 | `20480400` | Mục tiêu của bản thân khi lượng máu cao,gây ST tăng 20% | Buff `10180400` | Chưa áp dụng |
| +6 | `10010000` | Mới bắt đầu tăng 50đ Nộ, lượt đầu có thể Nộ Công | Bản thân · Nộ +50 | Hoạt động |
| +7 | `10200000` | HP của tất cả Tướng +2000 | Đội xuất trận · HP +2000 | Hoạt động |
| +8 | `20630600` | Ra trận lần 1 khi tấn công, ST gây ra tăng 75% | Buff `10130600` | Chưa áp dụng |
| +9 | `10210000` | Tất cả thuộc tính của Tướng +3% | Đội xuất trận · % Công +3%, % HP +3%, % Thủ +3% | Hoạt động |
| +10 | `10030800` | Bạo Kích +4000 | Bản thân · Bạo +4000 | Hoạt động |
| +11 | `10480800` | Sát thương tất cả Tướng gây ra +8000 , miễn giảm sát thương +8000 | Đội xuất trận · ST cộng +8000, Miễn giảm ST +8000 | Hoạt động |
| +12 | `10490480` | HP+28800 | Bản thân · HP +28800 | Hoạt động |
| +13 | `10080870` | Chính Xác +4350 | Bản thân · Chính Xác +4350 | Hoạt động |
| +14 | `10500800` | Công+4800 | Bản thân · Công +4800 | Hoạt động |
| +15 | `20660830` | Khi Nộ Công, bỏ qua 83% Thủ của mục tiêu | Buff `10560830` | Chưa áp dụng |

## Musou Yokai (`12015017`)

Bậc tối đa từ HeroStepRelation +15. Bậc tài năng cao nhất trong bảng +15.

| Bậc | TAL | Hiệu ứng VN | Dữ liệu áp dụng | R7.16 |
|---:|---:|---|---|---|
| +1 | `21211000` | Khi mở trận bản thân thêm Khiên có 240% Thủ | Buff `20121000` | Chưa áp dụng |
| +2 | `10130160` | Công +80 | Bản thân · Công +80 | Hoạt động |
| +3 | `10030160` | Bạo Kích +800 | Bản thân · Bạo +800 | Hoạt động |
| +4 | `10190000` | Công của tất cả Tướng +200 | Đội xuất trận · Công +200 | Hoạt động |
| +5 | `20040000` | Khi tiêu diệt mục tiêu, tăng thêm 25đ Nộ | Buff `10280000` | Chưa áp dụng |
| +6 | `10010000` | Mới bắt đầu tăng 50đ Nộ, lượt đầu có thể Nộ Công | Bản thân · Nộ +50 | Hoạt động |
| +7 | `10200000` | HP của tất cả Tướng +2000 | Đội xuất trận · HP +2000 | Hoạt động |
| +8 | `20630600` | Ra trận lần 1 khi tấn công, ST gây ra tăng 75% | Buff `10130600` | Chưa áp dụng |
| +9 | `10210000` | Tất cả thuộc tính của Tướng +3% | Đội xuất trận · % Công +3%, % HP +3%, % Thủ +3% | Hoạt động |
| +10 | `20480800` | Mục tiêu của bản thân khi lượng máu cao,gây ST tăng 40% | Buff `10180800` | Chưa áp dụng |
| +11 | `10480800` | Sát thương tất cả Tướng gây ra +8000 , miễn giảm sát thương +8000 | Đội xuất trận · ST cộng +8000, Miễn giảm ST +8000 | Hoạt động |
| +12 | `10490480` | HP+28800 | Bản thân · HP +28800 | Hoạt động |
| +13 | `10080870` | Chính Xác +4350 | Bản thân · Chính Xác +4350 | Hoạt động |
| +14 | `10500800` | Công+4800 | Bản thân · Công +4800 | Hoạt động |
| +15 | `20660830` | Khi Nộ Công, bỏ qua 83% Thủ của mục tiêu | Buff `10560830` | Chưa áp dụng |

## Takemaru Yokai (`12015018`)

Bậc tối đa từ HeroStepRelation +15. Bậc tài năng cao nhất trong bảng +15.

| Bậc | TAL | Hiệu ứng VN | Dữ liệu áp dụng | R7.16 |
|---:|---:|---|---|---|
| +1 | `21211000` | Khi mở trận bản thân thêm Khiên có 240% Thủ | Buff `20121000` | Chưa áp dụng |
| +2 | `10130160` | Công +80 | Bản thân · Công +80 | Hoạt động |
| +3 | `10030160` | Bạo Kích +800 | Bản thân · Bạo +800 | Hoạt động |
| +4 | `10160000` | Công của tất cả Tướng +250 | Đội xuất trận · Công +250 | Hoạt động |
| +5 | `20010000` | Khi Công, Chính Xác tăng 100% | Buff `20010000` | Chưa áp dụng |
| +6 | `10010000` | Mới bắt đầu tăng 50đ Nộ, lượt đầu có thể Nộ Công | Bản thân · Nộ +50 | Hoạt động |
| +7 | `10170000` | HP của tất cả Tướng +2500 | Đội xuất trận · HP +2500 | Hoạt động |
| +8 | `20750000` | Khi tiêu diệt mục tiêu, tiếp tục tấn công mục tiêu kế | Buff `20060000` | Chưa áp dụng |
| +9 | `10180000` | Tất cả thuộc tính của Tướng +4% | Đội xuất trận · % Công +4%, % HP +4%, % Thủ +4% | Hoạt động |
| +10 | `20500800` | Khi HP của mục tiêu thấp hơn 50%, gây ST tăng 40% | Buff `10200800` | Chưa áp dụng |
| +11 | `10480800` | Sát thương tất cả Tướng gây ra +8000 , miễn giảm sát thương +8000 | Đội xuất trận · ST cộng +8000, Miễn giảm ST +8000 | Hoạt động |
| +12 | `10490480` | HP+28800 | Bản thân · HP +28800 | Hoạt động |
| +13 | `10080870` | Chính Xác +4350 | Bản thân · Chính Xác +4350 | Hoạt động |
| +14 | `10500800` | Công+4800 | Bản thân · Công +4800 | Hoạt động |
| +15 | `20660830` | Khi Nộ Công, bỏ qua 83% Thủ của mục tiêu | Buff `10560830` | Chưa áp dụng |

## Tứ Đấu Thần (`12015022`)

Bậc tối đa từ HeroStepRelation +15. Bậc tài năng cao nhất trong bảng +15.

| Bậc | TAL | Hiệu ứng VN | Dữ liệu áp dụng | R7.16 |
|---:|---:|---|---|---|
| +2 | `10130200` | Công +100 | Bản thân · Công +100 | Hoạt động |
| +3 | `10030200` | Bạo Kích +1000 | Bản thân · Bạo +1000 | Hoạt động |
| +4 | `10160000` | Công của tất cả Tướng +250 | Đội xuất trận · Công +250 | Hoạt động |
| +5 | `20480600` | Mục tiêu của bản thân khi lượng máu cao,gây ST tăng 30% | Buff `10180600` | Chưa áp dụng |
| +6 | `10010000` | Mới bắt đầu tăng 50đ Nộ, lượt đầu có thể Nộ Công | Bản thân · Nộ +50 | Hoạt động |
| +7 | `10170000` | HP của tất cả Tướng +2500 | Đội xuất trận · HP +2500 | Hoạt động |
| +8 | `20340807` | Khi Nộ Công,48% giảm 75% hiệu quả trị liệu 2 lượt của mục tiêu | Buff `20300807` | Chưa áp dụng |
| +9 | `10180000` | Tất cả thuộc tính của Tướng +4% | Đội xuất trận · % Công +4%, % HP +4%, % Thủ +4% | Hoạt động |
| +10 | `21221000` | Khi đánh kỹ năng Nộ, 80% tăng 50đ Nộ cho bản thân | Buff `11111000` | Chưa áp dụng |
| +11 | `10481000` | Sát thương tất cả Tướng gây ra +10000 , miễn giảm sát thương +10000 | Đội xuất trận · ST cộng +10000, Miễn giảm ST +10000 | Hoạt động |
| +12 | `10490600` | HP+36000 | Bản thân · HP +36000 | Hoạt động |
| +13 | `10081000` | Chính Xác +5000 | Bản thân · Chính Xác +5000 | Hoạt động |
| +14 | `10501000` | Công+6000 | Bản thân · Công +6000 | Hoạt động |
| +15 | `10021000` | Chịu ST giảm 30% | Bản thân · % miễn giảm ST +30% | Hoạt động |

## Inu Kimi (`12015023`)

Bậc tối đa từ HeroStepRelation +15. Bậc tài năng cao nhất trong bảng +15.

| Bậc | TAL | Hiệu ứng VN | Dữ liệu áp dụng | R7.16 |
|---:|---:|---|---|---|
| +2 | `10150200` | HP +1000 | Bản thân · HP +1000 | Hoạt động |
| +3 | `10060200` | Né +800 | Bản thân · Né +800 | Hoạt động |
| +4 | `10160000` | Công của tất cả Tướng +250 | Đội xuất trận · Công +250 | Hoạt động |
| +5 | `20540600` | Khi HP của bản thân cao hơn 50%, chịu ST giảm 30% | Buff `10240600` | Chưa áp dụng |
| +6 | `10010000` | Mới bắt đầu tăng 50đ Nộ, lượt đầu có thể Nộ Công | Bản thân · Nộ +50 | Hoạt động |
| +7 | `10170000` | HP của tất cả Tướng +2500 | Đội xuất trận · HP +2500 | Hoạt động |
| +8 | `10050600` | Né +1800 | Bản thân · Né +1800 | Hoạt động |
| +9 | `10180000` | Tất cả thuộc tính của Tướng +4% | Đội xuất trận · % Công +4%, % HP +4%, % Thủ +4% | Hoạt động |
| +10 | `10100800` | Điểm Trị Liệu +24% | Bản thân · % Trị Liệu +40% | Hoạt động |
| +11 | `10481000` | Sát thương tất cả Tướng gây ra +10000 , miễn giảm sát thương +10000 | Đội xuất trận · ST cộng +10000, Miễn giảm ST +10000 | Hoạt động |
| +12 | `10490600` | HP+36000 | Bản thân · HP +36000 | Hoạt động |
| +13 | `10651000` | Kháng Bạo+5000 | Bản thân · Kháng Bạo +5000 | Hoạt động |
| +14 | `10501000` | Công+6000 | Bản thân · Công +6000 | Hoạt động |
| +15 | `20641000` | Ra trận lần 1,2,3, khi bản thân chịu ST giảm 75% | Buff `10141000` | Chưa áp dụng |
