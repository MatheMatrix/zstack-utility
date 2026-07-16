import imp
import os
import sys
import types
import unittest

import mock


def _identity_decorator(*dargs, **dkwargs):
    def deco(func):
        return func

    if dargs and callable(dargs[0]) and len(dargs) == 1 and not dkwargs:
        return dargs[0]
    return deco


class _LoggerStub(object):
    def warning(self, msg):
        pass

    def debug(self, msg):
        pass


class _LogStub(object):
    @staticmethod
    def sensitive_fields(*args, **kwargs):
        return _identity_decorator

    @staticmethod
    def get_logger(name):
        return _LoggerStub()


def _module(name, created_modules=None):
    m = types.ModuleType(name)
    sys.modules[name] = m
    if created_modules is not None:
        created_modules.append(m)
    return m


def _load_host_plugin_with_stubs():
    module_names = [
        'kvmagent',
        'kvmagent.kvmagent',
        'kvmagent.plugins',
        'kvmagent.plugins.vm_plugin',
        'kvmagent.plugins.imagestore',
        'kvmagent.plugins.prometheus',
        'yaml',
        'zstacklib',
        'zstacklib.utils',
        'zstacklib.utils.bash',
        'zstacklib.utils.http',
        'zstacklib.utils.lvm',
        'zstacklib.utils.ceph',
        'zstacklib.utils.pci',
        'zstacklib.utils.gpu',
        'zstacklib.utils.qemu',
        'zstacklib.utils.linux',
        'zstacklib.utils.iptables',
        'zstacklib.utils.iproute',
        'zstacklib.utils.ebtables',
        'zstacklib.utils.jsonobject',
        'zstacklib.utils.lock',
        'zstacklib.utils.sizeunit',
        'zstacklib.utils.thread',
        'zstacklib.utils.xmlobject',
        'zstacklib.utils.ovs',
        'zstacklib.utils.shell',
        'zstacklib.utils.misc',
        'zstacklib.utils.ip',
        'zstacklib.utils.report',
        'zstacklib.utils.ovn',
        'zstacklib.utils.plugin',
    ]
    sentinel = object()
    old_modules = dict((name, sys.modules.get(name, sentinel))
                       for name in module_names)
    created_modules = []

    def stub_module(name):
        return _module(name, created_modules)

    try:
        kvmagent_pkg = stub_module('kvmagent')
        kvmagent_mod = stub_module('kvmagent.kvmagent')

        class AgentResponse(object):
            def __init__(self):
                self.success = True
                self.error = None

        class AgentCommand(object):
            pass

        class KvmAgent(object):
            pass

        kvmagent_mod.AgentResponse = AgentResponse
        kvmagent_mod.AgentCommand = AgentCommand
        kvmagent_mod.KvmAgent = KvmAgent
        kvmagent_mod.replyerror = _identity_decorator
        kvmagent_pkg.kvmagent = kvmagent_mod

        plugins_pkg = stub_module('kvmagent.plugins')
        kvmagent_pkg.plugins = plugins_pkg
        for name in ['vm_plugin', 'imagestore', 'prometheus']:
            m = stub_module('kvmagent.plugins.' + name)
            setattr(plugins_pkg, name, m)

        plugins_pkg.vm_plugin.VirtualizerInfoTO = type(
            'VirtualizerInfoTO', (object,), {})
        plugins_pkg.vm_plugin.LibvirtAutoReconnect = _identity_decorator
        plugins_pkg.imagestore.ImageStoreClient = type(
            'ImageStoreClient', (object,), {})
        plugins_pkg.prometheus.get_service_type_map = lambda: {}
        plugins_pkg.prometheus.register_service_type = \
            lambda *args, **kwargs: None

        stub_module('yaml')

        zstacklib_pkg = stub_module('zstacklib')
        utils_pkg = stub_module('zstacklib.utils')
        zstacklib_pkg.utils = utils_pkg
        for name in [
                'http', 'lvm', 'ceph', 'pci', 'gpu', 'qemu', 'linux', 'iptables',
                'iproute', 'ebtables', 'jsonobject', 'lock', 'sizeunit',
                'thread', 'xmlobject', 'ovs', 'shell', 'ip', 'report',
                'misc', 'ovn', 'plugin']:
            m = stub_module('zstacklib.utils.' + name)
            setattr(utils_pkg, name, m)

        utils_pkg.iptables.get_iptables_cmd = lambda: 'iptables'
        utils_pkg.ebtables.get_ebtables_cmd = lambda: 'ebtables'
        utils_pkg.ip.get_nic_supported_max_speed = lambda *args, **kwargs: None
        utils_pkg.ip.get_nic_driver_type = lambda *args, **kwargs: None
        utils_pkg.pci.VendorEnum = type('VendorEnum', (object,), {})
        utils_pkg.sizeunit.get_size = lambda *args, **kwargs: None
        utils_pkg.lock.Flock = type(
            'Flock', (object,),
            {'__init__': lambda self, *args, **kwargs: None})
        utils_pkg.lock.file_lock = _identity_decorator
        utils_pkg.thread.AsyncThread = _identity_decorator
        utils_pkg.linux.retry = _identity_decorator
        utils_pkg.shell.run = lambda cmd: 0
        utils_pkg.shell.call = lambda cmd: ''
        utils_pkg.report.Report = type('Report', (object,), {})

        bash_mod = stub_module('zstacklib.utils.bash')
        bash_mod.bash_roe = lambda cmd: (0, '', '')
        bash_mod.bash_r = lambda cmd: 0
        bash_mod.bash_o = lambda cmd: ''
        bash_mod.in_bash = _identity_decorator
        bash_mod.log = _LogStub
        utils_pkg.bash = bash_mod

        root = os.path.abspath(os.path.join(
            os.path.dirname(__file__), '..', '..', '..'))
        host_plugin_path = os.path.join(
            root, 'kvmagent', 'kvmagent', 'plugins', 'host_plugin.py')
        return imp.load_source(
            '_host_plugin_rpmdb_repair_under_test', host_plugin_path)
    finally:
        created_module_ids = set(id(module) for module in created_modules)
        for name, module in list(sys.modules.items()):
            if id(module) in created_module_ids:
                sys.modules.pop(name, None)
        for name, old_module in old_modules.items():
            if old_module is sentinel:
                sys.modules.pop(name, None)
            else:
                sys.modules[name] = old_module


