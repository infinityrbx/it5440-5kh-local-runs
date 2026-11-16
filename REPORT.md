# IT5440 · 5-KH · Báo cáo chạy mô hình cục bộ

16/11/2026

## Tóm tắt

Hiệu ứng vị trí xuất hiện rõ trên dữ liệu tổng hợp ở 16k, nhưng không xuất hiện trên code thật (toolz). Trên D2 với qwen3.5:9b, n = 50: đầu 98%, giữa 78%, cuối 98% (sign test p = 0,002; D = +0,20 [0,10; 0,32]). Cùng 50 câu ở 4k thì không có hiệu ứng (96 / 92 / 92%, p = 0,63).

Trên D1 (builder đã sửa filler), cả hai mô hình cục bộ đều sụt ở giữa theo điểm khớp một phần. Mức sụt của qwen2.5-coder:7b (D ≈ +0,13 đến +0,28) lớn hơn qwen3.5:9b (D ≈ +0,03 đến +0,10). Trên toolz, qwen3.5:9b không sụt ở giữa (p = 1), khớp với kết quả nhóm đã có trên DeepSeek và Qwen3.6-27B.

Mọi con số dưới đây được tính lại từ log thô bằng một script (`analysis/analyze.py`). Bảng đầy đủ do script sinh ra nằm ở `analysis/SUMMARY.md`.

## Thiết lập

Hai mô hình mở chạy cục bộ qua Ollama trên Apple M2 Pro 16 GB (GPU dùng được khoảng 10–11 GB), temperature 0, cửa sổ ngữ cảnh 24.576 token, mỗi lần một truy vấn. Chế độ thinking của qwen3.5 được tắt qua API gốc của Ollama, và đã kiểm tra 0 dòng có thinking.

| Tập dữ liệu | Nội dung | Mô hình | Độ dài | Cách chấm |
| --- | --- | --- | --- | --- |
| D2 SemTrace-Dep (`pilot.py` v5) | Chuỗi 5 hàm tổng hợp, độ sâu 2, CoT, tối đa 2048 token đầu ra | qwen3.5:9b | 4k, 16k; 50 câu (seed 2: 20, seed 3: 30) | Đúng/sai toàn bộ |
| D1 SemTrace (builder của nhóm, commit cf1f333) | 30 câu 2 chữ số + 30 câu 4 chữ số | qwen2.5-coder:7b, qwen3.5:9b | không filler, 4k, 16k | Khớp một phần (tỉ lệ phần tử đúng) |
| toolz (pipeline của nhóm, `toolz_final_clean`) | 40 câu k=1 + 40 câu k=3, filler seed 0 | qwen2.5-coder:7b, qwen3.5:9b | không filler, 4k | Đúng/sai toàn bộ |

Filler được dựng một lần cho mỗi câu và dùng lại ở mọi vị trí. Script kiểm tra `filler_hash` giống nhau ở đầu, giữa và cuối, nên chênh lệch chỉ đến từ vị trí.

Cách đo: D = (đầu + cuối)/2 − giữa, tính theo từng câu rồi lấy trung bình, khoảng tin cậy 95% bằng bootstrap 10.000 lần. So sánh cặp dùng sign test chính xác trên các cặp khác kết quả (McNemar). Trong bảng, b:c = số câu đúng ở vị trí so sánh nhưng sai ở giữa : số câu ngược lại. D1 chấm khớp một phần vì khớp chính xác gần như bằng 0 (2/30 câu 2 chữ số với qwen3.5 khi không có filler).

## Kết quả

### D2 SemTrace-Dep: sụt ở giữa tại 16k, không sụt tại 4k

