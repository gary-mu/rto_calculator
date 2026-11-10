"""Calculation logic for the RTO calculator. Pure Python: no Streamlit in here.

The policy rules are the ones the app has always used:

* A workday is a weekday that is not a company holiday.
* Company holidays are the US federal holidays, the day after Thanksgiving
  and, optionally, a Christmas break (the weekdays of Dec 24 to Dec 31).
* The requirement is counted month by month, a percentage of that month's
  workdays, rounded down.
* PTO is accounted for in one of two ways: it is taken out of the workdays
  before the percentage is applied, or it counts as a day in the office.
* A sick day or another absence is accounted for the same way as a PTO day,
  but does not use up the PTO allowance.
* The holiday list can be replaced with the person's own.
"""

from __future__ import annotations

import csv
import io
import json
import math
from dataclasses import dataclass, field
from datetime import date, timedelta
from fractions import Fraction

import holidays as hd

PTO_SUBTRACT = "subtract"  # PTO subtracted from workdays
PTO_AS_OFFICE = "office"  # PTO as a day in office
PTO_MODES = (PTO_SUBTRACT, PTO_AS_OFFICE)

STATE_VERSION = 1


# ---------------------------------------------------------------- policy


@dataclass(frozen=True)
class Policy:
    start: date
    end: date
    percent: float = 60.0
    pto_mode: str = PTO_SUBTRACT
    christmas_break: bool = True
    pto_allowance: int = 20
    # ((date, name), ...) replaces the built-in US list when set.
    custom_holidays: tuple | None = None

    def __post_init__(self):
        if self.end < self.start:
            raise ValueError("The period ends before it starts.")
        if not 0 <= self.percent <= 100:
            raise ValueError("The percentage must be between 0 and 100.")
        if self.pto_mode not in PTO_MODES:
            raise ValueError(f"Unknown PTO accounting: {self.pto_mode}")


def default_policy(today: date) -> Policy:
    return Policy(start=date(today.year, 1, 1), end=date(today.year, 12, 31))


# -------------------------------------------------------------- calendar


def _holidays_for_years(years, christmas_break: bool) -> dict[date, str]:
    out: dict[date, str] = {}
    for d, name in hd.US(years=list(years)).items():
        out[d] = name
    for year in years:
        thursdays = [
            date(year, 11, day)
            for day in range(1, 31)
            if date(year, 11, day).weekday() == 3
        ]
        out[thursdays[3] + timedelta(days=1)] = "Day After Thanksgiving"
        if christmas_break:
            for day in range(24, 32):
                d = date(year, 12, day)
                if d.weekday() < 5 and day != 25:
                    out[d] = "Christmas Break"
    return out


def company_holidays(start: date, end: date, christmas_break: bool = True) -> dict[date, str]:
    """Holidays that fall inside the period, in date order."""
    every = _holidays_for_years(range(start.year, end.year + 1), christmas_break)
    return {d: every[d] for d in sorted(every) if start <= d <= end}


def policy_holidays(policy: Policy) -> dict[date, str]:
    """The holidays in force for a policy: the person's own list if they set one."""
    if policy.custom_holidays is None:
        return company_holidays(policy.start, policy.end, policy.christmas_break)
    return {d: name for d, name in sorted(policy.custom_holidays) if policy.start <= d <= policy.end}


def _off_fixed(policy: Policy) -> set[date]:
    """Holidays in and around the period, for measuring stretches off."""
    if policy.custom_holidays is not None:
        return {d for d, _ in policy.custom_holidays}
    years = range(policy.start.year - 1, policy.end.year + 2)
    return set(_holidays_for_years(years, policy.christmas_break))


