import threading
import Queue


class Future(object):
    def __init__(self):
        self._condition = threading.Condition()
        self._result = None
        self._exception = None
        self._done = False

    def set_result(self, result):
        with self._condition:
            self._result = result
            self._done = True
            self._condition.notify_all()

    def set_exception(self, exception):
        with self._condition:
            self._exception = exception
            self._done = True
            self._condition.notify_all()

    def result(self, timeout=None):
        with self._condition:
            if not self._done:
                self._condition.wait(timeout)
                if not self._done:
                    raise Exception("result not available within timeout")
            if self._exception:
                raise self._exception
            return self._result

    def exception(self, timeout=None):
        with self._condition:
            if not self._done:
                self._condition.wait(timeout)
                if not self._done:
                    raise Exception("exception not available within timeout")
            return self._exception

    def done(self):
        with self._condition:
            return self._done


class ThreadPoolExecutor(object):
    def __init__(self, max_workers):
        self._max_workers = max_workers
        self._work_queue = Queue.Queue()
        self._threads = []
        self._shutdown = False
        self._shutdown_lock = threading.Lock()

        for _ in range(max_workers):
            t = threading.Thread(target=self._worker)
            t.daemon = True
            t.start()
            self._threads.append(t)

    def _worker(self):
        while True:
            with self._shutdown_lock:
                if self._shutdown and self._work_queue.empty():
                    break

            block = True
            with self._shutdown_lock:
                block = not self._shutdown

            try:
                task = self._work_queue.get(block=block)
            except Queue.Empty:
                with self._shutdown_lock:
                    if self._shutdown:
                        break
                continue

            if task is None:
                self._work_queue.task_done()
                break

            func, args, kwargs, future = task
            try:
                result = func(*args,  ** kwargs)
                future.set_result(result)
            except Exception as e:
                future.set_exception(e)
            finally:
                self._work_queue.task_done()

    def submit(self, func, *args,  ** kwargs):
        with self._shutdown_lock:
            if self._shutdown:
                raise RuntimeError("cannot submit after shutdown")

            future = Future()
            self._work_queue.put((func, args, kwargs, future))
            return future

    def shutdown(self, wait=True):
        with self._shutdown_lock:
            if self._shutdown:
                return
            self._shutdown = True

        for _ in self._threads:
            try:
                self._work_queue.put_nowait(None)
            except Queue.Full:
                pass

        if wait:
            self._work_queue.join()
            for t in self._threads:
                t.join()

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        self.shutdown(wait=True)
        return False