import imp
import os
import sys
import types
import unittest

import mock


def _module(name, created_modules=None):
    m = types.ModuleType(name)
    sys.modules[name] = m
    if created_modules is not None:
        created_modules.append(m)
    return m


def _load_ansible_zstacklib_with_stubs():
    module_names = [
        'ansible',
        'ansible.constants',
        'ansible.context',
        'ansible.executor',
        'ansible.executor.task_queue_manager',
        'ansible.module_utils',
        'ansible.module_utils.common',
        'ansible.module_utils.common.collections',
        'ansible.inventory',
        'ansible.inventory.manager',
        'ansible.parsing',
        'ansible.parsing.dataloader',
        'ansible.playbook',
        'ansible.playbook.play',
        'ansible.plugins',
        'ansible.plugins.cache',
        'ansible.plugins.cache.memory',
        'ansible.plugins.callback',
        'ansible.vars',
        'ansible.vars.manager',
        'jinja2',
        'yaml',
    ]
    sentinel = object()
    old_modules = dict((name, sys.modules.get(name, sentinel))
                       for name in module_names)
    created_modules = []

    def stub_module(name):
        return _module(name, created_modules)

    try:
        stub_module('jinja2')
        stub_module('yaml')

        ansible_pkg = stub_module('ansible')
        constants = stub_module('ansible.constants')
        constants.set_constant = lambda *args, **kwargs: None
        ansible_pkg.constants = constants
        ansible_pkg.context = stub_module('ansible.context')

        executor = stub_module('ansible.executor')
        tqm = stub_module('ansible.executor.task_queue_manager')

        class TaskQueueManager(object):
            def __init__(self, *args, **kwargs):
                self._loader = None
                self._callbacks_loaded = False

            def run(self, play):
                return 0

            def cleanup(self):
                pass

        tqm.TaskQueueManager = TaskQueueManager
        executor.task_queue_manager = tqm
        ansible_pkg.executor = executor

        module_utils = stub_module('ansible.module_utils')
        common = stub_module('ansible.module_utils.common')
        collections = stub_module('ansible.module_utils.common.collections')
        collections.ImmutableDict = dict
        common.collections = collections
        module_utils.common = common

        inventory = stub_module('ansible.inventory')
        inventory_manager = stub_module('ansible.inventory.manager')
        inventory_manager.InventoryManager = type(
            'InventoryManager', (object,),
            {'__init__': lambda self, *args, **kwargs: None})
        inventory.manager = inventory_manager

        parsing = stub_module('ansible.parsing')
        dataloader = stub_module('ansible.parsing.dataloader')
        dataloader.DataLoader = type(
            'DataLoader', (object,),
            {'__init__': lambda self, *args, **kwargs: None})
        parsing.dataloader = dataloader

        playbook = stub_module('ansible.playbook')
        play = stub_module('ansible.playbook.play')

        class Play(object):
            def load(self, *args, **kwargs):
                return self

        play.Play = Play
        playbook.play = play

        plugins = stub_module('ansible.plugins')
        cache = stub_module('ansible.plugins.cache')
        memory = stub_module('ansible.plugins.cache.memory')
        callback = stub_module('ansible.plugins.callback')
        cache.BaseCacheModule = type('BaseCacheModule', (object,), {})
        cache.memory = memory
        memory.CacheModule = None
        callback.CallbackBase = type(
            'CallbackBase', (object,),
            {'__init__': lambda self, *args, **kwargs: None})
        plugins.cache = cache
        plugins.callback = callback

        vars_pkg = stub_module('ansible.vars')
        vars_manager = stub_module('ansible.vars.manager')
        vars_manager.VariableManager = type(
            'VariableManager', (object,),
            {'__init__': lambda self, *args, **kwargs: None})
        vars_pkg.manager = vars_manager

        root = os.path.abspath(os.path.join(
            os.path.dirname(__file__), '..', '..', '..'))
        zstacklib_path = os.path.join(
            root, 'zstacklib', 'ansible', 'zstacklib.py')
        return imp.load_source(
            '_ansible_zstacklib_rpmdb_repair_under_test', zstacklib_path)
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


zstacklib = _load_ansible_zstacklib_with_stubs()


class _HostPostInfo(object):
    def __init__(self):
        self.host = 'host'
        self.post_url = ''
        self.post_label = None
        self.post_label_param = None