def parse_holiday_csv(text: str):
    """Read 'date,name' rows. Dates as 2026-07-03 or 7/3/2026; a header row is fine.

    Returns ({date: name}, number of rows that could not be read).
    """
    found: dict[date, str] = {}
    bad = 0
    for row in csv.reader(io.StringIO(text)):
        cells = [c.strip() for c in row]
        if not cells or not any(cells):
            continue
        raw, name = cells[0], (cells[1] if len(cells) > 1 else "")
        d = None
        try:
            d = date.fromisoformat(raw)
        except ValueError:
            parts = raw.replace("-", "/").split("/")
            if len(parts) == 3 and all(x.isdigit() for x in parts):
                m, dd, y = (int(x) for x in parts)
                try:
                    d = date(y if y > 99 else 2000 + y, m, dd)
                except ValueError:
                    d = None
        if d is None:
            if raw.lower() not in ("date", "day"):
                bad += 1
            continue
        found[d] = name or "Company holiday"
    return dict(sorted(found.items())), bad


def daterange(start: date, end: date):
    d = start
    while d <= end:
        yield d
        d += timedelta(days=1)


def workdays_between(start: date, end: date, holiday_dates) -> list[date]:
    return [d for d in daterange(start, end) if d.weekday() < 5 and d not in holiday_dates]


def month_key(d: date) -> str:
    return f"{d.year:04d}-{d.month:02d}"


# ----------------------------------------------------------- requirement


def required_days(workdays: int, pto: int, percent: float, pto_mode: str) -> int:
    """Office days required in one month. Rounded down, never negative."""
    share = Fraction(str(percent)) / 100
    if pto_mode == PTO_SUBTRACT:
        need = math.floor(max(0, workdays - pto) * share)
    else:
        need = math.floor(workdays * share) - pto
    return max(0, need)


def office_share(workdays: int, pto: int, attended: int, pto_mode: str) -> float:
    """Percent of workdays spent in the office, counted the way the policy counts.

    PTO subtracted from workdays: logged days over the workdays left after PTO.
    PTO as a day in office: logged days plus PTO days over all workdays.
    """
    if pto_mode == PTO_SUBTRACT:
        base, done = workdays - pto, attended
    else:
        base, done = workdays, attended + pto
    if base <= 0:
        return 0.0
    return min(100.0, 100.0 * done / base)


@dataclass(frozen=True)
class MonthSummary:
    key: str  # "2026-11"
    first: date  # first day of the month, for labels
    workdays: int
    holidays: int
    pto: int
    required: int
    attended: int
    remaining: int  # required days not yet logged
    left: int  # workdays from today on that are still free
    shortfall: int  # remaining days that no longer fit in the month
    is_past: bool
    is_current: bool
    share: float = 0.0  # percent of the month's workdays in the office so far
    sick: int = 0
    other: int = 0


@dataclass(frozen=True)
class Summary:
    months: list[MonthSummary]
    workdays: int
    holidays: int
    pto: int
    required: int
    attended: int
    remaining: int
    shortfall: int
    current: MonthSummary | None = None
    share: float = 0.0  # percent of the period's workdays in the office so far
    sick: int = 0
    other: int = 0

    @property
    def remaining_ahead(self) -> int:
        """Days still to go from the current month on. Past months are closed."""
        return sum(m.remaining for m in self.months if not m.is_past)

    @property
    def counted(self) -> int:
        """Logged days that count toward a month's requirement."""
        return sum(min(m.attended, m.required) for m in self.months)


def _clean(days, workday_set) -> set[date]:
    return {d for d in days if d in workday_set}


