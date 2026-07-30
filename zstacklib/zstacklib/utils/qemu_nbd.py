import errno
import os
import signal
import subprocess

from zstacklib.utils import linux

DEFAULT_KILL_TIMEOUT = 60
DEFAULT_KILL_INTERVAL = 1


def export(port, *args):
    command = 'qemu-nbd -p %s' % port
    if args:
        command += ' ' + ' '.join(str(arg) for arg in args)
    process = subprocess.Popen(command, shell=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    return process


def find_qemu_nbd_process(pattern):
    return 0 if linux.find_process_list_by_command('qemu-nbd', [pattern]) else 1


def kill_qemu_nbd_process(pattern):
    pids = linux.find_process_list_by_command('qemu-nbd', [pattern])
    for pid in pids:
        try:
            os.kill(int(pid), signal.SIGTERM)
        except OSError as e:
            if e.errno != errno.ESRCH:
                raise
    return 0 if pids else 1


def wait_qemu_nbd_process_gone(pattern, timeout=DEFAULT_KILL_TIMEOUT, interval=DEFAULT_KILL_INTERVAL):
    def gone(_):
        return find_qemu_nbd_process(pattern) != 0

    return linux.wait_callback_success(gone, timeout=timeout, interval=interval)


def kill_nbd_process_by_flag(flag, timeout=DEFAULT_KILL_TIMEOUT, interval=DEFAULT_KILL_INTERVAL):
    ret = kill_qemu_nbd_process(flag)
    if not wait_qemu_nbd_process_gone(flag, timeout, interval):
        raise Exception('timeout waiting qemu-nbd process[%s] gone after SIGTERM' % flag)
    return ret
