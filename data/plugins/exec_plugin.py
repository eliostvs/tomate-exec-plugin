from __future__ import unicode_literals

import logging
import subprocess
from locale import gettext as _

import gi

gi.require_version('Gtk', '3.0')

from gi.repository import Gtk

import tomate.plugin
from tomate.constant import State
from tomate.event import Events, on
from tomate.graph import graph
from tomate.utils import suppress_errors

logger = logging.getLogger(__name__)

CONFIG_SECTION_NAME = 'exec_plugin'
CONFIG_START_OPTION_NAME = 'start_command'
CONFIG_STOP_OPTION_NAME = 'stop_command'
CONFIG_FINISH_OPTION_NAME = 'finish_command'
COMMANDS = [
    CONFIG_START_OPTION_NAME,
    CONFIG_STOP_OPTION_NAME,
    CONFIG_FINISH_OPTION_NAME
]


def parse_command(command):
    if command is not None:
        return command.strip()


class ExecPlugin(tomate.plugin.Plugin):
    has_settings = True

    @suppress_errors
    def __init__(self):
        super(ExecPlugin, self).__init__()
        self.config = graph.get('tomate.config')
        self.preference_window = PreferenceDialog(self.config)

    @suppress_errors
    @on(Events.Session, [State.started])
    def on_session_started(self, *args, **kwargs):
        command = parse_command(self.config.get(CONFIG_SECTION_NAME, CONFIG_START_OPTION_NAME))
        if command:
            self.execute_command(command, 'started')

    @suppress_errors
    @on(Events.Session, [State.stopped])
    def on_session_stopped(self, *args, **kwargs):
        command = parse_command(self.config.get(CONFIG_SECTION_NAME, CONFIG_STOP_OPTION_NAME))
        if command:
            self.execute_command(command, 'stopped')

    @suppress_errors
    @on(Events.Session, [State.finished])
    def on_session_finished(self, *args, **kwargs):
        command = parse_command(self.config.get(CONFIG_SECTION_NAME, CONFIG_FINISH_OPTION_NAME))
        if command:
            self.execute_command(command, 'finished')

    @staticmethod
    def execute_command(command, event):
        try:
            logger.debug("action=runCommandStart event=%s cmd='%s'", event, command)

            output = subprocess.check_output(command, shell=True, stderr=subprocess.STDOUT)

            logger.debug('action=runCommandComplete event=%s output=%s', event, output)

            return True

        except subprocess.CalledProcessError as error:
            logger.debug('action=runCommandFailed event=%s cmd=%s output=%s returncode=%s',
                         event, error.cmd, error.output, error.returncode)

            return False

    def settings_window(self):
        return self.preference_window.run()


class PreferenceDialog:
    rows = 0

    def __init__(self, config):
        self.config = config

        self.widget = Gtk.Dialog(
            _('Preferences'),
            None,
            modal=True,
            resizable=False,
            window_position=Gtk.WindowPosition.CENTER_ON_PARENT,
            buttons=(Gtk.STOCK_CLOSE, Gtk.ResponseType.CLOSE)
        )
        self.widget.connect('response', self.on_dialog_response)
        self.widget.set_size_request(350, 300)

        grid = Gtk.Grid(
            column_spacing=6,
            margin_bottom=12,
            margin_left=12,
            margin_right=12,
            margin_top=12,
            row_spacing=6,
        )

        self.add_section(grid)
        self.add_option(grid, 'On start:', CONFIG_START_OPTION_NAME)
        self.add_option(grid, 'On stop:', CONFIG_STOP_OPTION_NAME)
        self.add_option(grid, 'On finish:', CONFIG_FINISH_OPTION_NAME)

        self.widget.get_content_area().add(grid)

    def add_section(self, grid):
        label = Gtk.Label('<b>{0}</b>'.format(_('Execute command')),
                          halign=Gtk.Align.START,
                          margin_left=6,
                          use_markup=True)
        grid.attach(label, 0, self.rows, 1, 1)
        self.rows += 1

    def run(self):
        self.read_config()
        self.widget.show_all()
        return self.widget

    def on_dialog_response(self, widget, response):
        for command_name in COMMANDS:
            entry = getattr(self, command_name + '_entry')
            command = parse_command(entry.get_text())

            if command:
                logger.debug('action=setConfig option=%s value=%s', command_name, command)
                self.config.set(CONFIG_SECTION_NAME, command_name, command)

        widget.hide()

    def read_config(self):
        logger.debug('action=readConfig')

        for command_name in COMMANDS:
            command = self.config.get(CONFIG_SECTION_NAME, command_name)
            switch = getattr(self, command_name + '_switch')
            entry = getattr(self, command_name + '_entry')

            if command is not None:
                switch.set_active(True)
                entry.set_sensitive(True)
                entry.set_text(command)
            else:
                switch.set_active(False)
                entry.set_sensitive(False)

    def add_option(self, grid, label, command_name):
        label = Gtk.Label(_(label),
                          margin_right=6,
                          hexpand=True,
                          halign=Gtk.Align.END)
        grid.attach(label, 0, self.rows, 1, 1)

        switch = Gtk.Switch(hexpand=True, halign=Gtk.Align.START)
        switch.connect('notify::active', self.on_switch_activate, command_name)
        grid.attach_next_to(switch, label, Gtk.PositionType.RIGHT, 1, 1)
        setattr(self, command_name + '_switch', switch)
        self.rows += 1

        entry = Gtk.Entry(margin_left=6, margin_right=6, editable=True, sensitive=False)
        grid.attach(entry, 0, self.rows, 4, 1)
        setattr(self, command_name + '_entry', entry)
        self.rows += 1

    def on_switch_activate(self, switch, param, command_name):
        entry = getattr(self, command_name + '_entry')

        if switch.get_active():
            entry.set_sensitive(True)
        else:
            self.reset_option(entry, command_name)

    def reset_option(self, entry, command_name):
        if entry.get_text():
            logger.debug('action=resetCommandConfig command=%s needed=true', command_name)
            self.config.remove(CONFIG_SECTION_NAME, command_name)
            entry.set_text('')
        else:
            logger.debug('action=resetCommandConfig command=%s needed=false', command_name)

        entry.set_sensitive(False)
