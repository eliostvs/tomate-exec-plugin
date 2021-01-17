import pytest
from blinker import Namespace
from gi.repository import Gtk
from tomate.pomodoro import State
from tomate.pomodoro.config import Config
from tomate.pomodoro.event import Events
from tomate.pomodoro.graph import graph

from tomate.ui.test import query_selector, by_name


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


@pytest.mark.parametrize("event", [State.started, State.stopped, State.finished])
def test_execute_commands_when_event_is_trigger(event, subject):
    subject.activate()

    calls = Events.Session.send(event)
    assert len(calls) == 1

    _, result = calls[0]
    assert result is True


@pytest.mark.parametrize(
    "event, command",
    [
        (State.started, "start_command"),
        (State.stopped, "stop_command"),
        (State.finished, "finish_command"),
    ],
)
def test_dont_execute_commands_when_not_configured(event, command, subject, config, tmpdir):
    config.remove("exec_plugin", command)

    subject.activate()

    calls = Events.Session.send(event)
    assert len(calls) == 1

    _, result = calls[0]
    assert result is False


def test_execute_command_fail(subject, config, tmpdir):
    config.set("exec_plugin", "start_command", "flflflf")

    subject.activate()

    calls = Events.Session.send(State.started)
    assert len(calls) == 1

    _, result = calls[0]
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

        entry = query_selector(window.widget, by_name(f"{name}_entry"))
        assert entry is not None
        assert entry.get_text() == command

        switch = query_selector(window.widget, by_name(f"{name}_switch"))
        assert switch is not None
        assert switch.get_active() is True

    def test_disable_command(self, subject, config):
        window = subject.settings_window(Gtk.Window())
        window.run()

        name = "start_command"
        switch = query_selector(window.widget, by_name(f"{name}_switch"))
        assert switch is not None
        switch.set_active(False)
        window.on_switch_activate(switch, None, name)

        entry = query_selector(window.widget, by_name(f"{name}_entry"))
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

        switch = query_selector(window.widget, by_name(f"{name}_switch"))
        assert switch is not None
        assert switch.get_active() is False

        entry = query_selector(window.widget, by_name(f"{name}_entry"))
        assert entry is not None
        assert entry.get_text() == ""

    def test_change_command(self, subject, config):
        window = subject.settings_window(Gtk.Window())
        window.run()

        name = "start_command"
        entry = query_selector(window.widget, by_name(f"{name}_entry"))
        assert entry is not None
        entry.set_text("echo changed")

        window.widget.emit("response", 0)
        assert config.get("exec_plugin", name) == "echo changed"
