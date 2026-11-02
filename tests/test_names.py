import pytest

from ledcontrol.names import title, trigger_info


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
    ("trigger", "label"),
    [
        ("none", "Manual control"),
        ("audio-mute", "Speaker muted"),
        ("cpu3", "CPU core 3 activity"),
        ("kbd-capslock", "Keyboard: Caps Lock"),
        ("BAT0-charging-blink-full-solid", "Battery 0: blink while charging, steady when full"),
        ("phy0assoc", "Wi-Fi connected"),
        ("hci0-power", "Bluetooth adapter on"),
        ("ucsi-source-psy-USBC000:002-online", "USB-C port 2: power source connected"),
        ("AC-online", "Power adapter connected"),
        ("ADP1-online", "Power supply connected"),
    ],
)
def test_known_trigger_detail_is_raw_name(trigger, label):
    assert trigger_info(trigger, RADIOS) == (label, trigger)


@pytest.mark.parametrize(
    ("trigger", "expected"),
    [
        ("rfkill0", ("Bluetooth radio enabled", "rfkill0 · tpacpi_bluetooth_sw")),
        ("rfkill2", ("Wi-Fi radio enabled", "rfkill2 · phy0")),
        ("rfkill9", ("Radio enabled", "rfkill9")),
        ("kbd-unknownlock", ("kbd-unknownlock", "")),
        ("BAT1-unknown", ("BAT1-unknown", "")),
        ("something-new", ("something-new", "")),
    ],
)
def test_trigger_info_special_cases(trigger, expected):
    assert trigger_info(trigger, RADIOS) == expected


@pytest.mark.parametrize(
    "trigger", ["none", "timer", "oneshot", "cpu", "rfkill0", "phy0rx", "BAT0-charging", "mtd"]
)
def test_labels_have_no_brackets_or_dashes(trigger):
    label, _ = trigger_info(trigger, RADIOS)
    assert not any(c in label for c in "()[]—")
