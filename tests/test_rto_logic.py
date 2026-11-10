from datetime import date, timedelta

import pytest

import rto_logic as rl
from rto_logic import PTO_AS_OFFICE, PTO_SUBTRACT, Policy

Y2026 = Policy(start=date(2026, 1, 1), end=date(2026, 12, 31))
JAN1 = date(2026, 1, 1)


# ------------------------------------------------------------ required days


@pytest.mark.parametrize(
    "workdays, pto, percent, mode, expected",
    [
        (22, 0, 60, PTO_SUBTRACT, 14),  # 13.2 rounds up
        (21, 0, 60, PTO_SUBTRACT, 13),  # 12.6 rounds up
        (22, 10, 60, PTO_SUBTRACT, 8),  # (22 - 10) * 0.6 = 7.2
        (22, 10, 60, PTO_AS_OFFICE, 4),  # 14 - 10
        (20, 0, 60, PTO_SUBTRACT, 12),
        (15, 0, 60, PTO_SUBTRACT, 9),  # 9.000000000000002 in floats, which would round up to 10
        (100, 0, 57, PTO_SUBTRACT, 57),  # 56.99999999999999 in floats
        (20, 0, 0, PTO_SUBTRACT, 0),
        (20, 0, 100, PTO_SUBTRACT, 20),
        (20, 25, 60, PTO_SUBTRACT, 0),  # more PTO than workdays
        (20, 15, 60, PTO_AS_OFFICE, 0),  # never negative
        (21, 0, 50, PTO_SUBTRACT, 11),  # 10.5 rounds up
    ],
)
def test_required_days(workdays, pto, percent, mode, expected):
    assert rl.required_days(workdays, pto, percent, mode) == expected


def test_policy_rejects_bad_input():
    with pytest.raises(ValueError):
        Policy(start=date(2026, 2, 1), end=date(2026, 1, 1))
    with pytest.raises(ValueError):
        Policy(start=JAN1, end=date(2026, 2, 1), percent=120)
    with pytest.raises(ValueError):
        Policy(start=JAN1, end=date(2026, 2, 1), pto_mode="nope")


# ---------------------------------------------------------------- holidays


def test_holidays_2026_with_christmas_break():
    hols = rl.company_holidays(Y2026.start, Y2026.end, True)
    assert hols[date(2026, 11, 26)].startswith("Thanksgiving")
    assert hols[date(2026, 11, 27)] == "Day After Thanksgiving"
    for day in (24, 28, 29, 30, 31):
        assert hols[date(2026, 12, day)] == "Christmas Break"
    assert "Christmas Break" not in hols[date(2026, 12, 25)]
    assert date(2026, 12, 26) not in hols  # a Saturday


def test_holidays_without_christmas_break():
    hols = rl.company_holidays(Y2026.start, Y2026.end, False)
    assert date(2026, 12, 24) not in hols
    assert date(2026, 12, 25) in hols


def test_day_after_thanksgiving_in_every_year_of_the_period():
    hols = rl.company_holidays(date(2025, 7, 1), date(2026, 12, 31), True)
    assert hols[date(2025, 11, 28)] == "Day After Thanksgiving"
    assert hols[date(2026, 11, 27)] == "Day After Thanksgiving"


def test_2026_workdays_match_the_original_app_and_months_round_up():
    """The live app showed 244 workdays for 2026. It rounded each month down
    (142 days at 60%); each month now rounds up."""
    s = rl.summarize(Y2026, set(), set(), JAN1)
    assert s.workdays == 244
    assert [m.workdays for m in s.months] == [20, 19, 22, 22, 20, 21, 22, 21, 21, 21, 18, 17]
    assert [m.required for m in s.months] == [12, 12, 14, 14, 12, 13, 14, 13, 13, 13, 11, 11]
    assert s.required == s.total == 152
    assert s.remaining == 152
    assert len(s.months) == 12


