"""PTO-maxxing: ask Gemini where to put PTO days.

The model proposes dates and explains them. It never does the arithmetic the
person relies on: rto_logic.check_pto filters the dates and computes every
number shown in the app.
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from datetime import date

from google import genai
from google.genai import errors, types

import rto_logic as rl

MODEL = "gemini-4-carbon"
# At the model's default thinking level a plan took about 110 seconds, right at
# the request deadline, and the API answered 504 whenever it ran a little
# over. At "LOW" the same plan comes back in about 6 seconds. The app checks
# every date and does the counting itself, so the model does not need to.
THINKING_LEVEL = "LOW"
TIMEOUT_MS = 180_000
KEY_NAMES = ("GEMINI_API_KEY", "GOOGLE_API_KEY")
MAX_WISH_CHARS = 500

SYSTEM = """You help one person plan paid time off (PTO) under their employer's return-to-office policy.

Their goal is the most time away from the office: long unbroken stretches off, built by placing PTO next to weekends and company holidays, while they can still meet the policy's required office days every month.

You are given the policy, a month-by-month table, the list of days that are free to book, a plan the app computed without you, and what the person said they want. What the person asks for comes first: if they want two weeks in July, give them two weeks in July even if it scores worse on paper, and say what it costs. Where they left it open, use your judgment to get them the best time off, and improve on the computed plan where you can rather than repeating it.

Rules the app enforces after you answer, so follow them exactly:
- Pick dates only from `free_days`. Anything else is discarded.
- Pick at most `pto_days_to_place` dates. You may pick fewer if more would not help.
- A month is only workable if its free days left after your PTO are at least the office days still required there. The table gives you what you need to check this; `required_rule` says how PTO changes the requirement.

The app works out the final office-day numbers itself and shows them next to your answer, so describe the plan rather than quoting totals. Write `summary` as two or three plain sentences to the person, and `breaks_note` as one sentence on the best stretch off. No markdown."""

SCHEMA = {
    "type": "object",
    "properties": {
        "dates": {
            "type": "array",
            "items": {"type": "string"},
            "description": "PTO dates to book, as YYYY-MM-DD, taken from free_days.",
        },
        "summary": {"type": "string"},
        "breaks_note": {"type": "string"},
    },
    "required": ["dates", "summary", "breaks_note"],
    "additionalProperties": False,
}


class PlannerError(Exception):
    """A message that is safe to show the person."""


@dataclass(frozen=True)
class Suggestion:
    dates: list
    summary: str
    breaks_note: str


def required_rule(policy: rl.Policy) -> str:
    """The month's requirement in words, for the model."""
    def how(mode):
        return "counts as a day in the office" if mode == rl.PTO_AS_OFFICE else "is taken out of the workdays first"
    return (
        f"Per month: required = ceil(counted_days * {policy.percent:g} / 100) - credited_days, never below 0. "
        f"A PTO day {how(policy.pto_mode)}. A sick day or other absence {how(policy.sick_rule)}. "
        f"A company holiday {how(policy.holiday_mode)}. "
        "counted_days are the weekdays left after everything taken out; credited_days are the days that count as in the office."
    )


def build_context(policy: rl.Policy, office_days, pto_days, today: date, budget: int,
                  max_pto_per_break: int, wishes: str, sick_days=(), other_days=()) -> dict:
    summary = rl.summarize(policy, office_days, pto_days, today, sick_days, other_days)
    holidays = rl.policy_holidays(policy)
    baseline = rl.plan_pto(policy, office_days, pto_days, today, budget, max_pto_per_break, sick_days, other_days)
    rule = required_rule(policy)
    return {
        "today": today.isoformat(),
        "period": [policy.start.isoformat(), policy.end.isoformat()],
        "required_rule": rule,
        "pto_days_to_place": budget,
        "preferred_max_pto_days_in_one_break": max_pto_per_break,
        "months": [
            {
                "month": m.key,
                "workdays": m.workdays,
                "pto_already_booked": m.pto,
                "sick_or_other_absence": m.sick + m.other,
                "company_holidays": m.holidays,
                "office_days_required": m.required,
                "office_days_logged": m.attended,
                "office_days_still_required": m.remaining,
                "free_workdays_left": m.left,
            }
            for m in summary.months
            if not m.is_past
        ],
        "company_holidays": {d.isoformat(): name for d, name in holidays.items() if d >= today},
        "pto_already_booked": sorted(d.isoformat() for d in pto_days if d >= today),
        "free_days": [f"{d.isoformat()} {d:%a}" for d in rl.free_days(policy, office_days, pto_days, today, sick_days, other_days)],
        "computed_plan": [d.isoformat() for d in baseline.dates],
        "what_the_person_wants": wishes.strip()[:MAX_WISH_CHARS] or "Nothing specific. Get me the most time off.",
    }


def parse_dates(items) -> list:
    out = []
    for item in items or []:
        try:
            out.append(date.fromisoformat(str(item)[:10]))
        except ValueError:
            continue
    return out


def suggest(api_key: str, context: dict) -> Suggestion:
    """One request to Gemini. Raises PlannerError with a message for the person."""
    client = genai.Client(api_key=api_key, http_options=types.HttpOptions(timeout=TIMEOUT_MS))
    try:
        response = client.models.generate_content(
            model=MODEL,
            contents=json.dumps(context, indent=1),
            config=types.GenerateContentConfig(
                system_instruction=SYSTEM,
                response_mime_type="application/json",
                response_json_schema=SCHEMA,
                thinking_config=types.ThinkingConfig(thinking_level=THINKING_LEVEL),
            ),
        )
    except errors.APIError as e:
        code = e.code or 0
        text = (e.message or "").lower()
        if code in (401, 403) or "api key" in text:
            raise PlannerError("The AI planner's API key was not accepted.") from e
        if code == 429:
            raise PlannerError("The AI planner is over its quota or busy. Try again in a minute.") from e
        if code == 504:
            raise PlannerError(
                "The AI planner took too long to answer. Try again, or use the quick plan."
            ) from e
        if code == 404:
            raise PlannerError(f"The AI planner's model ({MODEL}) is not available to this API key.") from e
        raise PlannerError(f"The AI planner returned an error ({code}). Try again.") from e
    except Exception as e:  # network trouble, timeouts
        raise PlannerError("Could not reach the AI planner. Check the connection and try again.") from e

    text = response.text
    if not text:
        raise PlannerError("The AI planner did not return a plan. Try rewording what you want.")
    try:
        data = json.loads(text)
        if not isinstance(data, dict):
            raise ValueError
    except ValueError as e:
        raise PlannerError("The AI planner's answer could not be read. Try again.") from e
    return Suggestion(
        dates=parse_dates(data.get("dates")),
        summary=str(data.get("summary", "")).strip(),
        breaks_note=str(data.get("breaks_note", "")).strip(),
    )
