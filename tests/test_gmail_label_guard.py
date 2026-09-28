"""YKS: label_apply must never take a message out of the inbox (28 Sept 2026)."""

import pytest

import gmail_tools


@pytest.fixture
def no_service(monkeypatch):
    calls = []
    monkeypatch.setattr(gmail_tools, "service", lambda *a, **k: calls.append(1))
    return calls


@pytest.mark.parametrize(
    "kwargs",
    [
        {"remove": ["INBOX"]},
        {"remove": ["UNREAD", " inbox "]},
        {"add": ["SPAM"]},
        {"add": ["trash"]},
    ],
)
def test_leaving_the_inbox_is_refused_before_any_call(no_service, kwargs):
    with pytest.raises(ValueError, match="never archives"):
        gmail_tools.label_apply(["m1"], **kwargs)
    assert no_service == []
