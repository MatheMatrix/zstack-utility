import threading
import unittest

from zstacklib.utils import jsonobject, plugin


class TestTaskDaemonConcurrency(unittest.TestCase):
    def test_shared_concurrency_limit(self):
        entered = [threading.Event() for _ in range(4)]
        release = threading.Event()
        task_spec = jsonobject.loads('{}')

        class TestDaemon(plugin.TaskDaemon):
            def __init__(self):
                super(TestDaemon, self).__init__(
                    task_spec, 'test', task_type='test-shared-concurrency', max_concurrency=3)

            def _cancel(self):
                pass

        def run(index):
            with TestDaemon():
                entered[index].set()
                release.wait()

        threads = [threading.Thread(target=run, args=(i,)) for i in range(4)]
        for thread in threads[:3]:
            thread.start()
        for event in entered[:3]:
            self.assertTrue(event.wait(1))

        threads[3].start()
        self.assertFalse(entered[3].wait(0.1))
        release.set()
        self.assertTrue(entered[3].wait(1))
        for thread in threads:
            thread.join(1)
            self.assertFalse(thread.is_alive())


if __name__ == '__main__':
    unittest.main()
