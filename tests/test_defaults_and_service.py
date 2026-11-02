import json
from pathlib import Path

import pytest
from conftest import make_led

from ledcontrol import sysfs
from ledcontrol.defaults import DefaultsStore, LedDefault, boot_id, restore_ops
from ledcontrol.privileged import WriteError
from ledcontrol.service import LedService


class FileWriter:
    """Writes straight into the fake tree, mimicking how sysfs reformats triggers."""

    def __init__(self, root: Path) -> None:
        self.root = root
        self.calls: list[tuple[str, str, str]] = []

    def write(self, led: str, attr: str, value: str) -> None:
        self.calls.append((led, attr, value))
        path = self.root / led / attr
        if not path.exists():
            raise WriteError(f"{led}: no attribute {attr}")
        if attr == "trigger":
            names, _ = sysfs.parse_trigger(path.read_text())
            if value not in names:
                raise WriteError(f"{led}: invalid trigger {value}")
            path.write_text(" ".join(f"[{n}]" if n == value else n for n in names))
            if value == "none":
                (self.root / led / "brightness").write_text("0")
        else:
            path.write_text(value)


@pytest.fixture
def service(leds_root: Path, tmp_path: Path) -> LedService:
    svc = LedService(FileWriter(leds_root), DefaultsStore(tmp_path / "cache", "boot1"), leds_root)
    svc.load_defaults()
    return svc


def test_boot_id(tmp_path: Path):
    (tmp_path / "boot_id").write_text("abc\n")
    assert boot_id(tmp_path / "boot_id") == "abc"


@pytest.mark.parametrize(
    ("default", "ops"),
    [
        (LedDefault("audio-mute", 1), [("trigger", "audio-mute")]),
        (LedDefault("none", 2), [("trigger", "none"), ("brightness", "2")]),
    ],
)
def test_restore_ops(default, ops):
    assert restore_ops(default) == ops


def test_snapshot_created_and_kept(leds_root: Path, tmp_path: Path):
    cache = tmp_path / "cache"
    cache.mkdir()
    (cache / "defaults-oldboot.json").write_text("{}")
    (cache / "defaults-oldformat.json").write_text("{}")
    store = DefaultsStore(cache, "boot1")
    store.load(sysfs.discover(leds_root))
    assert not (cache / "defaults-oldboot.json").exists()
    assert not (cache / "defaults-oldformat.json").exists()
    assert json.loads(store.path.read_text())["defaults"]["platform::mute"] == {
        "trigger": "audio-mute",
        "brightness": 1,
    }

    # A later run in the same boot must keep the original snapshot.
    (leds_root / "platform::mute" / "trigger").write_text("[none] audio-mute")
    again = DefaultsStore(cache, "boot1")
    again.load(sysfs.discover(leds_root))
    assert again.get("platform::mute") == LedDefault("audio-mute", 1)


def test_new_led_is_added_to_snapshot(leds_root: Path, tmp_path: Path, service: LedService):
    make_led(tmp_path, "new::led", brightness=1)
    service.load_defaults()
    assert service.defaults.get("new::led") == LedDefault("none", 1)
    assert service.defaults.get("platform::mute") == LedDefault("audio-mute", 1)


def test_corrupt_snapshot_is_recreated(leds_root: Path, tmp_path: Path):
    store = DefaultsStore(tmp_path / "cache", "boot1")
    store.path.parent.mkdir(parents=True)
    store.path.write_text("{broken")
    store.load(sysfs.discover(leds_root))
    assert store.get("platform::mute") == LedDefault("audio-mute", 1)


def test_reset_single_led(service: LedService):
    service.set("platform::mute", "trigger", "none")
    assert not service.is_default(service.led("platform::mute"))
    service.reset("platform::mute")
    assert service.led("platform::mute").active_trigger == "audio-mute"
    assert service.is_default(service.led("platform::mute"))


