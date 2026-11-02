"""Client side of the root helper (see helper.py)."""

from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path
from typing import Protocol

HELPER_PATH = Path(__file__).resolve().with_name("helper.py")


class WriteError(Exception):
    pass


class Writer(Protocol):
    def write(self, led: str, attr: str, value: str) -> None: ...


def pkexec_argv() -> list[str]:
    # -I: isolated mode, so root never imports anything from user-writable paths
    # besides the helper script itself.
    return ["pkexec", sys.executable, "-I", str(HELPER_PATH)]


class HelperClient:
    """Talks to one long-lived helper process, so authentication happens once."""

    def __init__(self, argv: list[str] | None = None) -> None:
        self._argv = argv or pkexec_argv()
        self._proc: subprocess.Popen[str] | None = None
        self._next_id = 0

    @property
    def running(self) -> bool:
        return self._proc is not None and self._proc.poll() is None

    def start(self) -> None:
        """Start the helper; blocks while the polkit password dialog is shown."""
        self.close()
        try:
            proc = subprocess.Popen(
                self._argv,
                stdin=subprocess.PIPE,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
                bufsize=1,
            )
        except OSError as exc:
            raise WriteError(f"cannot start helper: {exc}") from None
        line = proc.stdout.readline()
        try:
            ready = json.loads(line).get("ready") if line else False
        except (json.JSONDecodeError, AttributeError):
            ready = False
        if not ready:
            proc.kill()
            _, err = proc.communicate()
            rc = proc.returncode
            detail = (err or "").strip() or f"exit code {rc}"
            if rc in (126, 127):
                detail = "authorization was cancelled or denied"
            raise WriteError(f"helper did not start: {detail}")
        self._proc = proc

    def write(self, led: str, attr: str, value: str) -> None:
        if not self.running:
            raise WriteError("not authorized (helper is not running)")
        self._next_id += 1
        request = {"id": self._next_id, "led": led, "attr": attr, "value": value}
        try:
            self._proc.stdin.write(json.dumps(request) + "\n")
            self._proc.stdin.flush()
            line = self._proc.stdout.readline()
        except OSError as exc:
            raise WriteError(f"helper connection lost: {exc}") from None
        if not line:
            raise WriteError("helper exited unexpectedly")
        reply = json.loads(line)
        if not reply.get("ok"):
            raise WriteError(f"{led}: {reply.get('error', 'unknown error')}")

    def close(self) -> None:
        if self._proc is None:
            return
        try:
            self._proc.stdin.close()
            self._proc.wait(timeout=2)
        except (OSError, subprocess.TimeoutExpired):
            self._proc.kill()
            self._proc.wait()
        finally:
            for stream in (self._proc.stdout, self._proc.stderr):
                if stream:
                    stream.close()
            self._proc = None
