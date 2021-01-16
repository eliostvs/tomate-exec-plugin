import pytest
from blinker import Namespace
from tomate.pomodoro import State
from tomate.pomodoro.config import Config
from tomate.pomodoro.event import Events
from tomate.pomodoro.graph import graph


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


@pytest.mark.parametrize("event, command", [
    (State.started, "start_command"),
    (State.stopped, "stop_command"),
    (State.finished, "finish_command")
])
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
