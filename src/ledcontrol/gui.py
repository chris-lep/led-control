"""GTK 4 user interface."""

from __future__ import annotations

import threading

import gi

gi.require_version("Gtk", "4.0")
from gi.repository import Gio, GLib, Gtk  # noqa: E402

from . import defaults, names, quirks, sysfs  # noqa: E402
from .privileged import HelperClient, WriteError  # noqa: E402
from .service import LedService  # noqa: E402
from .sysfs import Led  # noqa: E402

APP_ID = "io.github.chris_lep.LedControl"
REFRESH_SECONDS = 2
IDENTIFY_INTERVAL_MS = 300


def _trigger_factory(with_detail: bool) -> Gtk.SignalListItemFactory:
    """Render a trigger as its label, optionally with the raw name below it."""
    factory = Gtk.SignalListItemFactory()

    def setup(_factory, item: Gtk.ListItem) -> None:
        box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL)
        box.append(Gtk.Label(xalign=0))
        if with_detail:
            detail = Gtk.Label(xalign=0)
            detail.add_css_class("dim-label")
            detail.add_css_class("caption")
            box.append(detail)
        item.set_child(box)

    def bind(_factory, item: Gtk.ListItem) -> None:
        label, _, detail = item.get_item().get_string().partition("\n")
        title = item.get_child().get_first_child()
        title.set_text(label)
        if with_detail:
            sub = title.get_next_sibling()
            sub.set_text(detail)
            sub.set_visible(bool(detail))

    factory.connect("setup", setup)
    factory.connect("bind", bind)
    return factory