| Độ dài (token prompt) | n | C0 | C1 đầu | C1 giữa | C1 cuối | C2 | C3 | Giữa so với đầu (b:c, p) | D [CI 95%] |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| 4k (4.216–4.572) | 50 | 100% | 96% | 92% | 92% | 96% | 98% | 3:1, p = 0,63 | +0,02 [−0,04; +0,09] |
| 16k (16.636–17.438) | 50 | 98% | 98% | 78% | 98% | 98% | 98% | 10:0, p = 0,002 | +0,20 [+0,10; +0,32] |

- Cả 10 câu sai ở giữa tại 16k đều đúng ở cả đầu lẫn cuối, và không có câu nào theo chiều ngược lại.
- 4 trong 10 câu sai là do câu trả lời bị cắt ở giới hạn 2048 token, và việc bị cắt chỉ xảy ra ở giữa. Bỏ 4 câu này thì vẫn còn 6:0, p = 0,031. 6 câu còn lại là lỗi lệch hằng số, trùng với kiểu truy vết sai chuỗi helper.
- C0, C2 và C3 đều từ 96–100%, nên mô hình làm được bài. Chỉ có việc đặt đoạn cần thiết ở giữa là gây hại. Chuyển khối cần thiết ra cuối (C2) hoặc cắt theo call graph (C3) đều khôi phục độ chính xác.
- So sánh vị trí giữa trên cùng 50 câu: 10 câu tệ đi khi lên 16k, 3 câu tốt lên, p = 0,092. Xu hướng là hiệu ứng tăng theo độ dài, nhưng chưa đủ ý nghĩa thống kê với n = 50.

### D1 SemTrace: sụt ở giữa theo điểm khớp một phần, mạnh hơn ở qwen2.5-coder

| Mô hình | Chữ số | Độ dài | Không filler | Đầu | Giữa | Cuối | D [CI 95%] |
| --- | --- | --- | --- | --- | --- | --- | --- |
| qwen2.5-coder:7b | 2 | 4k | 0,25 | 0,37 | 0,16 | 0,43 | +0,25 [+0,19; +0,30] |
| qwen2.5-coder:7b | 2 | 16k | 0,25 | 0,26 | 0,06 | 0,43 | +0,28 [+0,22; +0,35] |
| qwen2.5-coder:7b | 4 | 4k | 0,24 | 0,15 | 0,05 | 0,23 | +0,14 [+0,08; +0,20] |
| qwen2.5-coder:7b | 4 | 16k | 0,24 | 0,06 | 0,00 | 0,21 | +0,13 [+0,09; +0,17] |
| qwen3.5:9b | 2 | 4k | 0,51 | 0,45 | 0,40 | 0,52 | +0,09 [+0,03; +0,14] |
| qwen3.5:9b | 2 | 16k | 0,51 | 0,33 | 0,28 | 0,42 | +0,10 [+0,03; +0,17] |
| qwen3.5:9b | 4 | 4k | 0,33 | 0,17 | 0,14 | 0,17 | +0,03 [−0,02; +0,08] |
| qwen3.5:9b | 4 | 16k | 0,33 | 0,13 | 0,08 | 0,11 | +0,04 [−0,00; +0,09] |

Mỗi dòng có 30 câu. Số câu khớp chính xác gần như bằng 0 (tối đa 1/90 ở mỗi dòng). Với qwen2.5-coder, vị trí cuối tốt hơn hẳn vị trí đầu, nghĩa là có thiên lệch gần đây (recency) bên cạnh mức sụt ở giữa. Với qwen3.5, D giống nhau ở 4k và 16k: 16k thấp hơn ở mọi vị trí chứ không riêng ở giữa.

### toolz (code thật): không có hiệu ứng vị trí ở 4k

| Mô hình | Không filler k=1 | Không filler k=3 | 4k k=1 đầu / giữa / cuối | Giữa so với đầu (b:c, p) | Giữa so với cuối (b:c, p) | 4k k=3 cụm đầu / giữa / cuối / rải |
| --- | --- | --- | --- | --- | --- | --- |
| qwen2.5-coder:7b | 52% | 20% | 52% / 38% / 45% | 7:1, p = 0,07 | 5:2, p = 0,45 | 30% / 38% / 35% / 32% |
| qwen3.5:9b | 50% | 30% | 38% / 40% / 40% | 3:4, p = 1,00 | 2:2, p = 1,00 | 30% / 22% / 22% / 20% |

