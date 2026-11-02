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
