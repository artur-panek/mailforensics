from mailforensics.branding import banner
from mailforensics.cli import main
from mailforensics.completions import completion_script
from mailforensics.console import supports_color
from mailforensics.demo import demo_trace
from mailforensics.render import render_explain


def test_forensic_banner_has_identity():
    assert "MAILFORENSICS" in banner()
    assert "trace the evidence" in banner()


def test_no_color_disables_auto(monkeypatch):
    monkeypatch.setenv("NO_COLOR", "")
    assert supports_color("auto") is False
    assert supports_color("always") is True


def test_demo_deferred_has_live_queue():
    trace = demo_trace("deferred")
    assert trace.status == "deferred"
    output = render_explain(trace, ascii_only=True)
    assert "QUEUE NOW" in output
    assert "queued-for-retry" in output


def test_completion_scripts_exist():
    for shell in ("bash", "zsh", "fish"):
        assert "mailforensics" in completion_script(shell)


def test_root_help_is_zero_and_shows_commands(capsys):
    assert main(["--help"]) == 0
    output = capsys.readouterr().out
    assert "mailforensics demo" in output
    assert "mailforensics doctor" in output


def test_demo_command_is_zero(capsys):
    assert main(["demo", "delivered", "--color", "never", "--ascii"]) == 0
    output = capsys.readouterr().out
    assert "MAILFORENSICS" in output
    assert "MAILBOX" in output