def summarize(policy: Policy, office_days, pto_days, today: date, sick_days=(), other_days=()) -> Summary:
    hols = policy_holidays(policy)
    wds = workdays_between(policy.start, policy.end, hols)
    wd_set = set(wds)
    pto = _clean(pto_days, wd_set)
    sick = _clean(sick_days, wd_set) - pto
    other = _clean(other_days, wd_set) - pto - sick
    away = pto | sick | other
    office = _clean(office_days, wd_set) - away

    by_month: dict[str, list[date]] = {}
    for d in daterange(policy.start, policy.end):
        by_month.setdefault(month_key(d), [])
    for d in wds:
        by_month[month_key(d)].append(d)
    hol_count: dict[str, int] = {}
    for d in hols:
        if d.weekday() < 5:
            hol_count[month_key(d)] = hol_count.get(month_key(d), 0) + 1

    months = []
    this_month = month_key(today)
    for key, days in by_month.items():
        m_pto = sum(1 for d in days if d in pto)
        m_sick = sum(1 for d in days if d in sick)
        m_other = sum(1 for d in days if d in other)
        m_away = m_pto + m_sick + m_other
        m_att = sum(1 for d in days if d in office)
        req = required_days(len(days), m_away, policy.percent, policy.pto_mode)
        remaining = max(0, req - m_att)
        left = sum(1 for d in days if d >= today and d not in away and d not in office)
        year, month = int(key[:4]), int(key[5:])
        months.append(
            MonthSummary(
                key=key,
                first=date(year, month, 1),
                workdays=len(days),
                holidays=hol_count.get(key, 0),
                pto=m_pto,
                required=req,
                attended=m_att,
                remaining=remaining,
                left=left,
                shortfall=max(0, remaining - left),
                is_past=key < this_month,
                is_current=key == this_month,
                share=office_share(len(days), m_away, m_att, policy.pto_mode),
                sick=m_sick,
                other=m_other,
            )
        )

    return Summary(
        months=months,
        workdays=len(wds),
        holidays=sum(hol_count.values()),
        pto=len(pto),
        required=sum(m.required for m in months),
        attended=sum(m.attended for m in months),
        remaining=sum(m.remaining for m in months),
        shortfall=sum(m.shortfall for m in months),
        current=next((m for m in months if m.is_current), None),
        share=office_share(len(wds), len(away), sum(m.attended for m in months), policy.pto_mode),
        sick=len(sick),
        other=len(other),
    )


# ----------------------------------------------------------- PTO planner


@dataclass(frozen=True)
class Break:
    start: date
    end: date
    days_off: int  # calendar days in a row, weekends and holidays included
    pto_dates: tuple[date, ...]  # the suggested PTO days inside it


@dataclass(frozen=True)
class PtoPlan:
    dates: list[date] = field(default_factory=list)
    breaks: list[Break] = field(default_factory=list)
    required_before: int = 0
    required_after: int = 0
    remaining_before: int = 0
    remaining_after: int = 0
    requested: int = 0

    @property
    def office_days_saved(self) -> int:
        return self.remaining_before - self.remaining_after


def _run(d: date, is_off) -> tuple[date, date]:
    lo = d
    while is_off(lo - timedelta(days=1)):
        lo -= timedelta(days=1)
    hi = d
    while is_off(hi + timedelta(days=1)):
        hi += timedelta(days=1)
    return lo, hi


def _rank_month(candidates, off_fixed, pto_existing, max_pto_per_break):
    """Order one month's free workdays by how long a stretch off each buys.

    Greedy: each pick is the day that adds the most days off in a row, given
    the picks before it. Returns [(date, days gained), ...].
    """
    chosen: set[date] = set()
    ranked = []
    pool = list(candidates)

    def is_off(d, extra=None):
        return d.weekday() >= 5 or d in off_fixed or d in pto_existing or d in chosen or d == extra

    while pool:
        best = None
        for c in pool:
            lo, hi = _run(c, lambda d: is_off(d, c))
            span = [d for d in daterange(lo, hi)]
            pto_in_run = sum(1 for d in span if d == c or d in chosen or d in pto_existing)
            if pto_in_run > max_pto_per_break:
                continue
            # Days already part of a break that has PTO in it are not new.
            already = 0
            for side in (c - timedelta(days=1), c + timedelta(days=1)):
                if is_off(side):
                    s_lo, s_hi = _run(side, is_off)
                    side_span = list(daterange(s_lo, s_hi))
                    if any(d in chosen or d in pto_existing for d in side_span):
                        already += len(side_span)
            gain = len(span) - already
            if best is None or gain > best[1]:
                best = (c, gain)
        if best is None:
            break
        chosen.add(best[0])
        pool.remove(best[0])
        ranked.append(best)
    return ranked


