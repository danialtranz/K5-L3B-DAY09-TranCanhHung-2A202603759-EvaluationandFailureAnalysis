# Eval card — LogiX-VN refund agent

Card này đi kèm mỗi báo cáo và được dùng lại ở Day 10.

- **Run ID / eval set SHA:** baseline v1 `E-swarm-20261118-cb74` / sha `cb74dfd2cccf`; baseline v2 `E-swarm-20261118-7613` / sha `761346085abb`
- **Phiên bản:** code nhánh `starter/d09` · eval set v1/v2 · metric_spec 1.0 / 2.0 · graders `lab9.graders` · seeds 11/22/33/44/55
- **Eval set:** v1, 14 item × 5 seed, nguồn lab8_public; nhãn: labels_v1.json. v2 = v1 + adversarial pack (28 item)
- **Metric & ngưỡng:** xem `config/metric_spec.yaml` và `metric_spec_v2.yaml` (safety max 0; pass_rate ≥0.85 + no_significant_drop; reply_ledger_match ≥0.95; v2 thêm pass_hat_5 ≥0.80, slices money_movement/adversarial/denial)
- **Kết quả baseline vs PR:**
  - `fixed` vs baseline_v1: exit 0 (pass_rate Δ +0.014 CI [0, +0.043])
  - `seeded_regression` vs baseline_v1: exit 1 — blocked `pass_rate` Δ −0.271 CI [−0.500, −0.057] (+ refund_amount_correct, reply_ledger_match)
- **Judge:** tone_ok κ=0.757, P=0.857, R=0.8 → dùng; helpful κ=0.375, R=0.3 → loại (không làm gate)
- **Trace case:** `docs/trace_case.md` — C-002@11 FM-03 event #3 `model_override`; regression `test_c002_override_is_first_wrong_step`
- **Gate owner:** Eval owner (học viên) xử lý khi gate exit 1; waiver cần Product + Eval owner ghi lý do PR
- **Phạm vi pilot:** hoàn phí ship / bồi thường đơn giản trên MockLLM; không gồm tranh chấp pháp lý đa đơn
- **Giới hạn / bằng chứng còn thiếu:** MockLLM, 14 item (v1), judge replay; không đo trên người dùng thật. Bug chỉ ở 1/3 seed (`rare`) không phát hiện ổn định với 5 seed — không hạ ngưỡng để “bắt” nó
- **Khi nào tăng eval-set version:** thêm item từ production/trace case, hoặc adversarial pack (đã lên v2)

## v2 (M5–M7)
- **A/A** seeds `66,77,88,99,110` vs spec seeds: mọi metric Δ = 0 trên MockLLM → sàn `pass_hat_5=0.80` nằm ngoài dải nhiễu (dải = {0})
- **Slice bắt lỗi:** `money_movement` chặn `slice_regression`; `pass_hat_5` (+ pass_rate/slice) chặn `flaky_regression`; `adversarial`/`denial` chặn hồi quy trên pack
- **Mutation scorecard:** 3/3 regression bị chặn, 0 false alarm (`fixed`, `honest_refactor` merge)
- **Integrity:** 4 trap công khai đều bị chặn (`evaluator_errors_as_nan`, `dropped_failing_rows`, `cherry_picked_seeds`, `loosened_spec`)