def test_reset_restores_brightness_for_untriggered_led(service: LedService):
    service.set("tpacpi::kbd_backlight", "brightness", "2")
    assert not service.is_default(service.led("tpacpi::kbd_backlight"))
    service.reset("tpacpi::kbd_backlight")
    assert service.led("tpacpi::kbd_backlight").brightness == 0


def test_reset_all(service: LedService):
    service.set("platform::mute", "trigger", "timer")
    service.set("tpacpi::lid_logo_dot", "trigger", "none")
    assert service.reset_all() == []
    assert all(service.is_default(led) for led in service.leds())


def test_reset_all_collects_errors(service: LedService, leds_root: Path):
    (leds_root / "platform::mute" / "trigger").write_text("[none] timer")  # audio-mute gone
    errors = service.reset_all()
    assert len(errors) == 1
    assert "invalid trigger audio-mute" in errors[0]


def test_reset_without_default(service: LedService):
    with pytest.raises(WriteError, match="no default"):
        service.reset("unknown")


def test_capture_defaults(service: LedService):
    service.set("platform::mute", "trigger", "none")
    service.capture_defaults()
    assert service.defaults.get("platform::mute") == LedDefault("none", 0)
    assert service.is_default(service.led("platform::mute"))


@pytest.fixture
def thinkpad(tmp_path: Path):
    """Firmware LEDs as reported right after boot: brightness 0, max 255."""
    make_led(tmp_path, "tpacpi::power", max_brightness=255)
    make_led(tmp_path, "tpacpi::standby", max_brightness=255)
    root = make_led(tmp_path, "tpacpi::lid_logo_dot", max_brightness=255)
    svc = LedService(FileWriter(root), DefaultsStore(tmp_path / "cache", "boot1"), root)
    svc.load_defaults()
    return svc


def test_firmware_leds_on_at_boot_default_to_on(thinkpad: LedService):
    assert thinkpad.defaults.get("tpacpi::power") == LedDefault("none", 255)
    assert thinkpad.defaults.get("tpacpi::lid_logo_dot") == LedDefault("none", 255)
    assert thinkpad.defaults.get("tpacpi::standby") == LedDefault("none", 0)
    assert thinkpad.led("tpacpi::power").brightness == 255
    assert all(thinkpad.is_default(led) for led in thinkpad.leds())


def test_firmware_led_reads_are_trusted_after_a_write(thinkpad: LedService, tmp_path: Path):
    thinkpad.set("tpacpi::power", "brightness", "0")
    assert thinkpad.led("tpacpi::power").brightness == 0
    assert not thinkpad.is_default(thinkpad.led("tpacpi::power"))

    # Survives an app restart within the same boot.
    again = LedService(thinkpad.writer, DefaultsStore(tmp_path / "cache", "boot1"), thinkpad.root)
    again.load_defaults()
    assert again.led("tpacpi::power").brightness == 0
    assert again.defaults.get("tpacpi::power") == LedDefault("none", 255)

    again.reset("tpacpi::power")
    assert again.led("tpacpi::power").brightness == 255


def test_identify_plan_for_triggered_led(service: LedService):
    blink, restore = service.identify_plan("platform::mute", toggles=4)
    # mute LED is on (brightness 1) and driven by audio-mute
    assert blink == [
        ("trigger", "none"),
        ("brightness", "0"),
        ("brightness", "1"),
        ("brightness", "0"),
        ("brightness", "1"),
    ]
    assert restore == [("trigger", "audio-mute")]


def test_identify_plan_for_untriggered_led(service: LedService):
    blink, restore = service.identify_plan("tpacpi::kbd_backlight", toggles=2)
    assert blink == [("brightness", "2"), ("brightness", "0")]
    assert restore == [("trigger", "none"), ("brightness", "0")]


def test_identify_restores_guessed_firmware_state(thinkpad: LedService):
    blink, restore = thinkpad.identify_plan("tpacpi::power", toggles=2)
    assert blink == [("brightness", "0"), ("brightness", "255")]
    assert restore == [("trigger", "none"), ("brightness", "255")]
