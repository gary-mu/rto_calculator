# rto_calculator

A Streamlit app for working out how many days you need in the office under a
return-to-office policy, keeping track of the days you have been in, and
deciding where to put PTO. Live at https://rto-calculate.streamlit.app/.

## What it does

- **Required days.** A percentage of each month's workdays, rounded down.
  A workday is a weekday that is not a company holiday (US federal holidays,
  the day after Thanksgiving and, optionally, the Christmas break).
- **Tracking.** Tap the days you were in the office, on PTO or out sick. The
  app shows what is still to go, and the share of workdays you have been in
  against the policy's percentage, with a progress bar.
- **PTO-maxxing.** Two planners for the PTO you have left. The quick plan is
  computed: each day goes where it lowers the office days still required, then
  where it buys the longest stretch off. The AI plan asks Gemini
  (`gemini-4-carbon`) to place the days around what you tell it you want. The
  model only proposes dates: the app keeps the ones that are free workdays,
  does all the counting itself, and warns if a month would fall short.

PTO is accounted for in one of two ways, chosen in the sidebar: taken out of
the workdays before the percentage is applied, or counted as a day in office.
A sick day is accounted for the same way, without using the PTO allowance.

## The AI planner's key

The AI plan needs a Gemini API key. Without one the button is disabled and
the quick plan still works. The key is read from `GEMINI_API_KEY` (or
`GOOGLE_API_KEY`), first in Streamlit secrets under `[general]`, then in the
environment. Never commit it: `.streamlit/secrets.toml` is git-ignored.

Locally, in `.streamlit/secrets.toml`:

```toml
[general]
GEMINI_API_KEY = "..."
```

On Streamlit Community Cloud: the app's Settings, then Secrets, with the same
two lines.

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
- `pto_ai.py`: the Gemini request for the AI plan.
- `tests/`: required days, remaining days, sick days, PTO planning, the AI
  planner's request and error handling, saved state.
- `theme/`: the Hallmark "Dusk" theme (tokens, base rules, app styles);
  `.streamlit/config.toml` mirrors its colours and fonts.
- `_build/`: `puppeteer-core` for the Hallmark linter (`npm install` there).
