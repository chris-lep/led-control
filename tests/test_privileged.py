import sys
from pathlib import Path

import pytest

from ledcontrol.privileged import HELPER_PATH, HelperClient, WriteError, pkexec_argv


def client_for(root: Path) -> HelperClient:
    return HelperClient([sys.executable, "-I", str(HELPER_PATH), "--root", str(root)])


def test_pkexec_argv_uses_isolated_helper():
    argv = pkexec_argv()
    assert argv[0] == "pkexec"
    assert argv[2:] == ["-I", str(HELPER_PATH)]
    assert Path(argv[1]).is_absolute()


def test_write_round_trip(leds_root: Path):
    client = client_for(leds_root)
    client.start()
    try:
        client.write("platform::mute", "trigger", "none")
        client.write("platform::mute", "brightness", "0")
    finally:
        client.close()
    assert (leds_root / "platform::mute" / "trigger").read_text() == "none"
    assert (leds_root / "platform::mute" / "brightness").read_text() == "0"
    assert not client.running


def test_write_error_is_raised(leds_root: Path):
    client = client_for(leds_root)
    client.start()
    try:
        with pytest.raises(WriteError, match="no such LED"):
            client.write("missing", "trigger", "none")
        client.write("platform::mute", "trigger", "none")  # still usable
    finally:
        client.close()


def test_write_without_start_fails():
    with pytest.raises(WriteError, match="not authorized"):
        HelperClient(["true"]).write("a", "b", "c")


@pytest.mark.parametrize(
    ("argv", "message"),
    [
        (["false"], "exit code 1"),
        ([sys.executable, "-c", "import sys; sys.exit(126)"], "cancelled or denied"),
        (["/nonexistent/binary"], "cannot start helper"),
        ([sys.executable, "-c", "print('hello')"], "did not start"),
    ],
)
def test_start_failures(argv, message):
    client = HelperClient(argv)
    with pytest.raises(WriteError, match=message):
        client.start()
    assert not client.running
