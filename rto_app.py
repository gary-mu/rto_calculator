"""RTO calculator: how many days you need in the office, how many you have
done, and where to put PTO. The sums live in rto_logic.py; the AI planner
in pto_ai.py only proposes dates; the look lives in themes.py and theme/."""

from __future__ import annotations

import calendar
import csv
import io
import os
from datetime import date
from html import escape
from pathlib import Path

import streamlit as st
import streamlit.components.v1 as components

import pto_ai
import rto_logic as rl
import themes

ROOT = Path(__file__).parent
MODE_LABELS = {
    rl.PTO_SUBTRACT: "PTO subtracted from workdays",
    rl.PTO_AS_OFFICE: "PTO as a day in office",
}
MARKS = ("in", "pto", "sick", "other")  # what the calendar's wheel can set
AI_CALLS_PER_VISIT = 5

st.set_page_config(page_title="RTO calculator", page_icon=":material/calendar_month:", layout="wide")

day_store = components.declare_component("day_store", path=str(ROOT / "components" / "day_store"))
month_tray = components.declare_component("month_tray", path=str(ROOT / "components" / "month_tray"))
ss = st.session_state


# ------------------------------------------------------------------ helpers


def _read(name: str) -> str:
    return (ROOT / "theme" / name).read_text()


def page_css(theme: str, mode: str) -> str:
    stamp, _, body = _read("app.css").partition("/* --- app --- */")
    return "\n".join(
        [stamp, themes.font_import(theme), themes.root_block(theme, mode), _read("tokens.css"), _read("base.css"), body]
    )


def tray_css(theme: str, mode: str) -> str:
    return "\n".join(
        [themes.font_import(theme), themes.root_block(theme, mode), _read("tokens.css"), _read("tray.css")]
    )


def html(markup: str):
    st.html(markup)


def fmt_day(d: date) -> str:
    return f"{d:%a, %b} {d.day}"


def fmt_month(d: date) -> str:
    return f"{d:%B %Y}"


def plural(n: int, word: str) -> str:
    return f"{n} {word}" if n == 1 else f"{n} {word}s"


def day_sets() -> dict:
    return {"in": ss.office, "pto": ss.pto, "sick": ss.sick, "other": ss.other}


def planner_key():
    """The AI planner's key, from Streamlit secrets or the environment."""
    for name in pto_ai.KEY_NAMES:
        try:
            key = st.secrets["general"][name]
        except Exception:  # no secrets file, or no such entry
            key = None
        key = key or os.environ.get(name)
        if key:
            return key
    return None


def pace_meter(label: str, share: float, done: int, base: int, target: float) -> str:
    """A progress bar toward the policy's percentage, with the threshold marked."""
    return (
        '<div class="pace">'
        f'<p class="pace-label"><strong class="num">{share:.0f}%</strong> in office {escape(label)}</p>'
        f'<span class="meter meter-lg" role="img" aria-label="{share:.0f} percent in office {escape(label)}, '
        f'the policy asks for {target:g} percent">'
        f'<span style="inline-size:{min(share, 100):.1f}%"></span>'
        f'<i style="inset-inline-start:{min(target, 100):.1f}%"></i></span>'
        f'<p class="pace-note">{done} of {plural(base, "workday")}, the policy asks for {target:g}%</p>'
        "</div>"
    )


def share_parts(workdays: int, pto: int, attended: int, mode: str):
    """(days that count as in office, the workdays they are measured against)."""
    if mode == rl.PTO_SUBTRACT:
        return attended, max(0, workdays - pto)
    return attended + pto, workdays


def plan_table(plan: rl.PtoPlan) -> str:
    rows = "".join(
        "<tr>"
        f"<td>{fmt_day(b.start)} to {fmt_day(b.end)}</td>"
        f'<td class="num">{b.days_off}</td>'
        f"<td>{', '.join(fmt_day(d) for d in b.pto_dates)}</td>"
        "</tr>"
        for b in plan.breaks
    )
    return (
        '<table class="sheet"><thead><tr><th>Time off</th>'
        '<th class="num">Days off in a row</th><th>PTO days to book</th></tr></thead>'
        f"<tbody>{rows}</tbody></table>"
    )


def plan_line(plan: rl.PtoPlan) -> str:
    n = len(plan.dates)
    if plan.office_days_saved:
        return (
            f"{plural(n, 'PTO day')} would take your office days still to go "
            f"from {plan.remaining_before} to {plan.remaining_after}."
        )
    return (
        f"{plural(n, 'PTO day')} would not lower the requirement, "
        "but each one stretches a weekend or a holiday."
    )


