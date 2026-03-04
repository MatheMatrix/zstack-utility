import sys
from unittest.mock import MagicMock

mock_modules = [
    'concurrentlog_handler',
    'progress_report',
    'simplejson',
    'pickledb',
    'pyroute2',
    'pyroute2.netlink',
    'pyroute2.netlink.rtnl',
    'pyroute2.netlink.rtnl.ifinfmsg',
    'netaddr',
    'xxhash',
    'libvirt',
    'log',
]

for mod in mock_modules:
    if mod not in sys.modules:
        sys.modules[mod] = MagicMock()

sys.modules['concurrentlog_handler'].ConcurrentRotatingFileHandler = MagicMock()
sys.modules['progress_report'].WatchThread_1 = MagicMock()
