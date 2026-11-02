"""Hardware facts that sysfs does not tell us.

ThinkPad firmware LEDs (``tpacpi::power``, ``tpacpi::lid_logo_dot``, …) are
driven by the embedded controller. On current models thinkpad_acpi cannot read
them back: ``brightness`` shows the kernel's cached value, which is 0 after boot
even though the firmware has the power LED and the lid dot switched on. They
also only know on and off (and blink), although they report
``max_brightness=255``.

The keyboard backlight and ThinkLight use different code in the driver and are
not affected.
"""

from __future__ import annotations

_TPACPI_READABLE = frozenset({"tpacpi::kbd_backlight", "tpacpi::thinklight"})

# Firmware LEDs that are lit while the machine is running.
_ON_AT_BOOT = frozenset({"tpacpi::power", "tpacpi::lid_logo_dot"})


def is_firmware_led(name: str) -> bool:
    """True for ThinkPad EC LEDs: on/off only and not readable until written."""
    return name.startswith("tpacpi:") and name not in _TPACPI_READABLE


def boot_brightness(name: str, reported: int, max_brightness: int) -> int:
    """Best guess at the brightness an LED really had at boot."""
    if name in _ON_AT_BOOT and reported == 0:
        return max_brightness
    return reported
