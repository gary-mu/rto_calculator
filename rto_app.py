"""RTO calculator: how many days you need in the office, how many you have
done, and where to put PTO. The sums live in rto_logic.py."""

from __future__ import annotations

import calendar
from datetime import date
from html import escape
from pathlib import Path

import streamlit as st
import streamlit.components.v1 as components

import rto_logic as rl

ROOT = Path(__file__).parent
MODE_LABELS = {
    rl.PTO_SUBTRACT: "PTO subtracted from workdays",
    rl.PTO_AS_OFFICE: "PTO as a day in office",
}
MARK_OFFICE, MARK_PTO = "In office", "PTO"

st.set_page_config(page_title="RTO calculator", page_icon=":material/calendar_month:", layout="wide")

day_store = components.declare_component("day_store", path=str(ROOT / "components" / "day_store"))
ss = st.session_state


# ------------------------------------------------------------------ helpers


def load_css() -> str:
    app = (ROOT / "theme" / "app.css").read_text()
    head, _, body = app.partition("/* --- app --- */")
    tokens = (ROOT / "theme" / "tokens.css").read_text()
    base = (ROOT / "theme" / "base.css").read_text()
    return f"{head}\n{tokens}\n{base}\n{body}"


def html(markup: str):
    st.html(markup)


def fmt_day(d: date) -> str:
    return f"{d:%a, %b} {d.day}"


def fmt_month(d: date) -> str:
    return f"{d:%B %Y}"


def plural(n: int, word: str) -> str:
    return f"{n} {word}" if n == 1 else f"{n} {word}s"


def apply_state(policy: rl.Policy, office: set, pto: set):
    """Put a policy and its days into the session, widgets included."""
    ss.office, ss.pto = set(office), set(pto)
    ss.p_start, ss.p_end = policy.start, policy.end
    ss.workdays_percentage = float(policy.percent)
    ss.pto_accounting_policy = MODE_LABELS[policy.pto_mode]
    ss.extended_christmas_break = policy.christmas_break
    ss.pto_allowance = int(policy.pto_allowance)
    ss.valid_policy = policy


def current_policy() -> rl.Policy:
    """The policy in the sidebar; the last valid one if the dates are wrong."""
    try:
        policy = rl.Policy(
            start=ss.p_start,
            end=ss.p_end,
            percent=float(ss.workdays_percentage),
            pto_mode=next(k for k, v in MODE_LABELS.items() if v == ss.pto_accounting_policy),
            christmas_break=bool(ss.extended_christmas_break),
            pto_allowance=int(ss.pto_allowance),
        )
    except (ValueError, TypeError, StopIteration):
        ss.policy_error = True
        return ss.valid_policy
    ss.policy_error = False
    ss.valid_policy = policy
    return policy


# ---------------------------------------------------------------- callbacks


def toggle_day(d: date):
    mine, other = (ss.office, ss.pto) if ss.get("mark_mode") != MARK_PTO else (ss.pto, ss.office)
    if d in mine:
        mine.discard(d)
    else:
        mine.add(d)
        other.discard(d)


def log_today(d: date):
    ss.office.add(d)
    ss.pto.discard(d)


def undo_today(d: date):
    ss.office.discard(d)