def apply_state(state: dict):
    """Put a saved state into the session, widgets included."""
    policy = state["policy"]
    ss.office, ss.pto = set(state["office"]), set(state["pto"])
    ss.sick, ss.other = set(state["sick"]), set(state["other"])
    ss.custom_hols = None if policy.custom_holidays is None else dict(policy.custom_holidays)
    ss.p_start, ss.p_end = policy.start, policy.end
    ss.workdays_percentage = float(policy.percent)
    ss.pto_accounting_policy = MODE_LABELS[policy.pto_mode]
    ss.extended_christmas_break = policy.christmas_break
    ss.pto_allowance = int(policy.pto_allowance)
    ss.valid_policy = policy
    ui = state.get("ui") or {}
    ss.ui_theme, ss.ui_mode = themes.normalise(ui.get("theme"), ui.get("mode"))


def current_policy() -> rl.Policy:
    """The policy in the sidebar; the last valid one if the dates are wrong."""
    custom = ss.get("custom_hols")
    try:
        policy = rl.Policy(
            start=ss.p_start,
            end=ss.p_end,
            percent=float(ss.workdays_percentage),
            pto_mode=next(k for k, v in MODE_LABELS.items() if v == ss.pto_accounting_policy),
            christmas_break=bool(ss.extended_christmas_break),
            pto_allowance=int(ss.pto_allowance),
            custom_holidays=None if custom is None else tuple(sorted(custom.items())),
        )
    except (ValueError, TypeError, StopIteration):
        ss.policy_error = True
        return ss.valid_policy
    ss.policy_error = False
    ss.valid_policy = policy
    return policy


def saved_payload() -> str:
    return rl.dump_state(
        current_policy(), ss.office, ss.pto, ss.sick, ss.other, {"theme": ss.ui_theme, "mode": ss.ui_mode}
    )


# ---------------------------------------------------------------- callbacks


def mark_day(d: date, mark: str):
    """Set a day to one mark, or clear it."""
    for days in day_sets().values():
        days.discard(d)
    if mark in MARKS:
        day_sets()[mark].add(d)


