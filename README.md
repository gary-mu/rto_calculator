# rto_calculator

A Streamlit app for working out how many days you need in the office under a
return-to-office policy, keeping track of the days you have been in, and
deciding where to put PTO. Live at https://rto-calculate.streamlit.app/.

## What it does

- **Required days.** A percentage of each month's workdays, rounded down.
  A workday is a weekday that is not a company holiday (US federal holidays,
  the day after Thanksgiving and, optionally, the Christmas break).
- **Tracking.** Tap the days you were in the office, or the days you are on
  PTO. The app shows what is still to go this month and from this month on.
- **PTO planning.** Suggests where to place the PTO you have left: first where
  it lowers the office days still required, then where a day buys the longest
  stretch off next to a weekend or holiday. It never suggests a plan that
  leaves a month without enough free days to meet the policy.

PTO is accounted for in one of two ways, chosen in the sidebar: taken out of
the workdays before the percentage is applied, or counted as a day in office.

## Where your days are kept

In your browser's `localStorage`, through the small component in
`components/day_store`. Nothing is stored on the server. The days survive a
reload and a restart of the app, but another browser or device starts empty;
the sidebar has a backup download and restore for moving them.

## Run it

```bash
python -m venv .venv && .venv/bin/pip install -r requirements.txt -r requirements-dev.txt
```

```bash
.venv/bin/streamlit run rto_app.py
```

```bash
.venv/bin/python -m pytest tests
```

## Layout

- `rto_app.py`: the screen.
- `rto_logic.py`: the calculations, with no Streamlit in them.
- `tests/`: required days, remaining days, PTO planning, saved state.
- `theme/`: the Hallmark "Dose" theme (tokens, base rules, app styles);
  `.streamlit/config.toml` mirrors its colours and fonts.
- `_build/`: `puppeteer-core` for the Hallmark linter (`npm install` there).
