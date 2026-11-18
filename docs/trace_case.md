# Trace case: từ trace tới quyết định sai đầu tiên

Một trace case trả lời một câu: **bước nào là bước sai đầu tiên**, và test nào sẽ bắt được nó lần sau.

```bash
cd src
python -m lab9.trace_case --shape seeded_regression --claim C-002 --seed 11
python -m lab9.trace_case --shape fixed --claim C-002 --seed 11   # đối chứng
```

Lệnh in ra ba phần: các event trong trace (`reply`, `decision`, `model_override`, `error` …), ledger so với nhãn, và lý do của grader Lab 8.

## Case đã điền

| Trường | Nội dung |
|---|---|
| Trial | `seeded_regression C-002@11`, run ID trong `reports/eval_seeded_regression.json` (cùng eval set sha `f0bd…`) |
| Triệu chứng | Lab8 grader FAIL (`status resolved != denied`); ledger `refund_vnd=20000` vs label `0`; reply nói đã hoàn 20.000đ |
| Bước sai đầu tiên | Event **#3** `model_override` `{"delay_days": 5}` — tin số ngày trong ticket thay vì DB |
| Vì sao là bước *đầu tiên* | Event 1–2 chỉ handoff + lookup_order (DB vẫn đúng). Sau override, quote (#4) thành 20000 entitled và host ghi refund |
| Failure mode | **FM-03** ticket_trust |
| Đối chứng | `fixed C-002@11`: không có `model_override`; quote `no_entitlement`; status denied; ledger 0 — PASS |
| Regression test | `tests/test_lab9_graders.py::test_override_event_breaks_db_fact` + metric `db_fact_kept`; trên report: `seeded_regression` db_fact_kept=0.9286 (warn), `fixed`=1.0 |
| Chưa chắc chắn | Trace không chứng minh intent của model; chỉ chứng minh override đã xảy ra trước khi tiền được ghi |

## Quy tắc

- Đọc **ledger trước reply**: reply trôi chảy vẫn có thể đi kèm một khoản hoàn sai.
- "Bước sai đầu tiên" phải dẫn số event cụ thể, không phải "agent bị nhầm".
- Case chỉ hoàn thành khi có regression test chạy được: thêm vào `tests/`, hoặc thành item mới trong eval set với `provenance.from_trace`.
