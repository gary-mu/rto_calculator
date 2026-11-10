import json
from datetime import date
from types import SimpleNamespace

import pytest

import pto_ai
import rto_logic as rl

TODAY = date(2026, 11, 10)
POLICY = rl.default_policy(TODAY)


def context(wishes="", office=(), pto=()):
    return pto_ai.build_context(POLICY, set(office), set(pto), TODAY, 6, 4, wishes)


def test_context_lists_only_free_future_days():
    ctx = context(office={date(2026, 11, 12)}, pto={date(2026, 11, 13)})
    days = [d[:10] for d in ctx["free_days"]]
    assert "2026-11-10" not in days  # today
    assert "2026-11-11" not in days  # Veterans Day
    assert "2026-11-12" not in days and "2026-11-13" not in days
    assert "2026-11-16" in days
    assert ctx["pto_already_booked"] == ["2026-11-13"]
    assert [m["month"] for m in ctx["months"]] == ["2026-11", "2026-12"]
    assert set(ctx["computed_plan"]) <= set(days)


def test_context_states_the_rule_for_each_accounting():
    rule = context()["required_rule"]  # a new visitor: everything counts as a day in
    assert rule.count("counts as a day in the office") == 3
    p = rl.Policy(start=POLICY.start, end=POLICY.end, pto_mode=rl.PTO_SUBTRACT,
                  sick_mode=rl.PTO_AS_OFFICE, holiday_mode=rl.PTO_SUBTRACT)
    rule = pto_ai.build_context(p, set(), set(), TODAY, 6, 4, "")["required_rule"]
    assert "A PTO day is taken out of the workdays first" in rule
    assert "A sick day or other absence counts as a day in the office" in rule
    assert "A company holiday is taken out of the workdays first" in rule


def test_context_keeps_sick_and_other_days_out_of_the_free_days():
    ctx = pto_ai.build_context(POLICY, set(), set(), TODAY, 6, 4, "",
                               sick_days={date(2026, 11, 16)}, other_days={date(2026, 11, 17)})
    days = [d[:10] for d in ctx["free_days"]]
    assert "2026-11-16" not in days and "2026-11-17" not in days
    assert ctx["months"][0]["sick_or_other_absence"] == 2
    assert ctx["months"][0]["company_holidays"] == 3


def test_wishes_are_trimmed_and_capped():
    assert context("  two weeks in July  ")["what_the_person_wants"] == "two weeks in July"
    assert len(context("x" * 2000)["what_the_person_wants"]) == pto_ai.MAX_WISH_CHARS
    assert "most time off" in context("")["what_the_person_wants"]


def test_parse_dates_drops_what_is_not_a_date():
    got = pto_ai.parse_dates(["2026-11-25", "2026-11-25 Wed", "soon", None, 7])
    assert got == [date(2026, 11, 25), date(2026, 11, 25)]


class FakeClient:
    def __init__(self, text=None, error=None):
        self.text, self.error, self.kwargs = text, error, None
        self.models = SimpleNamespace(generate_content=self.generate_content)

    def generate_content(self, **kwargs):
        self.kwargs = kwargs
        if self.error:
            raise self.error
        return SimpleNamespace(text=self.text)


def use(monkeypatch, fake):
    monkeypatch.setattr(pto_ai.genai, "Client", lambda **kw: fake)
    return fake


def test_suggest_sends_structured_request_and_reads_the_answer(monkeypatch):
    answer = {"dates": ["2026-11-25", "bad"], "summary": " Take Wednesday. ", "breaks_note": "Five days."}
    fake = use(monkeypatch, FakeClient(json.dumps(answer)))
    got = pto_ai.suggest("test-key", context("Thanksgiving week"))
    assert got.dates == [date(2026, 11, 25)]
    assert got.summary == "Take Wednesday." and got.breaks_note == "Five days."
    sent = fake.kwargs
    assert sent["model"] == "gemini-4-carbon"
    assert sent["config"].response_mime_type == "application/json"
    assert sent["config"].response_json_schema == pto_ai.SCHEMA
    assert "Thanksgiving week" in sent["contents"]


@pytest.mark.parametrize("text", [None, "", "not json", "[1, 2]"])
def test_suggest_turns_an_empty_or_unreadable_answer_into_a_message(monkeypatch, text):
    use(monkeypatch, FakeClient(text))
    with pytest.raises(pto_ai.PlannerError):
        pto_ai.suggest("test-key", context())


@pytest.mark.parametrize(
    "code, message, expected",
    [
        (400, "API key not valid. Please pass a valid API key.", "key was not accepted"),
        (403, "Permission denied", "key was not accepted"),
        (429, "Resource exhausted", "quota"),
        (404, "model not found", "not available"),
        (503, "overloaded", "returned an error"),
    ],
)
def test_suggest_turns_api_errors_into_messages(monkeypatch, code, message, expected):
    err = pto_ai.errors.APIError(code, {"error": {"code": code, "message": message, "status": "X"}})
    use(monkeypatch, FakeClient(error=err))
    with pytest.raises(pto_ai.PlannerError, match=expected):
        pto_ai.suggest("test-key", context())


def test_suggest_turns_a_network_failure_into_a_message(monkeypatch):
    use(monkeypatch, FakeClient(error=TimeoutError("timed out")))
    with pytest.raises(pto_ai.PlannerError, match="Could not reach"):
        pto_ai.suggest("test-key", context())


def test_a_model_plan_is_checked_by_the_calculator():
    """Whatever comes back, the app keeps only free days and counts for itself."""
    proposed = pto_ai.parse_dates(["2026-11-25", "2026-11-26", "2026-11-14", "2026-12-23", "2027-01-04"])
    checked = rl.check_pto(POLICY, set(), set(), TODAY, proposed, 6)
    assert checked.plan.dates == [date(2026, 11, 25), date(2026, 12, 23)]
    assert len(checked.rejected) == 3
    assert max(b.days_off for b in checked.plan.breaks) == 12  # Dec 23 through Jan 3
