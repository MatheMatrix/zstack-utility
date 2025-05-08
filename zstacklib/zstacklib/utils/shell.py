'''

@author: frank
'''
import json
import os
import subprocess

from zstacklib.utils import log
from zstacklib.utils import lock

logger = log.get_logger(__name__)

# instead of closing [3, ulimit -n)
def _linux_close_fds(self, but):
    for fd in [int(n) for n in os.listdir('/proc/%d/fd' % os.getpid())]:
        if fd > 2 and fd != but:
            try:
                os.close(fd)
            except:
                pass


subprocess.Popen._close_fds = _linux_close_fds


@lock.lock("subprocess.popen")
def get_process(cmd, shell=None, workdir=None, pipe=None, executable=None):
    if pipe:
        return subprocess.Popen(cmd, shell=shell, stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                                close_fds=True, executable=executable, cwd=workdir)
    else:
        return subprocess.Popen(cmd, shell=shell, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                                close_fds=True, executable=executable, cwd=workdir)


class ShellError(Exception):
    '''shell error'''


class ShellCmd(object):
    '''
    classdocs
    '''
    stdout = None  # type: str

    def __init__(self, cmd, workdir=None, pipe=True):
        '''
        Constructor
        '''
        self.cmd = cmd
        self.process = get_process(cmd, True, workdir, pipe, "/bin/bash")

        self.stdout = None
        self.stderr = None
        self.return_code = None

    def raise_error(self, err=()):
        """
        :param err: extend error message
        :return:
        """
        if err is ():
            err = []
        err.append('failed to execute shell command: %s' % self.cmd.split(' ', 1)[0])
        err.append('return code: %s' % self.process.returncode)
        err.append('stdout: %s' % self.stdout)
        err.append('stderr: %s' % self.stderr)
        raise ShellError('\n'.join(err))

    def __call__(self, is_exception=True, logcmd=True):
        if logcmd:
            log.get_logger(__name__).debug(self.cmd)

        (self.stdout, self.stderr) = self.process.communicate()
        if is_exception and self.process.returncode != 0:
            self.raise_error()

        self.return_code = self.process.returncode
        return self.stdout


def call(cmd, exception=True, workdir=None):
    # type: (str, bool, bool) -> str
    return ShellCmd(cmd, workdir)(exception)


def run(cmd, workdir=None):
    s = ShellCmd(cmd, workdir, False)
    s(False)
    return s.return_code


def check_run(cmd, workdir=None):
    s = ShellCmd(cmd, workdir, False)
    s(True)
    return s.return_code


def run_without_log(cmd, workdir=None):
    s = ShellCmd(cmd, workdir, False)
    s(is_exception=False, logcmd=False)
    return s.return_code


def run_with_json_result(cmd, workdir=None):
    s = ShellCmd(cmd, workdir)
    s(is_exception=False, logcmd=True)

    output = s.stdout
    if s.return_code != 0 or output is None:
        return None

    json_start = output.find('{')
    if json_start == -1:
        logger.error("No JSON data found in command %s output, output: %s", cmd, output)
        return None

    json_str = output[json_start:]
    try:
        return json.loads(json_str)
    except ValueError as ve:
        logger.error("JSON decode failed for command: %s, error: %s", cmd, ve)
        return None
