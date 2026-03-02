# -*- coding: utf-8 -*-
import os
import time
import threading
from zstacklib.utils import shell, log, linux
from zstacklib.utils import jsonobject
from zstacklib.utils.bash import bash_roe, in_bash

logger = log.get_logger(__name__)

TOKEN_FILE_DIR = "/var/lib/zstack/consoleProxy/"
PROXY_LOG_DIR = "/var/log/zstack/consoleProxy/"


class ConsoleTokenFile(object):
    def __init__(self, token=None, directory=TOKEN_FILE_DIR):
        self.directory = directory
        self.token = token

    def get_absolute_path(self):
        return os.path.join(self.directory, self.token)

    def flush_write(self, context):
        with open(self.get_absolute_path(), 'w') as f:
            f.write(context)


class ConsoleTokenFileController(object):
    def __init__(self, token_dir=TOKEN_FILE_DIR):
        self.token_dir = token_dir
        self.timers = {}

        # recreate token dir to avoid abuse of existing tokens
        if os.path.exists(token_dir):
            linux.rm_dir_force(token_dir)
            linux.mkdir(token_dir)

    def delete_token_file(self, token_file):
        shell.call("rm -f %s" % token_file.get_absolute_path())

    def cancel_delete_token_task(self, token_file):
        timer = self.timers.get(token_file.token)
        if timer and timer.is_alive():
            timer.cancel()
            logger.debug('cancel the task of deleting the token file[%s]' % token_file.get_absolute_path())

    def submit_delete_token_task(self, token_file, expiredDate):
        interval = float(expiredDate) / 1000 - time.time()
        self.cancel_delete_token_task(token_file)
        timer = threading.Timer(interval, self.delete_token_file, args=[token_file])
        self.timers[token_file.token] = timer
        timer.start()
        logger.info("the token file[%s] will be deleted after %s seconds" % (token_file.get_absolute_path(), interval))