Mỗi ô có 40 câu. qwen3.5 không sụt ở giữa. qwen2.5-coder có xu hướng giữa thấp hơn đầu (p = 0,07), nhưng chưa đạt ý nghĩa. Với k=3, việc dồn hay rải các đoạn cần thiết không tạo khác biệt rõ ở cả hai mô hình.

## Ý nghĩa với các giả thuyết, hạn chế và việc còn lại

Kết quả cục bộ ủng hộ hướng "phương pháp + kết quả null trên code thật + recency" mà nhóm đang cân nhắc. Đồng thời nó cho thấy hiệu ứng chỉ xuất hiện ở dữ liệu tổng hợp và ngữ cảnh dài.

| Giả thuyết (theo bản nháp) | Bằng chứng cục bộ | Đánh giá |
| --- | --- | --- |
| H1: hiệu ứng vị trí, A = max − min ≥ 15 điểm % | D2 16k: A = 20 điểm %, p = 0,002. D2 4k: A = 4. toolz qwen3.5 4k: A = 2 | Đạt ở D2 16k, không đạt ở 4k và trên code thật |
| H2: truy xuất nguyên văn vẫn tốt (lexical recall ≥ 95%) trong khi suy luận sụt | D1 qwen2.5-coder: chép lại đúng 100% khi đoạn cần thiết nằm ở giữa (4k và 16k, 120 lượt), trong khi điểm khớp một phần ở giữa chỉ 0,00–0,16 | Phù hợp: mô hình tìm thấy đoạn code nhưng truy vết sai |
| H3: C2/C3 khôi phục độ chính xác về gần C0 | D2 16k: C2 98%, C3 98%, C0 98%, so với C1 giữa 78% | Đạt, nhưng C3 chính xác tuyệt đối trên code tổng hợp (100/100 ngữ cảnh), nên đây là cận trên |

Ngưỡng trong cột đầu ghi theo bản nháp. Nhóm trưởng nên kiểm tra lại cách ánh xạ này trước khi đưa vào báo cáo.

**Hạn chế**

- Cỡ mẫu nhỏ: D2 có n = 50, các ô của D1 và toolz có n = 30–40. So sánh 4k với 16k (p = 0,09) chưa đủ ý nghĩa.
- Chỉ có hai mô hình nhỏ, lượng tử hóa 4-bit, chạy một lần với temperature 0 và một filler seed. toolz cục bộ chỉ chạy đến 4k.
- Ở D2 16k, 4 câu trả lời ở giữa bị cắt ở 2048 token. Đây cũng có thể là một dấu hiệu của hiệu ứng: mô hình suy luận lan man hơn khi đoạn cần thiết nằm ở giữa.
- D1 gần mức sàn khi chấm chính xác, nên mọi kết luận về D1 dựa trên điểm khớp một phần.

**Việc còn lại**

- [ ] Chạy lại D1 bằng builder đã sửa filler trên DeepSeek-V4-Flash và Qwen3.6-27B, vì kết quả D1 cũ (`compare_deepseek.jsonl`) còn lỗi filler. Việc này cần API key của nhóm.
- [ ] Thống nhất cách đưa kết quả cục bộ vào bảng kết quả chính trước hạn đóng băng 18/11.

## Repo và cách tái lập

Xem `README.md`: cấu trúc thư mục, thay đổi duy nhất trong code của nhóm (`run_eval.py`, bật bằng `OLLAMA_NATIVE=1`), lệnh chạy lại từng phần và nhật ký các hàng đợi. Chạy `python3 analysis/analyze.py` để tính lại mọi bảng ở trên.
