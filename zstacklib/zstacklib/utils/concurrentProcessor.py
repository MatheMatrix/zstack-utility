import threading
import queue

from zstacklib.utils import log

logger = log.get_logger(__name__)


class ConcurrentProcessor:
    def __init__(self, max_queue_size=10):
        self.max_queue_size = max_queue_size
        self.queue = queue.Queue(maxsize=self.max_queue_size)
        self.results = []
        self.threads = []

    def worker(self):
        while True:
            item = self.queue.get()
            if item is None:
                break
            try:
                result = self.process_item(item)
                if result is not None:
                    self.results.append(result)
            except Exception as e:
                logger.warn("Error processing item: %s" % e)
            finally:
                self.queue.task_done()

    def process_item(self, item):
        # This method should be overridden in subclasses
        raise NotImplementedError("Subclasses must implement process_item method")

    def producer(self, items):
        for item in items:
            self.queue.put(item)

        # Add end markers
        for _ in range(self.max_queue_size):
            self.queue.put(None)

    def run(self, items):
        # Start worker threads
        for _ in range(self.max_queue_size):
            t = threading.Thread(target=self.worker)
            t.start()
            self.threads.append(t)

        # Start producer thread
        producer_thread = threading.Thread(target=self.producer, args=(items,))
        producer_thread.start()

        # Wait for producer to finish
        producer_thread.join()

        # Wait for all tasks to complete
        self.queue.join()

        # Wait for all worker threads to finish
        for t in self.threads:
            t.join()

        return self.results
