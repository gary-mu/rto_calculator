import legal


def test_both_pages_exist_and_are_dated():
    assert set(legal.PAGES) == {"privacy", "terms"}
    for title, body in legal.PAGES.values():
        assert body.lstrip().startswith(f"# {title}")
        assert f"Last updated: {legal.UPDATED}" in body


def test_no_placeholders_are_published():
    for _, body in legal.PAGES.values():
        for leftover in ("example.com", "your-app-email", "TODO", "[your", "{"):
            assert leftover not in body


def test_privacy_policy_does_not_overclaim():
    text = legal.PRIVACY
    # The host sets analytics cookies the app does not control: say so.
    assert "There are no ads and no analytics" not in text
    assert "Streamlit Community Cloud" in text and "analytics cookies" in text
    # Deleting an account cannot promise more than the live table.
    assert "backups" in text


def test_contact_uses_an_email_once_one_is_set(monkeypatch):
    assert "mailto:" not in legal._contact("Questions")
    monkeypatch.setattr(legal, "CONTACT_EMAIL", "privacy@rto.test")
    line = legal._contact("Questions")
    assert "mailto:privacy@rto.test" in line and "issues" in line
