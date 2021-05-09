import logging
import subprocess
from locale import gettext as _

import gi

gi.require_version("Gtk", "3.0")

from wiring import Graph
from gi.repository import Gtk

import tomate.pomodoro.plugin as plugin
from tomate.pomodoro import Bus, Config, Events, on, suppress_errors

logger = logging.getLogger(__name__)

SECTION_NAME = "exec_plugin"
START_OPTION = "start_command"
STOP_OPTION = "stop_command"
FINISH_OPTION = "finish_command"
OPTIONS = [
    START_OPTION,
    STOP_OPTION,
    FINISH_OPTION,
]


def strip_space(command):
    if command is not None:
        return command.strip()


class ExecPlugin(plugin.Plugin):
    has_settings = True

    @suppress_errors
    def __init__(self):
        super().__init__()
        self.config = None

    def configure(self, bus: Bus, graph: Graph) -> None:
        super().configure(bus, graph)
        self.config = graph.get("tomate.config")

    @suppress_errors
    @on(Events.SESSION_START)
    def on_session_started(self, *_, **__):
        return self.call_command(START_OPTION, "start")

    @suppress_errors
    @on(Events.SESSION_INTERRUPT)
    def on_session_stopped(self, *_, **__):
        return self.call_command(STOP_OPTION, "stop")

    @suppress_errors
    @on(Events.SESSION_END)
    def on_session_finished(self, *_, **__):
        return self.call_command(FINISH_OPTION, "finish")

    def call_command(self, option, event):
        command = self.read_command(option)
        if command:
            try:
                logger.debug("action=runCommandStart event=%s cmd='%s'", event, command)
                output = subprocess.check_output(command, shell=True, stderr=subprocess.STDOUT)
                logger.debug("action=runCommandEnd event=%s output=%s", event, output)
                return True
            except subprocess.CalledProcessError as error:
                logger.debug(
                    "action=runCommandFailed event=%s cmd=%s output=%s returncode=%s",
                    event,
                    error.cmd,
                    error.output,
                    error.returncode,
                )
        return False

    def read_command(self, option):
        return strip_space(self.config.get(SECTION_NAME, option))

    def settings_window(self, toplevel):
        return SettingsDialog(self.config, toplevel)


class SettingsDialog:
    def __init__(self, config: Config, toplevel):
        self.config = config
        self.widget = self.create_dialog(toplevel)

    def create_dialog(self, toplevel) -> Gtk.Dialog:
        grid = Gtk.Grid(column_spacing=12, row_spacing=12, margin_bottom=12)
        self.create_section(grid)
        self.create_option(grid, 1, _("On start:"), START_OPTION)
        self.create_option(grid, 3, _("On stop:"), STOP_OPTION)
        self.create_option(grid, 5, _("On finish:"), FINISH_OPTION)
        dialog = Gtk.Dialog(
            border_width=12,
            modal=True,
            resizable=False,
            title=_("Preferences"),
            transient_for=toplevel,
            window_position=Gtk.WindowPosition.CENTER_ON_PARENT,
        )
        dialog.add_button(_("Close"), Gtk.ResponseType.CLOSE)
        dialog.connect("response", lambda w, _: w.destroy())
        dialog.set_size_request(350, -1)
        dialog.get_content_area().add(grid)
        return dialog

    def create_section(self, grid: Gtk.Grid) -> None:
        label = Gtk.Label(
            label="<b>{0}</b>".format(_("Commands")),
            halign=Gtk.Align.START,
            hexpand=True,
            use_markup=True,
        )
        grid.attach(label, 0, 0, 1, 1)

    def run(self) -> None:
        self.widget.show_all()
        return self.widget

    def create_option(self, grid: Gtk.Grid, row: int, label: str, option: str) -> None:
        command = self.config.get(SECTION_NAME, option, fallback="")

        label = Gtk.Label(label=_(label), hexpand=True, halign=Gtk.Align.END)
        grid.attach(label, 0, row, 1, 1)

        entry = Gtk.Entry(editable=True, sensitive=bool(command), text=command, name=option + "_entry")
        entry.connect("notify::text", self.on_command_change, option)
        grid.attach(entry, 0, row + 1, 4, 1)

        switch = Gtk.Switch(hexpand=True, halign=Gtk.Align.START, active=bool(command), name=option + "_switch")
        switch.connect("notify::active", self.on_option_change, entry, option)
        grid.attach_next_to(switch, label, Gtk.PositionType.RIGHT, 1, 1)

    def on_command_change(self, entry: Gtk.Entry, _, option: str) -> None:
        command = strip_space(entry.props.text)
        if command:
            logger.debug("action=set_option option=%s command=%s", option, command)
            self.config.set(SECTION_NAME, option, command)

    def on_option_change(self, switch: Gtk.Switch, _, entry: Gtk.Entry, option: str) -> None:
        if switch.props.active:
            entry.props.sensitive = True
        else:
            self.remove_option(entry, option)

    def remove_option(self, entry: Gtk.Entry, option: str) -> None:
        logger.debug("action=remove_option option=%s", option)
        self.config.remove(SECTION_NAME, option)
        entry.set_properties(text="", sensitive=False)
