"""Per-boot snapshot of each LED's original state, used for "Reset".

The kernel has no "default" attribute, and every change made through sysfs is
lost on reboot. So the state the LEDs had when the app first ran during the
current boot is treated as the default. The snapshot lives in
``~/.cache/led-control/defaults-<boot_id>.json`` (not in /run/user, because that
is wiped on logout while LED changes survive until reboot).
"""

from __future__ import annotations

import json
import os
from collections.abc import Iterable
from dataclasses import asdict, dataclass
from pathlib import Path

from .sysfs import Led

BOOT_ID_PATH = Path("/proc/sys/kernel/random/boot_id")


@dataclass(frozen=True)
class LedDefault:
    trigger: str
    brightness: int


def boot_id(path: Path = BOOT_ID_PATH) -> str:
    return path.read_text().strip()


def cache_dir() -> Path:
    base = os.environ.get("XDG_CACHE_HOME") or Path.home() / ".cache"
    return Path(base) / "led-control"


def of(led: Led) -> LedDefault:
    return LedDefault(trigger=led.active_trigger, brightness=led.brightness)


class DefaultsStore:
    def __init__(self, directory: Path, boot: str) -> None:
        self.path = directory / f"defaults-{boot}.json"
        self._defaults: dict[str, LedDefault] = {}

    def get(self, name: str) -> LedDefault | None:
        return self._defaults.get(name)

    def load(self, leds: Iterable[Led]) -> None:
        """Load this boot's snapshot, adding any LED not seen before.

        Snapshots from earlier boots are deleted.
        """
        self.path.parent.mkdir(parents=True, exist_ok=True)
        for old in self.path.parent.glob("defaults-*.json"):
            if old != self.path:
                old.unlink(missing_ok=True)
        try:
            raw = json.loads(self.path.read_text())
            self._defaults = {name: LedDefault(**d) for name, d in raw.items()}
        except (FileNotFoundError, json.JSONDecodeError, TypeError):
            self._defaults = {}
        new = {led.name: of(led) for led in leds if led.name not in self._defaults}
        if new or not self.path.exists():
            self._defaults.update(new)
            self._save()

    def capture(self, leds: Iterable[Led]) -> None:
        """Replace the snapshot with the current state."""
        self._defaults = {led.name: of(led) for led in leds}
        self._save()

    def _save(self) -> None:
        data = {name: asdict(d) for name, d in sorted(self._defaults.items())}
        tmp = self.path.with_suffix(".tmp")
        tmp.write_text(json.dumps(data, indent=2) + "\n")
        tmp.replace(self.path)


def restore_ops(default: LedDefault) -> list[tuple[str, str]]:
    """The (attribute, value) writes that bring an LED back to ``default``.

    The trigger goes first: switching triggers resets brightness. Brightness is
    only restored for "none", since any other trigger drives it on its own.
    """
    ops = [("trigger", default.trigger)]
    if default.trigger == "none":
        ops.append(("brightness", str(default.brightness)))
    return ops
