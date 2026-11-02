"""Human-readable titles for LED device names.

LED names follow ``devicename:color:function`` (any part may be empty), e.g.
``tpacpi::lid_logo_dot`` or ``input3::capslock``. The device part is often
numbered differently per boot or machine, so most rules match the function.
"""

from __future__ import annotations

import re

_EXACT = {
    "tpacpi::power": "Power button",
    "tpacpi::lid_logo_dot": "Lid logo dot (the “i” in ThinkPad)",
    "tpacpi::kbd_backlight": "Keyboard backlight",
    "tpacpi::thinklight": "ThinkLight",
    "tpacpi::thinkvantage": "ThinkVantage button",
    "tpacpi::standby": "Standby",
    "tpacpi:orange:batt": "Battery (orange)",
    "tpacpi:green:batt": "Battery (green)",
}

_FUNCTION = {
    "mute": "Speaker mute key",
    "micmute": "Microphone mute key",
    "capslock": "Caps Lock",
    "numlock": "Num Lock",
    "scrolllock": "Scroll Lock",
    "compose": "Compose",
    "kana": "Kana",
    "kbd_backlight": "Keyboard backlight",
    "charging": "Charging",
}

_WIFI = re.compile(r"^phy\d+-led$")


def title(name: str) -> str:
    if name in _EXACT:
        return _EXACT[name]
    if _WIFI.match(name):
        return "Wi-Fi"
    parts = name.split(":")
    function = parts[-1]
    color = parts[1] if len(parts) == 3 else ""
    label = _FUNCTION.get(function) or function.replace("_", " ").replace("-", " ").strip()
    if not label:
        return name
    label = label[0].upper() + label[1:]
    return f"{label} ({color})" if color else label


# --- triggers -----------------------------------------------------------------

_TRIGGERS = {
    "none": "None (set brightness by hand)",
    "default": "Driver's default trigger",
    "default-on": "Always on",
    "timer": "Blink (timer)",
    "oneshot": "Blink once per event (oneshot)",
    "heartbeat": "Heartbeat (blinks with system load)",
    "pattern": "Custom pattern",
    "activity": "CPU activity (all cores)",
    "transient": "Switch on for a while (transient)",
    "netdev": "Network device activity",
    "input-events": "Any input activity",
    "backlight": "Follows display backlight",
    "panic": "Kernel panic",
    "audio-mute": "Speaker muted",
    "audio-micmute": "Microphone muted",
    "disk-activity": "Disk activity",
    "disk-read": "Disk reads",
    "disk-write": "Disk writes",
    "mtd": "Flash memory (MTD) activity",
    "nand-disk": "NAND flash activity",
    "cpu": "CPU activity (any core)",
    "usb-gadget": "USB gadget activity",
    "usb-host": "USB host activity",
    "rfkill-any": "Any radio enabled",
    "rfkill-none": "All radios disabled",
    "bluetooth-power": "Bluetooth on",
    "rc-feedback": "Remote control (IR) received",
    "AC-online": "Power adapter connected",
}

_KBD = {
    "capslock": "Caps Lock",
    "numlock": "Num Lock",
    "scrolllock": "Scroll Lock",
    "kanalock": "Kana Lock",
    "shiftlock": "Shift held",
    "altgrlock": "AltGr held",
    "ctrllock": "Ctrl held",
    "altlock": "Alt held",
    "shiftllock": "Left Shift held",
    "shiftrlock": "Right Shift held",
    "ctrlllock": "Left Ctrl held",
    "ctrlrlock": "Right Ctrl held",
}

_BATTERY = {
    "charging-or-full": "charging or full",
    "charging": "charging",
    "full": "full",
    "charging-blink-full-solid": "blink while charging, steady when full",
    "charging-orange-full-green": "orange while charging, green when full",
}

_WIFI_TRIGGER = {
    "rx": "receiving",
    "tx": "sending",
    "assoc": "connected",
    "radio": "radio on",
    "tpt": "throughput",
}

_RADIO_KIND = {"wlan": "Wi-Fi", "bluetooth": "Bluetooth", "wwan": "Mobile broadband"}

_PATTERNS = [
    (re.compile(r"^cpu(\d+)$"), lambda m: f"CPU core {m[1]} activity"),
    (re.compile(r"^kbd-(\w+)$"), lambda m: _KBD.get(m[1]) and f"Keyboard: {_KBD[m[1]]}"),
    (
        re.compile(r"^(BAT\d+)-(.+)$"),
        lambda m: _BATTERY.get(m[2]) and f"Battery {m[1][3:]}: {_BATTERY[m[2]]}",
    ),
    (
        re.compile(r"^(phy\d+)(rx|tx|assoc|radio|tpt)$"),
        lambda m: f"Wi-Fi {_WIFI_TRIGGER[m[2]]} ({m[1]})",
    ),
    (re.compile(r"^(hci\d+)-power$"), lambda m: f"Bluetooth adapter on ({m[1]})"),
    (re.compile(r"^mmc(\d+)$"), lambda m: f"Memory card activity (mmc{m[1]})"),
    (
        re.compile(r"^ucsi-source-psy-\w+:0*(\d+)-online$"),
        lambda m: f"USB-C port {m[1]}: power source connected",
    ),
    (re.compile(r"^(.+)-online$"), lambda m: f"Power supply connected ({m[1]})"),
]


def trigger_title(name: str, radios: dict[str, tuple[str, str]] | None = None) -> str:
    """Plain-language label for a trigger, or the raw name if unknown.

    ``radios`` maps rfkill devices (``rfkill0``) to their (type, name), as read
    from /sys/class/rfkill.
    """
    if name in _TRIGGERS:
        return _TRIGGERS[name]
    if re.fullmatch(r"rfkill\d+", name):
        kind, dev = (radios or {}).get(name, ("", ""))
        if kind:
            return f"{_RADIO_KIND.get(kind, kind)} radio enabled ({dev})"
        return f"Radio enabled ({name})"
    for pattern, make in _PATTERNS:
        if (match := pattern.match(name)) and (label := make(match)):
            return label
    return name


def trigger_choice(name: str, radios: dict[str, tuple[str, str]] | None = None) -> str:
    """Dropdown text: the label plus the raw name, so both are searchable."""
    label = trigger_title(name, radios)
    return label if label == name else f"{label} — {name}"
