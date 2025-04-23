import unittest
import time
import threading

from zstacklib.utils.future import ThreadPoolExecutor


class Barrier(object):
    def __init__(self, n):
        self.n = n
        self.count = 0
        self.mutex = threading.Semaphore(1)
        self.barrier = threading.Semaphore(0)

    def wait(self):
        self.mutex.acquire()
        self.count += 1
        if self.count == self.n:
            self.barrier.release()
        self.mutex.release()
        self.barrier.acquire()
        self.barrier.release()


class TestThreadPool(unittest.TestCase):
    def test_successful_task(self):
        def func():
            return 42

        with ThreadPoolExecutor(max_workers=2) as executor:
            future = executor.submit(func)
            self.assertEqual(future.result(), 42)

    def test_exception_propagation(self):
        def func():
            raise ValueError("test error")

        with ThreadPoolExecutor(max_workers=2) as executor:
            future = executor.submit(func)
            try:
                future.result()
                self.fail("Expected exception not raised")
            except ValueError as e:
                self.assertEqual(str(e), "test error")

    def test_timeout_behavior(self):
        def long_running():
            time.sleep(1)
            return 42

        with ThreadPoolExecutor(max_workers=1) as executor:
            future = executor.submit(long_running)
            try:
                future.result(timeout=0.1)
                self.fail("Expected TimeoutError not raised")
            except Exception as e:
                assert str(e) == "result not available within timeout"

    def test_shutdown_behavior(self):
        executor = ThreadPoolExecutor(max_workers=1)
        executor.shutdown()
        try:
            executor.submit(lambda: None)
            self.fail("Expected RuntimeError not raised")
        except RuntimeError:
            pass

    def test_concurrent_execution(self):
        start_barrier = Barrier(3)
        results = []

        def task():
            start_barrier.wait()
            time.sleep(0.2)
            results.append(1)

        with ThreadPoolExecutor(max_workers=2) as executor:
            executor.submit(task)
            executor.submit(task)
            start_barrier.wait()

        self.assertEqual(len(results), 2)

    def test_shutdown_wait(self):
        results = []

        def task():
            time.sleep(0.2)
            results.append(42)

        executor = ThreadPoolExecutor(max_workers=1)
        future = executor.submit(task)
        executor.shutdown(wait=True)
        self.assertTrue(future.done())
        self.assertEqual(results, [42])


if __name__ == '__main__':
    unittest.main(verbosity=2)
