# Changelog

All notable changes to this project are documented here. The format follows
[Keep a Changelog](https://keepachangelog.com/en/1.1.0/), and versions follow
[Semantic Versioning](https://semver.org/).

## [Unreleased]

## [0.1.0] - 2026-11-21

### Added

- GTK 4 app that lists every LED in `/sys/class/leds` with a readable title.
- Per LED: the trigger (readable name plus the raw kernel name), the brightness (a switch for
  on/off LEDs, a slider for dimmable ones) and trigger-specific options such as `delay_on` /
  `delay_off` for `timer`.
- Reset one LED or all of them to the state recorded at the first start after boot;
  **Use current state as defaults** in the menu.
- **Identify** blinks an LED a few times and then restores its previous state.
- ThinkPad firmware LEDs (`tpacpi::power`, `tpacpi::lid_logo_dot`, …) shown as on/off, with
  their unreadable state at boot handled.
- Asks for the password once (polkit) and keeps a small validating root helper for the
  session; opens read-only if cancelled, with **Unlock** to retry.
- `make install` / `make uninstall`: per-user launcher, menu entry and icon.
- All changes are temporary: they are written to sysfs only and are gone after a reboot.

[Unreleased]: https://github.com/chris-lep/led-control/compare/v0.1.0...HEAD
[0.1.0]: https://github.com/chris-lep/led-control/releases/tag/v0.1.0
