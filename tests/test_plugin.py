import subprocess

import pytest
from blinker import NamedSignal
from gi.repository import Gtk
from tomate.pomodoro.config import Config
from tomate.pomodoro.event import Events
from tomate.pomodoro.graph import graph
from tomate.ui.test import Q

SECTION_NAME = "exec_plugin"


@pytest.fixture
def check_output(mocker, monkeypatch):
    import exec_plugin
    check_output = mocker.Mock(spec=subprocess.check_output)
    monkeypatch.setattr(exec_plugin.subprocess, "check_output", check_output)
    return check_output


@pytest.fixture
def bus():
    return NamedSignal("Test")


@pytest.fixture
def config(bus, tmpdir):
    instance = Config(bus)
    tmp_path = tmpdir.mkdir("tomate").join("tomate.config")
    instance.config_path = lambda: tmp_path.strpath

    graph.providers.clear()
    graph.register_instance("tomate.config", instance)
    return instance


@pytest.fixture
def subject(bus, config):
    graph.providers.clear()
    graph.register_instance("tomate.config", config)
    graph.register_instance("tomate.bus", bus)

    import exec_plugin
    return exec_plugin.ExecPlugin()


@pytest.mark.parametrize(
    "event, option",
    [
        (Events.SESSION_START, "start_command"),
        (Events.SESSION_INTERRUPT, "stop_command"),
        (Events.SESSION_END, "finish_command"),
    ],
)
def test_execute_command_when_event_is_trigger(event, option, bus, check_output, config, subject):
    subject.activate()

    bus.send(event)

    command = config.get(SECTION_NAME, option)
    check_output.assert_called_once_with(command, shell=True, stderr=subprocess.STDOUT)


@pytest.mark.parametrize(
    "event, option",
    [
        (Events.SESSION_START, "start_command"),
        (Events.SESSION_INTERRUPT, "stop_command"),
        (Events.SESSION_END, "finish_command"),
    ],
)
def test_does_not_execute_commands_when_they_are_not_configured(event, option, bus, check_output, config, subject):
    config.remove(SECTION_NAME, option)
    subject.activate()

    bus.send(event)

    check_output.assert_not_called()


def test_execute_command_fail(bus, config, subject):
    config.set(SECTION_NAME, "start_command", "flflflf")

    subject.activate()

    calls = bus.send(Events.SESSION_START)
    assert_methods_called(calls)


def assert_methods_called(calls):
    assert len(calls) == 1

    command_result = 0
    _, result = calls[command_result]

    assert result is False


class TestSettingsWindow:
    @pytest.mark.parametrize(
        "option,command",
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
    def test_without_custom_commands(self, option, config, subject):
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
    def test_disable_command(self, option, config, subject):
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
    def test_enable_command(self, option, config, subject):
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