class LedCard(Gtk.Frame):
    """Controls for one LED."""

    def __init__(self, window: MainWindow, led: Led) -> None:
        super().__init__()
        self.window = window
        self.name = led.name
        self.led = led
        self._updating = False
        self._extras_key: tuple = ()
        self._extra_entries: dict[str, Gtk.Entry] = {}
        self._identify_restore: list[tuple[str, str]] | None = None
        self._identify_source = 0

        title = Gtk.Box(spacing=8)
        self.title_label = Gtk.Label(xalign=0, hexpand=True)
        self.reset_button = Gtk.Button(label="Reset")
        self.reset_button.connect("clicked", self._on_reset)
        self.identify_button = Gtk.Button(
            label="Identify", tooltip_text="Blink this LED a few times, then restore it"
        )
        self.identify_button.connect("clicked", self._on_identify)
        title.append(self.title_label)
        title.append(self.identify_button)
        title.append(self.reset_button)

        self.grid = Gtk.Grid(column_spacing=12, row_spacing=6)
        self._trigger_names = list(led.triggers) or ["none"]
        self.trigger = Gtk.DropDown.new_from_strings(self._choices(self._trigger_names))
        self.trigger.set_factory(_trigger_factory(with_detail=False))
        self.trigger.set_list_factory(_trigger_factory(with_detail=True))
        self.trigger.set_enable_search(True)
        self.trigger.set_search_match_mode(Gtk.StringFilterMatchMode.SUBSTRING)
        self.trigger.connect("notify::selected", self._on_trigger)
        self._add_row(0, "Trigger", self.trigger)

        self.max = led.max_brightness
        on_off = self.max <= 1 or quirks.is_firmware_led(led.name)
        if on_off:
            self.brightness = Gtk.Switch(halign=Gtk.Align.START)
            self.brightness.connect("notify::active", self._on_switch)
        else:
            self.brightness = Gtk.Scale.new_with_range(Gtk.Orientation.HORIZONTAL, 0, self.max, 1)
            self.brightness.set_digits(0)
            self.brightness.set_draw_value(True)
            self.brightness.set_hexpand(True)
            self.brightness.connect("value-changed", self._on_scale)
        self._add_row(1, "On" if on_off else f"Brightness (0–{self.max})", self.brightness)

        self.extras = Gtk.Grid(column_spacing=12, row_spacing=6)
        self.grid.attach(self.extras, 0, 2, 2, 1)

        box = Gtk.Box(
            orientation=Gtk.Orientation.VERTICAL,
            spacing=8,
            margin_top=8,
            margin_bottom=10,
            margin_start=12,
            margin_end=12,
        )
        box.append(title)
        box.append(self.grid)
        if quirks.is_firmware_led(led.name):
            note = Gtk.Label(
                label="Firmware LED: the driver can't read its state, so the shown value is "
                "a guess until you change it here.",
                xalign=0,
                wrap=True,
            )
            note.add_css_class("dim-label")
            note.add_css_class("caption")
            box.append(note)
        self.set_child(box)
        self.update(led)

    def _choices(self, triggers: list[str]) -> list[str]:
        # "label\ndetail": the factories show the parts on two lines, and search
        # matches either.
        return [
            "\n".join(filter(None, names.trigger_info(t, self.window.radios))) for t in triggers
        ]

    def _add_row(self, row: int, text: str, widget: Gtk.Widget) -> None:
        label = Gtk.Label(label=text, xalign=0)
        label.add_css_class("dim-label")
        self.grid.attach(label, 0, row, 1, 1)
        self.grid.attach(widget, 1, row, 1, 1)

    # --- state -> widgets ---------------------------------------------------

    @property
    def identifying(self) -> bool:
        return self._identify_restore is not None

    def update(self, led: Led) -> None:
        if self.identifying:
            return  # the LED is blinking; don't mirror that in the widgets
        self._updating = True
        try:
            self.led = led
            service = self.window.service
            is_default = service.is_default(led)
            changed = "" if is_default else "  <small>(changed)</small>"
            esc = GLib.markup_escape_text
            self.title_label.set_markup(
                f"<b>{esc(names.title(led.name))}</b>{changed}\n"
                f"<small><tt>{esc(led.name)}</tt></small>"
            )
            default = service.defaults.get(led.name)
            if default is None:
                tip = "No default recorded"
            else:
                tip = f"Back to trigger “{default.trigger}”"
                if default.trigger == "none":
                    tip += f", brightness {default.brightness}"
            self.reset_button.set_tooltip_text(tip)
            self.reset_button.set_sensitive(not is_default)

            model = self.trigger.get_model()
            if led.triggers and self._trigger_names != list(led.triggers):
                old = len(self._trigger_names)
                self._trigger_names = list(led.triggers)
                model.splice(0, old, self._choices(self._trigger_names))
            if led.active_trigger in self._trigger_names:
                index = self._trigger_names.index(led.active_trigger)
                if self.trigger.get_selected() != index:
                    self.trigger.set_selected(index)

            if isinstance(self.brightness, Gtk.Switch):
                if self.brightness.get_active() != (led.brightness > 0):
                    self.brightness.set_active(led.brightness > 0)
            elif round(self.brightness.get_value()) != led.brightness:
                self.brightness.set_value(led.brightness)

            self._update_extras(led)
        finally:
            self._updating = False

    def _update_extras(self, led: Led) -> None:
        key = tuple((a.name, a.writable) for a in led.extras)
        if key != self._extras_key:
            self._extras_key = key
            while child := self.extras.get_first_child():
                self.extras.remove(child)
            self._extra_entries = {}
            for row, attr in enumerate(led.extras):
                label = Gtk.Label(label=attr.name, xalign=0)
                label.add_css_class("dim-label")
                entry = Gtk.Entry(hexpand=True, sensitive=attr.writable)
                if attr.value is None:
                    entry.set_placeholder_text("write-only" if attr.writable else "unreadable")
                entry.connect("activate", self._on_extra, attr.name)
                apply = Gtk.Button(label="Set", sensitive=attr.writable)
                apply.connect("clicked", self._on_extra_button, entry, attr.name)
                self.extras.attach(label, 0, row, 1, 1)
                self.extras.attach(entry, 1, row, 1, 1)
                self.extras.attach(apply, 2, row, 1, 1)
                self._extra_entries[attr.name] = entry
        for attr in led.extras:
            entry = self._extra_entries[attr.name]
            focused = entry.has_focus() or entry.get_focus_child() is not None
            if attr.value is not None and not focused and entry.get_text() != attr.value:
                entry.set_text(attr.value)

    # --- widgets -> sysfs ---------------------------------------------------

    def _write(self, attr: str, value: str) -> None:
        self.window.run(self.window.service.set, self.name, attr, value)

    def _on_reset(self, _button: Gtk.Button) -> None:
        self.window.run(self.window.service.reset, self.name)

    def _on_identify(self, _button: Gtk.Button) -> None:
        service = self.window.service
        blink, restore = service.identify_plan(self.name)
        self._identify_restore = restore
        self._set_controls_sensitive(False)
        steps = iter(blink)

        def step() -> bool:
            attr_value = next(steps, None)
            if attr_value is None:
                self.finish_identify()
                return GLib.SOURCE_REMOVE
            try:
                service.set(self.name, *attr_value)
            except WriteError as exc:
                self.window.show_error(str(exc))
                self.finish_identify()
                return GLib.SOURCE_REMOVE
            return GLib.SOURCE_CONTINUE

        if step():
            self._identify_source = GLib.timeout_add(IDENTIFY_INTERVAL_MS, step)

    def finish_identify(self) -> None:
        """Stop blinking and restore the state from before Identify."""
        if self._identify_restore is None:
            return
        if self._identify_source:
            GLib.source_remove(self._identify_source)
            self._identify_source = 0
        restore, self._identify_restore = self._identify_restore, None
        try:
            for attr, value in restore:
                self.window.service.set(self.name, attr, value)
        except WriteError as exc:
            self.window.show_error(str(exc))
        self._set_controls_sensitive(True)
        self.window.refresh()

    def _set_controls_sensitive(self, sensitive: bool) -> None:
        for widget in (self.grid, self.identify_button):
            widget.set_sensitive(sensitive)
        if not sensitive:
            self.reset_button.set_sensitive(False)
        self.window.update_reset_all()

    def _on_trigger(self, dropdown: Gtk.DropDown, _pspec) -> None:
        if self._updating:
            return
        index = dropdown.get_selected()
        if index >= len(self._trigger_names):  # Gtk.INVALID_LIST_POSITION
            return
        trigger = self._trigger_names[index]
        if trigger != self.led.active_trigger:
            self._write("trigger", trigger)

    def _on_switch(self, switch: Gtk.Switch, _pspec) -> None:
        if not self._updating:
            self._write("brightness", str(self.max if switch.get_active() else 0))

    def _on_scale(self, scale: Gtk.Scale) -> None:
        value = round(scale.get_value())
        if not self._updating and value != self.led.brightness:
            self._write("brightness", str(value))

    def _on_extra(self, entry: Gtk.Entry, name: str) -> None:
        self._write(name, entry.get_text())

    def _on_extra_button(self, _button: Gtk.Button, entry: Gtk.Entry, name: str) -> None:
        self._write(name, entry.get_text())


