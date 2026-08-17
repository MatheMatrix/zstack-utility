import unittest
import re
import json

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


if __name__ == "__main__":
    unittest.main()
