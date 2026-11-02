from pathlib import Path

import pytest
from conftest import make_led

from ledcontrol import sysfs


@pytest.mark.parametrize(
    ("text", "expected"),
    [
        ("none [audio-mute] timer\n", (("none", "audio-mute", "timer"), "audio-mute")),
        ("[none] timer", (("none", "timer"), "none")),
        ("", ((), "none")),
        ("none timer", (("none", "timer"), "none")),
    ],
)
def test_parse_trigger(text, expected):
    assert sysfs.parse_trigger(text) == expected


def test_discover_reads_all_leds_sorted(leds_root: Path):
    leds = sysfs.discover(leds_root)
    assert [led.name for led in leds] == [
        "platform::mute",
        "tpacpi::kbd_backlight",
        "tpacpi::lid_logo_dot",
    ]
    mute = leds[0]
    assert mute.brightness == 1
    assert mute.max_brightness == 1
    assert mute.active_trigger == "audio-mute"
    assert mute.triggers == ("none", "audio-mute", "timer")
    assert mute.extras == ()


def test_extras_are_trigger_specific_files(leds_root: Path):
    dot = sysfs.read_led(leds_root / "tpacpi::lid_logo_dot")
    assert dot.extras == (
        sysfs.Attr("delay_off", "500", True),
        sysfs.Attr("delay_on", "500", True),
    )


def test_write_only_and_read_only_extras(tmp_path: Path):
    root = make_led(tmp_path, "x", extras={"shot": ("", 0o200), "hw": ("1", 0o444)})
    led = sysfs.read_led(root / "x")
    assert led.extras == (sysfs.Attr("hw", "1", False), sysfs.Attr("shot", None, True))


def test_missing_root_gives_no_leds(tmp_path: Path):
    assert sysfs.discover(tmp_path / "nope") == []


def test_unreadable_values_fall_back(tmp_path: Path):
    root = make_led(tmp_path, "x")
    (root / "x" / "brightness").write_text("garbage")
    (root / "x" / "max_brightness").unlink()
    led = sysfs.read_led(root / "x")
    assert (led.brightness, led.max_brightness) == (0, 1)


def test_radios(tmp_path: Path):
    for name, kind, dev in [("rfkill0", "bluetooth", "hci0"), ("rfkill1", "wlan", "phy0")]:
        (tmp_path / name).mkdir()
        (tmp_path / name / "type").write_text(kind + "\n")
        (tmp_path / name / "name").write_text(dev + "\n")
    assert sysfs.radios(tmp_path) == {"rfkill0": ("bluetooth", "hci0"), "rfkill1": ("wlan", "phy0")}
    assert sysfs.radios(tmp_path / "missing") == {}
