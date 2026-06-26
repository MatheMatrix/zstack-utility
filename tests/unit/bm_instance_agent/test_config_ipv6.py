import importlib
import os
from unittest.mock import MagicMock


BM_AGENT_BIND_IP_ENV = 'BM_AGENT_BIND_IP'
IPV6_BIND_ADDRESS = '::'
EXPLICIT_BIND_ADDRESS = '2001:db8::10'


def test_pecan_api_config_defaults_to_dual_stack_bind():
    old_value = os.environ.pop(BM_AGENT_BIND_IP_ENV, None)
    try:
        config = importlib.import_module("bm_instance_agent.api.config")
        config = importlib.reload(config)
        assert config.server['host'] == IPV6_BIND_ADDRESS
    finally:
        if old_value is not None:
            os.environ[BM_AGENT_BIND_IP_ENV] = old_value


def test_pecan_api_config_accepts_explicit_bind_env():
    old_value = os.environ.get(BM_AGENT_BIND_IP_ENV)
    os.environ[BM_AGENT_BIND_IP_ENV] = EXPLICIT_BIND_ADDRESS
    try:
        config = importlib.import_module("bm_instance_agent.api.config")
        config = importlib.reload(config)
        assert config.server['host'] == EXPLICIT_BIND_ADDRESS
    finally:
        if old_value is None:
            os.environ.pop(BM_AGENT_BIND_IP_ENV, None)
        else:
            os.environ[BM_AGENT_BIND_IP_ENV] = old_value


def test_oslo_api_config_defaults_to_dual_stack_bind():
    try:
        oslo_config = importlib.import_module("oslo_config")
    except ImportError:
        return
    if isinstance(oslo_config, MagicMock):
        return

    old_value = os.environ.pop(BM_AGENT_BIND_IP_ENV, None)
    try:
        config = importlib.import_module("bm_instance_agent.conf.api")
        config = importlib.reload(config)
        host_opts = [opt for opt in config.opts if getattr(opt, 'name', None) == 'host_ip']
        if not host_opts:
            return
        host_opt = host_opts[0]
        assert host_opt.default == IPV6_BIND_ADDRESS
    finally:
        if old_value is not None:
            os.environ[BM_AGENT_BIND_IP_ENV] = old_value
