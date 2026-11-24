import json
from datetime import date
from types import SimpleNamespace

import pytest

import rto_logic as rl
import sync

TODAY = date(2026, 11, 23)


def state(office=(), pto=(), sick=(), other=(), **policy):
    p = rl.default_policy(TODAY)
    if policy:
        p = rl.Policy(start=p.start, end=p.end, **policy)
    return {"policy": p, "office": set(office), "pto": set(pto), "sick": set(sick), "other": set(other), "ui": {}}


def nov(*days):
    return {date(2026, 11, d) for d in days}


# ----------------------------------------------------------------- identity


def test_user_key_is_stable_scrambled_and_peppered():
    a = sync.user_key("https://accounts.google.com:12345", "pepper")
    assert a == sync.user_key("https://accounts.google.com:12345", "pepper")
    assert a != sync.user_key("https://accounts.google.com:12346", "pepper")
    assert a != sync.user_key("https://accounts.google.com:12345", "other")
    assert "12345" not in a and len(a) == 64


def test_content_hash_ignores_appearance_but_not_days():
    p = rl.default_policy(TODAY)
    h = sync.content_hash(p, nov(2), set(), set(), set())
    assert h == sync.content_hash(p, nov(2), set(), set(), set())
    assert h != sync.content_hash(p, nov(2, 3), set(), set(), set())
    assert h != sync.content_hash(rl.Policy(start=p.start, end=p.end, percent=50), nov(2), set(), set(), set())


# ---------------------------------------------------------- signing in


def test_first_sign_in_pushes_this_browser_to_the_empty_account():
    assert sync.decide(state(office=nov(2, 3)), False, None) == sync.PUSH


def test_an_unchanged_copy_of_the_account_takes_the_account():
    # The laptop synced, then the phone added a day: the laptop must not ask or overwrite.
    assert sync.decide(state(office=nov(2)), True, state(office=nov(2, 3))) == sync.TAKE


def test_a_new_device_with_nothing_marked_takes_the_account():
    assert sync.decide(state(), False, state(office=nov(2, 3), pto=nov(20))) == sync.TAKE


def test_a_browser_whose_days_are_already_in_the_account_takes_the_account():
    assert sync.decide(state(office=nov(2)), False, state(office=nov(2, 3))) == sync.TAKE


def test_a_browser_with_days_the_account_lacks_asks():
    assert sync.decide(state(office=nov(2, 4)), False, state(office=nov(2, 3))) == sync.ASK
    # the same date marked differently also counts
    assert sync.decide(state(pto=nov(2)), False, state(office=nov(2))) == sync.ASK


def test_merge_keeps_the_account_and_adds_only_unmarked_dates():
    account = state(office=nov(2, 3), pto=nov(20), percent=50)
    browser = state(office=nov(4), pto=nov(2), sick=nov(5), other=nov(20))
    got = sync.merge(account, browser)
    assert got["policy"].percent == 50  # the account's policy
    assert got["office"] == nov(2, 3, 4)  # Nov 2 stays in office, not the browser's PTO
    assert got["pto"] == nov(20)  # Nov 20 stays PTO, not the browser's other absence
    assert got["sick"] == nov(5) and got["other"] == set()
    assert sync.extra_days(account, browser) == 4
    assert sync.extra_days(account, state(office=nov(2))) == 0


# ------------------------------------------------------------------ stores


@pytest.fixture(params=["memory", "file"])
def store(request, tmp_path):
    return sync.MemoryStore() if request.param == "memory" else sync.FileStore(str(tmp_path / "s" / "accounts.json"))


def test_store_round_trip_and_revisions(store):
    assert store.get("k") is None
    assert store.put("k", "one", None) == 1
    assert store.get("k") == sync.Remote("one", 1)
    assert store.put("k", "two", 1) == 2
    assert store.get("k") == sync.Remote("two", 2)
    store.delete("k")
    assert store.get("k") is None


