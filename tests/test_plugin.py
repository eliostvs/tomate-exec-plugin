import subprocess

import pytest
from gi.repository import Gtk
from wiring import Graph

from tomate.pomodoro import Bus, Config, Events, SessionPayload, SessionType
from tomate.ui.testing import Q

SECTION_NAME = "exec_plugin"


def random_payload(session_type: SessionType = SessionType.POMODORO) -> SessionPayload:
    return SessionPayload(
        id="1234",
        type=session_type,
        duration=0,
        pomodoros=0,
    )


@pytest.fixture
def check_output(mocker, monkeypatch):
    import exec_plugin

    check_output = mocker.Mock(spec=subprocess.check_output)
    monkeypatch.setattr(exec_plugin.subprocess, "check_output", check_output)
    return check_output


@pytest.fixture
def bus() -> Bus:
    return Bus()


@pytest.fixture
def graph() -> Graph:
    g = Graph()
    g.register_instance(Graph, g)
    return g


@pytest.fixture
def config(bus, tmpdir):
    instance = Config(bus)
    tmp_path = tmpdir.mkdir("tomate").join("tomate.config")
    instance.config_path = lambda: tmp_path.strpath
    return instance


@pytest.fixture
def plugin(bus, config, graph):
    graph.providers.clear()
    graph.register_instance("tomate.config", config)
    graph.register_instance("tomate.bus", bus)

    import exec_plugin

    instance = exec_plugin.ExecPlugin()
    instance.configure(bus, graph)
    return instance


@pytest.mark.parametrize(
    "event, option",
    [
        (Events.SESSION_START, "start_command"),
        (Events.SESSION_INTERRUPT, "stop_command"),
        (Events.SESSION_END, "finish_command"),
    ],
)
def test_execute_command_when_event_is_trigger(event, option, bus, check_output, config, plugin):
    plugin.activate()

    bus.send(event, random_payload())

    command = config.get(SECTION_NAME, option)
    check_output.assert_called_once_with(command, shell=True, stderr=subprocess.STDOUT)


@pytest.mark.parametrize(
    "event, section, session_type",
    [
        (Events.SESSION_START, "start_command", SessionType.POMODORO),
        (Events.SESSION_INTERRUPT, "stop_command", SessionType.LONG_BREAK),
        (Events.SESSION_END, "finish_command", SessionType.SHORT_BREAK),
    ],
)
def test_interpolate_command(event, section, session_type, bus, check_output, config, plugin):
    config.set(SECTION_NAME, section, "$event $type")
    plugin.activate()

    bus.send(event, random_payload(session_type))

    check_output.assert_called_once_with(f"{event.name} {session_type.name}", shell=True, stderr=subprocess.STDOUT)


@pytest.mark.parametrize(
    "event, option",
    [
        (Events.SESSION_START, "start_command"),
        (Events.SESSION_INTERRUPT, "stop_command"),
        (Events.SESSION_END, "finish_command"),
    ],
)
def test_does_not_execute_commands_when_they_are_not_configured(event, option, bus, check_output, config, plugin):
    config.remove(SECTION_NAME, option)
    plugin.activate()

    assert bus.send(event, random_payload()) == [False]

    check_output.assert_not_called()


def test_execute_command_fail(bus, config, plugin):
    config.set(SECTION_NAME, "start_command", "fail")

    plugin.activate()

    assert bus.send(Events.SESSION_START, random_payload()) == [False]


class TestSettingsWindow:
    @pytest.mark.parametrize(
        "option,command",
        [
            ("start_command", "echo start"),
            ("stop_command", "echo stop"),
            ("finish_command", "echo finish"),
        ],
    )
    def test_with_custom_commands(self, option, command, plugin):
        dialog = plugin.settings_window(Gtk.Window())

        switch = Q.select(dialog.widget, Q.props("name", f"{option}_switch"))
        assert switch.props.active is True

        entry = Q.select(dialog.widget, Q.props("name", f"{option}_entry"))
        assert entry.props.text == command

    @pytest.mark.parametrize("option", ["start_command", "stop_command", "finish_command"])
    def test_without_custom_commands(self, option, config, plugin):
        config.remove_section(SECTION_NAME)
        config.save()

        assert config.has_section(SECTION_NAME) is False

        dialog = plugin.settings_window(Gtk.Window())

        switch = Q.select(dialog.widget, Q.props("name", f"{option}_switch"))
        assert switch.props.active is False

        entry = Q.select(dialog.widget, Q.props("name", f"{option}_entry"))
        assert entry.props.text == ""

    @pytest.mark.parametrize("option", ["start_command", "stop_command", "finish_command"])
    def test_disable_command(self, option, config, plugin):
        dialog = plugin.settings_window(Gtk.Window())

        switch = Q.select(dialog.widget, Q.props("name", f"{option}_switch"))
        switch.props.active = False

        entry = Q.select(dialog.widget, Q.props("name", f"{option}_entry"))
        assert entry.props.sensitive is False
        assert entry.props.text == ""

        dialog.widget.emit("response", 0)
        assert dialog.widget.props.window is None

        config.load()
        assert config.has_option(SECTION_NAME, option) is False

    @pytest.mark.parametrize("option", ["start_command", "stop_command", "finish_command"])
    def test_configure_command(self, option, config, plugin):
        config.remove(SECTION_NAME, option)

        dialog = plugin.settings_window(Gtk.Window())

        switch = Q.select(dialog.widget, Q.props("name", f"{option}_switch"))
        switch.props.active = True

        entry = Q.select(dialog.widget, Q.props("name", f"{option}_entry"))
        assert entry.props.sensitive is True
        entry.props.text = "echo changed"

        dialog.widget.emit("response", 0)
        assert dialog.widget.props.window is None

        config.load()
        assert config.get(SECTION_NAME, option) == "echo changed"
