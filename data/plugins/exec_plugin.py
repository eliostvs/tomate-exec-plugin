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
START_OPTION_NAME = "start_command"
STOP_OPTION_NAME = "stop_command"
FINISH_OPTION_NAME = "finish_command"
COMMANDS = [
    START_OPTION_NAME,
    STOP_OPTION_NAME,
    FINISH_OPTION_NAME,
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
        return self.call_command(START_OPTION_NAME, "start")

    @suppress_errors
    @on(Events.SESSION_INTERRUPT)
    def on_session_stopped(self, *_, **__):
        return self.call_command(STOP_OPTION_NAME, "stop")

    @suppress_errors
    @on(Events.SESSION_END)
    def on_session_finished(self, *_, **__):
        return self.call_command(FINISH_OPTION_NAME, "finish")

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
    rows = 0

    def __init__(self, config: Config, toplevel):
        self.config = config
        self.create_widget(toplevel)

    def create_widget(self, toplevel):
        grid = Gtk.Grid(column_spacing=12, row_spacing=12, margin_bottom=12)
        self.create_section(grid)
        self.create_option(grid, _("On start:"), START_OPTION_NAME)
        self.create_option(grid, _("On stop:"), STOP_OPTION_NAME)
        self.create_option(grid, _("On finish:"), FINISH_OPTION_NAME)
        self.widget = Gtk.Dialog(
            border_width=12,
            modal=True,
            resizable=False,
            title=_("Preferences"),
            transient_for=toplevel,
            window_position=Gtk.WindowPosition.CENTER_ON_PARENT,
        )
        self.widget.add_button(_("Close"), Gtk.ResponseType.CLOSE)
        self.widget.connect("response", self.on_close)
        self.widget.set_size_request(350, -1)
        self.widget.get_content_area().add(grid)

    def create_section(self, grid):
        label = Gtk.Label(
            label="<b>{0}</b>".format(_("Execute command")),
            halign=Gtk.Align.START,
            hexpand=True,
            use_markup=True,
        )
        grid.attach(label, 0, self.rows, 1, 1)
        self.rows += 1

    def run(self):
        self.read_config()
        self.widget.show_all()
        return self.widget

    def on_close(self, widget, _):
        for command_name in COMMANDS:
            entry = getattr(self, command_name + "_entry")
            command = strip_space(entry.get_text())
            if command:
                logger.debug("action=setConfig option=%s value=%s", command_name, command)
                self.config.set(SECTION_NAME, command_name, command)

        widget.destroy()

    def read_config(self):
        logger.debug("action=readConfig")

        for command_name in COMMANDS:
            command = self.config.get(SECTION_NAME, command_name)
            switch = getattr(self, command_name + "_switch")
            entry = getattr(self, command_name + "_entry")

            if command is not None:
                switch.props.active = True
                entry.set_properties(sensitive=True, text=command)
            else:
                switch.props.active = False
                entry.props.sensitive = False

    def create_option(self, grid, label, command):
        label = Gtk.Label(label=_(label), hexpand=True, halign=Gtk.Align.END)
        grid.attach(label, 0, self.rows, 1, 1)

        switch = Gtk.Switch(hexpand=True, halign=Gtk.Align.START, name=command + "_switch")
        switch.connect("notify::active", self.on_switch_toggle, command)
        grid.attach_next_to(switch, label, Gtk.PositionType.RIGHT, 1, 1)
        setattr(self, command + "_switch", switch)
        self.rows += 1

        entry = Gtk.Entry(editable=True, sensitive=False, name=command + "_entry")
        grid.attach(entry, 0, self.rows, 4, 1)
        setattr(self, command + "_entry", entry)
        self.rows += 1

    def on_switch_toggle(self, switch, _, command_name):
        entry = getattr(self, command_name + "_entry")

        if switch.get_active():
            entry.set_sensitive(True)
        else:
            self.reset_option(entry, command_name)

    def reset_option(self, entry, command_name):
        logger.debug("action=remove_config command=%s", command_name)
        self.config.remove(SECTION_NAME, command_name)
        entry.set_properties(text="", sensitive=False)