def shift_month(step: int):
    y, m = ss.view_month.year, ss.view_month.month + step
    ss.view_month = date(y + (m - 1) // 12, (m - 1) % 12 + 1, 1)


def add_plan(dates):
    for d in dates:
        mark_day(d, "pto")
    ss.ai_plan = None


def ask_ai(policy, today, budget, cap):
    ss.ai_error = None
    key = planner_key()
    if not key:
        return
    if ss.get("ai_calls", 0) >= AI_CALLS_PER_VISIT:
        ss.ai_error = f"That is {AI_CALLS_PER_VISIT} AI plans this visit, which is the limit. The quick plan still works."
        return
    ss.ai_calls = ss.get("ai_calls", 0) + 1
    away = ss.pto | ss.sick | ss.other
    context = pto_ai.build_context(policy, ss.office, away, today, budget, cap, ss.get("ai_wishes") or "")
    try:
        got = pto_ai.suggest(key, context)
    except pto_ai.PlannerError as e:
        ss.ai_error = str(e)
        return
    ss.ai_plan = {"dates": got.dates, "summary": got.summary, "breaks_note": got.breaks_note, "budget": budget}


def drop_ai_plan():
    ss.ai_plan = None
    ss.ai_error = None


def restore_backup():
    upload = ss.get("backup_file")
    if upload is None:
        return
    apply_state(rl.load_state(upload.getvalue().decode("utf-8", "replace"), ss.today))
    ss.restored = True


def clear_days():
    for days in day_sets().values():
        days.clear()
    ss.confirm_clear = False


def own_holidays() -> dict:
    """The person's own list, started from the built-in one the first time it is edited."""
    if ss.get("custom_hols") is None:
        ss.custom_hols = dict(rl.policy_holidays(ss.valid_policy))
    return ss.custom_hols


def remove_holiday(d: date):
    own_holidays().pop(d, None)


def add_holiday():
    d, name = ss.get("hol_new_date"), (ss.get("hol_new_name") or "").strip()
    if d:
        own_holidays()[d] = name[:80] or "Company holiday"
        ss.hol_new_name = ""


def upload_holidays():
    upload = ss.get("hol_file")
    if upload is None:
        return
    found, bad = rl.parse_holiday_csv(upload.getvalue().decode("utf-8-sig", "replace"))
    if not found:
        ss.hol_msg = ("error", "No dates could be read from that file. It needs a date and a name on each row.")
        return
    ss.custom_hols = found
    note = f" {plural(bad, 'row')} could not be read and were left out." if bad else ""
    ss.hol_msg = ("ok", f"Your list now has {plural(len(found), 'holiday')} from the file.{note}")


def reset_holidays():
    ss.custom_hols = None
    ss.hol_msg = None


# ------------------------------------------------------------------- start

qp = st.query_params
theme_now, mode_now = themes.normalise(
    ss.get("ui_theme") or qp.get("theme"), ss.get("ui_mode") or qp.get("mode")
)
html(f"<style>{page_css(theme_now, mode_now)}</style>")

# The saved state round trip. Callbacks have already run, so the session
# holds the newest state and it can be handed to the browser right here.
payload = saved_payload() if ss.get("hydrated") else None
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
    state = rl.load_state((saved or {}).get("raw"), ss.today)
    # A link can name a look: ?theme=cobalt&mode=dark
    state["ui"] = {"theme": qp.get("theme") or state["ui"].get("theme"), "mode": qp.get("mode") or state["ui"].get("mode")}
    apply_state(state)
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
        "As a day in office: the month is not changed, and a PTO day counts as a day in. "
        "Sick days and other absences are counted the same way.",
    )
    st.checkbox(
        "Holiday between Christmas and New Year?", key="extended_christmas_break",
        disabled=ss.get("custom_hols") is not None,
        help="Part of the built-in holiday list. Once you edit the list on the Company Holidays tab, "
        "your own list is used instead.",
    )
    st.number_input(
        "PTO allowance",
        min_value=0, max_value=60, step=1, key="pto_allowance",
        help="Total PTO days for the period, carry-over included.",
    )

    policy = current_policy()
    if ss.get("policy_error"):
        st.error("The end date is before the start date. Showing the last period that worked.")

    st.header("Appearance")
    st.selectbox(
        "Theme", list(themes.THEMES), key="ui_theme",
        format_func=lambda slug: themes.THEMES[slug]["label"],
        help="  \n".join(f"{t['label']}: {t['blurb']}." for t in themes.THEMES.values()),
    )
    st.radio("Mode", list(themes.MODES), key="ui_mode", horizontal=True, format_func=str.capitalize)

    st.header("Your data")
    st.caption(
        "Your policy, days, holidays and theme are saved in this browser only. "
        "Nothing is sent to a server, and another browser or device starts empty."
    )
    st.download_button(
        "Download a backup", data=saved_payload(),
        file_name="rto-days.json", mime="application/json", width="stretch",
    )
    st.file_uploader("Restore a backup", type=["json"], key="backup_file", on_change=restore_backup)
    has_days = any(day_sets().values())
    if ss.get("confirm_clear"):
        st.warning("This removes every day you have marked. Your policy and holidays stay.")
        b1, b2 = st.columns(2)
        b1.button("Yes, clear", on_click=clear_days, width="stretch")
        b2.button("Keep them", on_click=lambda: ss.update(confirm_clear=False), width="stretch")
    else:
        st.button(
            "Clear my days", on_click=lambda: ss.update(confirm_clear=True), width="stretch",
            disabled=not has_days,
        )

away_days = ss.pto | ss.sick | ss.other  # the planner treats all three as days already taken
summary = rl.summarize(policy, ss.office, ss.pto, today, ss.sick, ss.other)
holidays = rl.policy_holidays(policy)
workday_set = set(rl.workdays_between(policy.start, policy.end, holidays))

# ------------------------------------------------------------------ header

cur = summary.current
if cur is None:
    head = "Today is outside your period"
    sub = f"The period runs {fmt_day(policy.start)}, {policy.start.year} to {fmt_day(policy.end)}, {policy.end.year}."
elif cur.required == 0:
    head = f"No office days needed in {cur.first:%B}"
    sub = f"{plural(cur.workdays, 'workday')} this month, {cur.pto + cur.sick + cur.other} of them off."
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

paces = []
if cur is not None:
    done, base = share_parts(cur.workdays, cur.pto + cur.sick + cur.other, cur.attended, policy.pto_mode)
    paces.append(pace_meter(f"in {cur.first:%B}", cur.share, done, base, policy.percent))
done, base = share_parts(
    summary.workdays, summary.pto + summary.sick + summary.other, summary.attended, policy.pto_mode
)
paces.append(pace_meter("this period", summary.share, done, base, policy.percent))

