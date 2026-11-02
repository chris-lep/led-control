import pytest

from ledcontrol.names import title


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
