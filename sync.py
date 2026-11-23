"""Optional accounts: keep a signed-in person's state in a database so it
follows them between devices. No Streamlit in here.

What is stored for an account is exactly what the browser stores (the JSON
from rto_logic.dump_state), under a scrambled ID. No name, no email.

Two people-shaped problems this handles:

* A browser that already has days in it signs in to an account that already
  has days. Neither is silently thrown away: see `decide`.
* The same account is open on two devices. Each save names the revision it
  started from; a save from a stale copy is refused (`Conflict`) and that
  device reloads instead of overwriting.
"""

from __future__ import annotations

import hashlib
import json
import os
from dataclasses import dataclass
from datetime import date, datetime, timezone

import rto_logic as rl

DAY_KINDS = ("office", "pto", "sick", "other")
TAKE, PUSH, ASK = "take", "push", "ask"


class StoreError(Exception):
    """The database could not be reached or refused the request."""


class Conflict(StoreError):
    """The account changed since this copy was read."""


@dataclass(frozen=True)
class Remote:
    payload: str
    rev: int


def user_key(subject: str, pepper: str = "") -> str:
    """A stable, scrambled ID for an account. The raw ID never leaves the app."""
    return hashlib.sha256(f"{pepper}|{subject}".encode()).hexdigest()


def content_hash(policy: rl.Policy, office, pto, sick, other) -> str:
    """A fingerprint of someone's policy and days, ignoring appearance."""
    return hashlib.sha256(rl.dump_state(policy, office, pto, sick, other, {}).encode()).hexdigest()


def marked(state: dict) -> dict:
    return {d: kind for kind in DAY_KINDS for d in state[kind]}


def decide(local: dict, local_is_synced_copy: bool, remote: dict | None) -> str:
    """What to do when a browser signs in.

    PUSH  the account is empty: this browser's state becomes the account's.
    TAKE  use the account's state. Safe when this browser holds an unchanged
          copy of the account, holds no days, or holds only days the account
          already has.
    ASK   this browser has days the account does not: let the person choose.
    """
    if remote is None:
        return PUSH
    if local_is_synced_copy:
        return TAKE
    mine, theirs = marked(local), marked(remote)
    if all(theirs.get(d) == kind for d, kind in mine.items()):
        return TAKE
    return ASK


def merge(account: dict, browser: dict) -> dict:
    """The account's state plus the browser's days on dates the account has not marked."""
    taken = set(marked(account))
    out = {kind: set(account[kind]) for kind in DAY_KINDS}
    for d, kind in marked(browser).items():
        if d not in taken:
            out[kind].add(d)
    return {"policy": account["policy"], "ui": account.get("ui", {}), **out}


def extra_days(account: dict, browser: dict) -> int:
    """How many of the browser's marked days the account does not have the same way."""
    theirs = marked(account)
    return sum(1 for d, kind in marked(browser).items() if theirs.get(d) != kind)


# ------------------------------------------------------------------ stores


class MemoryStore:
    """For tests."""

    def __init__(self):
        self.rows: dict[str, Remote] = {}

    def get(self, key: str) -> Remote | None:
        return self.rows.get(key)

    def put(self, key: str, payload: str, expected_rev: int | None) -> int:
        current = self.rows.get(key)
        if (current.rev if current else None) != expected_rev:
            raise Conflict("The account changed on another device.")
        rev = (expected_rev or 0) + 1
        self.rows[key] = Remote(payload, rev)
        return rev

    def delete(self, key: str) -> None:
        self.rows.pop(key, None)


class FileStore(MemoryStore):
    """A JSON file, for trying the signed-in flow on a laptop. Not for production."""

    def __init__(self, path: str):
        super().__init__()
        self.path = path
        self._load()

    def _load(self):
        try:
            with open(self.path) as f:
                self.rows = {k: Remote(v["payload"], v["rev"]) for k, v in json.load(f).items()}
        except (OSError, ValueError, KeyError, TypeError):
            self.rows = {}

    def _save(self):
        os.makedirs(os.path.dirname(self.path) or ".", exist_ok=True)
        with open(self.path, "w") as f:
            json.dump({k: {"payload": r.payload, "rev": r.rev} for k, r in self.rows.items()}, f)

    def get(self, key):
        self._load()
        return super().get(key)

    def put(self, key, payload, expected_rev):
        self._load()
        rev = super().put(key, payload, expected_rev)
        self._save()
        return rev

    def delete(self, key):
        self._load()
        super().delete(key)
        self._save()


class SupabaseStore:
    """One table in Supabase, reached over its REST interface.

        create table rto_state (
          user_key   text primary key,
          payload    text not null,
          rev        bigint not null,
          updated_at timestamptz not null default now()
        );
        alter table rto_state enable row level security;

    With row level security on and no policies, only the secret key this app
    holds can read or write the table.
    """

    def __init__(self, url: str, key: str, table: str = "rto_state", http=None, timeout: float = 10.0):
        if http is None:
            import requests

            http = requests
        self.http = http
        self.endpoint = f"{url.rstrip('/')}/rest/v1/{table}"
        self.headers = {
            "apikey": key,
            "Authorization": f"Bearer {key}",
            "Content-Type": "application/json",
            "Prefer": "return=representation",
        }
        self.timeout = timeout

    def _call(self, method: str, params=None, body=None):
        try:
            r = self.http.request(
                method, self.endpoint, params=params, json=body, headers=self.headers, timeout=self.timeout
            )
        except Exception as e:  # network trouble, timeouts
            raise StoreError("Could not reach the account database.") from e
        if r.status_code == 409:
            raise Conflict("The account changed on another device.")
        if r.status_code >= 400:
            raise StoreError(f"The account database returned an error ({r.status_code}).")
        try:
            return r.json() if r.content else []
        except ValueError as e:
            raise StoreError("The account database sent an unreadable answer.") from e

    def get(self, key: str) -> Remote | None:
        rows = self._call("GET", {"user_key": f"eq.{key}", "select": "payload,rev"})
        return Remote(rows[0]["payload"], int(rows[0]["rev"])) if rows else None

    def put(self, key: str, payload: str, expected_rev: int | None) -> int:
        now = datetime.now(timezone.utc).isoformat()
        if expected_rev is None:
            self._call("POST", body={"user_key": key, "payload": payload, "rev": 1, "updated_at": now})
            return 1
        rows = self._call(
            "PATCH",
            {"user_key": f"eq.{key}", "rev": f"eq.{expected_rev}"},
            {"payload": payload, "rev": expected_rev + 1, "updated_at": now},
        )
        if not rows:  # nothing matched: someone else saved first, or the row is gone
            raise Conflict("The account changed on another device.")
        return expected_rev + 1

    def delete(self, key: str) -> None:
        self._call("DELETE", {"user_key": f"eq.{key}"})


def load(payload: str, today: date) -> dict:
    return rl.load_state(payload, today)
