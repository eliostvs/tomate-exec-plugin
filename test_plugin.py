from __future__ import unicode_literals

import subprocess

import pytest
from mock import Mock
from tomate.constant import State
from tomate.event import Events
from tomate.graph import graph


def method_called(result):
    return result[0][0]


@pytest.fixture
def check_output():
    return Mock()


@pytest.fixture(autouse=True)
def config():
    mock = Mock()
    graph.providers.clear()
    graph.register_instance('tomate.config', mock)

    Events.Session.receivers.clear()

    return mock


@pytest.fixture
def plugin(monkeypatch, check_output):
    import exec_plugin

    monkeypatch.setattr(exec_plugin.subprocess, 'check_output', check_output)

    return exec_plugin.ExecPlugin()


def get_side_effect_not_return(option_name):
    from exec_plugin import CONFIG_SECTION_NAME

    def side_effect(section, option):
        if section == CONFIG_SECTION_NAME and option == option_name:
            return None

        raise Exception()

    return side_effect


def get_side_effect_return(option_name):
    from exec_plugin import CONFIG_SECTION_NAME

    def side_effect(section, option):
        if section == CONFIG_SECTION_NAME and option == option_name:
            return 'command'

    return side_effect


def test_execute_start_command_when_configured(plugin, config, check_output):
    from exec_plugin import CONFIG_START_OPTION_NAME

    config.get.side_effect = get_side_effect_return(CONFIG_START_OPTION_NAME)

    plugin.activate()

    result = Events.Session.send(State.started)

    assert len(result) == 1
    assert plugin.on_session_started == method_called(result)
    check_output.assert_called_once_with('command', shell=True, stderr=subprocess.STDOUT)


def test_execute_stop_command_when_configured(plugin, config, check_output):
    from exec_plugin import CONFIG_STOP_OPTION_NAME

    config.get.side_effect = get_side_effect_return(CONFIG_STOP_OPTION_NAME)

    plugin.activate()

    result = Events.Session.send(State.stopped)

    assert len(result) == 1
    assert plugin.on_session_stopped == method_called(result)
    check_output.assert_called_once_with('command', shell=True, stderr=subprocess.STDOUT)


def test_execute_finished_command_when_configured(plugin, config, check_output):
    from exec_plugin import CONFIG_FINISH_OPTION_NAME

    config.get.side_effect = get_side_effect_return(CONFIG_FINISH_OPTION_NAME)

    plugin.activate()

    result = Events.Session.send(State.finished)

    assert len(result) == 1
    assert plugin.on_session_finished == method_called(result)
    check_output.assert_called_once_with('command', shell=True, stderr=subprocess.STDOUT)


def test_not_execute_finished_command_when_not_configured(plugin, config, check_output):
    from exec_plugin import CONFIG_FINISH_OPTION_NAME

    config.get.side_effect = get_side_effect_not_return(CONFIG_FINISH_OPTION_NAME)

    plugin.activate()

    result = Events.Session.send(State.finished)

    assert len(result) == 1
    assert plugin.on_session_finished == method_called(result)
    check_output.assert_not_called()


def test_not_execute_stop_command_when_not_configured(plugin, config, check_output):
    from exec_plugin import CONFIG_STOP_OPTION_NAME

    config.get.side_effect = get_side_effect_not_return(CONFIG_STOP_OPTION_NAME)

    plugin.activate()

    result = Events.Session.send(State.stopped)

    assert len(result) == 1
    assert plugin.on_session_stopped == method_called(result)
    check_output.assert_not_called()


def test_not_execute_start_command_when_not_configured(plugin, config, check_output):
    from exec_plugin import CONFIG_START_OPTION_NAME

    config.get.side_effect = get_side_effect_not_return(CONFIG_START_OPTION_NAME)

    plugin.activate()

    result = Events.Session.send(State.started)

    assert len(result) == 1
    assert plugin.on_session_started == method_called(result)
    check_output.assert_not_called()


def test_execute_command_return_error(plugin, config, check_output):
    from exec_plugin import CONFIG_START_OPTION_NAME

    config.get.side_effect = get_side_effect_return(CONFIG_START_OPTION_NAME)

    check_output.side_effect = subprocess.CalledProcessError(-1, 'command')

    assert plugin.execute_command(CONFIG_START_OPTION_NAME, '') is False
