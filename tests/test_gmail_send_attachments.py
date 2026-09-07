"""Outgoing attachments on gmail_send / gmail_draft / gmail_reply.

Two properties are pinned:

1. The bytes that leave are the bytes on disk. The raw payload is decoded and
   re-parsed with the stdlib so the assertion is on the MIME message Gmail will
   actually receive, not on our own intermediate structure.
2. A missing file fails BEFORE any API call. `send` is exercised with a service
   that raises if touched: if the guard ever moves after the network call, the
   test goes red on the fake service, not on a silently attachment-less mail.
"""

from __future__ import annotations

import base64
import email
import email.policy
from email.message import EmailMessage
from unittest.mock import MagicMock

import pytest

import gmail_tools


def _parse(raw: str) -> EmailMessage:
    parsed = email.message_from_bytes(
        base64.urlsafe_b64decode(raw), policy=email.policy.default
    )
    assert isinstance(parsed, EmailMessage)
    return parsed


def test_build_raw_carries_file_bytes_verbatim(tmp_path):
    pdf = tmp_path / "lettre.pdf"
    payload = b"%PDF-1.4\n" + bytes(range(256)) * 40  # binary, not base64-safe by accident
    pdf.write_bytes(payload)

    raw, _ = gmail_tools._build_raw(
        ["a@example.com"], "sujet", "corps", attachments=[str(pdf)]
    )
    msg = _parse(raw)

    assert msg.get_body().get_content().strip() == "corps"
    parts = list(msg.iter_attachments())
    assert [p.get_filename() for p in parts] == ["lettre.pdf"]
    assert parts[0].get_content_type() == "application/pdf"
    assert parts[0].get_content() == payload


def test_build_raw_without_attachments_stays_single_part():
    raw, _ = gmail_tools._build_raw(["a@example.com"], "s", "b")
    msg = _parse(raw)
    assert not msg.is_multipart()
    assert list(msg.iter_attachments()) == []


def test_missing_attachment_raises_before_any_api_call(tmp_path, monkeypatch):
    svc = MagicMock()
    svc.users.side_effect = AssertionError("API touched before attachment check")
    monkeypatch.setattr(gmail_tools, "service", lambda *a, **k: svc)

    with pytest.raises(FileNotFoundError, match="Attachment not found"):
        gmail_tools.send(
            ["a@example.com"], "s", "b", attachments=[str(tmp_path / "absent.pdf")]
        )


def test_send_dry_run_reports_attachments(tmp_path, monkeypatch):
    monkeypatch.setattr(
        gmail_tools, "service", lambda *a, **k: (_ for _ in ()).throw(AssertionError("no API"))
    )
    f = tmp_path / "x.txt"
    f.write_text("hello")
    out = gmail_tools.send(["a@example.com"], "s", "b", attachments=[str(f)], dry_run=True)
    assert out["dry_run"] is True
    assert out["attachments"] == [{"filename": "x.txt", "size": 5}]
