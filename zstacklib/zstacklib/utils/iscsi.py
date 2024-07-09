import glob
import os
import re
import urlparse

import linux
import lock
import shell
import device


# only support single ip
def get_device_path_by_wwn(disk_id):
    fnames = os.listdir('/dev/disk/by-id/')
    for fname in fnames:
        if not fname.startswith('wwn-') or not fname.endswith(disk_id):
            continue
        link_path = os.path.join('/dev/disk/by-id/', fname)
        wwid = device.get_device_wwid(os.path.basename(os.readlink(link_path)))
        if id in wwid:
            return link_path


def get_iscsi_device_serial(disk_path):
    cmd = shell.ShellCmd("sg_inq %s | grep 'serial number'" % disk_path)
    cmd(False)
    if cmd.return_code != 0:
        return None

    splits = cmd.stdout.split(":")
    if len(splits) != 2:
        return ""

    return splits[1].strip()


def get_device_path_by_serial(id):
    cmd = shell.ShellCmd("iscsiadm -m session -P 3 | grep -E 'Attached scsi disk'")
    cmd(False)
    if cmd.return_code != 0:
        return None
    disk_regex = re.compile(r'Attached scsi disk (\w+)\s+State: running')

    for line in cmd.stdout.splitlines():
        matches = disk_regex.search(line)
        if not matches:
            continue

        disk_path = "/dev/%s" % matches.group(1)
        if get_iscsi_device_serial(disk_path) == id:
            return disk_path

    return ""


class IscsiLogin(object):
    def __init__(self, url=None):
        if url:
            u = urlparse.urlparse(url)
            self.server_hostname = u.hostname
            self.server_port = u.port
            self.target = u.path.split('/')[1]
            self.chap_username = u.username
            self.chap_password = u.password
            self.disk_id = u.path.split('/')[2]
            self.lun = "*"
        else:
            self.server_hostname = None
            self.server_port = None
            self.target = None
            self.chap_username = None
            self.chap_password = None
            self.lun = 0

    @lock.lock('iscsiadm')
    def login(self):
        assert self.server_hostname, "hostname cannot be None"
        assert self.server_port, "port cannot be None"
        assert self.target, "target cannot be None"

        device_path = os.path.join('/dev/disk/by-path/', 'ip-%s:%s-iscsi-%s-lun-%s' % (
            self.server_hostname, self.server_port, self.target, self.lun))

        config_iscsi_startup_if_needed()
        shell.call('iscsiadm -m discovery -t sendtargets -p %s:%s' % (self.server_hostname, self.server_port))

        if self.chap_username and self.chap_password:
            shell.call(
                'iscsiadm   --mode node  --targetname "%s"  -p %s:%s --op=update --name node.session.auth.authmethod --value=CHAP' % (
                    self.target, self.server_hostname, self.server_port))
            shell.call(
                'iscsiadm   --mode node  --targetname "%s"  -p %s:%s --op=update --name node.session.auth.username --value=%s' % (
                    self.target, self.server_hostname, self.server_port, self.chap_username))
            shell.call(
                'iscsiadm   --mode node  --targetname "%s"  -p %s:%s --op=update --name node.session.auth.password --value=%s' % (
                    self.target, self.server_hostname, self.server_port, self.chap_password))

        s = shell.ShellCmd('iscsiadm  --mode node  --targetname "%s"  -p %s:%s --login' % (
            self.target, self.server_hostname, self.server_port))
        s(False)
        if s.return_code != 0 and 'already present' not in s.stderr:
            s.raise_error()

        shell.run("timeout 30 iscsiadm -m session -R")

        def wait_device_to_show(_):
            return bool(glob.glob(device_path))

        if not linux.wait_callback_success(wait_device_to_show, timeout=30, interval=0.5):
            raise Exception('ISCSI device[%s] is not shown up after 30s' % device_path)

        return device_path

    @staticmethod
    def rescan():
        shell.run("timeout 30 iscsiadm -m session -R")
        shell.run("timeout 360 /usr/bin/rescan-scsi-bus.sh -r")
        # only affect wwn devices
        shell.run("udevadm trigger --subsystem-match=block")

    def get_device_path(self):
        splits = self.disk_id.split("_", 1)
        disk_type, id = splits[0], splits[1]
        if disk_type == 'wwn':
            return get_device_path_by_wwn(id)
        elif disk_type == 'serial':
            return get_device_path_by_serial(id)

        return None

    def retry_get_device_path(self):
        def _get_device_path(_):
            return self.get_device_path()

        self.rescan()
        path = linux.wait_callback_success(_get_device_path, timeout=30, interval=0.5)
        if not path:
            raise Exception('unable to find device path for disk id[%s]' % self.disk_id)
        return path


def do_config_iscsi_startup():
    conf_path = "/etc/iscsi/iscsid.conf"
    if not os.path.exists(conf_path):
        raise Exception(conf_path + " not found")

    if linux.filter_file_lines_by_regex(conf_path, '^\s*iscsid.startup'):
        return

    with open(conf_path, 'a') as file:
        file.write("\niscsid.startup = /bin/systemctl start iscsid.socket iscsiuio.socket\n")

    return None


config_iscsi_startup_needed = True


@lock.lock('config_iscsi_startup_if_needed')
def config_iscsi_startup_if_needed():
    global config_iscsi_startup_needed
    if config_iscsi_startup_needed:
        do_config_iscsi_startup()
        config_iscsi_startup_needed = False


# support multiple ip
# e.g. iscsi://172.27.15.189,172.27.12.27:3260/iqn.2024-01.com.sds.wds:662ba14b7316/6001405042040000b7f0d8a20da2a2c9
def connect_iscsi_target(url, connect_all=False):
    login = None
    u = urlparse.urlparse(url)
    server_hostnames = sorted(u.hostname.split(','))
    errs = []
    for server_hostname in server_hostnames:
        new_url = url.replace(u.hostname, server_hostname)
        try:
            login = IscsiLogin(new_url)
            login.login()
            if not connect_all:
                break
        except Exception as e:
            errs.append(str(e))

    if len(errs) == len(server_hostnames):
        raise Exception('failed to login iscsi target[%s], errors: %s' % (url, ' '.join(errs)))

    return login.retry_get_device_path()