def test_partial_months_are_clipped_to_the_period():
    p = Policy(start=date(2026, 3, 16), end=date(2026, 4, 10))
    s = rl.summarize(p, set(), set(), p.start)
    assert [m.key for m in s.months] == ["2026-03", "2026-04"]
    assert s.months[0].workdays == 12  # Mar 16 to Mar 31
    assert s.months[1].workdays == 8  # Apr 1 to Apr 10
    assert s.required == 8 + 5  # 7.2 and 4.8, rounded up


# ---------------------------------------------------- tracking and remaining


def march(*days):
    return {date(2026, 3, d) for d in days}


def test_remaining_days_after_logging():
    # March 2026 has 22 workdays, so 14 are required at 60%.
    s = rl.summarize(Y2026, march(2, 3, 4), set(), date(2026, 3, 9))
    m = next(x for x in s.months if x.key == "2026-03")
    assert (m.workdays, m.required, m.attended, m.remaining) == (22, 14, 3, 11)
    assert m.left == 17  # Mar 9 to Mar 31
    assert m.shortfall == 0
    assert m.is_current and s.current is m
    assert s.attended == 3


def test_weekend_holiday_and_out_of_period_logs_do_not_count():
    logged = {date(2026, 3, 7), date(2026, 1, 1), date(2027, 3, 1)} | march(2)
    s = rl.summarize(Y2026, logged, set(), date(2026, 3, 9))
    assert s.attended == 1


def test_extra_days_do_not_carry_into_another_month():
    every_day = {d for d in rl.daterange(date(2026, 3, 1), date(2026, 3, 31))}
    s = rl.summarize(Y2026, every_day, set(), date(2026, 4, 1))
    m = next(x for x in s.months if x.key == "2026-03")
    assert m.attended == 22 and m.remaining == 0
    assert s.counted == 14
    assert s.remaining == 152 - 14


def test_shortfall_when_the_month_can_no_longer_be_met():
    # Mar 26 onward leaves 4 workdays; 14 required, 2 logged.
    s = rl.summarize(Y2026, march(2, 3), set(), date(2026, 3, 26))
    m = next(x for x in s.months if x.key == "2026-03")
    assert (m.remaining, m.left, m.shortfall) == (12, 4, 8)
    feb = next(x for x in s.months if x.key == "2026-02")
    assert feb.is_past and feb.left == 0 and feb.shortfall == feb.required


def test_still_to_go_leaves_out_closed_months():
    s = rl.summarize(Y2026, march(2, 3), set(), date(2026, 3, 9))
    jan_feb = sum(m.required for m in s.months if m.key < "2026-03")
    assert s.remaining == 152 - 2
    assert s.remaining_ahead == 152 - 2 - jan_feb


def test_plan_counts_savings_from_the_current_month_on():
    today = date(2026, 11, 10)
    plan = rl.plan_pto(Y2026, set(), set(), today, 4)
    before = rl.summarize(Y2026, set(), set(), today)
    assert plan.remaining_before == before.remaining_ahead == 11 + 11
    assert plan.remaining_after < plan.remaining_before


def test_pto_subtracted_from_workdays():
    pto = march(16, 17, 18, 19, 20)
    s = rl.summarize(Y2026, set(), pto, JAN1)
    m = next(x for x in s.months if x.key == "2026-03")
    assert (m.pto, m.required) == (5, 11)  # (22 - 5) * 0.6 = 10.2


def test_pto_as_a_day_in_office():
    p = Policy(start=Y2026.start, end=Y2026.end, pto_mode=PTO_AS_OFFICE)
    s = rl.summarize(p, set(), march(16, 17, 18, 19, 20), JAN1)
    m = next(x for x in s.months if x.key == "2026-03")
    assert (m.pto, m.required) == (5, 9)  # 14 - 5


def test_a_day_marked_both_ways_counts_as_pto():
    s = rl.summarize(Y2026, march(2), march(2), JAN1)
    assert s.attended == 0 and s.pto == 1


# ------------------------------------------------------------- PTO planner


def test_no_budget_means_no_plan():
    plan = rl.plan_pto(Y2026, set(), set(), JAN1, 0)
    assert plan.dates == [] and plan.office_days_saved == 0