class MainWindow(Gtk.ApplicationWindow):
    def __init__(self, app: Gtk.Application, service: LedService, client: HelperClient) -> None:
        super().__init__(
            application=app, title="LED Control", default_width=560, default_height=720
        )
        self.service = service
        self.client = client
        self.cards: dict[str, LedCard] = {}
        self.radios = sysfs.radios()

        header = Gtk.HeaderBar()
        refresh = Gtk.Button(icon_name="view-refresh-symbolic", tooltip_text="Refresh")
        refresh.connect("clicked", lambda _b: self.refresh())
        self.reset_all = Gtk.Button(label="Reset all")
        self.reset_all.connect("clicked", lambda _b: self._reset_all())
        menu = Gio.Menu()
        menu.append("Use current state as defaults", "win.capture-defaults")
        menu_button = Gtk.MenuButton(icon_name="open-menu-symbolic", menu_model=menu)
        capture = Gio.SimpleAction.new("capture-defaults", None)
        capture.connect("activate", lambda *_: self._capture_defaults())
        self.add_action(capture)
        header.pack_start(refresh)
        header.pack_end(menu_button)
        header.pack_end(self.reset_all)
        self.set_titlebar(header)

        self.banner = Gtk.Box(
            spacing=8, margin_top=6, margin_bottom=6, margin_start=12, margin_end=12
        )
        self.banner_label = Gtk.Label(xalign=0, hexpand=True, wrap=True)
        self.unlock = Gtk.Button(label="Unlock")
        self.unlock.connect("clicked", lambda _b: self.authorize())
        self.banner.append(self.banner_label)
        self.banner.append(self.unlock)

        self.status = Gtk.Label(
            xalign=0, wrap=True, margin_start=12, margin_end=12, margin_bottom=6, visible=False
        )
        self.status.add_css_class("error")
        self._status_timeout = 0

        self.list = Gtk.Box(
            orientation=Gtk.Orientation.VERTICAL,
            spacing=10,
            margin_top=10,
            margin_bottom=10,
            margin_start=12,
            margin_end=12,
        )
        scroller = Gtk.ScrolledWindow(vexpand=True, child=self.list)

        root = Gtk.Box(orientation=Gtk.Orientation.VERTICAL)
        root.append(self.banner)
        root.append(scroller)
        root.append(self.status)
        self.set_child(root)

        self.refresh()
        GLib.timeout_add_seconds(REFRESH_SECONDS, self._tick)
        self.authorize()

    # --- authorization ------------------------------------------------------

    def _set_locked(self, locked: bool, message: str = "") -> None:
        self.banner.set_visible(locked)
        self.banner_label.set_text(message)
        self.list.set_sensitive(not locked)
        self.reset_all.set_sensitive(not locked)

    def authorize(self) -> None:
        """Start the root helper in a thread, so the window stays responsive
        while the polkit password dialog is open."""
        self._set_locked(True, "Waiting for authorization…")
        self.unlock.set_sensitive(False)

        def done(error: str | None) -> bool:
            self.unlock.set_sensitive(True)
            if error:
                self._set_locked(True, f"Read-only: {error}.")
            else:
                self._set_locked(False)
            return GLib.SOURCE_REMOVE

        def work() -> None:
            try:
                self.client.start()
                error = None
            except WriteError as exc:
                error = str(exc)
            GLib.idle_add(done, error)

        threading.Thread(target=work, daemon=True).start()

    # --- actions ------------------------------------------------------------

    def run(self, func, *args) -> None:
        try:
            func(*args)
        except WriteError as exc:
            self.show_error(str(exc))
        self.refresh()

    def update_reset_all(self) -> None:
        busy = any(card.identifying for card in self.cards.values())
        self.reset_all.set_sensitive(self.client.running and not busy)

    def _reset_all(self) -> None:
        errors = self.service.reset_all()
        if errors:
            self.show_error("\n".join(errors))
        self.refresh()

    def _capture_defaults(self) -> None:
        self.service.capture_defaults()
        self.refresh()

    def show_error(self, message: str) -> None:
        self.status.set_text(message)
        self.status.set_visible(True)
        if self._status_timeout:
            GLib.source_remove(self._status_timeout)

        def hide() -> bool:
            self.status.set_visible(False)
            self._status_timeout = 0
            return GLib.SOURCE_REMOVE

        self._status_timeout = GLib.timeout_add_seconds(8, hide)

    def _tick(self) -> bool:
        self.refresh()
        return GLib.SOURCE_CONTINUE

    def refresh(self) -> None:
        leds = self.service.leds()
        if [led.name for led in leds] != list(self.cards):
            self.service.load_defaults()  # picks up hot-plugged LEDs
            while child := self.list.get_first_child():
                self.list.remove(child)
            self.cards = {}
            for led in leds:
                card = LedCard(self, led)
                self.cards[led.name] = card
                self.list.append(card)
            if not leds:
                self.list.append(Gtk.Label(label="No LEDs found in /sys/class/leds"))
        else:
            for led in leds:
                self.cards[led.name].update(led)


class LedControlApp(Gtk.Application):
    def __init__(self) -> None:
        super().__init__(application_id=APP_ID, flags=Gio.ApplicationFlags.DEFAULT_FLAGS)
        self.client = HelperClient()
        self.window: MainWindow | None = None

    def do_activate(self) -> None:
        if self.window is None:
            store = defaults.DefaultsStore(defaults.cache_dir(), defaults.boot_id())
            service = LedService(self.client, store)
            service.load_defaults()
            self.window = MainWindow(self, service, self.client)
        self.window.present()

    def do_shutdown(self) -> None:
        if self.window is not None:
            for card in self.window.cards.values():
                card.finish_identify()
        self.client.close()
        Gtk.Application.do_shutdown(self)


def main() -> int:
    # WM_CLASS / app id must match the .desktop file name for the menu icon and
    # taskbar grouping to work.
    GLib.set_prgname(APP_ID)
    GLib.set_application_name("LED Control")
    Gtk.Window.set_default_icon_name(APP_ID)
    return LedControlApp().run(None)
