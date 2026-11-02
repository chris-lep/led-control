# LED Control

A small GTK 4 app for the LEDs the kernel exposes in `/sys/class/leds`
(on this ThinkPad: mute/mic-mute, lid logo dot, keyboard backlight, power, lock keys, …).

For every LED you can set:

- the **trigger** (what drives the LED: `none`, `audio-mute`, `disk-activity`, `timer`, …)
- the **brightness** (switch for on/off LEDs, slider for dimmable ones)
- **trigger-specific options**, which appear when the trigger provides them
  (e.g. `delay_on` / `delay_off` for `timer`)

and **reset** one LED or all of them to their defaults.

**All changes are temporary.** They are written to sysfs only and are gone after a reboot.

## Running

```sh
bin/led-control
```

The app asks for your password once (polkit) and then runs a small root helper
for the rest of the session. If you cancel, it opens read-only; click **Unlock** to retry.

Requirements, all preinstalled on Linux Mint 22: `/usr/bin/python3` with PyGObject and
GTK 4 (`python3-gi`, `gir1.2-gtk-4.0`), and `pkexec`. The launcher always uses the system
Python, because a conda/venv Python usually has no GTK bindings.

## How "defaults" work

The kernel has no "default" setting. So the first time the app runs after a boot, it
records every LED's trigger and brightness in
`~/.cache/led-control/defaults-v2-<boot_id>.json`, and **Reset** returns to that state.
Snapshots from earlier boots are deleted automatically.

If you changed LEDs by hand before opening the app, use the menu entry
**Use current state as defaults** after fixing them, or delete the snapshot file and
reopen the app.

Resetting writes the trigger first, then the brightness, and the brightness only when
the trigger is `none` (any other trigger drives the brightness itself).

### ThinkPad firmware LEDs

`tpacpi::power`, `tpacpi::lid_logo_dot`, `tpacpi::standby`, `tpacpi::thinkvantage` and
similar are driven by the embedded controller, and `thinkpad_acpi` can't read them back.
After boot the kernel reports brightness 0, even though the power LED and the lid dot are
on. The app therefore assumes those two are **on** at boot, and only trusts the reported
value once it has written to the LED itself (recorded in the snapshot as `touched`).
If you change one of these LEDs from a shell, the app can show it wrong.

These LEDs only know on and off (and blink, via the `timer` trigger), although they report
`max_brightness=255`, so the app shows a switch for them.

The power LED's colour, the charging LED and the FnLock LED are handled entirely by the
firmware. They are not in `/sys/class/leds`, so they can't be controlled.

## Doing the same by hand

Everything the app does is a plain write to sysfs:

```sh
cat /sys/class/leds/platform::mute/trigger              # [active] trigger is in brackets
echo none | sudo tee /sys/class/leds/platform::mute/trigger
echo 0    | sudo tee /sys/class/leds/platform::mute/brightness
echo audio-mute | sudo tee /sys/class/leds/platform::mute/trigger   # back to default
```

## Layout

| Path | Purpose |
|---|---|
| `src/ledcontrol/sysfs.py` | Read LEDs, triggers and trigger options (no privileges) |
| `src/ledcontrol/helper.py` | Root helper: JSON lines on stdin/stdout, validates every write. Stdlib only, run with `python3 -I` |
| `src/ledcontrol/privileged.py` | Starts the helper via `pkexec` and talks to it |
| `src/ledcontrol/defaults.py` | Per-boot default snapshot and reset logic |
| `src/ledcontrol/quirks.py` | Hardware facts sysfs doesn't report (ThinkPad firmware LEDs) |
| `src/ledcontrol/service.py` | GUI-independent operations (set, reset, reset all) |
| `src/ledcontrol/gui.py` | GTK 4 interface |
| `bin/led-control` | Launcher |

The helper only writes regular, writable files located directly in
`/sys/class/leds/<led>/`. It rejects path separators, symlinked attributes, `uevent`,
`max_brightness` and multi-line values.

## Development

Dev tools live in a conda env (`environment.yml`: Python 3.12, pytest, ruff):

```sh
conda env create -f environment.yml     # once
conda activate led-control
pytest                                  # GUI tests are skipped here (no GTK in conda)
ruff check . && ruff format --check .
```

The GUI tests need the system Python's GTK. Use the system Python with pytest from the env:

```sh
PYTHONPATH=~/miniconda3/envs/led-control/lib/python3.12/site-packages \
  /usr/bin/python3 -m pytest -p no:cacheprovider
```

All tests use a fake LED tree in a temp directory. None of them touch the real
`/sys/class/leds` or need root.