def test_one_day_bridges_a_holiday_to_the_weekend():
    # Juneteenth 2026 is a Friday and Independence Day is observed on Friday
    # Jul 3; in June the best single day is next to the Juneteenth weekend.
    p = Policy(start=date(2026, 6, 1), end=date(2026, 6, 30), pto_mode=PTO_AS_OFFICE)
    plan = rl.plan_pto(p, set(), set(), date(2026, 5, 31), 1)
    assert len(plan.dates) == 1
    (b,) = plan.breaks
    assert b.days_off == 4
    assert plan.dates[0] in (date(2026, 6, 18), date(2026, 6, 22))


def test_plan_spreads_into_long_weekends_before_stacking():
    p = Policy(start=date(2026, 3, 1), end=date(2026, 3, 31), pto_mode=PTO_AS_OFFICE)
    plan = rl.plan_pto(p, set(), set(), date(2026, 2, 28), 3)
    assert len(plan.dates) == 3
    assert all(d.weekday() in (0, 4) for d in plan.dates)  # Mondays or Fridays
    assert len(plan.breaks) == 3 and all(b.days_off == 3 for b in plan.breaks)


def test_plan_minimises_required_office_days():
    """With PTO taken out of workdays, where the days go changes the total."""
    plan = rl.plan_pto(Y2026, set(), set(), JAN1, 6)
    assert len(plan.dates) == 6
    # Brute force the best split of 6 days across months.
    base = rl.summarize(Y2026, set(), set(), JAN1)
    best = {0: 0}
    for m in base.months:
        nxt = {}
        for used, saved in best.items():
            for k in range(0, 7 - used):
                gain = m.required - rl.required_days(m.workdays - 0, k, 60, PTO_SUBTRACT)
                nxt[used + k] = max(nxt.get(used + k, -1), saved + gain)
        best = nxt
    assert plan.office_days_saved == max(best.values())
    assert plan.required_after == plan.required_before - plan.office_days_saved
    assert plan.office_days_saved >= 4


def test_pto_as_office_saves_one_office_day_per_pto_day():
    p = Policy(start=Y2026.start, end=Y2026.end, pto_mode=PTO_AS_OFFICE)
    plan = rl.plan_pto(p, set(), set(), JAN1, 5)
    assert plan.office_days_saved == 5


def test_plan_only_uses_free_future_workdays():
    today = date(2026, 6, 10)
    office = {date(2026, 6, 12)}
    pto = {date(2026, 7, 6)}
    plan = rl.plan_pto(Y2026, office, pto, today, 8)
    hols = rl.company_holidays(Y2026.start, Y2026.end, True)
    for d in plan.dates:
        assert d > today
        assert d.weekday() < 5 and d not in hols
        assert d not in office and d not in pto


def test_plan_respects_the_cap_on_pto_days_in_one_break():
    p = Policy(start=date(2026, 3, 1), end=date(2026, 3, 31), pto_mode=PTO_AS_OFFICE)
    plan = rl.plan_pto(p, set(), set(), date(2026, 2, 28), 12, max_pto_per_break=2)
    assert all(len(b.pto_dates) <= 2 for b in plan.breaks)
    # Existing PTO counts toward the cap as well.
    existing = {date(2026, 3, 9), date(2026, 3, 10)}
    plan = rl.plan_pto(p, set(), existing, date(2026, 2, 28), 12, max_pto_per_break=2)
    assert date(2026, 3, 6) not in plan.dates and date(2026, 3, 11) not in plan.dates


def test_plan_never_makes_a_month_impossible():
    # Mar 23: 7 workdays left, 14 required, 7 logged, so 7 more are needed.
    logged = march(2, 3, 4, 5, 6, 9, 10)
    today = date(2026, 3, 22)
    p = Policy(start=date(2026, 3, 1), end=date(2026, 3, 31))
    plan = rl.plan_pto(p, logged, set(), today, 5)
    after = rl.summarize(p, logged, set(plan.dates), today)
    assert after.shortfall == 0
    # A third PTO day would leave 4 free days for 5 required ones.
    assert len(plan.dates) == 2


