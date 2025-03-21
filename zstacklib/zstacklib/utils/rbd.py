import os
import ConfigParser
import subprocess
import errno
import traceback
import threading

from zstacklib.utils import log
from zstacklib.utils import jsonobject
from zstacklib.utils import bash
from zstacklib.utils import linux
from zstacklib.utils import thread

logger = log.get_logger(__name__)
EOF = "this_is_end"


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


_rw_singleton_lock = threading.Lock()
_rw_singleton = None


def get_rbd_rw_handler():
    global _rw_singleton
    if _rw_singleton is None:
        with _rw_singleton_lock:
            if _rw_singleton is None:
                _rw_singleton = RbdRWHandler()
    return _rw_singleton


class RbdRWHandler(object):
    def __init__(self):
        self.rbd_rw_path = "/var/lib/zstack/virtualenv/kvm/lib/python2.7/site-packages/zstacklib/scripts/rbd_rw.py"
        self.rbd_rw_process = None
        self.init_rbd_rw_process()

    def init_rbd_rw_process(self):
        """
        1. check if the rbd_rw.py is running, if yes, kill it
        2. running our own rbd_rw.py to read/write rbd volume to rbd storage
        3. through pipe to communicate with rbd_rw.py
        """
        pids = linux.find_all_process_by_cmdline([self.rbd_rw_path])
        if pids:
            logger.debug("find last rbd_rw.py process %s" % pids)
            for pid in pids:
                linux.kill_process(pid, is_exception=False)
        self.rbd_rw_process = subprocess.Popen(
            ["python2", self.rbd_rw_path],
            stdout=subprocess.PIPE,
            stdin=subprocess.PIPE,
            stderr=subprocess.PIPE
        )

        @thread.AsyncThread
        def dump_stderr():
            """debug all stderr from rbd_rw_process"""
            try:
                while True:
                    line = self.rbd_rw_process.stderr.readline()
                    if line == "":  # EOF
                        logger.debug("rbd_rw_process stderr pipe is closed")
                        break
                    logger.warn("rbd_rw_process: %s" % line)
            except Exception as e:
                logger.warn("failed to read rbd_rw_process stderr: %s" % e)
                content = traceback.format_exc()
                logger.warn(content)
        dump_stderr()

    def write(self, path, fs_id, host_id, chunk_size, content):
        logger.debug("use rbd_rw.py to update rbd volume [path:%s, hostId:%d] timestamp with content: %s"
                     % (path, host_id, content))
        offset = host_id * chunk_size
        cmd = "writehb %s %d %d %s\n" % (path, fs_id, offset, str(content) + EOF)
        logger.info(cmd)
        ret_str = "{}"
        try:
            self.rbd_rw_process.stdin.write(cmd)
            self.rbd_rw_process.stdin.flush()
            ret_str = self.rbd_rw_process.stdout.readline().strip()
        except KeyboardInterrupt:
            pass
        except IOError as e:
            if e.errno == errno.EPIPE:
                logger.warn("rbd_rw.py has been killed, restart it")
                self.init_rbd_rw_process()
                return False
            logger.warn("failed to use rbd_rw.py update rbd volume [path:%s, hostId:%d] timestamp. \n"
                        " IOError: %s" % (path, host_id, str(e)))
            return False
        ret = jsonobject.loads(ret_str)
        if not ret.success:
            logger.warn("failed to use rbd_pw.py update rbd volume [path:%s, hostId:%d] timestamp. \n"
                        " reason: %s" % (path, host_id, ret.reason))
            return False
        return True

    def read(self, path, fs_id, host_id, chunk_size):
        logger.debug("use rbd_rw.py to read rbd volume [path:%s, hostId:%d] timestamp" % (path, host_id))
        offset = host_id * chunk_size
        cmd = "source /var/lib/zstack/virtualenv/kvm/bin/activate && timeout 20 python %s read %s %d %d %d" % (
            self.rbd_rw_path, path, fs_id, offset, chunk_size)
        r, o, e = bash.bash_roe(cmd)
        if r != 0:
            logger.warn("failed to use rbd_rw.py read rbd volume [path:%s] at offset %d\n"
                        " return code:%s\n stdout:%s\n stderr: %s\n" %
                        (path, offset, r, o[0:min(128, len(o))], e))
            return None
        hb_content = o.split(EOF)[0]
        return hb_content
