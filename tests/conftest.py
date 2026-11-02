"""Fake /sys/class/leds trees for tests."""

from __future__ import annotations

from pathlib import Path

import pytest


def make_led(
    tmp_path: Path,
    name: str,
    *,
    brightness: int = 0,
    max_brightness: int = 1,
    trigger: str = "[none] timer disk-activity",
    extras: dict[str, tuple[str, int]] | None = None,
) -> Path:
    """Create a device directory plus a class symlink, like real sysfs does."""
    device = tmp_path / "devices" / name.replace(":", "_")
    device.mkdir(parents=True)
    (device / "brightness").write_text(f"{brightness}\n")
    (device / "max_brightness").write_text(f"{max_brightness}\n")
    (device / "max_brightness").chmod(0o444)
    (device / "trigger").write_text(trigger + "\n")
    (device / "uevent").write_text("")
    (device / "power").mkdir()
    for attr, (value, mode) in (extras or {}).items():
        (device / attr).write_text(value)
        (device / attr).chmod(mode)
    root = tmp_path / "leds"
    root.mkdir(exist_ok=True)
    (root / name).symlink_to(device)
    return root


@pytest.fixture
def leds_root(tmp_path: Path) -> Path:
    make_led(tmp_path, "platform::mute", brightness=1, trigger="none [audio-mute] timer")
    make_led(tmp_path, "tpacpi::kbd_backlight", max_brightness=2)
    return make_led(
        tmp_path,
        "tpacpi::lid_logo_dot",
        brightness=255,
        max_brightness=255,
        trigger="none [timer] disk-activity",
        extras={"delay_on": ("500\n", 0o644), "delay_off": ("500\n", 0o644)},
    )
