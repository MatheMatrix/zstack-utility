import unittest
import re
import json
import threading

try:
    from unittest import mock
except ImportError:
    import mock

from zstacklib.utils import qmp

# ------------------------------------------------

test_qmp_command1 = '{"execute": "object-add", "arguments":{ "qom-type": "colo-compare", "id": "comp","props": { "primary_in": ' \
                    '"primary-in-c","secondary_in": "secondary-in-s","outdev":"primary-out-c", "iothread": "iothread", "vnet_hdr_support": true } } }'

# ------------------------------------------------
except_qmp_command1 = '{"execute": "object-add", "arguments": {"vnet_hdr_support": true, "iothread": "iothread", "secondary_in": ' \
                      '"secondary-in-s", "primary_in": "primary-in-c", "id": "comp", "qom-type": "colo-compare", "outdev": "primary-out-c"}}'

# ------------------------------------------------
test_qmp_command2 = '{"execute": "object-add", "arguments":{ "qom-type": "filter-mirror", "id": "fm-%s", "props": { "netdev": "hostnet%s",' \
                    ' "queue": "tx", "outdev": "zs-mirror-%s", "vnet_hdr_support": true} } }'


# ------------------------------------------------


class Test(unittest.TestCase):
    def test_function_is_bad_vm_root_volume(self):
        def remove_command_props_parameter(cmd):
            if re.match(r'.*object-add.*arguments.*props.*', cmd):
                j_cmd = json.loads(cmd)
                props = j_cmd.get("arguments").get("props")
                j_cmd.get("arguments").pop("props")
                j_cmd.get("arguments").update(props)
                cmd = json.dumps(j_cmd)
            return cmd

        assert remove_command_props_parameter(test_qmp_command1) == except_qmp_command1
        assert qmp.qmp_subcmd("6.2.0", test_qmp_command2) == remove_command_props_parameter(test_qmp_command2)

    def test_execute_qmp_uses_argv_without_shell_interpolation(self):
        command = json.dumps({
            "execute": "drive-mirror",
            "arguments": {"target": "nbd://host:10809/vol-a';touch-pwned;#"}
        })
        process = mock.Mock()
        process.returncode = 0
        process.communicate.return_value = (b'{"return": {}}', b'')

        with mock.patch.object(qmp.shell, "get_process", return_value=process) as get_process:
            self.assertEqual({}, qmp._execute_qmp_command("vm-uuid", command))

        args, kwargs = get_process.call_args
        self.assertEqual(
            ["virsh", "qemu-monitor-command", "vm-uuid", command], args[0])
        self.assertIs(False, kwargs["shell"])
        self.assertIs(True, kwargs["pipe"])

    def test_execute_qmp_timeout_kills_stuck_virsh(self):
        timers = []

        class ControllableTimer(object):
            def __init__(self, delay, function):
                self.delay = delay
                self.function = function
                self.daemon = False
                self.cancelled = False
                self.start_called = False
                timers.append(self)

            def start(self):
                self.start_called = True
                worker = threading.Thread(target=self.function)
                worker.daemon = True
                worker.start()

            def cancel(self):
                self.cancelled = True

        class StuckProcess(object):
            def __init__(self):
                self.returncode = None
                self.killed = False
                self.kill_event = threading.Event()

            def communicate(self):
                if not self.kill_event.wait(1):
                    raise AssertionError("communicate returned before timeout killed the process")
                return b'', b''

            def kill(self):
                self.killed = True
                self.returncode = -9
                self.kill_event.set()

        process = StuckProcess()
        with mock.patch.object(qmp.shell, "get_process",
                               return_value=process), \
             mock.patch.object(qmp.threading, "Timer", ControllableTimer):
            with self.assertRaises(qmp.QMPTimeoutError):
                qmp._execute_qmp_command(
                    "vm-uuid", '{"execute":"query-block-jobs"}',
                    command_timeout=2)

        self.assertTrue(process.killed)
        self.assertEqual(2.0, timers[0].delay)
        self.assertTrue(timers[0].start_called)
        self.assertTrue(timers[0].cancelled)

    def test_execute_qmp_rejects_invalid_timeout_before_spawning_virsh(self):
        invalid_timeouts = [0, -1, "invalid", float("nan"), float("inf")]
        for command_timeout in invalid_timeouts:
            with mock.patch.object(qmp.shell, "get_process") as get_process:
                with self.assertRaises(ValueError):
                    qmp._execute_qmp_command(
                        "vm-uuid", '{"execute":"query-block-jobs"}',
                        command_timeout=command_timeout)
            get_process.assert_not_called()

    def test_execute_qmp_reaps_virsh_when_timer_start_fails(self):
        class FailingTimer(object):
            def __init__(self, delay, function):
                self.daemon = False

            def start(self):
                raise RuntimeError("timer unavailable")

        process = mock.Mock()
        process.communicate.return_value = (b'', b'')
        with mock.patch.object(qmp.shell, "get_process",
                               return_value=process), \
             mock.patch.object(qmp.threading, "Timer", FailingTimer):
            with self.assertRaises(RuntimeError):
                qmp._execute_qmp_command(
                    "vm-uuid", '{"execute":"query-block-jobs"}',
                    command_timeout=2)

        process.kill.assert_called_once_with()
        process.communicate.assert_called_once_with()

    def test_execute_qmp_keeps_process_timeout_out_of_qmp_arguments(self):
        with mock.patch.object(
                qmp, "_execute_qmp_command", return_value={}) as execute:
            qmp.execute_qmp_command(
                "vm-uuid", "query-block-jobs",
                command_timeout=3, sample_value=7)

        command = json.loads(execute.call_args[0][1].decode("utf-8"))
        self.assertEqual({"sample-value": 7}, command["arguments"])
        self.assertEqual(3, execute.call_args[1]["command_timeout"])


if __name__ == "__main__":
    unittest.main()
