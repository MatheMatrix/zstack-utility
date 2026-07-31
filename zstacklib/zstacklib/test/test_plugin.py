'''

@author: frank
'''
import unittest
import os.path
import time
from zstacklib.utils import plugin

class TestPlugin(unittest.TestCase):
    def setUp(self):
        with plugin.task_operator_lock:
            plugin.task_daemons.clear()
            plugin.cancelled_task_tombstones.clear()

    def tearDown(self):
        with plugin.task_operator_lock:
            plugin.task_daemons.clear()
            plugin.cancelled_task_tombstones.clear()

    def test_plugin_start(self):
        plugin_rgty = plugin.PluginRegistry(os.path.abspath('zstacklib/test/plugin/plugins.cfg'))
        config = {'key':'value'}
        plugin_rgty.configure_plugins(config)
        plugin_rgty.start_plugins()
        plugin1 = plugin_rgty.get_plugin('Plugin1')
        self.assertTrue(plugin1.start_called)
        self.assertEqual(config['key'], plugin1.config['key'])
        
    def test_plugin_stop(self):
        plugin_rgty = plugin.PluginRegistry(os.path.abspath('zstacklib/test/plugin/plugins.cfg'))
        plugin_rgty.start_plugins()
        plugin_rgty.stop_plugins()
        plugin1 = plugin_rgty.get_plugin('Plugin1')
        self.assertTrue(plugin1.stop_called)

    def test_cancel_job_keeps_missing_task_failure_by_default(self):
        cmd = type('Cmd', (), {'cancellationApiId': 'missing-api'})()
        rsp = plugin._cancel_job(cmd, plugin.CancelJobResponse(), times=0, interval=0)

        self.assertFalse(rsp.success)
        self.assertEqual('no matched job to cancel', rsp.error)

    def test_cancel_before_registration_cancels_late_task(self):
        cmd = type('Cmd', (), {
            'cancellationApiId': 'late-api',
            'allowTaskNotFound': True,
        })()
        rsp = plugin._cancel_job(cmd, plugin.CancelJobResponse(), times=0, interval=0)
        self.assertEqual('TASK_NOT_FOUND', rsp.cancelResult)

        task = FakeTask()
        self.assertFalse(plugin.TaskManager.add_task(cmd.cancellationApiId, task))
        self.assertTrue(task.canceled)
        self.assertTrue(plugin.TaskManager.cancel_tombstone_matched(cmd.cancellationApiId))

    def test_task_daemon_context_rejects_pending_cancellation(self):
        plugin.TaskManager.remember_cancellation('late-daemon-api')
        daemon = FakeTaskDaemon(_task_spec('late-daemon-api'))
        body_entered = False

        with self.assertRaises(plugin.TaskCanceledByPendingCancellation):
            with daemon:
                body_entered = True

        self.assertFalse(body_entered)
        self.assertTrue(daemon.canceled)
        self.assertTrue(daemon.closed)

    def test_expired_cancel_tombstones_are_pruned(self):
        plugin.cancelled_task_tombstones['expired-api'] = {
            'expiresAt': time.time() - 1,
            'matched': False,
        }

        plugin.TaskManager.remember_cancellation('current-api')

        self.assertNotIn('expired-api', plugin.cancelled_task_tombstones)
        self.assertIn('current-api', plugin.cancelled_task_tombstones)


class FakeTask(object):
    def __init__(self):
        self.canceled = False

    def cancel(self):
        self.canceled = True


class ThreadContext(dict):
    def __getattr__(self, name):
        return self.get(name)

    def __getitem__(self, name):
        return self.get(name)


def _task_spec(api_id):
    spec = type('Spec', (), {})()
    spec.threadContext = ThreadContext(api=api_id)
    spec.taskContext = None
    return spec


class FakeTaskDaemon(plugin.TaskDaemon):
    def __init__(self, spec):
        super(FakeTaskDaemon, self).__init__(spec, 'fakeTask')
        self.canceled = False

    def _cancel(self):
        self.canceled = True


if __name__ == "__main__":
    #import sys;sys.argv = ['', 'Test.testName']
    unittest.main()
