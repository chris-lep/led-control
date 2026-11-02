import pytest

from ledcontrol import quirks


@pytest.mark.parametrize(
    ("name", "expected"),
    [
        ("tpacpi::power", True),
        ("tpacpi::lid_logo_dot", True),
        ("tpacpi:orange:batt", True),
        ("tpacpi::kbd_backlight", False),
        ("tpacpi::thinklight", False),
        ("platform::mute", False),
    ],
)
def test_is_firmware_led(name, expected):
    assert quirks.is_firmware_led(name) is expected


def test_boot_brightness():
    assert quirks.boot_brightness("tpacpi::power", 0, 255) == 255
    assert quirks.boot_brightness("tpacpi::lid_logo_dot", 255, 255) == 255
    assert quirks.boot_brightness("tpacpi::standby", 0, 255) == 0
    assert quirks.boot_brightness("platform::mute", 0, 1) == 0
