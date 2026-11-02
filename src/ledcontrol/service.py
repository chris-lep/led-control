"""GUI-independent operations: read LEDs, change them, reset to defaults."""

from __future__ import annotations

from pathlib import Path

from . import sysfs
from .defaults import DefaultsStore, of, restore_ops
from .privileged import WriteError, Writer
from .sysfs import Led


class LedService:
    def __init__(
        self, writer: Writer, defaults: DefaultsStore, root: Path = sysfs.LEDS_ROOT
    ) -> None:
        self.writer = writer
        self.defaults = defaults
        self.root = root

    def leds(self) -> list[Led]:
        return sysfs.discover(self.root)

    def led(self, name: str) -> Led:
        return sysfs.read_led(self.root / name)

    def load_defaults(self) -> None:
        self.defaults.load(self.leds())

    def capture_defaults(self) -> None:
        self.defaults.capture(self.leds())

    def is_default(self, led: Led) -> bool:
        default = self.defaults.get(led.name)
        if default is None:
            return True
        current = of(led)
        if default.trigger != "none":
            return current.trigger == default.trigger
        return current == default

    def set(self, name: str, attr: str, value: str) -> None:
        self.writer.write(name, attr, value)

    def reset(self, name: str) -> None:
        default = self.defaults.get(name)
        if default is None:
            raise WriteError(f"{name}: no default recorded")
        for attr, value in restore_ops(default):
            self.writer.write(name, attr, value)

    def reset_all(self) -> list[str]:
        """Reset every LED; returns error messages for the ones that failed."""
        errors = []
        for led in self.leds():
            try:
                self.reset(led.name)
            except WriteError as exc:
                errors.append(str(exc))
        return errors
