import errno
import unittest

from zstacklib.utils import qemu_nbd


class TestQemuNbd(unittest.TestCase):
    def test_kill_nbd_process_by_flag_sends_sigterm_and_waits_until_gone(self):
        calls = []
        original_find = qemu_nbd.linux.find_process_list_by_command
        original_wait = qemu_nbd.linux.wait_callback_success
        original_kill = qemu_nbd.os.kill
        results = [['123', '456'], []]

        def find(command, arguments):
            calls.append(('find', command, arguments))
            return results.pop(0)

        def kill(pid, sig):
            calls.append(('kill', pid, sig))

        def wait(callback, callback_data=None, timeout=60, interval=1):
            calls.append(('wait', timeout, interval))
            return callback(callback_data)

        qemu_nbd.linux.find_process_list_by_command = find
        qemu_nbd.linux.wait_callback_success = wait
        qemu_nbd.os.kill = kill
        try:
            ret = qemu_nbd.kill_nbd_process_by_flag('/dev/vg/volume', timeout=7, interval=2)
        finally:
            qemu_nbd.linux.find_process_list_by_command = original_find
            qemu_nbd.linux.wait_callback_success = original_wait
            qemu_nbd.os.kill = original_kill

        self.assertEqual(0, ret)
        self.assertEqual(('find', 'qemu-nbd', ['/dev/vg/volume']), calls[0])
        self.assertEqual(('kill', 123, qemu_nbd.signal.SIGTERM), calls[1])
        self.assertEqual(('kill', 456, qemu_nbd.signal.SIGTERM), calls[2])
        self.assertEqual(('wait', 7, 2), calls[3])
        self.assertEqual(('find', 'qemu-nbd', ['/dev/vg/volume']), calls[4])

    def test_kill_nbd_process_by_flag_returns_1_when_no_process(self):
        original_find = qemu_nbd.linux.find_process_list_by_command
        original_wait = qemu_nbd.linux.wait_callback_success
        original_kill = qemu_nbd.os.kill

        qemu_nbd.linux.find_process_list_by_command = lambda command, arguments: []
        qemu_nbd.linux.wait_callback_success = lambda *args, **kwargs: self.fail('wait should not run')
        qemu_nbd.os.kill = lambda *args, **kwargs: self.fail('kill should not run')
        try:
            self.assertEqual(1, qemu_nbd.kill_nbd_process_by_flag('/dev/vg/volume'))
        finally:
            qemu_nbd.linux.find_process_list_by_command = original_find
            qemu_nbd.linux.wait_callback_success = original_wait
            qemu_nbd.os.kill = original_kill

    def test_kill_nbd_fails_when_process_still_exists(self):
        original_find = qemu_nbd.linux.find_process_list_by_command
        original_wait = qemu_nbd.linux.wait_callback_success
        original_kill = qemu_nbd.os.kill

        qemu_nbd.linux.find_process_list_by_command = lambda command, arguments: ['123']
        qemu_nbd.linux.wait_callback_success = lambda callback, callback_data=None, timeout=60, interval=1: False
        qemu_nbd.os.kill = lambda pid, sig: None
        try:
            try:
                qemu_nbd.kill_nbd_process_by_flag('/dev/vg/volume')
                self.fail('expected qemu-nbd timeout')
            except Exception as e:
                self.assertIn('timeout waiting qemu-nbd process', str(e))
        finally:
            qemu_nbd.linux.find_process_list_by_command = original_find
            qemu_nbd.linux.wait_callback_success = original_wait
            qemu_nbd.os.kill = original_kill

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

    def test_kill_nbd_process_by_flag_ignores_exited_process(self):
        original_find = qemu_nbd.linux.find_process_list_by_command
        original_wait = qemu_nbd.linux.wait_callback_success
        original_kill = qemu_nbd.os.kill

        def kill(pid, sig):
            raise OSError(errno.ESRCH, 'process gone')

        qemu_nbd.linux.find_process_list_by_command = lambda command, arguments: ['123']
        qemu_nbd.linux.wait_callback_success = lambda callback, callback_data=None, timeout=60, interval=1: True
        qemu_nbd.os.kill = kill
        try:
            self.assertEqual(0, qemu_nbd.kill_nbd_process_by_flag('/dev/vg/volume'))
        finally:
            qemu_nbd.linux.find_process_list_by_command = original_find
            qemu_nbd.linux.wait_callback_success = original_wait
            qemu_nbd.os.kill = original_kill


if __name__ == "__main__":
    unittest.main()
