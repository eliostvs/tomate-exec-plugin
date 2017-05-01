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


class ExecPlugin(tomate.plugin.Plugin):
    has_settings = True

    @suppress_errors
    def __init__(self):
        super(ExecPlugin, self).__init__()
        self.config = graph.get('tomate.config')

    @suppress_errors
    @on(Events.Session, [State.started])
    def on_session_started(self, *args, **kwargs):
        command = self.config.get(CONFIG_SECTION_NAME, CONFIG_START_OPTION_NAME)
        if command:
            self.execute_command(command)

    @suppress_errors
    @on(Events.Session, [State.stopped])
    def on_session_stopped(self, *args, **kwargs):
        command = self.config.get(CONFIG_SECTION_NAME, CONFIG_STOP_OPTION_NAME)
        if command:
            self.execute_command(command)

    @suppress_errors
    @on(Events.Session, [State.finished])
    def on_session_finished(self, *args, **kwargs):
        command = self.config.get(CONFIG_SECTION_NAME, CONFIG_FINISH_OPTION_NAME)
        if command:
            self.execute_command(command)

    @staticmethod
    def execute_command(command):
        try:
            logger.debug("action=execCommandStart cmd='%s'", command)

            output = subprocess.check_output(command, shell=True, stderr=subprocess.STDOUT)

            logger.debug('action=execCommandComplete output=%s', output)

            return True

        except subprocess.CalledProcessError as error:
            logger.debug('action=CommandFailed cmd=%s output=%s returncode=%s',
                         error.cmd, error.output, error.returncode)

            return False

    def settings_window(self):
        pass
        # return self.preference_dialog.run()


class PreferenceDialog:
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
        self.widget.connect('response', lambda widget, response: widget.hide())
        self.widget.set_size_request(350, 200)

        self.custom_option = Gtk.Switch(hexpand=True, halign=Gtk.Align.START)
        self.custom_option.connect('notify::active', self.on_option_activate)

        label = Gtk.Label(_('Custom alarm:'),
                          margin_right=12,
                          hexpand=True,
                          halign=Gtk.Align.END)

        self.file_path = Gtk.Entry(editable=False,
                                   sensitive=False,
                                   secondary_icon_name=Gtk.STOCK_FILE,
                                   secondary_icon_activatable=True)

        self.file_path.connect('icon-press', self.on_icon_press)

        grid = Gtk.Grid(
            column_spacing=6,
            margin_bottom=12,
            margin_left=12,
            margin_right=12,
            margin_top=12,
            row_spacing=6,
        )

        grid.attach(label, 0, 0, 1, 1)
        grid.attach_next_to(self.custom_option, label, Gtk.PositionType.RIGHT, 1, 1)
        grid.attach(self.file_path, 0, 1, 4, 1)

        self.widget.get_content_area().add(grid)

    def run(self):
        self.read_config()
        self.widget.show_all()
        return self.widget

    def read_config(self):
        logger.debug('action=readConfig')

        file_uri = self.config.get(CONFIG_SECTION_NAME, CONFIG_START_OPTION_NAME)
        if file_uri is not None:
            self.custom_option.set_active(True)
            self.file_path.set_sensitive(True)
            self.file_path.set_text(file_uri)
        else:
            self.custom_option.set_active(False)
            self.file_path.set_sensitive(False)

    def on_option_activate(self, switch, param):
        if switch.get_active():
            self.file_path.set_sensitive(True)
        else:
            self.reset_option()

    def reset_option(self):
        if self.file_path.get_text():
            logger.debug('action=alarmOptionReset needed=true')
            self.file_path.set_text('')
            self.config.remove(CONFIG_SECTION_NAME, CONFIG_OPTION_NAME)
        else:
            logger.debug('action=alarmOptionReset needed=false')

        self.file_path.set_sensitive(False)