def shift_month(step: int):
    y, m = ss.view_month.year, ss.view_month.month + step
    ss.view_month = date(y + (m - 1) // 12, (m - 1) % 12 + 1, 1)


def add_plan(dates):
    ss.pto.update(dates)
    ss.office.difference_update(dates)


def restore_backup():
    upload = ss.get("backup_file")
    if upload is None:
        return
    policy, office, pto = rl.load_state(upload.getvalue().decode("utf-8", "replace"), ss.today)
    apply_state(policy, office, pto)
    ss.restored = True


def clear_days():
    ss.office, ss.pto = set(), set()
    ss.confirm_clear = False


# ------------------------------------------------------------------- start

html(f"<style>{load_css()}</style>")

# The saved state round trip. Callbacks have already run, so the session
# holds the newest state and it can be handed to the browser right here.
payload = None
if ss.get("hydrated"):
    payload = rl.dump_state(current_policy(), ss.office, ss.pto)
with st.container(key="store"):
    saved = day_store(save=payload, key="day_store", default=None)

if not ss.get("hydrated"):
    if saved is None and not ss.get("skip_saved"):
        html(
            '<div class="loading" role="status"><p class="wordmark">RTO calculator</p>'
            "<p>Looking for the days you saved in this browser…</p></div>"
        )
        st.button("Start without them", key="skip_saved_btn", on_click=lambda: ss.update(skip_saved=True))
        st.stop()
    try:
        ss.today = date.fromisoformat((saved or {}).get("today", ""))
    except ValueError:
        ss.today = date.today()
    apply_state(*rl.load_state((saved or {}).get("raw"), ss.today))
    ss.first_visit = not (saved or {}).get("raw")
    ss.hydrated = True
    st.rerun()

today: date = ss.today

# ----------------------------------------------------------------- sidebar

with st.sidebar:
    html('<p class="wordmark">RTO calculator</p>')
    st.header("Your policy")
    st.date_input("Start Date", key="p_start")
    st.date_input("End Date", key="p_end")
    st.number_input(
        "% of workdays required in office",
        min_value=0.0, max_value=100.0, step=1.0, key="workdays_percentage",
        help="The share of each month's workdays you are required to be in the office. "
        "The result is rounded down, month by month.",
    )
    st.radio(
        "Choose how PTO is accounted for",
        list(MODE_LABELS.values()),
        key="pto_accounting_policy",
        help="Subtracted from workdays: a PTO day shrinks the month before the percentage is applied. "
        "As a day in office: the month is not changed, and a PTO day counts as a day in.",
    )
    st.checkbox("Holiday between Christmas and New Year?", key="extended_christmas_break")
    st.number_input(
        "PTO allowance",
        min_value=0, max_value=60, step=1, key="pto_allowance",
        help="Total PTO days for the period, carry-over included.",
    )

    policy = current_policy()
    if ss.get("policy_error"):
        st.error("The end date is before the start date. Showing the last period that worked.")

    st.header("Your data")
    st.caption(
        "Your policy and days are saved in this browser only. "
        "Nothing is sent to a server, and another browser or device starts empty."
    )
    st.download_button(
        "Download a backup",
        data=rl.dump_state(policy, ss.office, ss.pto),
        file_name="rto-days.json", mime="application/json", width="stretch",
    )
    st.file_uploader("Restore a backup", type=["json"], key="backup_file", on_change=restore_backup)
    if ss.get("confirm_clear"):
        st.warning("This removes every office day and PTO day you have marked.")
        b1, b2 = st.columns(2)
        b1.button("Yes, clear", on_click=clear_days, width="stretch")
        b2.button("Keep them", on_click=lambda: ss.update(confirm_clear=False), width="stretch")
    else:
        st.button(
            "Clear my days", on_click=lambda: ss.update(confirm_clear=True), width="stretch",
            disabled=not (ss.office or ss.pto),
        )

summary = rl.summarize(policy, ss.office, ss.pto, today)
holidays = rl.company_holidays(policy.start, policy.end, policy.christmas_break)
workday_set = set(rl.workdays_between(policy.start, policy.end, holidays))
in_period = policy.start <= today <= policy.end

# ------------------------------------------------------------------ header

cur = summary.current
if cur is None:
    head = "Today is outside your period"
    sub = f"The period runs {fmt_day(policy.start)}, {policy.start.year} to {fmt_day(policy.end)}, {policy.end.year}."
elif cur.required == 0:
    head = f"No office days needed in {cur.first:%B}"
    sub = f"{plural(cur.workdays, 'workday')} this month, {cur.pto} on PTO."
elif cur.remaining == 0:
    head = f"{cur.first:%B} is covered"
    sub = f"{cur.attended} of {cur.required} office days logged."
elif cur.shortfall:
    head = f"{cur.first:%B} needs {plural(cur.remaining, 'more day')}"
    sub = (
        f"{cur.attended} of {cur.required} logged, and only "
        f"{plural(cur.left, 'free workday')} left this month."
    )
else:
    head = f"{plural(cur.remaining, 'more office day')} in {cur.first:%B}"
    sub = f"{cur.attended} of {cur.required} logged, {plural(cur.left, 'free workday')} left to pick from."

top_l, top_r = st.columns([5, 2], vertical_alignment="bottom")
with top_l:
    html(
        f"<h1>{escape(head)}</h1><p class=\"lead\">{escape(sub)}</p>"
    )
with top_r:
    with st.container(key="today_action"):
        if today in ss.office:
            st.button("Undo today's log", on_click=undo_today, args=(today,), width="stretch")
        else:
            st.button(
                "I'm in today", type="primary", on_click=log_today, args=(today,), width="stretch",
                disabled=today not in workday_set,
                help=None if today in workday_set else "Today is not a workday in your period.",
            )

pto_note = f"of {policy.pto_allowance} allowed"
ahead = [m for m in summary.months if not m.is_past]
still_note = f"from {ahead[0].first:%B} on" if ahead and ahead[0].first > policy.start else "in this period"
if not ahead:
    still_note = "the period has ended"
stats = [
    ("Required this period", summary.required, f"{policy.percent:g}% of {summary.workdays} workdays, by month"),
    ("Been in", summary.attended, "days you have logged"),
    ("Still to go", summary.remaining_ahead, still_note),
    ("PTO placed", summary.pto, pto_note),
]
html(
    '<dl class="stats">'
    + "".join(
        f'<div><dt>{escape(label)}</dt><dd class="num">{value}</dd><dd class="note">{escape(note)}</dd></div>'
        for label, value, note in stats
    )
    + "</dl>"
)
if summary.pto > policy.pto_allowance:
    st.warning(
        f"You have placed {summary.pto} PTO days, "
        f"{summary.pto - policy.pto_allowance} more than your allowance of {policy.pto_allowance}."
    )
if ss.pop("restored", False):
    st.success("Backup restored.")

track_tab, plan_tab, month_tab, holiday_tab = st.tabs(["Track", "Plan PTO", "By month", "Company Holidays"])

# ------------------------------------------------------------------- track

with track_tab:
    first_month = policy.start.replace(day=1)
    last_month = policy.end.replace(day=1)
    if "view_month" not in ss:
        ss.view_month = today.replace(day=1)
    ss.view_month = min(max(ss.view_month, first_month), last_month)
    vm: date = ss.view_month
    msum = next(m for m in summary.months if m.key == rl.month_key(vm))

    if "mark_mode" not in ss or ss.mark_mode is None:
        ss.mark_mode = MARK_OFFICE
    bar_l, bar_r = st.columns([3, 2], vertical_alignment="bottom")
    with bar_l, st.container(key="monthnav"):
        n1, n2, n3 = st.columns([1, 5, 1], vertical_alignment="center")
        n1.button(
            "", icon=":material/chevron_left:", key="prev_month", on_click=shift_month, args=(-1,),
            disabled=vm <= first_month, help="Previous month", width="stretch",
        )
        with n2:
            html(
                f'<h2 class="month">{fmt_month(vm)}</h2>'
                f'<p class="month-note">{msum.attended} of {msum.required} office days, {msum.pto} PTO</p>'
            )
        n3.button(
            "", icon=":material/chevron_right:", key="next_month", on_click=shift_month, args=(1,),
            disabled=vm >= last_month, help="Next month", width="stretch",
        )
    with bar_r:
        st.segmented_control(
            "Tap a day to mark it as", [MARK_OFFICE, MARK_PTO], key="mark_mode", width="stretch",
        )

    with st.container(key="tray"):
        html(
            '<div class="tray-head" aria-hidden="true">'
            + "".join(f"<span>{d}</span>" for d in ("Mon", "Tue", "Wed", "Thu", "Fri"))
            + "</div>"
        )
        for week in calendar.Calendar(firstweekday=0).monthdatescalendar(vm.year, vm.month):
            days = [d for d in week[:5]]
            if not any(d.month == vm.month for d in days):
                continue
            cols = st.columns(5, gap="small")
            for col, d in zip(cols, days):
                with col:
                    if d.month != vm.month or not (policy.start <= d <= policy.end):
                        html('<div class="day-gap"></div>')
                        continue
                    tag = f"w{d.weekday()}" + ("-now" if d == today else "")
                    iso = d.isoformat()
                    if d in holidays:
                        st.button(
                            str(d.day), key=f"day-hol-{tag}-{iso}", disabled=True, width="stretch",
                            help=holidays[d], icon=":material/celebration:",
                        )
                    elif d in ss.pto:
                        st.button(
                            str(d.day), key=f"day-pto-{tag}-{iso}", icon=":material/beach_access:",
                            on_click=toggle_day, args=(d,), width="stretch",
                        )
                    elif d in ss.office:
                        st.button(
                            str(d.day), key=f"day-in-{tag}-{iso}", icon=":material/check:",
                            on_click=toggle_day, args=(d,), width="stretch",
                        )
                    else:
                        st.button(
                            str(d.day), key=f"day-free-{tag}-{iso}",
                            on_click=toggle_day, args=(d,), width="stretch",
                        )

    html(
        '<ul class="legend">'
        '<li><span class="key key-in"></span>In office</li>'
        '<li><span class="key key-pto"></span>PTO</li>'
        '<li><span class="key key-hol"></span>Company holiday</li>'
        '<li><span class="key key-now"></span>Today</li>'
        "</ul>"
    )
    if ss.get("first_visit") and not (ss.office or ss.pto):
        st.caption(
            "Nothing logged yet. Tap the days you were in the office, "
            "or switch to PTO and tap the days you are taking off."
        )

# -------------------------------------------------------------------- plan

with plan_tab:
    left_pto = max(0, policy.pto_allowance - summary.pto)
    if left_pto == 0:
        html(
            "<h2>No PTO days left to place</h2>"
            f'<p class="lead">All {policy.pto_allowance} days of your allowance are on the calendar. '
            "Raise the allowance in the sidebar, or clear a PTO day on the Track tab.</p>"
        )
    else:
        html(
            "<h2>Where to put your PTO</h2>"
            '<p class="lead">Each day goes where it cuts the most office days, '
            "then where it buys the longest stretch off.</p>"
        )
        p1, p2, _ = st.columns([2, 2, 3])
        budget = p1.number_input(
            "PTO days to place", min_value=1, max_value=left_pto, value=left_pto, step=1,
            help=f"You have {left_pto} of {policy.pto_allowance} PTO days not yet on the calendar.",
        )
        cap = p2.number_input(
            "Most PTO days in one break", min_value=1, max_value=10, value=4, step=1, key="plan_cap",
            help="Keeps the plan from spending a whole week of PTO in one go. Raise it for longer trips.",
        )
        plan = rl.plan_pto(policy, ss.office, ss.pto, today, int(budget), int(cap))
        if not plan.dates:
            st.info("There are no free workdays left in the period to place PTO on.")
        else:
            n = len(plan.dates)
            if plan.office_days_saved:
                line = (
                    f"{plural(n, 'PTO day')} would take your office days still to go "
                    f"from {plan.remaining_before} to {plan.remaining_after}."
                )
            else:
                line = (
                    f"{plural(n, 'PTO day')} would not lower the requirement, "
                    "but each one stretches a weekend or a holiday."
                )
            rows = "".join(
                "<tr>"
                f"<td>{fmt_day(b.start)} to {fmt_day(b.end)}</td>"
                f'<td class="num">{b.days_off}</td>'
                f"<td>{', '.join(fmt_day(d) for d in b.pto_dates)}</td>"
                "</tr>"
                for b in plan.breaks
            )
            html(
                f'<p class="plan-line">{escape(line)}</p>'
                '<table class="sheet"><thead><tr><th>Time off</th>'
                '<th class="num">Days off in a row</th><th>PTO days to book</th></tr></thead>'
                f"<tbody>{rows}</tbody></table>"
            )
            if n < budget:
                st.caption(
                    f"Only {n} of the {budget} days fit: the rest would break the cap on one break "
                    "or leave a month without enough free days to meet the policy."
                )
            st.button(
                f"Add {plural(n, 'day')} to my PTO", on_click=add_plan, args=(plan.dates,), key="add_plan",
            )

# ---------------------------------------------------------------- by month

with month_tab:
    rows = []
    for m in summary.months:
        done = min(m.attended, m.required)
        pct = 100 if m.required == 0 else round(100 * done / m.required)
        if m.required == 0:
            state = "None needed"
        elif m.remaining == 0:
            state = "Covered"
        elif m.is_past:
            state = f"{m.remaining} not logged"
        elif m.shortfall:
            state = f"{m.remaining} to go, {m.left} free"
        else:
            state = f"{m.remaining} to go"
        rows.append(
            f'<tr class="{"is-now" if m.is_current else ""}">'
            f"<th scope=\"row\">{m.first:%b %Y}</th>"
            f'<td class="num">{m.workdays}</td><td class="num">{m.pto}</td>'
            f'<td class="num">{m.required}</td><td class="num">{m.attended}</td>'
            f'<td><span class="meter" role="img" aria-label="{done} of {m.required} office days">'
            f'<span style="inline-size:{pct}%"></span></span></td>'
            f"<td>{state}</td></tr>"
        )
    html(
        '<table class="sheet"><thead><tr><th>Month</th><th class="num">Workdays</th>'
        '<th class="num">PTO</th><th class="num">Required</th><th class="num">Been in</th>'
        "<th>Progress</th><th>Status</th></tr></thead>"
        f"<tbody>{''.join(rows)}</tbody>"
        f'<tfoot><tr><th scope="row">Period</th><td class="num">{summary.workdays}</td>'
        f'<td class="num">{summary.pto}</td><td class="num">{summary.required}</td>'
        f'<td class="num">{summary.attended}</td><td></td><td>{summary.remaining_ahead} to go</td></tr></tfoot>'
        "</table>"
    )

# ---------------------------------------------------------------- holidays

with holiday_tab:
    if not holidays:
        st.info("No company holidays fall inside this period.")
    else:
        html(
            '<table class="sheet"><thead><tr><th>Date</th><th>Holiday Name</th></tr></thead><tbody>'
            + "".join(
                f"<tr><td>{fmt_day(d)}, {d.year}</td><td>{escape(name)}</td></tr>"
                for d, name in holidays.items()
            )
            + "</tbody></table>"
        )
