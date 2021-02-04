import subprocess

import pytest
from blinker import signal
from gi.repository import Gtk
from tomate.pomodoro import State
from tomate.pomodoro.config import Config
from tomate.pomodoro.event import Events
from tomate.pomodoro.graph import graph
from tomate.ui.test import Q

SECTION_NAME = "exec_plugin"


@pytest.fixture()
def check_output(mocker, monkeypatch):
    import exec_plugin

    m = mocker.Mock()
    monkeypatch.setattr(exec_plugin.subprocess, "check_output", m)
    return m


@pytest.fixture()
def config(tmpdir):
    instance = Config(signal("dispatcher"))
    tmp_path = tmpdir.mkdir("tomate").join("tomate.config")
    instance.config_path = lambda: tmp_path.strpath

    graph.providers.clear()
    graph.register_instance("tomate.config", instance)
    return instance


@pytest.fixture
def subject(config):
    Events.Session.receivers.clear()

    import exec_plugin
    return exec_plugin.ExecPlugin()


@pytest.mark.parametrize(
    "event, option",
    [
        (State.started, "start_command"),
        (State.stopped, "stop_command"),
        (State.finished, "finish_command"),
    ],
)
def test_execute_command_when_event_is_trigger(event, option, subject, config, check_output):
    subject.activate()

    Events.Session.send(event)

    command = config.get(SECTION_NAME, option)
    check_output.assert_called_once_with(command, shell=True, stderr=subprocess.STDOUT)


@pytest.mark.parametrize(
    "event, option",
    [
        (State.started, "start_command"),
        (State.stopped, "stop_command"),
        (State.finished, "finish_command"),
    ],
)
def test_do_not_execute_commands_when_not_configured(event, option, subject, config, check_output):
    config.remove(SECTION_NAME, option)
    subject.activate()

    Events.Session.send(event)

    check_output.assert_not_called()


def test_execute_command_fail(subject, config):
    config.set(SECTION_NAME, "start_command", "flflflf")

    subject.activate()

    calls = Events.Session.send(State.started)
    assert_methods_called(calls)


def assert_methods_called(calls):
    assert len(calls) == 1

    command_result = 0
    _, result = calls[command_result]

    assert result is False


class TestSettingsWindow:
    @pytest.mark.parametrize(
        "option, command",
        [
            ("start_command", "echo start"),
            ("stop_command", "echo stop"),
            ("finish_command", "echo finish"),
        ],
    )
    def test_with_custom_commands(self, option, command, subject):
        window = subject.settings_window(Gtk.Window())
        window.run()

        switch = Q.select(window.widget, Q.name(f"{option}_switch"))
        assert switch.get_active() is True

        entry = Q.select(window.widget, Q.name(f"{option}_entry"))
        assert entry.get_text() == command

    @pytest.mark.parametrize("option", ["start_command", "stop_command", "finish_command"])
    def test_without_custom_commands(self, option, subject, config):
        config.remove_section(SECTION_NAME)
        config.save()

        assert config.has_section(SECTION_NAME) is False

        window = subject.settings_window(Gtk.Window())
        window.run()

        switch = Q.select(window.widget, Q.name(f"{option}_switch"))
        assert switch.get_active() is False

        entry = Q.select(window.widget, Q.name(f"{option}_entry"))
        assert entry.get_text() == ""

    @pytest.mark.parametrize("option", ["start_command", "stop_command", "finish_command"])
    def test_disable_command(self, option, subject, config):
        window = subject.settings_window(Gtk.Window())
        window.run()

        switch = Q.select(window.widget, Q.name(f"{option}_switch"))
        switch.set_active(False)
        switch.notify("activate")

        entry = Q.select(window.widget, Q.name(f"{option}_entry"))
        assert entry.get_sensitive() is False
        assert entry.get_text() == ""

        window.widget.emit("response", 0)
        assert config.has_option(SECTION_NAME, option) is False

    @pytest.mark.parametrize("option", ["start_command", "stop_command", "finish_command"])
    def test_enable_command(self, option, subject, config):
        config.remove(SECTION_NAME, option)

        window = subject.settings_window(Gtk.Window())
        window.run()

        switch = Q.select(window.widget, Q.name(f"{option}_switch"))
        switch.set_active(True)
        switch.notify("activate")

        entry = Q.select(window.widget, Q.name(f"{option}_entry"))
        assert entry.get_sensitive() is True
        entry.set_text("echo changed")

        window.widget.emit("response", 0)
        assert config.get(SECTION_NAME, option) == "echo changed"