def plan_pto(
    policy: Policy,
    office_days,
    pto_days,
    today: date,
    budget: int,
    max_pto_per_break: int = 4,
) -> PtoPlan:
    """Place up to `budget` more PTO days.

    First aim: the fewest office days still required, without making any
    month impossible to meet. Second aim, among plans that tie on the first:
    the longest stretches off per PTO day (bridging weekends and holidays).
    """
    before = summarize(policy, office_days, pto_days, today)
    plan0 = PtoPlan(
        required_before=before.required,
        required_after=before.required,
        remaining_before=before.remaining_ahead,
        remaining_after=before.remaining_ahead,
        requested=max(0, budget),
    )
    if budget <= 0:
        return plan0

    off_fixed = _off_fixed(policy)
    hols = policy_holidays(policy)
    wds = workdays_between(policy.start, policy.end, hols)
    wd_set = set(wds)
    pto = _clean(pto_days, wd_set)
    office = _clean(office_days, wd_set) - pto

    options = []  # per month: list of (p, remaining, score, dates)
    for m in before.months:
        cands = [
            d for d in wds
            if month_key(d) == m.key and d > today and d not in pto and d not in office
        ]
        ranked = _rank_month(cands, off_fixed, pto, max_pto_per_break) if cands else []
        rows = [(0, m.remaining, 0, [])]
        score = 0
        for i, (d, gain) in enumerate(ranked, start=1):
            score += gain
            req = required_days(m.workdays, m.pto + i, policy.percent, policy.pto_mode)
            remaining = max(0, req - m.attended)
            if max(0, remaining - (m.left - i)) > m.shortfall:
                break  # would make the month harder to meet than it is now
            rows.append((i, remaining, score, [x for x, _ in ranked[:i]]))
        options.append(rows)

    # Knapsack over months: minimise remaining office days, then maximise score.
    best: dict[int, tuple[int, int, list]] = {0: (0, 0, [])}
    for rows in options:
        nxt: dict[int, tuple[int, int, list]] = {}
        for used, (rem, neg_score, dates) in best.items():
            for p, m_rem, m_score, m_dates in rows:
                if used + p > budget:
                    break
                cand = (rem + m_rem, neg_score - m_score, dates + m_dates)
                cur = nxt.get(used + p)
                if cur is None or cand[:2] < cur[:2]:
                    nxt[used + p] = cand
        best = nxt
    # Fewest office days first; then the best stretches; then the fewest PTO days.
    _used, (_rem, _neg, dates) = min(best.items(), key=lambda kv: (kv[1][0], kv[1][1], kv[0]))
    dates = sorted(dates)
    if not dates:
        return plan0

    return _build_plan(policy, office_days, pto_days, today, dates, budget, before)


def _build_plan(policy, office_days, pto_days, today, dates, requested, before=None) -> PtoPlan:
    """The numbers and breaks for a given set of new PTO dates."""
    before = before or summarize(policy, office_days, pto_days, today)
    dates = sorted(dates)
    off_fixed = _off_fixed(policy)
    existing = set(pto_days)
    after = summarize(policy, office_days, existing | set(dates), today)
    chosen = set(dates)

    def is_off(d):
        return d.weekday() >= 5 or d in off_fixed or d in existing or d in chosen

    breaks, seen = [], set()
    for d in dates:
        if d in seen:
            continue
        lo, hi = _run(d, is_off)
        inside = tuple(x for x in dates if lo <= x <= hi)
        seen.update(inside)
        breaks.append(Break(start=lo, end=hi, days_off=(hi - lo).days + 1, pto_dates=inside))

    return PtoPlan(
        dates=dates,
        breaks=breaks,
        required_before=before.required,
        required_after=after.required,
        remaining_before=before.remaining_ahead,
        remaining_after=after.remaining_ahead,
        requested=requested,
    )


def free_days(policy: Policy, office_days, pto_days, today: date) -> list[date]:
    """Workdays after today that are neither logged nor already PTO."""
    hols = policy_holidays(policy)
    taken = set(office_days) | set(pto_days)
    return [d for d in workdays_between(policy.start, policy.end, hols) if d > today and d not in taken]


@dataclass(frozen=True)
class CheckedPlan:
    plan: PtoPlan
    rejected: list  # proposed dates that are not free future workdays, or over budget
    short_months: list  # (MonthSummary before, extra days short) for months the plan makes impossible


