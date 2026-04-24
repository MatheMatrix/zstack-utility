# Server Specific Configurations
# See https://pecan.readthedocs.org/en/latest/configuration.html#server-configuration # noqa
import os
server = {
    'port': 7090,
    'host': os.environ.get('BM_AGENT_BIND_IP', '::')
}

# Pecan Application Configurations
# See https://pecan.readthedocs.org/en/latest/configuration.html#application-configuration # noqa
app = {
    'root': 'bm_instance_agent.api.controllers.root.RootController',
    'modules': ['bm_instance_agent.api'],
    'debug': False
}
