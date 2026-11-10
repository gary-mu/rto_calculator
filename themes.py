"""The app's themes. Each is a Hallmark catalogue theme's palette and faces,
with a light and a dark ground, expressed as one set of token names so the
stylesheets never hold a colour of their own.

Token roles:
  paper / paper-2          the page and the sidebar
  surface, key, key-hover  the calendar pane and its day keys
  field                    inputs
  ink / ink-2 / muted      text
  rule / edge              hairlines; `edge` is strong enough for a control's border
  accent (+ink, +hi)       the primary action, the current tab, focus
  band (+ink, +muted, +track, +fill, +tick)   the status band at the top
  mark-in / pto / sick / other (+ink)         the four things a day can be
"""

from __future__ import annotations

DEFAULT_THEME = "garden"
DEFAULT_MODE = "light"
MODES = ("light", "dark")


def _o(l, c, h, a=None):
    return f"oklch({l}% {c} {h}{f' / {a}' if a is not None else ''})"


THEMES = {
    "garden": {
        "label": "Garden",
        "blurb": "Deep green and cream, a serif head, lime for progress",
        "fonts": "family=Vollkorn:wght@600&family=Hanken+Grotesk:wght@400;500;600",
        "display": '"Vollkorn", ui-serif, Georgia, serif',
        "body": '"Hanken Grotesk", ui-sans-serif, system-ui, sans-serif',
        "weight": 600, "tracking": "-0.012em",
        "radius-card": "8px", "radius-inner": "6px", "radius-control": "999px",
        "light": {
            "paper": _o(95.8, 0.024, 90), "paper-2": _o(92.6, 0.030, 90),
            "surface": _o(98.6, 0.012, 90), "key": _o(93, 0.030, 90), "key-hover": _o(89, 0.034, 90),
            "field": _o(98.6, 0.012, 90),
            "ink": _o(23, 0.050, 152), "ink-2": _o(33, 0.048, 150), "muted": _o(44, 0.034, 142),
            "rule": _o(83, 0.024, 112), "edge": _o(58, 0.034, 140),
            "accent": _o(42, 0.125, 145), "accent-ink": _o(97, 0.015, 95), "accent-hi": _o(35, 0.11, 147),
            "band": _o(27, 0.060, 152), "band-ink": _o(95.8, 0.024, 90), "band-muted": _o(84, 0.040, 110),
            "band-track": _o(95.8, 0.024, 90, 0.18), "band-fill": _o(88, 0.17, 125), "band-tick": _o(95.8, 0.024, 90),
            "mark-in": _o(42, 0.125, 145), "mark-in-ink": _o(97, 0.015, 95),
            "mark-pto": _o(70, 0.14, 55), "mark-pto-ink": _o(18, 0.03, 50),
            "mark-sick": _o(42, 0.11, 350), "mark-sick-ink": _o(97, 0.012, 350),
            "mark-other": _o(72, 0.035, 100), "mark-other-ink": _o(18, 0.02, 100),
        },
        "dark": {
            "paper": _o(19, 0.035, 152), "paper-2": _o(23, 0.040, 152),
            "surface": _o(24, 0.042, 152), "key": _o(30, 0.046, 152), "key-hover": _o(35, 0.048, 152),
            "field": _o(26, 0.042, 152),
            "ink": _o(95, 0.024, 90), "ink-2": _o(87, 0.030, 95), "muted": _o(74, 0.035, 120),
            "rule": _o(34, 0.040, 150), "edge": _o(56, 0.040, 140),
            "accent": _o(86, 0.17, 125), "accent-ink": _o(20, 0.035, 152), "accent-hi": _o(91, 0.15, 125),
            "band": _o(29, 0.065, 150), "band-ink": _o(95.8, 0.024, 90), "band-muted": _o(84, 0.040, 110),
            "band-track": _o(95.8, 0.024, 90, 0.16), "band-fill": _o(86, 0.17, 125), "band-tick": _o(95.8, 0.024, 90),
            "mark-in": _o(86, 0.17, 125), "mark-in-ink": _o(20, 0.035, 152),
            "mark-pto": _o(76, 0.13, 55), "mark-pto-ink": _o(18, 0.03, 50),
            "mark-sick": _o(76, 0.10, 350), "mark-sick-ink": _o(18, 0.03, 350),
            "mark-other": _o(70, 0.030, 110), "mark-other-ink": _o(16, 0.02, 110),
        },
    },
    "ultraviolet": {
        "label": "Ultraviolet",
        "blurb": "Lavender or a violet night, one saturated violet",
        "fonts": "family=Outfit:wght@500&family=Onest:wght@400;500;600",
        "display": '"Outfit", ui-sans-serif, system-ui, sans-serif',
        "body": '"Onest", ui-sans-serif, system-ui, sans-serif',
        "weight": 500, "tracking": "-0.03em",
        "radius-card": "16px", "radius-inner": "10px", "radius-control": "999px",
        "light": {
            "paper": _o(95, 0.02, 300), "paper-2": _o(92, 0.03, 300),
            "surface": _o(98.8, 0.008, 300), "key": _o(93.5, 0.026, 300), "key-hover": _o(89, 0.04, 300),
            "field": _o(98.8, 0.008, 300),
            "ink": _o(18, 0.02, 300), "ink-2": _o(28, 0.03, 300), "muted": _o(44, 0.05, 300),
            "rule": _o(84, 0.04, 300), "edge": _o(58, 0.07, 297),
            "accent": _o(50, 0.25, 290), "accent-ink": _o(97, 0.01, 300), "accent-hi": _o(43, 0.22, 290),
            "band": _o(46, 0.24, 290), "band-ink": _o(98, 0.008, 300), "band-muted": _o(90, 0.05, 297),
            "band-track": _o(98, 0.008, 300, 0.22), "band-fill": _o(98, 0.008, 300), "band-tick": _o(88, 0.15, 95),
            "mark-in": _o(50, 0.25, 290), "mark-in-ink": _o(97, 0.01, 300),
            "mark-pto": _o(82, 0.15, 80), "mark-pto-ink": _o(20, 0.04, 80),
            "mark-sick": _o(52, 0.20, 10), "mark-sick-ink": _o(98, 0.01, 10),
            "mark-other": _o(72, 0.05, 300), "mark-other-ink": _o(18, 0.02, 300),
        },
        "dark": {
            "paper": _o(15, 0.04, 295), "paper-2": _o(19, 0.05, 295),
            "surface": _o(20, 0.052, 295), "key": _o(26, 0.06, 295), "key-hover": _o(31, 0.07, 295),
            "field": _o(22, 0.052, 295),
            "ink": _o(96, 0.01, 300), "ink-2": _o(87, 0.03, 300), "muted": _o(73, 0.05, 300),
            "rule": _o(30, 0.06, 295), "edge": _o(56, 0.08, 297),
            "accent": _o(76, 0.15, 295), "accent-ink": _o(15, 0.04, 295), "accent-hi": _o(82, 0.12, 295),
            "band": _o(40, 0.21, 290), "band-ink": _o(98, 0.008, 300), "band-muted": _o(88, 0.05, 297),
            "band-track": _o(98, 0.008, 300, 0.2), "band-fill": _o(98, 0.008, 300), "band-tick": _o(88, 0.15, 95),
            "mark-in": _o(76, 0.15, 295), "mark-in-ink": _o(15, 0.04, 295),
            "mark-pto": _o(84, 0.14, 80), "mark-pto-ink": _o(20, 0.04, 80),
            "mark-sick": _o(74, 0.15, 10), "mark-sick-ink": _o(17, 0.04, 10),
            "mark-other": _o(68, 0.045, 300), "mark-other-ink": _o(15, 0.03, 300),
        },
    },
    "furrow": {
        "label": "Furrow",
        "blurb": "Manila paper, an ink band, tangerine and grass green",
        "fonts": "family=Red+Hat+Display:wght@600&family=Red+Hat+Text:wght@400;500;600",
        "display": '"Red Hat Display", "Red Hat Text", ui-sans-serif, sans-serif',
        "body": '"Red Hat Text", ui-sans-serif, system-ui, sans-serif',
        "weight": 600, "tracking": "-0.035em",
        "radius-card": "10px", "radius-inner": "6px", "radius-control": "6px",
        "light": {
            "paper": _o(96, 0.011, 85), "paper-2": _o(92.5, 0.016, 85),
            "surface": _o(99.3, 0.005, 85), "key": _o(93.5, 0.016, 85), "key-hover": _o(89, 0.02, 85),
            "field": _o(99.3, 0.005, 85),
            "ink": _o(18, 0.006, 60), "ink-2": _o(28, 0.008, 60), "muted": _o(43, 0.012, 60),
            "rule": _o(86, 0.013, 85), "edge": _o(58, 0.014, 70),
            "accent": _o(70, 0.19, 40), "accent-ink": _o(18, 0.006, 60), "accent-hi": _o(75, 0.17, 44),
            "focus": _o(48, 0.16, 40),  # the tangerine is too pale to ring a control on manila
            "band": _o(18, 0.006, 60), "band-ink": _o(96, 0.011, 85), "band-muted": _o(80, 0.014, 85),
            "band-track": _o(96, 0.011, 85, 0.16), "band-fill": _o(70, 0.19, 40), "band-tick": _o(96, 0.011, 85),
            "mark-in": _o(46, 0.11, 150), "mark-in-ink": _o(98, 0.01, 85),
            "mark-pto": _o(70, 0.19, 40), "mark-pto-ink": _o(18, 0.006, 60),
            "mark-sick": _o(68, 0.07, 232), "mark-sick-ink": _o(16, 0.02, 232),
            "mark-other": _o(72, 0.07, 58), "mark-other-ink": _o(16, 0.02, 58),
        },
        "dark": {
            "paper": _o(17, 0.008, 60), "paper-2": _o(21, 0.010, 60),
            "surface": _o(22, 0.010, 60), "key": _o(28, 0.012, 60), "key-hover": _o(33, 0.013, 60),
            "field": _o(24, 0.010, 60),
            "ink": _o(95, 0.011, 85), "ink-2": _o(86, 0.012, 85), "muted": _o(72, 0.014, 70),
            "rule": _o(31, 0.012, 60), "edge": _o(55, 0.014, 70),
            "accent": _o(72, 0.18, 42), "accent-ink": _o(16, 0.006, 60), "accent-hi": _o(78, 0.16, 46),
            "band": _o(26, 0.014, 60), "band-ink": _o(96, 0.011, 85), "band-muted": _o(80, 0.014, 85),
            "band-track": _o(96, 0.011, 85, 0.14), "band-fill": _o(72, 0.18, 42), "band-tick": _o(96, 0.011, 85),
            "mark-in": _o(72, 0.14, 150), "mark-in-ink": _o(15, 0.02, 150),
            "mark-pto": _o(72, 0.18, 42), "mark-pto-ink": _o(16, 0.006, 60),
            "mark-sick": _o(74, 0.07, 232), "mark-sick-ink": _o(15, 0.02, 232),
            "mark-other": _o(72, 0.06, 58), "mark-other-ink": _o(15, 0.02, 58),
        },
    },
    "cobalt": {
        "label": "Cobalt",
        "blurb": "Cool white or graphite, one electric blue",
        "fonts": "family=Familjen+Grotesk:wght@600&family=IBM+Plex+Sans:wght@400;500;600",
        "display": '"Familjen Grotesk", system-ui, sans-serif',
        "body": '"IBM Plex Sans", system-ui, sans-serif',
        "weight": 600, "tracking": "-0.028em",
        "radius-card": "8px", "radius-inner": "6px", "radius-control": "6px",
        "light": {
            "paper": _o(98.6, 0.005, 250), "paper-2": _o(95.5, 0.009, 252),
            "surface": _o(99.4, 0.003, 250), "key": _o(95.2, 0.010, 252), "key-hover": _o(91, 0.016, 252),
            "field": _o(99.4, 0.003, 250),
            "ink": _o(21, 0.028, 262), "ink-2": _o(34, 0.022, 260), "muted": _o(47, 0.018, 258),
            "rule": _o(88, 0.010, 252), "edge": _o(60, 0.02, 256),
            "accent": _o(52, 0.19, 258), "accent-ink": _o(98.6, 0.005, 250), "accent-hi": _o(43, 0.2, 262),
            "band": _o(48, 0.19, 259), "band-ink": _o(98.6, 0.005, 250), "band-muted": _o(90, 0.035, 255),
            "band-track": _o(98.6, 0.005, 250, 0.22), "band-fill": _o(98.6, 0.005, 250), "band-tick": _o(86, 0.14, 85),
            "mark-in": _o(52, 0.19, 258), "mark-in-ink": _o(98.6, 0.005, 250),
            "mark-pto": _o(82, 0.14, 82), "mark-pto-ink": _o(20, 0.03, 82),
            "mark-sick": _o(50, 0.18, 20), "mark-sick-ink": _o(98.6, 0.008, 20),
            "mark-other": _o(72, 0.022, 256), "mark-other-ink": _o(18, 0.024, 262),
        },
        "dark": {
            "paper": _o(18, 0.024, 262), "paper-2": _o(21.5, 0.025, 262),
            "surface": _o(22.5, 0.026, 262), "key": _o(28.5, 0.028, 262), "key-hover": _o(33, 0.03, 262),
            "field": _o(24.5, 0.026, 262),
            "ink": _o(94, 0.010, 250), "ink-2": _o(85, 0.014, 252), "muted": _o(72, 0.022, 256),
            "rule": _o(32, 0.026, 262), "edge": _o(56, 0.03, 258),
            "accent": _o(76, 0.13, 254), "accent-ink": _o(18, 0.024, 262), "accent-hi": _o(83, 0.10, 254),
            "band": _o(43, 0.2, 262), "band-ink": _o(98.6, 0.005, 250), "band-muted": _o(88, 0.04, 255),
            "band-track": _o(98.6, 0.005, 250, 0.2), "band-fill": _o(98.6, 0.005, 250), "band-tick": _o(86, 0.14, 85),
            "mark-in": _o(76, 0.13, 254), "mark-in-ink": _o(18, 0.024, 262),
            "mark-pto": _o(84, 0.13, 82), "mark-pto-ink": _o(20, 0.03, 82),
            "mark-sick": _o(74, 0.14, 20), "mark-sick-ink": _o(17, 0.04, 20),
            "mark-other": _o(68, 0.022, 256), "mark-other-ink": _o(15, 0.024, 262),
        },
    },
    "dusk": {
        "label": "Dusk",
        "blurb": "Slate or bone, periwinkle and apricot",
        "fonts": "family=Wix+Madefor+Display:wght@500&family=Wix+Madefor+Text:wght@400;500;600",
        "display": '"Wix Madefor Display", ui-sans-serif, system-ui, sans-serif',
        "body": '"Wix Madefor Text", ui-sans-serif, system-ui, sans-serif',
        "weight": 500, "tracking": "-0.022em",
        "radius-card": "18px", "radius-inner": "10px", "radius-control": "999px",
        "light": {
            "paper": _o(95.5, 0.008, 75), "paper-2": _o(92, 0.010, 75),
            "surface": _o(99.5, 0.003, 75), "key": _o(93.5, 0.009, 75), "key-hover": _o(89, 0.011, 75),
            "field": _o(99.5, 0.003, 75),
            "ink": _o(22, 0.022, 268), "ink-2": _o(34, 0.022, 266), "muted": _o(45, 0.016, 265),
            "rule": _o(86, 0.009, 75), "edge": _o(58, 0.014, 265),
            "accent": _o(44, 0.13, 274), "accent-ink": _o(97, 0.008, 274), "accent-hi": _o(37, 0.13, 274),
            "band": _o(22, 0.022, 268), "band-ink": _o(96, 0.006, 75), "band-muted": _o(80, 0.012, 262),
            "band-track": _o(96, 0.006, 75, 0.14), "band-fill": _o(77, 0.10, 274), "band-tick": _o(83, 0.095, 62),
            "mark-in": _o(44, 0.13, 274), "mark-in-ink": _o(97, 0.008, 274),
            "mark-pto": _o(80, 0.105, 62), "mark-pto-ink": _o(20, 0.03, 62),
            "mark-sick": _o(48, 0.14, 330), "mark-sick-ink": _o(98, 0.008, 330),
            "mark-other": _o(72, 0.014, 265), "mark-other-ink": _o(18, 0.02, 268),
        },
        "dark": {
            "paper": _o(17.5, 0.014, 268), "paper-2": _o(21, 0.016, 268),
            "surface": _o(22, 0.018, 268), "key": _o(27.5, 0.018, 268), "key-hover": _o(32, 0.02, 268),
            "field": _o(24, 0.017, 268),
            "ink": _o(96, 0.006, 75), "ink-2": _o(85, 0.010, 262), "muted": _o(72, 0.016, 262),
            "rule": _o(30, 0.016, 266), "edge": _o(55, 0.018, 264),
            "accent": _o(77, 0.10, 274), "accent-ink": _o(19, 0.035, 274), "accent-hi": _o(84, 0.085, 274),
            "band": _o(25, 0.02, 268), "band-ink": _o(96, 0.006, 75), "band-muted": _o(80, 0.012, 262),
            "band-track": _o(96, 0.006, 75, 0.12), "band-fill": _o(77, 0.10, 274), "band-tick": _o(83, 0.095, 62),
            "mark-in": _o(77, 0.10, 274), "mark-in-ink": _o(19, 0.035, 274),
            "mark-pto": _o(83, 0.095, 62), "mark-pto-ink": _o(20, 0.03, 62),
            "mark-sick": _o(74, 0.11, 330), "mark-sick-ink": _o(17, 0.04, 330),
            "mark-other": _o(70, 0.014, 262), "mark-other-ink": _o(15, 0.02, 268),
        },
    },
}


def normalise(theme, mode):
    theme = theme if theme in THEMES else DEFAULT_THEME
    mode = mode if mode in MODES else DEFAULT_MODE
    return theme, mode


def font_import(theme: str) -> str:
    return f'@import url("https://fonts.googleapis.com/css2?{THEMES[theme]["fonts"]}&display=swap");'


def root_block(theme: str, mode: str) -> str:
    """The :root token block for one theme and ground."""
    theme, mode = normalise(theme, mode)
    t = THEMES[theme]
    lines = [f"color-scheme: {mode};"]
    lines += [f"--color-{name}: {value};" for name, value in t[mode].items()]
    if "focus" not in t[mode]:
        lines.append("--color-focus: var(--color-accent);")
    lines += [
        f"--font-display: {t['display']};",
        f"--font-body: {t['body']};",
        f"--display-weight: {t['weight']};",
        f"--tracking-display: {t['tracking']};",
        f"--radius-card: {t['radius-card']};",
        f"--radius-inner: {t['radius-inner']};",
        f"--radius-control: {t['radius-control']};",
        "--radius-pill: 999px; --rule-hair: 1px;",
    ]
    return ":root {\n  " + "\n  ".join(lines) + "\n}"