host_plugin = _load_host_plugin_with_stubs()


class TestRpmdbRepair(unittest.TestCase):
    def setUp(self):
        host_plugin.logger = mock.Mock()

    def _continue(self):
        return host_plugin.RpmdbRepairDecision(False, True, None)

    def test_parse_package_processes(self):
        output = ("123 S 70 456 yum yum install foo\n"
                  "abc S 1 789 rpm ignored\n")
        processes = host_plugin._parse_package_processes(output)

        self.assertEqual(1, len(processes))
        self.assertEqual(123, processes[0]['pid'])
        self.assertEqual('S', processes[0]['stat'])
        self.assertEqual(70, processes[0]['etimes'])
        self.assertEqual(456, processes[0]['start_ticks'])
        self.assertEqual('yum', processes[0]['comm'])
        self.assertEqual('yum install foo', processes[0]['args'])

    def test_terminate_revalidates_identity_and_age_before_each_signal(self):
        process = {
            'pid': 123,
            'stat': 'S',
            'etimes': 120,
            'start_ticks': 456,
            'comm': 'yum',
            'args': 'yum install foo'
        }

        with mock.patch.object(host_plugin, '_run_rpmdb_output_command',
                               return_value=(True, '', None)) as run_cmd:
            decision = host_plugin._terminate_package_processes([process])

        command = run_cmd.call_args[0][0]
        self.assertFalse(decision.stop)
        self.assertIn('target_specs="123:456"', command)
        self.assertIn('current_start_ticks', command)
        self.assertIn('[ "$current_start_ticks" = "$expected_start_ticks" ]',
                      command)
        self.assertIn('[ "$current_etimes" -ge 60 ]', command)
        self.assertGreaterEqual(command.count(
            'is_same_stale_package_process "$pid" '
            '"$expected_start_ticks"'), 2)
        self.assertIn('kill -TERM "$pid"', command)
        self.assertIn('kill -KILL "$pid"', command)
        self.assertNotIn('kill -TERM $term_pids', command)
        self.assertNotIn('kill -KILL $kill_pids', command)

    def test_rebuild_rechecks_processes_and_fds_before_destructive_work(self):
        with mock.patch.object(host_plugin, '_run_rpmdb_output_command',
                               return_value=(True, '', None)) as run_cmd:
            decision = host_plugin._backup_and_rebuild_rpmdb()

        command = run_cmd.call_args[0][0]
        backup_pos = command.index('tar czf "$backup_file"')
        remove_pos = command.index('rm -f "$dbpath"/__db.*')
        guard_positions = []
        offset = 0
        while True:
            pos = command.find('require_idle_rpmdb', offset)
            if pos < 0:
                break
            guard_positions.append(pos)
            offset = pos + 1

        self.assertFalse(decision.stop)
        self.assertIn('ps -eo pid=,ppid=,comm=,args=', command)
        self.assertIn('for fd in /proc/[0-9]*/fd/*', command)
        self.assertGreaterEqual(len(guard_positions), 3)
        self.assertLess(guard_positions[1], backup_pos)
        self.assertGreater(guard_positions[2], backup_pos)
        self.assertLess(guard_positions[2], remove_pos)
        self.assertIn('rm -f "$backup_file"', command)

    def test_first_pass_stops_when_yum_fails_but_rpmdb_is_healthy(self):
        with mock.patch.object(host_plugin, '_rpmdb_check',
                               return_value=True):
            decision = host_plugin._evaluate_rpmdb_repair_state([])

        self.assertTrue(decision.stop)
        self.assertTrue(decision.success)
        self.assertIn('rpmdb is healthy', decision.message)

    def test_second_pass_does_not_stop_before_cleanup_when_no_processes(self):
        with mock.patch.object(host_plugin, '_rpmdb_check',
                               return_value=True), \
                mock.patch.object(host_plugin, '_list_rpmdb_users',
                                  return_value=([], None)):
            decision = host_plugin._evaluate_rpmdb_repair_state(
                [], check_remaining_processes=True)

        self.assertFalse(decision.stop)

    def test_process_checks_do_not_ignore_whole_process_group(self):
        with mock.patch.object(host_plugin, '_run_rpmdb_output_command',
                               return_value=(True, '', None)) as run_cmd:
            host_plugin._list_package_processes()
            package_command = run_cmd.call_args[0][0]

        self.assertNotIn('proc_pgid == pgid', package_command)
        self.assertNotIn('ps -o pgid= -p $$', package_command)

        with mock.patch.object(host_plugin, '_run_rpmdb_output_command',
                               return_value=(True, '', None)) as run_cmd:
            host_plugin._list_rpmdb_users()
            rpmdb_command = run_cmd.call_args[0][0]

        self.assertNotIn('proc_pgid', rpmdb_command)
        self.assertNotIn('ps -o pgid= -p $$', rpmdb_command)

    def test_d_state_package_process_stops_repair(self):
        process = {
            'pid': 123,
            'stat': 'D',
            'etimes': 120,
            'comm': 'rpm',
            'args': 'rpm -qa'
        }

        decision = host_plugin._evaluate_rpmdb_repair_state([process])

        self.assertTrue(decision.stop)
        self.assertFalse(decision.success)
        self.assertIn('D state', decision.message)

    def test_young_package_process_waits_and_still_stops_repair(self):
        process = {
            'pid': 123,
            'stat': 'S',
            'etimes': 1,
            'comm': 'yum',
            'args': 'yum install foo'
        }

        with mock.patch.object(host_plugin.time, 'sleep') as sleep, \
                mock.patch.object(host_plugin, '_yum_rpmdb_check',
                                  return_value=False), \
                mock.patch.object(host_plugin, '_list_package_processes',
                                  return_value=([process], None)), \
                mock.patch.object(host_plugin,
                                  '_evaluate_rpmdb_repair_state',
                                  return_value=self._continue()):
            decision = host_plugin._wait_for_young_package_processes([process])

        sleep.assert_called_once_with(host_plugin.RPMDB_REPAIR_WAIT_SECONDS)
        self.assertTrue(decision.stop)
        self.assertTrue(decision.success)
        self.assertIn('below stale threshold', decision.message)

    def test_repair_cleans_yum_pid_again_after_terminating_processes(self):
        stale_process = {
            'pid': 123,
            'stat': 'S',
            'etimes': 120,
            'comm': 'yum',
            'args': 'yum install foo'
        }

        with mock.patch.object(host_plugin, '_yum_rpmdb_check',
                               side_effect=[False, False, False]), \
                mock.patch.object(host_plugin,
                                  '_check_rpmdb_repair_prerequisites',
                                  return_value=self._continue()), \
                mock.patch.object(host_plugin, '_remove_stale_yum_pid_files',
                                  side_effect=[self._continue(),
                                               self._continue()]) \
                as remove_pid, \
                mock.patch.object(host_plugin, '_check_rpmdb_opened',
                                  return_value=self._continue()), \
                mock.patch.object(host_plugin, '_list_package_processes',
                                  side_effect=[([stale_process], None),
                                               ([stale_process], None),
                                               ([], None)]), \
                mock.patch.object(host_plugin,
                                  '_evaluate_rpmdb_repair_state',
                                  side_effect=[self._continue(),
                                               self._continue()]), \
                mock.patch.object(host_plugin,
                                  '_wait_for_young_package_processes',
                                  return_value=self._continue()), \
                mock.patch.object(host_plugin, '_terminate_package_processes',
                                  return_value=self._continue()), \
                mock.patch.object(host_plugin, '_rpmdb_check',
                                  return_value=True):
            success, error = host_plugin.repair_rpmdb_if_damaged_on_host()

        self.assertTrue(success)
        self.assertIn('rpmdb is healthy after clearing', error)
        self.assertEqual(2, remove_pid.call_count)

    def test_repair_rebuilds_only_when_rpmdb_is_broken_and_unused(self):
        with mock.patch.object(host_plugin, '_yum_rpmdb_check',
                               side_effect=[False, False, False, True]), \
                mock.patch.object(host_plugin,
                                  '_check_rpmdb_repair_prerequisites',
                                  return_value=self._continue()), \
                mock.patch.object(host_plugin, '_remove_stale_yum_pid_files',
                                  return_value=self._continue()), \
                mock.patch.object(host_plugin, '_check_rpmdb_opened',
                                  return_value=self._continue()), \
                mock.patch.object(host_plugin, '_list_package_processes',
                                  side_effect=[([], None),
                                               ([], None),
                                               ([], None)]), \
                mock.patch.object(host_plugin, '_rpmdb_check',
                                  side_effect=[False, False]), \
                mock.patch.object(host_plugin, '_list_rpmdb_users',
                                  side_effect=[([], None),
                                               ([], None),
                                               ([], None)]), \
                mock.patch.object(host_plugin, '_terminate_package_processes',
                                  return_value=self._continue()), \
                mock.patch.object(host_plugin, '_backup_and_rebuild_rpmdb',
                                  return_value=self._continue()) as rebuild:
            success, error = host_plugin.repair_rpmdb_if_damaged_on_host()

        self.assertTrue(success)
        self.assertIsNone(error)
        rebuild.assert_called_once_with()

    def test_repair_skips_dependency_update_when_rpmdb_is_opened(self):
        with mock.patch.object(host_plugin, '_yum_rpmdb_check',
                               side_effect=[False, False]), \
                mock.patch.object(host_plugin,
                                  '_check_rpmdb_repair_prerequisites',
                                  return_value=self._continue()), \
                mock.patch.object(host_plugin, '_remove_stale_yum_pid_files',
                                  return_value=self._continue()), \
                mock.patch.object(host_plugin, '_list_rpmdb_users',
                                  return_value=(['123'], None)), \
                mock.patch.object(host_plugin, '_list_package_processes') \
                as list_processes, \
                mock.patch.object(host_plugin, '_backup_and_rebuild_rpmdb') \
                as rebuild:
            success, error = host_plugin.repair_rpmdb_if_damaged_on_host()

        self.assertTrue(success)
        self.assertIn('rpmdb is still opened', error)
        list_processes.assert_not_called()
        rebuild.assert_not_called()


if __name__ == '__main__':
    unittest.main()