class TestAnsibleRpmdbRepair(unittest.TestCase):
    def setUp(self):
        zstacklib.warn = mock.Mock()
        self.host_post_info = _HostPostInfo()

    def _continue(self):
        return zstacklib.RpmdbRepairDecision(False, True, None)

    def test_remote_repair_command_disables_yum0_setup(self):
        with mock.patch.object(zstacklib, 'run_remote_command',
                               return_value=True) as run_remote:
            zstacklib._run_rpmdb_status_command(
                'yum --disablerepo=* list installed', self.host_post_info)

        command = run_remote.call_args[0][0]
        kwargs = run_remote.call_args[1]
        self.assertIn('flock -w 60 -x 9', command)
        self.assertIn(') 9>/run/zstack-yum.lock', command)
        self.assertNotIn('flock -E', command)
        self.assertFalse(kwargs['setup_yum0'])
        self.assertTrue(kwargs['return_status'])

    def test_transaction_command_puts_yum0_setup_inside_lock(self):
        with mock.patch.object(zstacklib, 'run_remote_command',
                               return_value=True) as run_remote:
            zstacklib.run_remote_rpmdb_transaction_command(
                'yum install -y foo', self.host_post_info,
                return_status=True)

        command = run_remote.call_args[0][0]
        kwargs = run_remote.call_args[1]
        self.assertIn('flock -w 60 -x 9', command)
        self.assertIn(') 9>/run/zstack-yum.lock', command)
        self.assertNotIn('flock -E', command)
        self.assertIn('rpm -q zstack-release', command)
        self.assertIn('yum install -y foo', command)
        self.assertLess(command.index('flock -w 60 -x 9'),
                        command.index('rpm -q zstack-release'))
        self.assertFalse(kwargs['setup_yum0'])
        self.assertTrue(kwargs['return_status'])

    def test_yum_install_package_uses_rpmdb_transaction_lock(self):
        with mock.patch.object(
                zstacklib, 'run_remote_rpmdb_transaction_command',
                side_effect=[False, (True, {})]) as run_locked, \
                mock.patch.object(zstacklib, 'handle_ansible_info'):
            self.assertTrue(zstacklib.yum_install_package(
                'foo', self.host_post_info))

        commands = [call[0][0] for call in run_locked.call_args_list]
        self.assertEqual(['rpm -q --whatprovides foo',
                          'yum --nogpgcheck install -y foo'], commands)
        self.assertFalse(
            run_locked.call_args_list[0][1].get('return_result', False))
        self.assertTrue(run_locked.call_args_list[1][1]['return_result'])

    def test_yum_force_install_updates_installed_package(self):
        with mock.patch.object(
                zstacklib, 'run_remote_rpmdb_transaction_command',
                side_effect=[True, (True, {})]) as run_locked, \
                mock.patch.object(zstacklib, 'handle_ansible_info'):
            self.assertTrue(zstacklib.yum_install_package(
                'foo', self.host_post_info, force_install=True))

        commands = [call[0][0] for call in run_locked.call_args_list]
        self.assertEqual(['rpm -q --whatprovides foo',
                          'yum --nogpgcheck update -y foo'], commands)

    def test_yum_install_failure_keeps_structured_ansible_result(self):
        result = {'contacted': {
            self.host_post_info.host: {
                'rc': 1,
                'stdout': 'stdout text',
                'stderr': 'stderr text'
            }}}
        with mock.patch.object(
                zstacklib, 'run_remote_rpmdb_transaction_command',
                side_effect=[False, (False, result)]), \
                mock.patch.object(zstacklib, 'handle_ansible_info'), \
                mock.patch.object(
                    zstacklib, '_fail_with_rpmdb_transaction_result') \
                as fail:
            zstacklib.yum_install_package('foo', self.host_post_info)

        fail.assert_called_once_with(
            'ERROR: YUM install package foo failed',
            result,
            self.host_post_info)
        self.assertEqual(
            'ansible.yum.install.pkg.fail',
            self.host_post_info.post_label)

    def test_yum_enable_repo_failure_keeps_structured_ansible_result(self):
        result = {'contacted': {
            self.host_post_info.host: {
                'rc': 1,
                'stdout': 'stdout text',
                'stderr': 'stderr text'
            }}}
        with mock.patch.object(
                zstacklib, 'run_remote_rpmdb_transaction_command',
                return_value=(False, result)), \
                mock.patch.object(zstacklib, 'handle_ansible_info'), \
                mock.patch.object(
                    zstacklib, '_fail_with_rpmdb_transaction_result') \
                as fail:
            zstacklib.yum_enable_repo(
                'foo', '*', 'zstack-local', self.host_post_info)

        fail.assert_called_once_with(
            'ERROR: Enable yum repo failed',
            result,
            self.host_post_info)
        self.assertEqual(
            'ansible.yum.enable.repo.fail',
            self.host_post_info.post_label)

    def test_yum_remove_failure_keeps_structured_ansible_result(self):
        result = {'contacted': {
            self.host_post_info.host: {
                'rc': 1,
                'stdout': 'stdout text',
                'stderr': 'stderr text'
            }}}
        with mock.patch.object(
                zstacklib, 'run_remote_rpmdb_transaction_command',
                side_effect=[True, (False, result)]), \
                mock.patch.object(zstacklib, 'handle_ansible_info'), \
                mock.patch.object(
                    zstacklib, '_fail_with_rpmdb_transaction_result') \
                as fail:
            zstacklib.yum_remove_package('foo', self.host_post_info)

        fail.assert_called_once_with(
            'ERROR: yum remove package foo failed',
            result,
            self.host_post_info)
        self.assertEqual(
            'ansible.yum.remove.pkg.fail',
            self.host_post_info.post_label)

    def test_install_release_uses_rpmdb_transaction_lock(self):
        class HostInfo(object):
            host_arch = 'x86_64'

        with mock.patch.object(zstacklib, 'get_host_releasever',
                               return_value='c79'), \
                mock.patch.object(zstacklib, 'copy'), \
                mock.patch.object(
                    zstacklib, 'run_remote_rpmdb_transaction_command') \
                as run_locked:
            zstacklib.install_release_on_host(
                True, HostInfo(), self.host_post_info)

        command = run_locked.call_args[0][0]
        self.assertIn('rpm -qi zstack-release', command)
        self.assertIn('rpm -e zstack-release', command)
        self.assertIn('rpm -i /opt/zstack-release-c79', command)

    def test_first_pass_stops_when_yum_fails_but_rpmdb_is_healthy(self):
        with mock.patch.object(zstacklib, '_rpmdb_check', return_value=True):
            decision = zstacklib._evaluate_rpmdb_repair_state(
                [], self.host_post_info)

        self.assertTrue(decision.stop)
        self.assertTrue(decision.success)
        self.assertIn('rpmdb is healthy', decision.message)

    def test_second_pass_does_not_stop_before_cleanup_when_no_processes(self):
        with mock.patch.object(zstacklib, '_rpmdb_check', return_value=True), \
                mock.patch.object(zstacklib, '_list_rpmdb_users',
                                  return_value=([], None)):
            decision = zstacklib._evaluate_rpmdb_repair_state(
                [], self.host_post_info, check_remaining_processes=True)

        self.assertFalse(decision.stop)

    def test_process_checks_do_not_ignore_whole_process_group(self):
        with mock.patch.object(zstacklib, '_run_rpmdb_output_command',
                               return_value=(True, '')) as run_cmd:
            zstacklib._list_package_processes(self.host_post_info)
            package_command = run_cmd.call_args[0][0]

        self.assertNotIn('proc_pgid == pgid', package_command)
        self.assertNotIn('ps -o pgid= -p $$', package_command)

        with mock.patch.object(zstacklib, '_run_rpmdb_output_command',
                               return_value=(True, '')) as run_cmd:
            zstacklib._list_rpmdb_users(self.host_post_info)
            rpmdb_command = run_cmd.call_args[0][0]

        self.assertNotIn('proc_pgid', rpmdb_command)
        self.assertNotIn('ps -o pgid= -p $$', rpmdb_command)

    def test_young_package_process_waits_and_still_stops_repair(self):
        process = {
            'pid': 123,
            'stat': 'S',
            'etimes': 1,
            'comm': 'yum',
            'args': 'yum install foo'
        }

        with mock.patch.object(zstacklib.time, 'sleep') as sleep, \
                mock.patch.object(zstacklib, '_yum_rpmdb_check',
                                  return_value=False), \
                mock.patch.object(zstacklib, '_list_package_processes',
                                  return_value=[process]), \
                mock.patch.object(zstacklib,
                                  '_evaluate_rpmdb_repair_state',
                                  return_value=self._continue()):
            decision = zstacklib._wait_for_young_package_processes(
                [process], self.host_post_info)

        sleep.assert_called_once_with(zstacklib.RPMDB_REPAIR_WAIT_SECONDS)
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

        with mock.patch.object(zstacklib, '_yum_rpmdb_check',
                               side_effect=[False, False, False]), \
                mock.patch.object(zstacklib,
                                  '_check_rpmdb_repair_prerequisites',
                                  return_value=self._continue()), \
                mock.patch.object(zstacklib, '_remove_stale_yum_pid_files',
                                  side_effect=[self._continue(),
                                               self._continue()]) \
                as remove_pid, \
                mock.patch.object(zstacklib, '_check_rpmdb_opened',
                                  return_value=self._continue()), \
                mock.patch.object(zstacklib, '_list_package_processes',
                                  side_effect=[[stale_process],
                                               [stale_process],
                                               []]), \
                mock.patch.object(zstacklib,
                                  '_evaluate_rpmdb_repair_state',
                                  side_effect=[self._continue(),
                                               self._continue()]), \
                mock.patch.object(zstacklib,
                                  '_wait_for_young_package_processes',
                                  return_value=self._continue()), \
                mock.patch.object(zstacklib, '_terminate_package_processes',
                                  return_value=self._continue()), \
                mock.patch.object(zstacklib, '_rpmdb_check',
                                  return_value=True):
            decision = zstacklib.repair_rpmdb_if_damaged(self.host_post_info)

        self.assertEqual(2, remove_pid.call_count)
        self.assertTrue(decision.stop)
        self.assertTrue(decision.success)
        self.assertIn('rpmdb is healthy after clearing', decision.message)

    def test_repair_rebuilds_only_when_rpmdb_is_broken_and_unused(self):
        with mock.patch.object(zstacklib, '_yum_rpmdb_check',
                               side_effect=[False, False, False, True]), \
                mock.patch.object(zstacklib,
                                  '_check_rpmdb_repair_prerequisites',
                                  return_value=self._continue()), \
                mock.patch.object(zstacklib, '_remove_stale_yum_pid_files',
                                  return_value=self._continue()), \
                mock.patch.object(zstacklib, '_check_rpmdb_opened',
                                  return_value=self._continue()), \
                mock.patch.object(zstacklib, '_list_package_processes',
                                  side_effect=[[], [], []]), \
                mock.patch.object(zstacklib, '_rpmdb_check',
                                  side_effect=[False, False]), \
                mock.patch.object(zstacklib, '_list_rpmdb_users',
                                  side_effect=[([], None),
                                               ([], None),
                                               ([], None)]), \
                mock.patch.object(zstacklib, '_terminate_package_processes',
                                  return_value=self._continue()), \
                mock.patch.object(zstacklib, '_backup_and_rebuild_rpmdb',
                                  return_value=self._continue()) as rebuild:
            decision = zstacklib.repair_rpmdb_if_damaged(self.host_post_info)

        self.assertFalse(decision.stop)
        rebuild.assert_called_once_with(self.host_post_info)

    def test_repair_skips_rebuild_when_rpmdb_is_opened(self):
        with mock.patch.object(zstacklib, '_yum_rpmdb_check',
                               side_effect=[False, False]), \
                mock.patch.object(zstacklib,
                                  '_check_rpmdb_repair_prerequisites',
                                  return_value=self._continue()), \
                mock.patch.object(zstacklib, '_remove_stale_yum_pid_files',
                                  return_value=self._continue()), \
                mock.patch.object(zstacklib, '_list_rpmdb_users',
                                  return_value=(['123'], None)), \
                mock.patch.object(zstacklib, '_list_package_processes') \
                as list_processes, \
                mock.patch.object(zstacklib, '_backup_and_rebuild_rpmdb') \
                as rebuild:
            decision = zstacklib.repair_rpmdb_if_damaged(self.host_post_info)

        self.assertTrue(decision.stop)
        self.assertTrue(decision.success)
        self.assertIn('rpmdb is still opened', decision.message)
        list_processes.assert_not_called()
        rebuild.assert_not_called()

    def test_zstacklib_fails_rpm_setup_when_repair_is_deferred(self):
        class HostInfo(object):
            host_arch = 'x86_64'
            ansible_distribution = 'centos core 7.9.2009'

        args = zstacklib.ZstackLibArgs()
        args.distro = 'centos'
        args.distro_release = 'Core'
        args.distro_version = 7
        args.zstack_repo = 'false'
        args.zstack_apt_source = None
        args.zstack_root = '/zstack'
        args.host_post_info = self.host_post_info
        args.trusted_host = 'host'
        args.pip_url = 'http://host/simple'
        args.yum_server = 'host'
        args.zstack_releasever = 'c79'
        args.apt_server = None
        args.require_python_env = 'true'
        args.host_info = HostInfo()

        deferred = zstacklib.RpmdbRepairDecision(
            True, True, 'rpmdb is busy')
        with mock.patch.object(zstacklib, 'enforce_history'), \
                mock.patch.object(zstacklib, 'check_umask'), \
                mock.patch.object(zstacklib, 'configure_hosts'), \
                mock.patch.object(zstacklib, 'repair_rpmdb_if_damaged',
                                  return_value=deferred), \
                mock.patch.object(zstacklib, 'install_release_on_host') \
                as install_release:
            with self.assertRaises(SystemExit):
                zstacklib.ZstackLib(args)

        install_release.assert_not_called()


if __name__ == '__main__':
    unittest.main()