def check_pto(policy: Policy, office_days, pto_days, today: date, proposed, budget: int) -> CheckedPlan:
    """Check PTO dates that came from somewhere else (a person, a model).

    Keeps only free future workdays, at most `budget` of them, and reports
    which months the plan would leave without enough free days to meet the
    policy. The numbers always come from summarize, never from the proposer.
    """
    allowed = set(free_days(policy, office_days, pto_days, today))
    keep, rejected = [], []
    for d in sorted(set(proposed)):
        if d in allowed and len(keep) < max(0, budget):
            keep.append(d)
        else:
            rejected.append(d)
    before = summarize(policy, office_days, pto_days, today)
    plan = _build_plan(policy, office_days, pto_days, today, keep, budget, before)
    after = summarize(policy, office_days, set(pto_days) | set(keep), today)
    short = [
        (b, a.shortfall - b.shortfall)
        for b, a in zip(before.months, after.months)
        if a.shortfall > b.shortfall
    ]
    return CheckedPlan(plan=plan, rejected=rejected, short_months=short)


# ------------------------------------------------------------- saved state


def dump_state(policy: Policy, office_days, pto_days, sick_days=(), other_days=(), ui=None) -> str:
    return json.dumps(
        {
            "v": STATE_VERSION,
            "policy": {
                "start": policy.start.isoformat(),
                "end": policy.end.isoformat(),
                "percent": policy.percent,
                "pto_mode": policy.pto_mode,
                "christmas_break": policy.christmas_break,
                "pto_allowance": policy.pto_allowance,
                "holidays": (
                    None if policy.custom_holidays is None
                    else [[d.isoformat(), name] for d, name in sorted(policy.custom_holidays)]
                ),
            },
            "office": sorted(d.isoformat() for d in office_days),
            "pto": sorted(d.isoformat() for d in pto_days),
            "sick": sorted(d.isoformat() for d in sick_days),
            "other": sorted(d.isoformat() for d in other_days),
            "ui": ui or {},
        },
        separators=(",", ":"),
    )


def _dates(items) -> set[date]:
    out = set()
    for item in items if isinstance(items, list) else []:
        try:
            out.add(date.fromisoformat(item))
        except (TypeError, ValueError):
            continue
    return out


def _holiday_pairs(items):
    if not isinstance(items, list):
        return None
    out = {}
    for item in items:
        try:
            out[date.fromisoformat(item[0])] = str(item[1])[:80]
        except (TypeError, ValueError, IndexError):
            continue
    return tuple(sorted(out.items()))


def load_state(raw, today: date):
    """Read saved state. Anything unreadable falls back to the defaults.

    Returns a dict: policy, office, pto, sick, other (sets of dates) and ui.
    """
    base = default_policy(today)
    try:
        data = json.loads(raw) if isinstance(raw, str) else raw
        if not isinstance(data, dict):
            raise ValueError
    except (TypeError, ValueError):
        return {"policy": base, "office": set(), "pto": set(), "sick": set(), "other": set(), "ui": {}}
    p = data.get("policy")
    if not isinstance(p, dict):
        p = {}
    try:
        policy = Policy(
            start=date.fromisoformat(p.get("start", base.start.isoformat())),
            end=date.fromisoformat(p.get("end", base.end.isoformat())),
            percent=float(p.get("percent", base.percent)),
            pto_mode=p.get("pto_mode", base.pto_mode),
            christmas_break=bool(p.get("christmas_break", base.christmas_break)),
            pto_allowance=int(p.get("pto_allowance", base.pto_allowance)),
            custom_holidays=_holiday_pairs(p.get("holidays")),
        )
    except (TypeError, ValueError):
        policy = base
    pto = _dates(data.get("pto"))
    sick = _dates(data.get("sick")) - pto
    other = _dates(data.get("other")) - pto - sick
    office = _dates(data.get("office")) - pto - sick - other
    ui = data.get("ui") if isinstance(data.get("ui"), dict) else {}
    return {"policy": policy, "office": office, "pto": pto, "sick": sick, "other": other, "ui": ui}
