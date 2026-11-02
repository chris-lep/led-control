"""GUI-independent operations: read LEDs, change them, reset to defaults."""

from __future__ import annotations

import dataclasses
from pathlib import Path

from . import quirks, sysfs
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
        return [self._effective(led) for led in sysfs.discover(self.root)]

    def led(self, name: str) -> Led:
        return self._effective(sysfs.read_led(self.root / name))

    def _effective(self, led: Led) -> Led:
        """Replace the meaningless 0 of never-written firmware LEDs by a guess."""
        if (
            quirks.is_firmware_led(led.name)
            and led.name not in self.defaults.touched
            and led.active_trigger == "none"
        ):
            guess = quirks.boot_brightness(led.name, led.brightness, led.max_brightness)
            if guess != led.brightness:
                return dataclasses.replace(led, brightness=guess)
        return led

    def _touch(self, name: str) -> None:
        if quirks.is_firmware_led(name):
            self.defaults.mark_touched(name)

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
        self._touch(name)

    def reset(self, name: str) -> None:
        default = self.defaults.get(name)
        if default is None:
            raise WriteError(f"{name}: no default recorded")
        for attr, value in restore_ops(default):
            self.writer.write(name, attr, value)
            self._touch(name)

    def identify_plan(
        self, name: str, toggles: int = 8
    ) -> tuple[list[tuple[str, str]], list[tuple[str, str]]]:
        """Writes that blink an LED, and the writes that restore it afterwards.

        The trigger is detached first so it can't fight the blinking, and the
        first toggle is the opposite of the current state, so it is visible.
        """
        led = self.led(name)
        blink = [] if led.active_trigger == "none" else [("trigger", "none")]
        lit = led.brightness == 0
        for _ in range(toggles):
            blink.append(("brightness", str(led.max_brightness if lit else 0)))
            lit = not lit
        return blink, restore_ops(of(led))

    def reset_all(self) -> list[str]:
        """Reset every LED; returns error messages for the ones that failed."""
        errors = []
        for led in self.leds():
            try:
                self.reset(led.name)
            except WriteError as exc:
                errors.append(str(exc))
        return errors