def test_plan_stays_within_budget_and_the_policy_is_still_met():
    for mode in (PTO_SUBTRACT, PTO_AS_OFFICE):
        p = Policy(start=Y2026.start, end=Y2026.end, pto_mode=mode)
        plan = rl.plan_pto(p, set(), set(), JAN1, 20)
        assert len(plan.dates) <= 20 and len(set(plan.dates)) == len(plan.dates)
        after = rl.summarize(p, set(), set(plan.dates), JAN1)
        assert after.shortfall == 0
        assert after.remaining == plan.remaining_after
        assert plan.remaining_after < plan.remaining_before


def test_breaks_cover_every_suggested_day():
    plan = rl.plan_pto(Y2026, set(), set(), JAN1, 10)
    covered = [d for b in plan.breaks for d in b.pto_dates]
    assert sorted(covered) == plan.dates
    for b in plan.breaks:
        assert b.days_off == (b.end - b.start) / timedelta(days=1) + 1
        assert b.days_off > len(b.pto_dates)


# ---------------------------------------------------------------- sick days


def test_sick_days_count_like_pto_but_not_against_the_allowance():
    sick = march(16, 17)
    s = rl.summarize(Y2026, set(), march(20), JAN1, sick)
    m = next(x for x in s.months if x.key == "2026-03")
    assert (m.pto, m.sick) == (1, 2)
    assert m.required == rl.required_days(22, 3, 60, PTO_SUBTRACT) == 12
    assert (s.pto, s.sick) == (1, 2)
    same_as_pto = rl.summarize(Y2026, set(), march(16, 17, 20), JAN1)
    assert s.required == same_as_pto.required


def test_sick_days_as_days_in_office():
    p = Policy(start=Y2026.start, end=Y2026.end, pto_mode=PTO_AS_OFFICE)
    s = rl.summarize(p, march(2), set(), date(2026, 3, 9), march(3, 4))
    m = s.current
    assert m.required == 14 - 2 and m.remaining == 11
    assert m.share == pytest.approx(100 * 3 / 22)


def test_a_sick_day_is_not_a_free_day_and_beats_an_office_log():
    s = rl.summarize(Y2026, march(10), set(), date(2026, 3, 9), march(10, 11))
    m = s.current
    assert m.attended == 0 and m.sick == 2
    assert m.left == 17 - 2


# ------------------------------------------------- office share and checks


@pytest.mark.parametrize(
    "workdays, pto, attended, mode, expected",
    [
        (20, 0, 12, PTO_SUBTRACT, 60.0),
        (20, 5, 9, PTO_SUBTRACT, 60.0),  # 9 of the 15 days left after PTO
        (20, 5, 7, PTO_AS_OFFICE, 60.0),  # 7 logged + 5 PTO of 20
        (20, 0, 0, PTO_SUBTRACT, 0.0),
        (20, 20, 0, PTO_SUBTRACT, 0.0),  # nothing left to attend
        (10, 8, 9, PTO_AS_OFFICE, 100.0),  # capped
    ],
)
def test_office_share(workdays, pto, attended, mode, expected):
    assert rl.office_share(workdays, pto, attended, mode) == pytest.approx(expected)


def test_summary_carries_month_and_period_share():
    s = rl.summarize(Y2026, march(2, 3, 4, 5, 6, 9, 10, 11, 12, 13, 16), set(), date(2026, 3, 17))
    assert s.current.share == pytest.approx(50.0)  # 11 of 22
    assert s.share == pytest.approx(100 * 11 / 244)


def test_check_pto_keeps_only_free_future_workdays_within_budget():
    today = date(2026, 6, 10)
    proposed = [
        date(2026, 6, 9),  # past
        date(2026, 6, 13),  # Saturday
        date(2026, 6, 19),  # Juneteenth
        date(2026, 6, 12),  # logged in office
        date(2026, 7, 6),  # already PTO
        date(2026, 6, 18), date(2026, 6, 22), date(2026, 6, 23),
    ]
    checked = rl.check_pto(Y2026, {date(2026, 6, 12)}, {date(2026, 7, 6)}, today, proposed, 2)
    assert checked.plan.dates == [date(2026, 6, 18), date(2026, 6, 22)]
    assert len(checked.rejected) == 6
    assert checked.short_months == []
    (b,) = checked.plan.breaks
    assert (b.start, b.end, b.days_off) == (date(2026, 6, 18), date(2026, 6, 22), 5)


