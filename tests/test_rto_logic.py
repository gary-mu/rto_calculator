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
        (22, 0, 60, PTO_SUBTRACT, 13),  # 13.2 rounds down
        (22, 10, 60, PTO_SUBTRACT, 7),  # (22 - 10) * 0.6 = 7.2
        (22, 10, 60, PTO_AS_OFFICE, 3),  # 13 - 10
        (20, 0, 60, PTO_SUBTRACT, 12),
        (15, 0, 60, PTO_SUBTRACT, 9),  # 9.000000000000002 in floats
        (100, 0, 57, PTO_SUBTRACT, 57),  # 56.99999999999999 in floats
        (20, 0, 0, PTO_SUBTRACT, 0),
        (20, 0, 100, PTO_SUBTRACT, 20),
        (20, 25, 60, PTO_SUBTRACT, 0),  # more PTO than workdays
        (20, 15, 60, PTO_AS_OFFICE, 0),  # never negative
        (21, 0, 50, PTO_SUBTRACT, 10),  # 10.5 rounds down
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


def test_2026_totals_match_the_original_app():
    """The live app showed 244 workdays and 142 required days for 2026 at 60%."""
    s = rl.summarize(Y2026, set(), set(), JAN1)
    assert s.workdays == 244
    assert s.required == 142
    assert s.remaining == 142
    assert len(s.months) == 12


def test_partial_months_are_clipped_to_the_period():
    p = Policy(start=date(2026, 3, 16), end=date(2026, 4, 10))
    s = rl.summarize(p, set(), set(), p.start)
    assert [m.key for m in s.months] == ["2026-03", "2026-04"]
    assert s.months[0].workdays == 12  # Mar 16 to Mar 31
    assert s.months[1].workdays == 8  # Apr 1 to Apr 10
    assert s.required == 7 + 4


# ---------------------------------------------------- tracking and remaining


def march(*days):
    return {date(2026, 3, d) for d in days}


def test_remaining_days_after_logging():
    # March 2026 has 22 workdays, so 13 are required at 60%.
    s = rl.summarize(Y2026, march(2, 3, 4), set(), date(2026, 3, 9))
    m = next(x for x in s.months if x.key == "2026-03")
    assert (m.workdays, m.required, m.attended, m.remaining) == (22, 13, 3, 10)
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
    assert s.counted == 13
    assert s.remaining == 142 - 13


def test_shortfall_when_the_month_can_no_longer_be_met():
    # Mar 26 onward leaves 4 workdays; 13 required, 2 logged.
    s = rl.summarize(Y2026, march(2, 3), set(), date(2026, 3, 26))
    m = next(x for x in s.months if x.key == "2026-03")
    assert (m.remaining, m.left, m.shortfall) == (11, 4, 7)
    feb = next(x for x in s.months if x.key == "2026-02")
    assert feb.is_past and feb.left == 0 and feb.shortfall == feb.required


def test_still_to_go_leaves_out_closed_months():
    s = rl.summarize(Y2026, march(2, 3), set(), date(2026, 3, 9))
    jan_feb = sum(m.required for m in s.months if m.key < "2026-03")
    assert s.remaining == 142 - 2
    assert s.remaining_ahead == 142 - 2 - jan_feb


def test_plan_counts_savings_from_the_current_month_on():
    today = date(2026, 11, 10)
    plan = rl.plan_pto(Y2026, set(), set(), today, 4)
    before = rl.summarize(Y2026, set(), set(), today)
    assert plan.remaining_before == before.remaining_ahead == 10 + 10
    assert plan.remaining_after < plan.remaining_before


def test_pto_subtracted_from_workdays():
    pto = march(16, 17, 18, 19, 20)
    s = rl.summarize(Y2026, set(), pto, JAN1)
    m = next(x for x in s.months if x.key == "2026-03")
    assert (m.pto, m.required) == (5, 10)  # (22 - 5) * 0.6 = 10.2


def test_pto_as_a_day_in_office():
    p = Policy(start=Y2026.start, end=Y2026.end, pto_mode=PTO_AS_OFFICE)
    s = rl.summarize(p, set(), march(16, 17, 18, 19, 20), JAN1)
    m = next(x for x in s.months if x.key == "2026-03")
    assert (m.pto, m.required) == (5, 8)  # 13 - 5


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
    # Mar 23: 7 workdays left, 13 required, 7 logged, so 6 more are needed.
    logged = march(2, 3, 4, 5, 6, 9, 10)
    today = date(2026, 3, 22)
    p = Policy(start=date(2026, 3, 1), end=date(2026, 3, 31))
    plan = rl.plan_pto(p, logged, set(), today, 5)
    after = rl.summarize(p, logged, set(plan.dates), today)
    assert after.shortfall == 0
    # A fifth PTO day would leave 2 free days for 3 required ones.
    assert len(plan.dates) == 4


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
    assert m.required == rl.required_days(22, 3, 60, PTO_SUBTRACT) == 11
    assert (s.pto, s.sick) == (1, 2)
    same_as_pto = rl.summarize(Y2026, set(), march(16, 17, 20), JAN1)
    assert s.required == same_as_pto.required


def test_sick_days_as_days_in_office():
    p = Policy(start=Y2026.start, end=Y2026.end, pto_mode=PTO_AS_OFFICE)
    s = rl.summarize(p, march(2), set(), date(2026, 3, 9), march(3, 4))
    m = s.current
    assert m.required == 13 - 2 and m.remaining == 10
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
    # Mar 22: 7 free workdays left and 6 more office days needed.
    logged = march(2, 3, 4, 5, 6, 9, 10)
    p = Policy(start=date(2026, 3, 1), end=date(2026, 3, 31))
    dates = [date(2026, 3, d) for d in (23, 24, 25, 26, 27)]
    checked = rl.check_pto(p, logged, set(), date(2026, 3, 22), dates, 5)
    ((month, extra),) = checked.short_months
    assert month.key == "2026-03" and extra == 1


# -------------------------------------------------------------- saved state


def test_state_round_trip():
    p = Policy(
        start=date(2026, 1, 1), end=date(2026, 6, 30), percent=50.0,
        pto_mode=PTO_AS_OFFICE, christmas_break=False, pto_allowance=15,
    )
    raw = rl.dump_state(p, march(2, 3), march(20))
    policy, office, pto, sick = rl.load_state(raw, date(2026, 3, 1))
    assert policy == p and office == march(2, 3) and pto == march(20) and sick == set()
    raw = rl.dump_state(p, march(2, 3), march(20), march(4))
    assert rl.load_state(raw, date(2026, 3, 1))[3] == march(4)


@pytest.mark.parametrize("raw", [None, "", "not json", "[1,2]", '{"policy": 4}'])
def test_unreadable_state_falls_back_to_defaults(raw):
    policy, office, pto, sick = rl.load_state(raw, date(2026, 3, 1))
    assert policy == rl.default_policy(date(2026, 3, 1))
    assert office == set() and pto == set() and sick == set()


def test_bad_entries_in_saved_state_are_dropped():
    raw = '{"v":1,"policy":{"start":"2026-05-01","end":"2026-01-01"},"office":["2026-03-02","2026-03-03","x",5],"pto":["2026-03-02"],"sick":["2026-03-02","2026-03-03"]}'
    policy, office, pto, sick = rl.load_state(raw, date(2026, 3, 1))
    assert policy == rl.default_policy(date(2026, 3, 1))  # end before start
    assert pto == march(2) and sick == march(3) and office == set()  # time off wins a clash
