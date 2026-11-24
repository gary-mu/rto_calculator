"""The privacy policy and the terms of service, shown at ?page=privacy and
?page=terms. Every statement here describes what the code does; if the app
changes what it stores or sends, change this file in the same pull request.
"""

UPDATED = "November 23, 2026"
REPO = "https://github.com/gary-mu/rto_calculator"

PRIVACY = f"""
# Privacy policy

Last updated: {UPDATED}

RTO calculator is a free tool, run by Gary Mu, for working out how many days
you need in the office under a return-to-office policy. This page says what
the app keeps about you, where, and what it sends to anyone else.

## The short version

- You can use the app without an account. Then everything you enter stays in
  your own browser.
- If you choose to sign in with Google, the same information is also saved to
  a database so it follows you to your other devices. It is saved under a
  scrambled ID. Your name and email address are not saved.
- There are no ads and no analytics, and nothing is sold or shared for
  marketing.

## What you enter

The app works with what you put into it: your policy settings (the period,
the percentage, what counts as a day in the office, your PTO allowance), the
days you mark (in office, PTO, sick day, other absence), your list of company
holidays, and the theme you picked.

## If you are not signed in

All of the above is stored in your browser's local storage, on your device.
The app's server works with it while your page is open in order to draw the
screen, and does not write it to a database. Another browser or device will
not have it. You can remove it at any time with "Clear my days" or by
clearing the site's data in your browser.

## If you sign in with Google

Signing in is optional. When you do:

- Google tells the app your basic profile: a Google account ID, your email
  address, your name and your profile picture. The app asks for nothing else
  from your Google account.
- The app uses the account ID to work out which saved data is yours, and
  shows your email address on screen so you can see which account you are
  using. It does not use the name or the picture.
- A sign-in cookie is kept in your browser so you stay signed in. It expires
  after 30 days, or when you sign out.
- The database holds one record for you: a scrambled version of your Google
  account ID (a salted hash, which cannot be turned back into the ID), the
  information listed under "What you enter", a revision number and the time
  it was last saved. Your name, email address and picture are not stored.

Information received from Google is used only to sign you in and to find
your own saved data. It is not used for advertising, and it is not sold or
passed to anyone else.

## The AI planner

If you press "Plan it with AI", the app sends a request to Google's Gemini
service to suggest PTO dates. The request contains your policy settings, the
month-by-month counts, your company holidays, the PTO you have already
booked, the workdays that are still free, and whatever you typed in the
"Anything to plan around?" box. It does not contain your name, your email
address or your account ID. Do not type personal details into that box.
Nothing is sent to Gemini unless you press the button.

## Other services the app relies on

- **Streamlit Community Cloud** hosts the app. Like any web host it handles
  your connection, which involves technical details such as your IP address.
  The app has Streamlit's usage statistics turned off.
- **Supabase** hosts the database used for signed-in accounts.
- **Google** provides sign-in and the Gemini service described above.
- **Google Fonts** serves the typefaces, so your browser contacts Google to
  download them.

Each of these handles data under its own privacy policy.

## How long it is kept, and how to delete it

- Data in your browser stays until you clear it.
- Data in your account stays until you delete it. "Delete account" in the
  sidebar removes your record from the database straight away and signs you
  out.
- You can download a copy of your data at any time with "Download a backup".

## Children

The app is meant for working adults and is not directed at children.

## Changes

If this policy changes, the date at the top will change with it. The full
history is public in the app's [source code]({REPO}).

## Contact

Questions or requests about your data: open an issue at
[{REPO.removeprefix("https://")}/issues]({REPO}/issues).
"""

TERMS = f"""
# Terms of service

Last updated: {UPDATED}

RTO calculator is a free tool run by Gary Mu. By using it you agree to these
terms. If you do not agree, please do not use it.

## What the app is

It helps you work out how many days you need in the office under a
return-to-office policy, keep track of the days you have been in, and plan
time off. It is a personal project and is not affiliated with your employer
or with any company whose policy you enter.

## The numbers are estimates

The app calculates from what you tell it and from a built-in list of
holidays that may not match your employer's. Your employer's own policy and
records are what count. Check anything that matters with your manager or HR
before relying on it. The app does not give legal, employment or HR advice.

## The AI planner

Suggestions from "Plan it with AI" are produced by an AI model and can be
wrong or unsuitable. The app checks suggested dates against your calendar,
but the decision to take time off, and whether it is approved, is yours and
your employer's.

## Your account

An account is optional. If you sign in with Google, you are responsible for
keeping your Google account secure. You can delete your saved data at any
time with "Delete account". How your information is handled is described in
the privacy policy.

## Using the app fairly

Do not misuse the app: do not try to break it, overload it, get at other
people's data, or use it to do anything unlawful.

## No guarantees

The app is provided as it is, free of charge and without warranties of any
kind. It may be slow, unavailable, changed or shut down at any time, and
saved data may be lost. Keep your own copy of anything important with
"Download a backup". To the extent the law allows, Gary Mu is not liable for
any loss or damage that comes from using the app or relying on what it shows.

## Changes

These terms may change. The date at the top will change with them, and the
full history is public in the app's [source code]({REPO}). Continuing to use
the app after a change means you accept the new terms.

## Contact

Questions about these terms: open an issue at
[{REPO.removeprefix("https://")}/issues]({REPO}/issues).
"""

PAGES = {
    "privacy": ("Privacy policy", PRIVACY),
    "terms": ("Terms of service", TERMS),
}
