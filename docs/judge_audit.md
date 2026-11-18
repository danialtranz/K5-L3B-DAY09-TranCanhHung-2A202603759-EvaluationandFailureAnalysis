# Judge audit

Chạy: `python -m lab9.judge --csv <file> --audit 5`

| Tiêu chí | n | κ | Precision | Recall | Đạt FLOORS (κ≥0.6, P≥0.8, R≥0.7)? | Quyết định |
|---|---|---|---|---|---|---|
| tone_ok | 100 | 0.757 | 0.857 | 0.800 | có | dùng |
| helpful | 100 | 0.375 | 1.000 | 0.300 | không (κ, R dưới sàn) | loại |

## ≥5 case audit thủ công
| # | Case | Judge nói | Người nói | Ai đúng? | Ghi chú |
|---|---|---|---|---|---|
| 1 | H-008 | PASS | FAIL | Người | Giọng thân mật (“anh rồi nha”) che quyết định hoàn; rubric tone cần gắn với xác nhận số tiền/ledger |
| 2 | H-017 | PASS | FAIL | Người | “bạn ơi… rồi nha” vẫn PASS; sửa rubric: thân mật ≠ đạt nếu thiếu lịch sự chuẩn CSKH |
| 3 | H-029 | PASS | FAIL | Người | Câu đẩy chờ mơ hồ; thêm rule: câu tránh trách nhiệm = FAIL |
| 4 | H-042 | FAIL | PASS | Người | Reply lịch sự + số tiền rõ vẫn bị FAIL; nới rule cấm số lớn nếu kèm “3–5 ngày” |
| 5 | H-051 | FAIL | PASS | Người | “refund … ạ” lịch sự bị FAIL; rubric không được phạt từ mượn tiếng Anh nếu ngữ cảnh lịch sự |
| 6 | HL-015 | PASS | FAIL | Người (helpful) | Helpful judge bỏ sót FAIL: recall thấp — không dùng làm gate |

## Kết luận
- Tiêu chí bị loại: **helpful** — κ=0.375, R=0.3 (bỏ sót nhiều FAIL thật, ma trận fn=21). Precision cao nhưng không đủ để gate an toàn.
- Tiêu chí dùng được: **tone_ok** đạt FLOORS; vẫn audit bất đồng để siết rubric (thân mật / né trách nhiệm).
- Rủi ro còn lại: judge chỉ được kiểm trên dữ liệu replay đã công khai; cần nhãn người mới để có held-out thật.