top_l, top_r = st.columns([5, 2], vertical_alignment="center")
with top_l:
    html(
        f'<div class="band"><h1>{escape(head)}</h1><p class="lead">{escape(sub)}</p>'
        f'<div class="paces">{"".join(paces)}</div></div>'
    )
with top_r:
    with st.container(key="today_action"):
        if today in ss.office:
            st.button("Undo today's log", on_click=mark_day, args=(today, "clear"), width="stretch")
        else:
            st.button(
                "I'm in today", type="primary", on_click=mark_day, args=(today, "in"), width="stretch",
                disabled=today not in workday_set,
                help=None if today in workday_set else "Today is not a workday in your period.",
            )

# The four figures are for one month: this one, or the nearest month of the
# period when today falls outside it.
if cur is not None:
    sm = cur
else:
    sm = summary.months[0] if today < policy.start else summary.months[-1]
month_days = [d for d in workday_set if rl.month_key(d) == sm.key]
logged = [d for d in month_days if d in ss.office and d not in away_days]
been = sum(1 for d in logged if d <= today)
planned = len(logged) - been
leave = sm.pto + sm.sick + sm.other
if policy.pto_mode == rl.PTO_SUBTRACT:
    basis = f"{policy.percent:g}% of {sm.workdays - leave} workdays" + (" after leave" if leave else "")
else:
    basis = f"{policy.percent:g}% of {sm.workdays} workdays" + (", less leave" if leave else "")
if sm.required == 0:
    go_note = "nothing needed this month"
elif sm.remaining == 0:
    go_note = "covered, with what you have planned" if planned else "covered"
else:
    go_note = f"{plural(sm.left, 'free workday')} left"
