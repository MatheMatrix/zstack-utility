import os

from oslo_config import cfg
from zstacklib.utils import network_ipv6


BM_AGENT_BIND_IP_ENV = 'BM_AGENT_BIND_IP'


opts = [
    cfg.HostAddressOpt('host_ip',
                       default=os.environ.get(BM_AGENT_BIND_IP_ENV, network_ipv6.DUAL_STACK_BIND_ADDRESS),
                       help='''
The ip address on which bm-instance-agent listens.
'''),
    cfg.PortOpt('port',
                default=7090,
                help='''
The TCP port on which bm-instance-agent listens.
'''),
    cfg.IntOpt('api_workers',
               help='''
Number of workers for Agent API. The default is equal to the number of CPUs
available if that can be datermined, else a default worker count of 1 is
returned.
'''),
    cfg.BoolOpt('enable_ssl_api',
                default=False,
                help='''
Enable the integrated stand-alone API to service requests via HTTPS instead
of HTTP, note, this option should always False.
''')
]


opt_group = cfg.OptGroup(name='api',
                         title='Options for the bm-instance-agent api')


API_OPTS = (opts)


def register_opts(conf):
    conf.register_group(opt_group)
    conf.register_opts(opts, group=opt_group)


def list_opts():
    return {
        opt_group: API_OPTS
    }