class VncPlugin(object):
    def __init__(self, db, token_ctrl, token_file_dir=TOKEN_FILE_DIR, proxy_log_dir=PROXY_LOG_DIR):
        self.db = db
        self.token_ctrl = token_ctrl
        self.TOKEN_FILE_DIR = token_file_dir
        self.PROXY_LOG_DIR = proxy_log_dir

    def _get_token_name_prefix(self, cmd):
        return '_'.join(cmd.token.split('_')[:2])

    def _make_token_file_name(self, prefix, timeout):
        return '%s_%s' % (prefix, time.time() + timeout)

    def _get_pid_on_port(self, port):
        out = shell.ShellCmd('netstat -anp | grep ":%s" | grep LISTEN' % port)
        out(False)
        out = out.stdout.strip()
        if "" == out:
            return None

        pid = out.split()[-1].split('/')[0]
        try:
            pid = int(pid)
            return pid
        except:
            return None

    def check_availability(self, args):
        proxyPort = args['proxyPort']
        targetHostname = args['targetHostname']
        targetPort = args['targetPort']
        token = args['token']

        pid = self._get_pid_on_port(proxyPort)
        if not pid:
            logger.debug('no websockify on proxy port[%s], availability false' % proxyPort)
            return False

        with open(os.path.join('/proc', str(pid), 'cmdline'), 'r') as fd:
            process_cmdline = fd.read()

        if 'websockify' not in process_cmdline:
            logger.debug('process[pid:%s] on proxy port[%s] is not websockify process, availability false' % (pid, proxyPort))
            return False

        info_str = self.db.get(token)
        if not info_str:
            logger.debug('cannot find information for process[pid:%s] on proxy port[%s], availability false' % (pid, proxyPort))
            return False

        info = jsonobject.loads(info_str)
        if token != info['token']:
            logger.debug('metadata[token] for process[pid:%s] on proxy port[%s] changed, availability false' % (pid, proxyPort))
            return False

        if targetPort != info['targetPort']:
            logger.debug('metadata[targetPort] for process[pid:%s] on proxy port[%s] changed, availability false' % (pid, proxyPort))
            return False

        if targetHostname != info['targetHostname']:
            logger.debug('metadata[targetHostname] for process[pid:%s] on proxy port[%s] changed, availability false' % (pid, proxyPort))
            return False

        return True

    def establish(self, cmd):
        log_file = os.path.join(self.PROXY_LOG_DIR, cmd.proxyHostname)

        token_file = ConsoleTokenFile(cmd.token)
        token_file.flush_write('%s: %s:%s' % (cmd.token, cmd.targetHostname, cmd.targetPort))
        self.token_ctrl.submit_delete_token_task(token_file, cmd.expiredDate)

        info = {
            'proxyHostname': cmd.proxyHostname,
            'proxyPort': cmd.proxyPort,
            'targetHostname': cmd.targetHostname,
            'targetPort': cmd.targetPort,
            'token': cmd.token,
            'logFile': log_file,
            'tokenFile': token_file.get_absolute_path(),
        }
        info_str = jsonobject.dumps(info)
        self.db.set(cmd.token, info_str)
        logger.debug('successfully add new vnc proxy token file %s' % info_str)

        ## kill garbage websockify process: same proxyip:proxyport, different cert file
        if not cmd.sslCertFile:
            command = "ps aux | grep '[z]stack.*websockify_init' | grep '%s:%d' | grep 'cert=' | awk '{ print $2 }'" % (cmd.proxyHostname, cmd.proxyPort)
        else:
            command = "ps aux | grep '[z]stack.*websockify_init' | grep '%s:%d' | grep -v '%s' | awk '{ print $2 }'" % (cmd.proxyHostname, cmd.proxyPort, cmd.sslCertFile)
        ret, out, err = bash_roe(command)
        for pid in out.splitlines():
            try:
                os.kill(int(pid), 15)
            except OSError:
                continue

        ## if websockify process exists, then return
        alive = False
        ret, out, err = bash_roe("ps aux | grep '[z]stack.*websockify_init'")
        for o in out.splitlines():
            if o.find("%s:%d" % (cmd.proxyHostname, cmd.proxyPort)) != -1:
                alive = True
                break
        if alive:
            return cmd.proxyPort

        ## start a new websockify process
        timeout = cmd.idleTimeout
        if not timeout:
            timeout = 600

        @in_bash
        def start_proxy():
            LOG_FILE = log_file
            PROXY_HOST_NAME = cmd.proxyHostname
            PROXY_PORT = cmd.proxyPort
            TOKEN_FILE_DIR = self.TOKEN_FILE_DIR
            TIMEOUT = timeout
            TLS_VERSION = "--ssl-version=%s" % cmd.tlsVersion if cmd.tlsVersion else ""
            start_cmd = '''python -c "from zstacklib.utils import log; import websockify; log.configure_log('{{LOG_FILE}}'); websockify.websocketproxy.websockify_init()" {{PROXY_HOST_NAME}}:{{PROXY_PORT}} -D --target-config={{TOKEN_FILE_DIR}} --idle-timeout={{TIMEOUT}} {{TLS_VERSION}}'''
            if cmd.sslCertFile:
                start_cmd += ' --cert=%s' % cmd.sslCertFile
            ret, out, err = bash_roe(start_cmd)
            if ret != 0:
                raise Exception('failed to start websockify on %s:%s, stderr: %s' % (cmd.proxyHostname, cmd.proxyPort, err))

        start_proxy()
        logger.debug('successfully establish new vnc proxy %s' % info_str)
        return cmd.proxyPort

    def delete(self, cmd):
        def kill_proxy_process():
            out = shell.ShellCmd(
                "netstat -ntp | grep '%s:%s *ESTABLISHED.*python'" % (cmd.targetHostname, cmd.targetPort))
            out(False)
            pids = [line.strip().split(' ')[-1].split('/')[0] for line in out.stdout.splitlines()]
            for pid in pids:
                try:
                    os.kill(int(pid), 15)
                except OSError:
                    continue

        token_file = ConsoleTokenFile(cmd.token)
        self.token_ctrl.cancel_delete_token_task(token_file)
        self.token_ctrl.delete_token_file(token_file)
        kill_proxy_process()
        logger.debug('deleted a vnc proxy for token: %s' % cmd.token)