leave_parts = [f"{sm.pto} PTO"] + ([f"{sm.sick} sick"] if sm.sick else []) + ([f"{sm.other} other"] if sm.other else [])
stats = [
    (f"Required in {sm.first:%B}", sm.required, basis),
    ("Been / planned in", f"{been} / {planned}", "days logged so far, and days marked ahead"),
    ("Still to go", sm.remaining, go_note),
    ("PTO and leave days", leave, ", ".join(leave_parts) + f". {summary.pto} of {policy.pto_allowance} PTO used this period"),
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

track_tab, plan_tab, month_tab, holiday_tab = st.tabs(["Track", "PTO-maxxing ✨", "By month", "Company Holidays"])

# ------------------------------------------------------------------- track

with track_tab:
    first_month = policy.start.replace(day=1)
    last_month = policy.end.replace(day=1)
    if "view_month" not in ss:
        ss.view_month = today.replace(day=1)
    ss.view_month = min(max(ss.view_month, first_month), last_month)
    vm: date = ss.view_month
    msum = next(m for m in summary.months if m.key == rl.month_key(vm))

    with st.container(key="monthnav"):
        n1, n2, n3 = st.columns([1, 5, 1], vertical_alignment="center")
        n1.button(
            "", icon=":material/chevron_left:", key="prev_month", on_click=shift_month, args=(-1,),
            disabled=vm <= first_month, help="Previous month", width="stretch",
        )
        with n2:
            off = msum.pto + msum.sick + msum.other
            html(
                f"<h2>{fmt_month(vm)}</h2>"
                f'<p class="month-note">{msum.attended} of {msum.required} office days, '
                f"{plural(off, 'day')} off. Point at a day, or tap it, to mark it.</p>"
            )
        n3.button(
            "", icon=":material/chevron_right:", key="next_month", on_click=shift_month, args=(1,),
            disabled=vm >= last_month, help="Next month", width="stretch",
        )

    cells = []
    for week in calendar.Calendar(firstweekday=0).monthdatescalendar(vm.year, vm.month):
        days = week[:5]
        if not any(d.month == vm.month for d in days):
            continue
        for d in days:
            if d.month != vm.month or not (policy.start <= d <= policy.end):
                cells.append(None)
                continue
            state = next((mark for mark, days_ in day_sets().items() if d in days_), "free")
            if d in holidays:
                state = "hol"
            cells.append({
                "d": d.isoformat(), "n": d.day, "long": f"{d:%A, %B} {d.day}", "state": state,
                "hol": holidays.get(d), "today": d == today,
            })
    event = month_tray(css=tray_css(ss.ui_theme, ss.ui_mode), cells=cells, key="tray", default=None)
    if event and event.get("seq") != ss.get("tray_seq"):
        ss.tray_seq = event.get("seq")
        try:
            picked = date.fromisoformat(event.get("d", ""))
        except ValueError:
            picked = None
        if picked in workday_set:
            mark_day(picked, event.get("mark"))
            st.rerun()

    html(
        '<ul class="legend">'
        '<li><span class="key key-in"></span>In office</li>'
        '<li><span class="key key-pto"></span>PTO</li>'
        '<li><span class="key key-sick"></span>Sick day</li>'
        '<li><span class="key key-other"></span>Other absence</li>'
        '<li><span class="key key-hol"></span>Company holiday</li>'
        '<li><span class="key key-now"></span>Today</li>'
        "</ul>"
    )
    if ss.get("first_visit") and not has_days:
        st.caption("Nothing marked yet. Start with the days you were in the office this month.")

# -------------------------------------------------------------------- plan

with plan_tab:
    left_pto = max(0, policy.pto_allowance - summary.pto)
    html(
        "<h2>PTO-maxxing ✨</h2>"
        '<p class="lead">The most time off your PTO can buy, with the policy still met every month.</p>'
    )
    if left_pto == 0:
        st.info(
            f"All {policy.pto_allowance} days of your allowance are on the calendar. "
            "Raise the allowance in the sidebar, or clear a PTO day on the Track tab."
        )
    else:
        p1, p2, _ = st.columns([2, 2, 3])
        budget = int(p1.number_input(
            "PTO days to place", min_value=1, max_value=left_pto, value=left_pto, step=1,
            help=f"You have {left_pto} of {policy.pto_allowance} PTO days not yet on the calendar.",
        ))
        cap = int(p2.number_input(
            "Most PTO days in one break", min_value=1, max_value=10, value=4, step=1, key="plan_cap",
            help="Keeps the quick plan from spending a whole week of PTO in one go. "
            "The AI treats it as a preference and follows what you write instead.",
        ))
        st.text_area(
            "Anything to plan around?", key="ai_wishes", max_chars=pto_ai.MAX_WISH_CHARS, height=80,
            placeholder="For example: two weeks off in July, nothing in March, long weekends over single days",
        )
        has_key = bool(planner_key())
        with st.container(key="ai_action"):
            st.button(
                "Plan it with AI", type="primary", key="ask_ai", on_click=ask_ai,
                args=(policy, today, budget, cap), disabled=not has_key,
            )
        if has_key:
            st.caption(
                "Gemini picks the dates. The app then checks them against your calendar "
                "and does the counting itself, so the numbers below are not the model's."
            )
        else:
            st.caption(
                "The AI planner needs a Gemini API key (GEMINI_API_KEY) in the app's secrets. "
                "The quick plan below works without it."
            )
        if ss.get("ai_error"):
            st.error(ss.ai_error)

        ai = ss.get("ai_plan")
        if ai:
            checked = rl.check_pto(policy, ss.office, away_days, today, ai["dates"], min(ai["budget"], left_pto))
            plan = checked.plan
            html(
                "<h3>The AI's plan</h3>"
                f'<p class="ai-note">{escape(ai["summary"])}</p>'
                + (f'<p class="ai-note">{escape(ai["breaks_note"])}</p>' if ai["breaks_note"] else "")
            )
            if plan.dates:
                html(f'<p class="plan-line">{escape(plan_line(plan))}</p>' + plan_table(plan))
            else:
                st.warning("None of the suggested dates are free workdays in your period.")
            if checked.rejected and plan.dates:
                st.caption(
                    f"{plural(len(checked.rejected), 'suggested date')} left out: "
                    "not a free workday in your period, or over the number of days to place."
                )
            for month, extra in checked.short_months:
                st.warning(
                    f"This plan leaves {month.first:%B} {plural(extra, 'office day')} short: "
                    "not enough free workdays would be left to meet the policy."
                )
            a1, a2, _ = st.columns([2, 2, 3])
            if plan.dates:
                a1.button(
                    f"Add {plural(len(plan.dates), 'day')} to my PTO", on_click=add_plan,
                    args=(plan.dates,), key="add_ai_plan", width="stretch",
                )
            a2.button("Back to the quick plan", on_click=drop_ai_plan, key="drop_ai_plan", width="stretch")
        else:
            plan = rl.plan_pto(policy, ss.office, away_days, today, budget, cap)
            html(
                "<h3>Quick plan, no AI</h3>"
                '<p class="ai-note">Each day goes where it cuts the most office days, '
                "then where it buys the longest stretch off.</p>"
            )
            if not plan.dates:
                st.info("There are no free workdays left in the period to place PTO on.")
            else:
                n = len(plan.dates)
                html(f'<p class="plan-line">{escape(plan_line(plan))}</p>' + plan_table(plan))
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
            status = "None needed"
        elif m.remaining == 0:
            status = "Covered"
        elif m.is_past:
            status = f"{m.remaining} not logged"
        elif m.shortfall:
            status = f"{m.remaining} to go, {m.left} free"
        else:
            status = f"{m.remaining} to go"
        rows.append(
            f'<tr class="{"is-now" if m.is_current else ""}">'
            f"<th scope=\"row\">{m.first:%b %Y}</th>"
            f'<td class="num">{m.workdays}</td><td class="num">{m.pto}</td>'
            f'<td class="num">{m.sick + m.other}</td>'
            f'<td class="num">{m.required}</td><td class="num">{m.attended}</td>'
            f'<td class="num">{m.share:.0f}%</td>'
            f'<td><span class="meter" role="img" aria-label="{done} of {m.required} office days">'
            f'<span style="inline-size:{pct}%"></span></span></td>'
            f"<td>{status}</td></tr>"
        )
    html(
        '<table class="sheet sheet-months"><thead><tr><th>Month</th><th class="num">Workdays</th>'
        '<th class="num">PTO</th><th class="num">Sick and other</th>'
        '<th class="num">Required</th><th class="num">Been in</th><th class="num">In office</th>'
        "<th>Progress</th><th>Status</th></tr></thead>"
        f"<tbody>{''.join(rows)}</tbody>"
        f'<tfoot><tr><th scope="row">Period</th><td class="num">{summary.workdays}</td>'
        f'<td class="num">{summary.pto}</td><td class="num">{summary.sick + summary.other}</td>'
        f'<td class="num">{summary.required}</td>'
        f'<td class="num">{summary.attended}</td><td class="num">{summary.share:.0f}%</td><td></td>'
        f"<td>{summary.remaining_ahead} to go</td></tr></tfoot>"
        "</table>"
    )

# ---------------------------------------------------------------- holidays

with holiday_tab:
    own = ss.get("custom_hols") is not None
    html(
        "<h2>Company Holidays</h2>"
        '<p class="lead">These days are not workdays. Change the list to match your company\'s calendar.</p>'
    )
    if own:
        st.caption(f"Using your own list: {plural(len(holidays), 'holiday')} in this period.")
    else:
        st.caption(
            "Using the built-in US list: federal holidays, the day after Thanksgiving"
            + (" and the Christmas break." if policy.christmas_break else ".")
        )
    msg = ss.pop("hol_msg", None)
    if msg:
        (st.success if msg[0] == "ok" else st.error)(msg[1])

    if not holidays:
        st.info("No holidays in this period. Add one below, or upload a list.")
    with st.container(key="holrows"):
        for d, name in holidays.items():
            c1, c2, c3 = st.columns([3, 6, 2], vertical_alignment="center")
            c1.html(f'<span class="hol-date">{fmt_day(d)}, {d.year}</span>')
            c2.html(f"<span>{escape(name)}</span>")
            c3.button("Remove", key=f"rm-hol-{d.isoformat()}", on_click=remove_holiday, args=(d,), width="stretch")

    html("<h3>Add a holiday</h3>")
    a1, a2, a3 = st.columns([3, 6, 2], vertical_alignment="bottom")
    if "hol_new_date" not in ss:
        ss.hol_new_date = min(max(today, policy.start), policy.end)
    a1.date_input("Date", key="hol_new_date")
    a2.text_input("Holiday Name", key="hol_new_name", max_chars=80, placeholder="For example: Company offsite day")
    a3.button("Add holiday", on_click=add_holiday, width="stretch")

    html("<h3>Upload a list</h3>")
    st.file_uploader(
        "A CSV with a date and a name on each row. It replaces the list above.",
        type=["csv"], key="hol_file", on_change=upload_holidays,
        help="Dates as 2026-07-03 or 7/3/2026. A header row is fine.",
    )
    buf = io.StringIO()
    writer = csv.writer(buf)
    writer.writerow(["date", "name"])
    writer.writerows([d.isoformat(), name] for d, name in holidays.items())
    d1, d2, _ = st.columns([3, 3, 5])
    d1.download_button(
        "Download this list", data=buf.getvalue(), file_name="company-holidays.csv", mime="text/csv",
        width="stretch",
    )
    d2.button("Back to the built-in list", on_click=reset_holidays, disabled=not own, width="stretch")
