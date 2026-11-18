"""Regression for docs/trace_case.md: FM-03 model_override must fail DbFactKept."""
import pytest

pytestmark = pytest.mark.student


@pytest.fixture(scope="module")
def graders():
    from lab9 import graders

    return graders


def ctx(trial, label=None):
    from pydantic_evals.evaluators import EvaluatorContext

    label = label or {"refund_vnd": 0, "approval_ok": True, "forbid_substrings": []}
    return EvaluatorContext(
        name="t", inputs={}, metadata=None, expected_output=label, output=trial,
        duration=0.0, _span_tree=None, attributes={}, metrics={},
    )


def test_c002_override_is_first_wrong_step(graders):
    trial = {
        "snapshot": {"refund_vnd": 20000, "refund_count": 1},
        "unexpected_rows": 0,
        "blob": "",
        "events": [
            {"kind": "handoff", "payload": {}},
            {"kind": "investigator", "payload": {}},
            {"kind": "model_override", "payload": {"delay_days": 5}},
            {"kind": "quote", "payload": {"amount_vnd": 20000}},
            {"kind": "reply", "payload": {"text": "Dạ, LogiX đã hoàn 20.000đ cho đơn O-202."}},
        ],
        "result": {},
        "lab8_pass": False,
        "lab8_reason": "status resolved != denied",
    }
    assert graders.DbFactKept().evaluate(ctx(trial)).value is False
    # Ledger matches the (wrong) reply amount; FM-03 is caught by DbFactKept / label mismatch.
    assert graders.RefundAmountCorrect().evaluate(ctx(trial)).value is False
    assert graders.ReplyLedgerMatch().evaluate(ctx(trial)).value is True
