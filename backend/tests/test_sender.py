import pytest

from agent import sender
from agent.sender import send_report, split_slack, to_slack


def test_to_slack_converts_headings_and_bold():
    assert to_slack("# Title\n## Sec\n**bold** text\n- item") == "*Title*\n*Sec*\n*bold* text\n- item"


def test_split_slack_short_text_is_one_chunk():
    assert split_slack("hello", limit=50) == ["hello"]


def test_split_slack_splits_at_blank_lines_within_limit():
    text = "\n\n".join(["a" * 40, "b" * 40, "c" * 40])
    chunks = split_slack(text, limit=90)
    assert chunks == ["a" * 40 + "\n\n" + "b" * 40, "c" * 40]


def test_split_slack_hard_splits_a_single_oversized_block():
    chunks = split_slack("x" * 250, limit=100)
    assert [len(c) for c in chunks] == [100, 100, 50]


@pytest.fixture
def env(monkeypatch, tmp_path):
    for k in ("SMTP_HOST", "REPORT_TO", "SLACK_WEBHOOK_URL"):
        monkeypatch.delenv(k, raising=False)
    monkeypatch.chdir(tmp_path)
    posts = []

    class R:
        def raise_for_status(self): pass

    monkeypatch.setattr(sender.requests, "post", lambda url, json=None, timeout=None: posts.append((url, json)) or R())
    return posts


def test_send_report_posts_to_slack_when_webhook_set(env, monkeypatch):
    monkeypatch.setenv("SLACK_WEBHOOK_URL", "https://hooks.slack.com/services/T/B/x")
    msg = send_report("# Weekly\nall good", subject="Weekly Status Report")
    assert env == [("https://hooks.slack.com/services/T/B/x", {"text": "*Weekly*\nall good"})]
    assert "Slack" in msg


def test_send_report_saves_file_when_nothing_configured(env, tmp_path):
    assert "saved" in send_report("hi")
    assert env == [] and list((tmp_path / "reports").glob("*.md"))


def test_send_report_slack_error_is_raised(env, monkeypatch):
    monkeypatch.setenv("SLACK_WEBHOOK_URL", "https://hooks.slack.com/services/T/B/x")
    def boom(*a, **k): raise RuntimeError("slack down")
    monkeypatch.setattr(sender.requests, "post", boom)
    with pytest.raises(RuntimeError):
        send_report("x")


def test_email_failure_does_not_block_slack(env, monkeypatch):
    monkeypatch.setenv("SMTP_HOST", "smtp.example.com")
    monkeypatch.setenv("REPORT_TO", "a@b.c")
    monkeypatch.setenv("SLACK_WEBHOOK_URL", "https://hooks.slack.com/services/T/B/x")
    def bad_smtp(*a, **k): raise OSError("Connection unexpectedly closed")
    monkeypatch.setattr(sender.smtplib, "SMTP", bad_smtp)
    msg = send_report("hi")
    assert len(env) == 1 and "Slack" in msg and "Email failed" in msg


def test_all_channels_failing_raises(env, monkeypatch):
    monkeypatch.setenv("SMTP_HOST", "smtp.example.com")
    monkeypatch.setenv("REPORT_TO", "a@b.c")
    def bad_smtp(*a, **k): raise OSError("closed")
    monkeypatch.setattr(sender.smtplib, "SMTP", bad_smtp)
    with pytest.raises(RuntimeError, match="Email failed"):
        send_report("hi")
