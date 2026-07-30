import errno
import unittest

from zstacklib.utils import qemu_nbd


class TestQemuNbd(unittest.TestCase):
    def test_kill_nbd_waits_until_process_gone(self):
        calls = []
        original_kill = qemu_nbd.kill_qemu_nbd_process
        original_wait = qemu_nbd.wait_qemu_nbd_process_gone

        def kill(pattern):
            calls.append(('kill', pattern))
            return 0

        def wait(pattern, timeout, interval):
            calls.append(('wait', pattern, timeout, interval))
            return True

        qemu_nbd.kill_qemu_nbd_process = kill
        qemu_nbd.wait_qemu_nbd_process_gone = wait
        try:
            ret = qemu_nbd.kill_nbd_process_by_flag('/dev/vg/volume', timeout=7, interval=2)
        finally:
            qemu_nbd.kill_qemu_nbd_process = original_kill
            qemu_nbd.wait_qemu_nbd_process_gone = original_wait

        self.assertEqual(0, ret)
        self.assertEqual(('kill', '/dev/vg/volume'), calls[0])
        self.assertEqual(('wait', '/dev/vg/volume', 7, 2), calls[1])

    def test_kill_nbd_fails_when_process_still_exists(self):
        original_kill = qemu_nbd.kill_qemu_nbd_process
        original_wait = qemu_nbd.wait_qemu_nbd_process_gone

        qemu_nbd.kill_qemu_nbd_process = lambda pattern: 0
        qemu_nbd.wait_qemu_nbd_process_gone = lambda pattern, timeout, interval: False
        try:
            self.assertRaises(Exception, qemu_nbd.kill_nbd_process_by_flag, '/dev/vg/volume')
        finally:
            qemu_nbd.kill_qemu_nbd_process = original_kill
            qemu_nbd.wait_qemu_nbd_process_gone = original_wait

    def test_find_qemu_nbd_process_uses_process_list(self):
        original_find = qemu_nbd.linux.find_process_list_by_command
        calls = []
        results = [[], ['123']]

        def find(command, arguments):
            calls.append((command, arguments))
            return results.pop(0)

        qemu_nbd.linux.find_process_list_by_command = find
        try:
            self.assertEqual(1, qemu_nbd.find_qemu_nbd_process('/dev/vg/missing'))
            self.assertEqual(0, qemu_nbd.find_qemu_nbd_process('/dev/vg/present'))
        finally:
            qemu_nbd.linux.find_process_list_by_command = original_find

        self.assertEqual(('qemu-nbd', ['/dev/vg/missing']), calls[0])
        self.assertEqual(('qemu-nbd', ['/dev/vg/present']), calls[1])

    def test_find_qemu_nbd_process_propagates_probe_error(self):
        original_find = qemu_nbd.linux.find_process_list_by_command

        def find(command, arguments):
            raise OSError('cannot read proc')

        qemu_nbd.linux.find_process_list_by_command = find
        try:
            self.assertRaises(OSError, qemu_nbd.find_qemu_nbd_process, '/dev/vg/volume')
        finally:
            qemu_nbd.linux.find_process_list_by_command = original_find

    def test_find_qemu_nbd_process_logs_proc_read_error(self):
        original_listdir = qemu_nbd.linux.os.listdir
        original_readlink = qemu_nbd.linux.os.readlink
        original_warn = qemu_nbd.linux.logger.warn
        warnings = []
        errors = [errno.EACCES, errno.ENOENT]

        qemu_nbd.linux.os.listdir = lambda path: ['123']

        def readlink(path):
            raise OSError(errors.pop(0), 'cannot read proc')

        qemu_nbd.linux.os.readlink = readlink
        qemu_nbd.linux.logger.warn = lambda message: warnings.append(message)
        try:
            self.assertEqual(1, qemu_nbd.find_qemu_nbd_process('/dev/vg/volume'))
            self.assertEqual(1, qemu_nbd.find_qemu_nbd_process('/dev/vg/volume'))
        finally:
            qemu_nbd.linux.os.listdir = original_listdir
            qemu_nbd.linux.os.readlink = original_readlink
            qemu_nbd.linux.logger.warn = original_warn

        self.assertEqual(1, len(warnings))
        self.assertIn('process[123]', warnings[0])

    def test_wait_qemu_nbd_process_gone_checks_presence(self):
        original_find = qemu_nbd.find_qemu_nbd_process
        original_wait = qemu_nbd.linux.wait_callback_success
        results = [0, 1]
        calls = []

        def find(pattern):
            return results.pop(0)

        def wait(callback, callback_data=None, timeout=60, interval=1):
            calls.append((timeout, interval))
            return callback(callback_data)

        qemu_nbd.find_qemu_nbd_process = find
        qemu_nbd.linux.wait_callback_success = wait
        try:
            self.assertFalse(qemu_nbd.wait_qemu_nbd_process_gone('/dev/vg/volume', 7, 2))
            self.assertTrue(qemu_nbd.wait_qemu_nbd_process_gone('/dev/vg/volume', 7, 2))
        finally:
            qemu_nbd.find_qemu_nbd_process = original_find
            qemu_nbd.linux.wait_callback_success = original_wait

        self.assertEqual([(7, 2), (7, 2)], calls)

    def test_kill_qemu_nbd_process_sends_sigterm(self):
        original_find = qemu_nbd.linux.find_process_list_by_command
        original_kill = qemu_nbd.os.kill
        calls = []

        qemu_nbd.linux.find_process_list_by_command = lambda command, arguments: ['123', '456']
        qemu_nbd.os.kill = lambda pid, sig: calls.append((pid, sig))
        try:
            self.assertEqual(0, qemu_nbd.kill_qemu_nbd_process('/dev/vg/volume'))
        finally:
            qemu_nbd.linux.find_process_list_by_command = original_find
            qemu_nbd.os.kill = original_kill

        self.assertEqual([(123, qemu_nbd.signal.SIGTERM), (456, qemu_nbd.signal.SIGTERM)], calls)

    def test_kill_qemu_nbd_process_ignores_exited_process(self):
        original_find = qemu_nbd.linux.find_process_list_by_command
        original_kill = qemu_nbd.os.kill

        def kill(pid, sig):
            raise OSError(errno.ESRCH, 'process gone')

        qemu_nbd.linux.find_process_list_by_command = lambda command, arguments: ['123']
        qemu_nbd.os.kill = kill
        try:
            self.assertEqual(0, qemu_nbd.kill_qemu_nbd_process('/dev/vg/volume'))
        finally:
            qemu_nbd.linux.find_process_list_by_command = original_find
            qemu_nbd.os.kill = original_kill


if __name__ == "__main__":
    unittest.main()
