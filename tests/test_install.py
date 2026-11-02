"""make install / uninstall into a temporary PREFIX."""

import shutil
import subprocess
from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parent.parent
APP_ID = "io.github.chris_lep.LedControl"

pytestmark = pytest.mark.skipif(shutil.which("make") is None, reason="make not installed")


def make(target: str, prefix: Path) -> subprocess.CompletedProcess:
    return subprocess.run(
        ["make", "-C", str(REPO), target, f"PREFIX={prefix}"],
        capture_output=True,
        text=True,
        check=True,
    )


def test_install_and_uninstall(tmp_path: Path):
    make("install", tmp_path)
    binary = tmp_path / "bin" / "led-control"
    desktop = tmp_path / "share" / "applications" / f"{APP_ID}.desktop"
    icon = tmp_path / "share" / "icons" / "hicolor" / "scalable" / "apps" / f"{APP_ID}.svg"

    assert binary.is_symlink()
    assert binary.resolve() == REPO / "bin" / "led-control"
    assert f"Exec={binary}\n" in desktop.read_text()
    assert icon.read_bytes() == (REPO / "data" / f"{APP_ID}.svg").read_bytes()
    if shutil.which("desktop-file-validate"):
        subprocess.run(["desktop-file-validate", str(desktop)], check=True)

    make("install", tmp_path)  # idempotent
    make("uninstall", tmp_path)
    assert not binary.exists() and not binary.is_symlink()
    assert not desktop.exists()
    assert not icon.exists()


def test_uninstall_keeps_foreign_launcher(tmp_path: Path):
    (tmp_path / "bin").mkdir()
    foreign = tmp_path / "bin" / "led-control"
    foreign.write_text("#!/bin/sh\n")
    result = make("uninstall", tmp_path)
    assert foreign.exists()
    assert "not a link to this repo" in result.stdout


def test_desktop_file_matches_app_id():
    """GTK groups windows by app id, which must equal the .desktop file name."""
    gui_source = (REPO / "src" / "ledcontrol" / "gui.py").read_text()
    assert f'APP_ID = "{APP_ID}"' in gui_source
    assert f"StartupWMClass={APP_ID}" in (REPO / "data" / f"{APP_ID}.desktop.in").read_text()
