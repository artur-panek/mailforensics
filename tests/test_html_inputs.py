from pathlib import Path

import pytest

from mailforensics import cli


@pytest.mark.parametrize("option, content", [
    ("--file", "2026-10-04T12:00:00Z gateway postfix/smtp[1200]: ABC123: status=sent\n"),
    ("--events", '{"timestamp":"2026-10-04T12:00:00Z","queue_id":"ABC123"}\n'),
    ("--queue-file", '{"queue_id":"ABC123","recipients":[]}\n'),
])
@pytest.mark.parametrize("alias", ["same-path", "relative", "symlink", "hardlink"])
def test_html_cannot_overwrite_input(tmp_path, monkeypatch, capsys, option, content, alias):
    source = tmp_path / "input"
    source.write_text(content, encoding="utf-8")
    report = source
    if alias == "relative":
        monkeypatch.chdir(tmp_path)
        report = Path("input")
    elif alias in {"symlink", "hardlink"}:
        report = tmp_path / "report.html"
        if alias == "symlink":
            report.symlink_to(source)
        else:
            report.hardlink_to(source)

    assert cli.main([
        option, str(source), "--no-plugins", "--queue", "ABC123", "--html", str(report),
    ]) == 2
    assert source.read_text(encoding="utf-8") == content
    assert "must not overwrite an input" in capsys.readouterr().err


def test_html_cannot_overwrite_default_log(tmp_path, monkeypatch, capsys):
    source = tmp_path / "mail.log"
    content = "2026-10-04T12:00:00Z gateway postfix/smtp[1200]: ABC123: status=sent\n"
    source.write_text(content, encoding="utf-8")
    monkeypatch.setattr(cli, "DEFAULT_LOGS", (source,))

    assert cli.main(["--no-plugins", "--queue", "ABC123", "--html", str(source)]) == 2
    assert source.read_text(encoding="utf-8") == content
    assert "must not overwrite an input" in capsys.readouterr().err


def test_html_can_replace_previous_report(tmp_path, capsys):
    source = tmp_path / "mail.log"
    source.write_text(
        "2026-10-04T12:00:00Z gateway postfix/smtp[1200]: ABC123: status=sent\n",
        encoding="utf-8",
    )
    report = tmp_path / "report.html"
    report.write_text("previous report", encoding="utf-8")

    assert cli.main([
        "--file", str(source), "--no-plugins", "--queue", "ABC123", "--html", str(report),
    ]) == 0
    assert report.read_text(encoding="utf-8").startswith("<!doctype html>")
    assert capsys.readouterr().err == ""
