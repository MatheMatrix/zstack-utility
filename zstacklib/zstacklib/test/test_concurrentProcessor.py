import unittest
import time

from zstacklib.utils.concurrentProcessor import ConcurrentProcessor


class TestItem:
    def __init__(self, value):
        self.value = value


class TestProcessor(ConcurrentProcessor):
    def process_item(self, item):
        # Simulate some processing time
        time.sleep(0.1)
        if item.value % 5 == 0:
            raise ValueError("Error processing item with value %d" % item.value)
        return item.value * 2


class TestConcurrentProcessor(unittest.TestCase):
    def test_basic_functionality(self):
        processor = TestProcessor(max_queue_size=10)
        items = [TestItem(i) for i in range(20)]
        results = processor.run(items)

        # Check if we got the correct number of results
        self.assertEqual(len(results), 16)  # 20 items - 4 errors = 16 results

        # Check if the results are correct
        expected_results = [i * 2 for i in range(20) if i % 5 != 0]
        self.assertEqual(sorted(results), expected_results)

    def test_empty_input(self):
        processor = TestProcessor()
        results = processor.run([])
        self.assertEqual(results, [])

    def test_all_items_error(self):
        class ErrorProcessor(ConcurrentProcessor):
            def process_item(self, item):
                raise ValueError("Always error")

        processor = ErrorProcessor()
        items = [TestItem(i) for i in range(5)]
        results = processor.run(items)
        self.assertEqual(results, [])

    def test_max_queue_size(self):
        processor = TestProcessor(max_queue_size=1)
        items = [TestItem(i) for i in range(10)]
        start_time = time.time()
        results = processor.run(items)
        end_time = time.time()

        # Check if we got all results
        self.assertEqual(len(results), 8)  # 10 items - 2 errors = 8 results

        # The processing should take at least 1 second (0.1s * 10 items)
        self.assertGreater(end_time - start_time, 1)


if __name__ == '__main__':
    unittest.main()