def test_check_pto_numbers_come_from_the_calculator():
    today = date(2026, 3, 1)
    dates = [date(2026, 3, d) for d in (16, 17, 18, 19, 20)]
    checked = rl.check_pto(Y2026, set(), set(), today, dates, 5)
    after = rl.summarize(Y2026, set(), set(dates), today)
    assert checked.plan.remaining_after == after.remaining_ahead
    assert checked.plan.office_days_saved == 3  # March goes from 13 to 10


def test_check_pto_flags_a_month_it_makes_impossible():
    # Mar 22: 7 free workdays left and 7 more office days needed.
    logged = march(2, 3, 4, 5, 6, 9, 10)
    p = Policy(start=date(2026, 3, 1), end=date(2026, 3, 31))
    dates = [date(2026, 3, d) for d in (23, 24, 25, 26, 27)]
    checked = rl.check_pto(p, logged, set(), date(2026, 3, 22), dates, 5)
    ((month, extra),) = checked.short_months
    assert month.key == "2026-03" and extra == 2  # 17 days at 60% is 11; 7 logged, 2 free days left


# -------------------------------------------------------------- saved state


def test_state_round_trip():
    p = Policy(
        start=date(2026, 1, 1), end=date(2026, 6, 30), percent=50.0,
        pto_mode=PTO_AS_OFFICE, christmas_break=False, pto_allowance=15,
        custom_holidays=((date(2026, 3, 17), "Founders Day"),),
        sick_mode=PTO_SUBTRACT, holiday_mode=PTO_AS_OFFICE,
    )
    raw = rl.dump_state(p, march(2, 3), march(20), march(4), march(5), {"theme": "garden", "mode": "dark"})
    got = rl.load_state(raw, date(2026, 3, 1))
    assert got["policy"] == p
    assert (got["office"], got["pto"], got["sick"], got["other"]) == (march(2, 3), march(20), march(4), march(5))
    assert got["ui"] == {"theme": "garden", "mode": "dark"}


@pytest.mark.parametrize("raw", [None, "", "not json", "[1,2]", '{"policy": 4}'])
def test_unreadable_state_falls_back_to_defaults(raw):
    got = rl.load_state(raw, date(2026, 3, 1))
    assert got["policy"] == rl.default_policy(date(2026, 3, 1))
    assert not (got["office"] or got["pto"] or got["sick"] or got["other"] or got["ui"])


def test_bad_entries_in_saved_state_are_dropped():
    raw = (
        '{"v":1,"policy":{"start":"2026-05-01","end":"2026-01-01"},'
        '"office":["2026-03-02","2026-03-03","2026-03-04","x",5],"pto":["2026-03-02"],'
        '"sick":["2026-03-02","2026-03-03"],"other":["2026-03-03","2026-03-04"],"ui":7}'
    )
    got = rl.load_state(raw, date(2026, 3, 1))
    assert got["policy"] == rl.default_policy(date(2026, 3, 1))  # end before start
    # time off wins a clash, in the order PTO, sick, other
    assert (got["pto"], got["sick"], got["other"], got["office"]) == (march(2), march(3), march(4), set())
    assert got["ui"] == {}


def test_state_saved_before_holidays_and_other_absence_still_loads():
    raw = '{"v":1,"policy":{"start":"2026-01-01","end":"2026-12-31"},"office":["2026-03-02"],"pto":[]}'
    got = rl.load_state(raw, date(2026, 3, 1))
    assert got["policy"].custom_holidays is None and got["office"] == march(2)


# ------------------------------------- three settings for what counts as in

IN, OUT = PTO_AS_OFFICE, PTO_SUBTRACT


def policy_with(pto, sick, hol, **kw):
    return Policy(start=Y2026.start, end=Y2026.end, pto_mode=pto, sick_mode=sick, holiday_mode=hol, **kw)


