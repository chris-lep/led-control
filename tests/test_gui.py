"""GUI smoke tests against a fake LED tree and the real helper protocol.

Skipped where PyGObject/GTK 4 or a display is unavailable (e.g. in the conda
env). See the README for running them with the system Python.
"""

import os
import sys
from pathlib import Path

import pytest
from conftest import make_led

from ledcontrol.defaults import DefaultsStore
from ledcontrol.privileged import HELPER_PATH, HelperClient
from ledcontrol.service import LedService

gi = pytest.importorskip("gi")
try:
    gi.require_version("Gtk", "4.0")
    from gi.repository import GLib, Gtk
except (ValueError, ImportError):
    pytest.skip("GTK 4 not available", allow_module_level=True)
if not (os.environ.get("DISPLAY") or os.environ.get("WAYLAND_DISPLAY")) or not Gtk.init_check():
    pytest.skip("no display", allow_module_level=True)

from ledcontrol import gui  # noqa: E402


def spin(until, timeout=5.0):
    ctx = GLib.MainContext.default()
    deadline = GLib.get_monotonic_time() + timeout * 1e6
    while not until() and GLib.get_monotonic_time() < deadline:
        ctx.iteration(False)
    assert until()


@pytest.fixture(scope="module")
def app():
    application = Gtk.Application(application_id=None)
    application.register(None)
    return application


@pytest.fixture
def window(app, leds_root: Path, tmp_path: Path):
    client = HelperClient([sys.executable, "-I", str(HELPER_PATH), "--root", str(leds_root)])
    service = LedService(client, DefaultsStore(tmp_path / "cache", "boot"), leds_root)
    service.load_defaults()
    win = gui.MainWindow(app, service, client)
    spin(lambda: client.running and win.list.get_sensitive())
    yield win
    client.close()
    win.destroy()


def test_cards_for_each_led(window):
    title = window.cards["platform::mute"].title_label.get_label()
    assert "Speaker mute key" in title and "platform::mute" in title
    assert list(window.cards) == [
        "platform::mute",
        "tpacpi::kbd_backlight",
        "tpacpi::lid_logo_dot",
    ]
    assert isinstance(window.cards["platform::mute"].brightness, Gtk.Switch)
    assert isinstance(window.cards["tpacpi::lid_logo_dot"].brightness, Gtk.Switch)
    assert isinstance(window.cards["tpacpi::kbd_backlight"].brightness, Gtk.Scale)
    assert set(window.cards["tpacpi::lid_logo_dot"]._extra_entries) == {"delay_on", "delay_off"}


def test_changing_trigger_writes_and_reset_restores(window, leds_root: Path):
    card = window.cards["platform::mute"]
    assert not card.reset_button.get_sensitive()
    card.trigger.set_selected(0)  # "none"
    assert (leds_root / "platform::mute" / "trigger").read_text() == "none"

    # The fake tree doesn't re-render brackets like sysfs; emulate it.
    (leds_root / "platform::mute" / "trigger").write_text("[none] audio-mute timer")
    window.refresh()
    assert card.reset_button.get_sensitive()
    card.reset_button.emit("clicked")
    assert (leds_root / "platform::mute" / "trigger").read_text() == "audio-mute"


def test_brightness_scale_writes(window, leds_root: Path):
    card = window.cards["tpacpi::kbd_backlight"]
    card.brightness.set_value(2)
    assert (leds_root / "tpacpi::kbd_backlight" / "brightness").read_text() == "2"


def test_brightness_switch_writes(window, leds_root: Path):
    card = window.cards["platform::mute"]
    card.brightness.set_active(False)
    assert (leds_root / "platform::mute" / "brightness").read_text() == "0"


def test_write_error_is_shown(window):
    window.run(window.service.set, "missing", "trigger", "none")
    assert window.status.get_visible()
    assert "no such LED" in window.status.get_text()


def test_firmware_led_gets_switch(app, tmp_path: Path):
    root = make_led(tmp_path, "tpacpi::power", max_brightness=255)
    client = HelperClient([sys.executable, "-I", str(HELPER_PATH), "--root", str(root)])
    service = LedService(client, DefaultsStore(tmp_path / "cache", "boot"), root)
    service.load_defaults()
    win = gui.MainWindow(app, service, client)
    spin(lambda: client.running and win.list.get_sensitive())
    try:
        card = win.cards["tpacpi::power"]
        assert isinstance(card.brightness, Gtk.Switch)
        assert card.brightness.get_active()  # guessed "on" although sysfs says 0
        card.brightness.set_active(False)
        assert (root / "tpacpi::power" / "brightness").read_text() == "0"
        assert not card.brightness.get_active()
        card.brightness.set_active(True)
        assert (root / "tpacpi::power" / "brightness").read_text() == "255"
    finally:
        client.close()
        win.destroy()


def test_identify_blinks_and_restores(window, leds_root: Path, monkeypatch):
    monkeypatch.setattr(gui, "IDENTIFY_INTERVAL_MS", 1)
    card = window.cards["platform::mute"]
    card.identify_button.emit("clicked")
    assert card.identifying
    assert not card.grid.get_sensitive()
    assert not window.reset_all.get_sensitive()
    assert (leds_root / "platform::mute" / "trigger").read_text() == "none"

    spin(lambda: not card.identifying)
    assert (leds_root / "platform::mute" / "trigger").read_text() == "audio-mute"
    assert card.grid.get_sensitive()
    assert window.reset_all.get_sensitive()


def test_finish_identify_restores_immediately(window, leds_root: Path):
    card = window.cards["tpacpi::kbd_backlight"]
    card.identify_button.emit("clicked")
    assert (leds_root / "tpacpi::kbd_backlight" / "brightness").read_text() == "2"
    card.finish_identify()
    assert not card.identifying
    assert (leds_root / "tpacpi::kbd_backlight" / "brightness").read_text() == "0"
