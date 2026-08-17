import os
from zstacklib.utils import network_ipv6


BM_AGENT_BIND_IP_ENV = 'BM_AGENT_BIND_IP'


# Server Specific Configurations
# See https://pecan.readthedocs.org/en/latest/configuration.html#server-configuration # noqa
server = {
    'port': 7090,
    'host': os.environ.get(BM_AGENT_BIND_IP_ENV, network_ipv6.DUAL_STACK_BIND_ADDRESS)
}

# Pecan Application Configurations
# See https://pecan.readthedocs.org/en/latest/configuration.html#application-configuration # noqa
app = {
    'root': 'bm_instance_agent.api.controllers.root.RootController',
    'modules': ['bm_instance_agent.api'],
    'debug': False
}