@pytest.mark.parametrize(
    "pto, sick, hol, total, credit, expected",
    [
        # 20 workdays, 2 weekday holidays, 3 PTO, 1 sick or other, 60%
        (OUT, OUT, OUT, 10, 0, 10),  # 16 days, 9.6 rounds up to 10
        (IN, IN, IN, 14, 6, 8),      # 22 days, 13.2 rounds up to 14, less 2 + 3 + 1
        (IN, OUT, OUT, 12, 3, 9),    # 19 days, 11.4 rounds up to 12, less 3
        (OUT, IN, OUT, 11, 1, 10),   # 17 days, 10.2 rounds up to 11, less 1
        (OUT, OUT, IN, 11, 2, 9),    # 18 days, 10.8 rounds up to 11, less 2
    ],
)
def test_month_required_for_each_setting(pto, sick, hol, total, credit, expected):
    need, base, got_credit, got_total = rl.month_required(policy_with(pto, sick, hol), 20, 2, 3, 1)
    assert (got_total, got_credit, need) == (total, credit, expected)
    assert got_total == -(-base * 60 // 100)


def test_21_days_at_60_percent_is_13():
    assert rl.month_required(policy_with(IN, IN, IN), 18, 3, 0, 0) == (10, 21, 3, 13)
    assert rl.month_required(policy_with(OUT, OUT, OUT), 21, 0, 0, 0) == (13, 21, 0, 13)


def test_month_required_matches_the_two_original_rules():
    for w, p in [(22, 0), (22, 10), (20, 15), (15, 3)]:
        assert rl.month_required(policy_with(OUT, OUT, OUT), w, 2, p, 0)[0] == rl.required_days(w, p, 60, OUT)
        assert rl.month_required(policy_with(IN, IN, OUT), w, 2, p, 0)[0] == rl.required_days(w, p, 60, IN)


def test_month_required_is_never_negative():
    assert rl.month_required(policy_with(IN, IN, IN), 5, 10, 5, 5) == (0, 15, 20, 9)


def test_a_new_visitor_has_everything_counting_as_a_day_in():
    p = rl.default_policy(date(2026, 3, 1))
    assert (p.pto_mode, p.sick_rule, p.holiday_mode) == (IN, IN, IN)
    s = rl.summarize(p, set(), set(), JAN1)
    # November 2026: 21 weekdays, 3 of them holidays. 12.6 rounds up to 13; 3 are already counted.
    nov = next(m for m in s.months if m.key == "2026-11")
    assert (nov.workdays, nov.holidays, nov.base, nov.credit) == (18, 3, 21, 3)
    assert (nov.total, nov.required) == (13, 10)
    assert nov.share == pytest.approx(100 * 3 / 21)


def test_holidays_as_days_in_change_the_year():
    out = rl.summarize(policy_with(OUT, OUT, OUT), set(), set(), JAN1)
    held = rl.summarize(policy_with(OUT, OUT, IN), set(), set(), JAN1)
    assert out.required == 152 and out.workdays == held.workdays == 244
    assert held.base == 261 and held.credit == 17
    assert held.required == sum(-(-m.base * 60 // 100) - m.holidays for m in held.months)
    assert held.total == held.required + 17
    assert held.required < out.required


def test_sick_days_can_be_counted_differently_from_pto():
    p = policy_with(OUT, IN, OUT)
    s = rl.summarize(p, set(), march(20), JAN1, march(16), march(17))
    m = next(x for x in s.months if x.key == "2026-03")
    # 22 workdays: PTO out leaves 21, 12.6 rounds up to 13, less 2 sick or other.
    assert (m.base, m.credit, m.total, m.required) == (21, 2, 13, 11)


def test_sick_setting_defaults_to_the_pto_setting():
    assert Policy(start=JAN1, end=date(2026, 2, 1), pto_mode=IN).sick_rule == IN
    assert Policy(start=JAN1, end=date(2026, 2, 1)).sick_rule == OUT


def test_planner_uses_each_setting():
    today = date(2026, 2, 28)
    march_only = dict(start=date(2026, 3, 1), end=date(2026, 3, 31))
    # PTO as a day in: every PTO day saves one office day.
    p = Policy(pto_mode=IN, sick_mode=OUT, holiday_mode=OUT, **march_only)
    plan = rl.plan_pto(p, set(), set(), today, 4, sick_days=march(2))
    assert plan.office_days_saved == 4 and date(2026, 3, 2) not in plan.dates
    # PTO out of the workdays: 21 left after the sick day, 13 required; 4 PTO leave 17, 11 required.
    p = Policy(pto_mode=OUT, sick_mode=OUT, holiday_mode=OUT, **march_only)
    plan = rl.plan_pto(p, set(), set(), today, 4, sick_days=march(2))
    assert (plan.remaining_before, plan.remaining_after) == (13, 11)
    checked = rl.check_pto(p, set(), set(), today, [date(2026, 3, 2), date(2026, 3, 6)], 4, sick_days=march(2))
    assert checked.plan.dates == [date(2026, 3, 6)] and checked.rejected == [date(2026, 3, 2)]


def test_state_saved_under_the_old_rules_keeps_them():
    raw = '{"v":1,"policy":{"start":"2026-01-01","end":"2026-12-31","pto_mode":"office"},"office":[],"pto":[]}'
    p = rl.load_state(raw, date(2026, 3, 1))["policy"]
    assert (p.pto_mode, p.sick_rule, p.holiday_mode) == (IN, IN, OUT)
    raw = '{"v":1,"policy":{"start":"2026-01-01","end":"2026-12-31","pto_mode":"subtract"},"office":[],"pto":[]}'
    p = rl.load_state(raw, date(2026, 3, 1))["policy"]
    assert (p.pto_mode, p.sick_rule, p.holiday_mode) == (OUT, OUT, OUT)


# -------------------------------------------- other absence, own holidays


def test_other_absence_counts_like_sick_and_pto():
    s = rl.summarize(Y2026, set(), march(20), JAN1, march(16), march(17, 18))
    m = next(x for x in s.months if x.key == "2026-03")
    assert (m.pto, m.sick, m.other) == (1, 1, 2)
    assert m.required == rl.required_days(22, 4, 60, PTO_SUBTRACT)
    assert (s.pto, s.sick, s.other) == (1, 1, 2)


def test_own_holiday_list_replaces_the_built_in_one():
    own = ((date(2026, 3, 17), "Founders Day"), (date(2027, 1, 4), "Outside the period"))
    p = Policy(start=Y2026.start, end=Y2026.end, custom_holidays=own)
    assert rl.policy_holidays(p) == {date(2026, 3, 17): "Founders Day"}
    s = rl.summarize(p, set(), set(), JAN1)
    assert s.workdays == 261 - 1  # every weekday of 2026 but one
    m = next(x for x in s.months if x.key == "2026-03")
    assert (m.workdays, m.holidays) == (21, 1)
    assert rl.policy_holidays(Y2026) == rl.company_holidays(Y2026.start, Y2026.end, True)


def test_an_empty_own_list_means_no_holidays():
    p = Policy(start=Y2026.start, end=Y2026.end, custom_holidays=())
    assert rl.policy_holidays(p) == {}
    assert rl.summarize(p, set(), set(), JAN1).workdays == 261


def test_planner_bridges_an_own_holiday():
    own = ((date(2026, 3, 19), "Founders Day"),)  # a Thursday
    p = Policy(start=date(2026, 3, 1), end=date(2026, 3, 31), pto_mode=PTO_AS_OFFICE, custom_holidays=own)
    plan = rl.plan_pto(p, set(), set(), date(2026, 2, 28), 1)
    assert plan.dates == [date(2026, 3, 20)]
    assert plan.breaks[0].days_off == 4


def test_parse_holiday_csv():
    text = "Date,Holiday Name\n2026-07-03,Independence Day (observed)\n11/26/2026,Thanksgiving\n\nnot a date,x\n2026-12-25\n"
    found, bad = rl.parse_holiday_csv(text)
    assert found == {
        date(2026, 7, 3): "Independence Day (observed)",
        date(2026, 11, 26): "Thanksgiving",
        date(2026, 12, 25): "Company holiday",
    }
    assert bad == 1
