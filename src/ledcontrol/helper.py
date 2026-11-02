"""Privileged writer for LED sysfs attributes.

This file is run as root through ``pkexec /usr/bin/python3 -I helper.py``.
Because of ``-I`` it cannot import the rest of the package, so it must stay
self-contained and use only the standard library.

Protocol: one JSON object per line on stdin, one JSON reply per line on stdout.
On start the helper prints ``{"ready": true}``.

    request:  {"id": 1, "led": "platform::mute", "attr": "trigger", "value": "none"}
    reply:    {"id": 1, "ok": true}
              {"id": 1, "ok": false, "error": "..."}

Only regular, owner-writable files directly inside an LED directory under the
LEDs root can be written. The helper exits when stdin is closed.
"""

from __future__ import annotations

import argparse
import json
import os
import stat
import sys
from pathlib import Path
from typing import TextIO

DEFAULT_ROOT = Path("/sys/class/leds")
FORBIDDEN_ATTRS = frozenset({"uevent", "max_brightness", "brightness_hw_changed"})
MAX_VALUE_LEN = 4096


class RequestError(Exception):
    pass


def _check_name(label: str, name: object) -> str:
    if not isinstance(name, str) or name in ("", ".", "..") or "/" in name or "\0" in name:
        raise RequestError(f"invalid {label} name: {name!r}")
    return name


def resolve_target(root: Path, led: object, attr: object) -> Path:
    """Validate a request and return the sysfs file it may write to."""
    led = _check_name("LED", led)
    attr = _check_name("attribute", attr)
    if attr in FORBIDDEN_ATTRS:
        raise RequestError(f"attribute {attr!r} may not be written")
    led_dir = root / led
    if not led_dir.is_dir():
        raise RequestError(f"no such LED: {led!r}")
    target = led_dir / attr
    try:
        # lstat: the LED directory itself may be a symlink (it is in sysfs),
        # but the attribute file must not be.
        st = os.lstat(target)
    except FileNotFoundError:
        raise RequestError(f"LED {led!r} has no attribute {attr!r}") from None
    if not stat.S_ISREG(st.st_mode):
        raise RequestError(f"{attr!r} is not a regular file")
    if not st.st_mode & stat.S_IWUSR:
        raise RequestError(f"{attr!r} is read-only")
    return target


def check_value(value: object) -> str:
    if not isinstance(value, str):
        raise RequestError("value must be a string")
    value = value.rstrip("\n")
    if len(value) > MAX_VALUE_LEN or "\n" in value or "\0" in value:
        raise RequestError("value must be a single line of at most 4096 characters")
    return value


def write_attr(target: Path, value: str) -> None:
    # O_TRUNC is what shell redirection uses; sysfs ignores it, regular files need it.
    fd = os.open(target, os.O_WRONLY | os.O_TRUNC | os.O_NOFOLLOW)
    try:
        os.write(fd, value.encode())
    finally:
        os.close(fd)


def handle(root: Path, request: object) -> dict:
    req_id = request.get("id") if isinstance(request, dict) else None
    try:
        if not isinstance(request, dict):
            raise RequestError("request must be a JSON object")
        target = resolve_target(root, request.get("led"), request.get("attr"))
        value = check_value(request.get("value"))
        try:
            write_attr(target, value)
        except OSError as exc:
            raise RequestError(
                f"writing {value!r} to {request['attr']} failed: {exc.strerror or exc}"
            ) from None
    except RequestError as exc:
        return {"id": req_id, "ok": False, "error": str(exc)}
    return {"id": req_id, "ok": True}


def serve(root: Path, stdin: TextIO, stdout: TextIO) -> None:
    def send(obj: dict) -> None:
        stdout.write(json.dumps(obj) + "\n")
        stdout.flush()

    send({"ready": True})
    for line in stdin:
        if not line.strip():
            continue
        try:
            request = json.loads(line)
        except json.JSONDecodeError:
            send({"id": None, "ok": False, "error": "malformed JSON"})
            continue
        send(handle(root, request))


def main(argv: list[str] | None = None) -> None:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--root", type=Path, default=DEFAULT_ROOT, help=argparse.SUPPRESS)
    args = parser.parse_args(argv)
    serve(args.root, sys.stdin, sys.stdout)


if __name__ == "__main__":
    main()
