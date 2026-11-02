import io
import json
import os
import subprocess
import sys
from pathlib import Path

import pytest

from ledcontrol import helper
from ledcontrol.privileged import HELPER_PATH


def test_resolve_valid_target(leds_root: Path):
    target = helper.resolve_target(leds_root, "platform::mute", "trigger")
    assert target == leds_root / "platform::mute" / "trigger"


@pytest.mark.parametrize(
    ("led", "attr", "message"),
    [
        ("..", "trigger", "invalid LED"),
        ("platform::mute/../x", "trigger", "invalid LED"),
        ("", "trigger", "invalid LED"),
        (None, "trigger", "invalid LED"),
        ("platform::mute", "../../etc/passwd", "invalid attribute"),
        ("platform::mute", "a\0b", "invalid attribute"),
        ("nope", "trigger", "no such LED"),
        ("platform::mute", "uevent", "may not be written"),
        ("platform::mute", "max_brightness", "may not be written"),
        ("platform::mute", "missing", "has no attribute"),
        ("platform::mute", "power", "not a regular file"),
    ],
)
def test_resolve_rejects(leds_root: Path, led, attr, message):
    with pytest.raises(helper.RequestError, match=message):
        helper.resolve_target(leds_root, led, attr)


def test_resolve_rejects_symlinked_attribute(leds_root: Path, tmp_path: Path):
    outside = tmp_path / "outside"
    outside.write_text("secret")
    (leds_root / "platform::mute" / "evil").symlink_to(outside)
    with pytest.raises(helper.RequestError, match="not a regular file"):
        helper.resolve_target(leds_root, "platform::mute", "evil")


@pytest.mark.skipif(os.geteuid() == 0, reason="root ignores file modes")
def test_resolve_rejects_read_only(leds_root: Path):
    (leds_root / "platform::mute" / "brightness").chmod(0o444)
    with pytest.raises(helper.RequestError, match="read-only"):
        helper.resolve_target(leds_root, "platform::mute", "brightness")


@pytest.mark.parametrize("value", [1, None, "a\nb", "x" * 5000, "a\0b"])
def test_check_value_rejects(value):
    with pytest.raises(helper.RequestError):
        helper.check_value(value)


def test_check_value_strips_trailing_newline():
    assert helper.check_value("none\n") == "none"


def test_handle_writes_value(leds_root: Path):
    reply = helper.handle(
        leds_root, {"id": 7, "led": "platform::mute", "attr": "trigger", "value": "none"}
    )
    assert reply == {"id": 7, "ok": True}
    assert (leds_root / "platform::mute" / "trigger").read_text() == "none"


def test_handle_reports_errors(leds_root: Path):
    assert helper.handle(leds_root, "nope")["ok"] is False
    reply = helper.handle(leds_root, {"id": 1, "led": "x", "attr": "trigger", "value": "a"})
    assert reply["id"] == 1
    assert "no such LED" in reply["error"]


def test_serve_protocol(leds_root: Path):
    requests = "\n".join(
        [
            json.dumps({"id": 1, "led": "platform::mute", "attr": "brightness", "value": "0"}),
            "",
            "not json",
        ]
    )
    out = io.StringIO()
    helper.serve(leds_root, io.StringIO(requests + "\n"), out)
    replies = [json.loads(line) for line in out.getvalue().splitlines()]
    assert replies == [
        {"ready": True},
        {"id": 1, "ok": True},
        {"id": None, "ok": False, "error": "malformed JSON"},
    ]


def test_helper_runs_isolated_as_script(leds_root: Path):
    """The helper must work with ``python -I`` (no package imports)."""
    request = {"id": 1, "led": "platform::mute", "attr": "trigger", "value": "timer"}
    result = subprocess.run(
        [sys.executable, "-I", str(HELPER_PATH), "--root", str(leds_root)],
        input=json.dumps(request) + "\n",
        capture_output=True,
        text=True,
        check=True,
    )
    assert result.stdout.splitlines()[-1] == json.dumps({"id": 1, "ok": True})
    assert (leds_root / "platform::mute" / "trigger").read_text() == "timer"
