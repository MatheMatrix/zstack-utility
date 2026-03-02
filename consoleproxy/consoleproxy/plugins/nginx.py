# -*- coding: utf-8 -*-
import os
from zstacklib.utils import log
from zstacklib.utils.bash import bash_roe

logger = log.get_logger(__name__)

BM2_INSTANCE_NGINX_CONF_DIR = "/var/lib/zstack/nginx/baremetal/v2/management_node/"


class NginxPlugin(object):
    def __init__(self, conf_dir=BM2_INSTANCE_NGINX_CONF_DIR):
        self.BM2_INSTANCE_NGINX_CONF_DIR = conf_dir

    def _ensure_service_running(self):
        ret, out, err = bash_roe("systemctl status zstack-baremetal-nginx.service")
        if ret != 0:
            bash_roe("systemctl start zstack-baremetal-nginx.service")
            ret, out, err = bash_roe("systemctl status zstack-baremetal-nginx.service")
        return ret == 0

    def check_availability(self, args):
        running = self._ensure_service_running()
        if not running:
            logger.warn('zstack-baremetal-nginx.service is not running, availability false')
        return running

    def establish(self, cmd):
        ret, out, err = bash_roe("systemctl status zstack-baremetal-nginx.service")
        if ret != 0:
            ret, out, err = bash_roe("systemctl start zstack-baremetal-nginx.service")
            if ret != 0:
                raise Exception("failed to start zstack-baremetal-nginx.service")

        if not os.path.exists(self.BM2_INSTANCE_NGINX_CONF_DIR):
            os.makedirs(self.BM2_INSTANCE_NGINX_CONF_DIR, exist_ok=True)

        conf_path = os.path.join(self.BM2_INSTANCE_NGINX_CONF_DIR, cmd.vmUuid + ".conf")
        with open(conf_path, 'w') as f:
            content = "location ^~/%s/ { proxy_set_header Host $host; proxy_pass http://%s:%s; }" % (
                cmd.token, cmd.targetHostname, cmd.targetPort)
            f.write(content)

        ret, out, err = bash_roe("systemctl reload zstack-baremetal-nginx.service")
        if ret != 0:
            raise Exception("failed to reload zstack-baremetal-nginx.service")
        return cmd.proxyPort

    def delete(self, cmd):
        ret, out, err = bash_roe("systemctl status zstack-baremetal-nginx.service")
        if ret != 0:
            ret, out, err = bash_roe("systemctl start zstack-baremetal-nginx.service")
            if ret != 0:
                raise Exception("failed to start zstack-baremetal-nginx.service")

        conf_path = os.path.join(self.BM2_INSTANCE_NGINX_CONF_DIR, cmd.vmUuid + ".conf")
        if os.path.exists(conf_path):
            os.remove(conf_path)

        ret, out, err = bash_roe("systemctl reload zstack-baremetal-nginx.service")
        if ret != 0:
            raise Exception("failed to reload zstack-baremetal-nginx.service")