def test_a_save_from_a_stale_copy_is_refused(store):
    store.put("k", "one", None)
    laptop_rev = phone_rev = store.get("k").rev
    store.put("k", "phone edit", phone_rev)
    with pytest.raises(sync.Conflict):
        store.put("k", "laptop edit", laptop_rev)
    assert store.get("k").payload == "phone edit"
    with pytest.raises(sync.Conflict):  # a second first-save for the same account
        store.put("k", "again", None)


def test_file_store_survives_a_restart(tmp_path):
    path = str(tmp_path / "accounts.json")
    sync.FileStore(path).put("k", "one", None)
    assert sync.FileStore(path).get("k") == sync.Remote("one", 1)


class FakeHttp:
    """Answers like Supabase's REST interface for one table."""

    def __init__(self):
        self.rows, self.calls, self.fail = {}, [], None

    def request(self, method, url, params=None, json=None, headers=None, timeout=None):
        self.calls.append((method, url, params, json, headers))
        if self.fail:
            if isinstance(self.fail, Exception):
                raise self.fail
            return SimpleNamespace(status_code=self.fail, content=b"{}", json=lambda: {})
        key = (params or {}).get("user_key", "eq.")[3:] or (json or {}).get("user_key")
        out, status = [], 200
        if method == "GET":
            out = [self.rows[key]] if key in self.rows else []
        elif method == "POST":
            if key in self.rows:
                status = 409
            else:
                self.rows[key] = {"payload": json["payload"], "rev": json["rev"]}
                out, status = [self.rows[key]], 201
        elif method == "PATCH":
            want = int(params["rev"][3:])
            if key in self.rows and self.rows[key]["rev"] == want:
                self.rows[key] = {"payload": json["payload"], "rev": json["rev"]}
                out = [self.rows[key]]
        elif method == "DELETE":
            self.rows.pop(key, None)
        body = __import__("json").dumps(out).encode()
        return SimpleNamespace(status_code=status, content=body, json=lambda: out)


def supabase():
    http = FakeHttp()
    return sync.SupabaseStore("https://example.supabase.co/", "secret-key", http=http), http


def test_supabase_store_round_trip_and_conflicts():
    store, http = supabase()
    assert store.get("k") is None
    assert store.put("k", "one", None) == 1
    assert store.put("k", "two", 1) == 2
    assert store.get("k") == sync.Remote("two", 2)
    with pytest.raises(sync.Conflict):
        store.put("k", "stale", 1)
    with pytest.raises(sync.Conflict):
        store.put("k", "again", None)
    store.delete("k")
    assert store.get("k") is None


def test_supabase_store_sends_the_key_and_filters_by_account():
    store, http = supabase()
    store.put("abc", "one", None)
    store.put("abc", "two", 1)
    method, url, params, body, headers = http.calls[-1]
    assert url == "https://example.supabase.co/rest/v1/rto_state"
    assert (method, params) == ("PATCH", {"user_key": "eq.abc", "rev": "eq.1"})
    assert body["payload"] == "two" and body["rev"] == 2 and "updated_at" in body
    assert headers["apikey"] == "secret-key" and headers["Authorization"] == "Bearer secret-key"
    assert "secret-key" not in json.dumps(body)


@pytest.mark.parametrize("failure", [500, 401, TimeoutError("timed out")])
def test_supabase_store_turns_failures_into_store_errors(failure):
    store, http = supabase()
    http.fail = failure
    with pytest.raises(sync.StoreError) as err:
        store.get("k")
    assert not isinstance(err.value, sync.Conflict)
    assert "secret-key" not in str(err.value)


def test_what_is_stored_is_the_same_json_the_browser_keeps():
    p = rl.default_policy(TODAY)
    payload = rl.dump_state(p, nov(2), nov(20), set(), set(), {"theme": "garden", "mode": "light"})
    store = sync.MemoryStore()
    store.put("k", payload, None)
    got = sync.load(store.get("k").payload, TODAY)
    assert got["office"] == nov(2) and got["pto"] == nov(20) and got["policy"] == p
    assert "email" not in payload and "name" not in json.loads(payload)
