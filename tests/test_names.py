import pytest

from ledcontrol.names import title, trigger_choice, trigger_title


@pytest.mark.parametrize(
    ("name", "expected"),
    [
        ("tpacpi::lid_logo_dot", "Lid logo dot (the “i” in ThinkPad)"),
        ("tpacpi::power", "Power button"),
        ("platform::mute", "Speaker mute key"),
        ("platform::micmute", "Microphone mute key"),
        ("input3::capslock", "Caps Lock"),
        ("input17::numlock", "Num Lock"),
        ("phy0-led", "Wi-Fi"),
        ("asus::kbd_backlight", "Keyboard backlight"),
        ("foo:red:status_light", "Status light (red)"),
        ("hci0-power", "Hci0 power"),
        (":::", ":::"),
    ],
)
def test_title(name, expected):
    assert title(name) == expected


RADIOS = {"rfkill0": ("bluetooth", "tpacpi_bluetooth_sw"), "rfkill2": ("wlan", "phy0")}


@pytest.mark.parametrize(
    ("trigger", "expected"),
    [
        ("none", "None (set brightness by hand)"),
        ("audio-mute", "Speaker muted"),
        ("cpu3", "CPU core 3 activity"),
        ("kbd-capslock", "Keyboard: Caps Lock"),
        ("kbd-unknownlock", "kbd-unknownlock"),
        ("BAT0-charging-blink-full-solid", "Battery 0: blink while charging, steady when full"),
        ("BAT1-unknown", "BAT1-unknown"),
        ("phy0assoc", "Wi-Fi connected (phy0)"),
        ("hci0-power", "Bluetooth adapter on (hci0)"),
        ("ucsi-source-psy-USBC000:002-online", "USB-C port 2: power source connected"),
        ("AC-online", "Power adapter connected"),
        ("ADP1-online", "Power supply connected (ADP1)"),
        ("rfkill0", "Bluetooth radio enabled (tpacpi_bluetooth_sw)"),
        ("rfkill2", "Wi-Fi radio enabled (phy0)"),
        ("rfkill9", "Radio enabled (rfkill9)"),
        ("something-new", "something-new"),
    ],
)
def test_trigger_title(trigger, expected):
    assert trigger_title(trigger, RADIOS) == expected


def test_trigger_choice_shows_raw_name():
    assert trigger_choice("audio-mute") == "Speaker muted — audio-mute"
    assert trigger_choice("something-new") == "something-new"
