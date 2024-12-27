import os
import ConfigParser

from zstacklib.utils import log

logger = log.get_logger(__name__)


def get_config_path_from_fs_id(fs_id):
    xstor_flag = "/home/xclient/"
    if os.path.exists(xstor_flag):
        config_path = "/etc/xstor_{0}.conf".format(fs_id)
        if os.path.exists(config_path):
            return config_path
        default_config_path = "/etc/xstor.conf"
        if not os.path.exists(default_config_path):
            raise Exception("no configuration file path is matched, system id: {0}.".format(fs_id))
        config = ConfigParser.ConfigParser()
        config.read(default_config_path)
        system_id = config.get('xstor', 'system_id', None)
        if system_id is None or system_id != str(fs_id):
            raise Exception("no configuration file path is matched, system id: {0}.".format(fs_id))
        return default_config_path
    else:
        raise Exception("no configuration file path is matched, fs id: {0}.".format(fs_id))
