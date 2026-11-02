"""Read-only access to LED class devices in sysfs (/sys/class/leds)."""

from __future__ import annotations

import os
import stat
from dataclasses import dataclass
from pathlib import Path

LEDS_ROOT = Path("/sys/class/leds")

# Entries every LED directory has that are not trigger-specific options.
STANDARD_ENTRIES = frozenset(
    {
        "brightness",
        "max_brightness",
        "trigger",
        "uevent",
        "device",
        "subsystem",
        "power",
        "brightness_hw_changed",
    }
)


@dataclass(frozen=True)
class Attr:
    """A trigger-specific attribute such as ``delay_on`` for the timer trigger."""

    name: str
    value: str | None  # None when the file is write-only or unreadable
    writable: bool


@dataclass(frozen=True)
class Led:
    name: str
    brightness: int
    max_brightness: int
    triggers: tuple[str, ...]
    active_trigger: str
    extras: tuple[Attr, ...]


def parse_trigger(text: str) -> tuple[tuple[str, ...], str]:
    """Parse the contents of a ``trigger`` file.

    The kernel lists all triggers separated by spaces and marks the active one
    with brackets, e.g. ``none [audio-mute] disk-activity``.
    """
    names: list[str] = []
    active = "none"
    for token in text.split():
        if token.startswith("[") and token.endswith("]"):
            token = token[1:-1]
            active = token
        names.append(token)
    return tuple(names), active


def _read(path: Path) -> str | None:
    try:
        return path.read_text().strip()
    except OSError:
        return None


def _read_int(path: Path, default: int = 0) -> int:
    text = _read(path)
    try:
        return int(text) if text is not None else default
    except ValueError:
        return default


def _extras(led_dir: Path) -> tuple[Attr, ...]:
    attrs = []
    for entry in sorted(os.scandir(led_dir), key=lambda e: e.name):
        if entry.name in STANDARD_ENTRIES:
            continue
        try:
            st = entry.stat(follow_symlinks=False)
        except OSError:
            continue
        if not stat.S_ISREG(st.st_mode):
            continue
        writable = bool(st.st_mode & stat.S_IWUSR)
        value = _read(Path(entry.path)) if st.st_mode & stat.S_IRUSR else None
        attrs.append(Attr(entry.name, value, writable))
    return tuple(attrs)


def read_led(led_dir: Path) -> Led:
    triggers, active = parse_trigger(_read(led_dir / "trigger") or "")
    return Led(
        name=led_dir.name,
        brightness=_read_int(led_dir / "brightness"),
        max_brightness=_read_int(led_dir / "max_brightness", default=1),
        triggers=triggers,
        active_trigger=active,
        extras=_extras(led_dir),
    )


def discover(root: Path = LEDS_ROOT) -> list[Led]:
    """Return all LEDs under ``root``, sorted by name."""
    if not root.is_dir():
        return []
    return [read_led(p) for p in sorted(root.iterdir(), key=lambda p: p.name) if p.is_dir()]


RFKILL_ROOT = Path("/sys/class/rfkill")


def radios(root: Path = RFKILL_ROOT) -> dict[str, tuple[str, str]]:
    """Map rfkill devices to (type, name), e.g. ``rfkill2 -> ("wlan", "phy0")``."""
    if not root.is_dir():
        return {}
    return {
        p.name: (_read(p / "type") or "", _read(p / "name") or "") for p in sorted(root.iterdir())
    }
