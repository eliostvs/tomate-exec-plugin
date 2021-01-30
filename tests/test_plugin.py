import pytest
import subprocess
from blinker import Namespace
from gi.repository import Gtk
from tomate.pomodoro import State
from tomate.pomodoro.config import Config
from tomate.pomodoro.event import Events
from tomate.pomodoro.graph import graph
from tomate.ui.test import Q


@pytest.fixture()
def check_output(mocker, monkeypatch):
    import exec_plugin

    m = mocker.Mock()
    monkeypatch.setattr(exec_plugin.subprocess, "check_output", m)
    return m


@pytest.fixture()
def dispatcher():
    return Namespace().signal("dispatcher")


@pytest.fixture()
def config(dispatcher, tmpdir):
    instance = Config(dispatcher)
    tmp_path = tmpdir.mkdir("tomate").join("tomate.config")
    instance.config_path = lambda: tmp_path.strpath

    graph.providers.clear()
    graph.register_instance("tomate.config", instance)

    return instance


@pytest.fixture
def subject(config):
    import exec_plugin

    Events.Session.receivers.clear()
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

    command = config.get("exec_plugin", option)
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
    config.remove("exec_plugin", option)

    subject.activate()

    Events.Session.send(event)

    check_output.assert_not_called()


def test_execute_command_fail(subject, config):
    config.set("exec_plugin", "start_command", "flflflf")

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
        "name, command",
        [
            ("start_command", "echo start"),
            ("stop_command", "echo stop"),
            ("finish_command", "echo finish"),
        ],
    )
    def test_when_has_commands(self, name, command, subject):
        window = subject.settings_window(Gtk.Window())
        window.run()

        entry = Q.select(window.widget, Q.name(f"{name}_entry"))
        assert entry is not None
        assert entry.get_text() == command

        switch = Q.select(window.widget, Q.name(f"{name}_switch"))
        assert switch is not None
        assert switch.get_active() is True

    def test_disable_command(self, subject, config):
        window = subject.settings_window(Gtk.Window())
        window.run()

        name = "start_command"
        switch = Q.select(window.widget, Q.name(f"{name}_switch"))
        assert switch is not None
        switch.set_active(False)
        window.on_switch_activate(switch, None, name)

        entry = Q.select(window.widget, Q.name(f"{name}_entry"))
        assert entry is not None
        assert entry.get_sensitive() is False
        assert entry.get_text() == ""

        window.widget.emit("response", 0)
        assert config.has_option("exec_plugin", name) is False

    @pytest.mark.parametrize("name", ["start_command", "stop_command", "finish_command"])
    def test_when_has_not_commands(self, name, subject, config):
        section = "exec_plugin"
        config.remove_section(section)
        config.save()

        assert config.has_section(section) is False

        window = subject.settings_window(Gtk.Window())
        window.run()

        switch = Q.select(window.widget, Q.name(f"{name}_switch"))
        assert switch is not None
        assert switch.get_active() is False

        entry = Q.select(window.widget, Q.name(f"{name}_entry"))
        assert entry is not None
        assert entry.get_text() == ""

    def test_change_command(self, subject, config):
        window = subject.settings_window(Gtk.Window())
        window.run()

        name = "start_command"
        entry = Q.select(window.widget, Q.name(f"{name}_entry"))
        assert entry is not None
        entry.set_text("echo changed")

        window.widget.emit("response", 0)
        assert config.get("exec_plugin", name) == "echo changed"
