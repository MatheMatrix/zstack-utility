import time
import weakref
import threading
import functools
from zstacklib.utils import named_queue as nq
import unittest

@nq.queue("default", 5, block=True, lock_enabled=True)
def task_block_lock(i):
    print(i)
    time.sleep(2)


@nq.queue("default", 5, block=False, lock_enabled=True)
def task_nonblock_lock(i):
    print(i)
    time.sleep(2)

@nq.queue("default", 5, block=True, lock_enabled=False)
def task_block_nonlock(i):
    print(i)
    time.sleep(2)

@nq.queue("default", 5, block=False, lock_enabled=False)
def task_nonblock_nonlock(i):
    print(i)
    time.sleep(2)

class TestCase(unittest.TestCase):
    def test_1(self):
        threading.Thread(target=task_block_lock, args=(1,)).start()
        threading.Thread(target=task_block_lock, args=(2,)).start()
        threading.Thread(target=task_block_lock, args=(3,)).start()
        threading.Thread(target=task_block_lock, args=(4,)).start()
        threading.Thread(target=task_block_lock, args=(5,)).start()

    def test_2(self):
        threading.Thread(target=task_nonblock_lock, args=(11,)).start()
        threading.Thread(target=task_nonblock_lock, args=(12,)).start()
        threading.Thread(target=task_nonblock_lock, args=(13,)).start()
        threading.Thread(target=task_nonblock_lock, args=(14,)).start()
        threading.Thread(target=task_nonblock_lock, args=(15,)).start()

    def test_3(self):
        threading.Thread(target=task_block_nonlock, args=(21,)).start()
        threading.Thread(target=task_block_nonlock, args=(22,)).start()
        threading.Thread(target=task_block_nonlock, args=(23,)).start()
        threading.Thread(target=task_block_nonlock, args=(24,)).start()
        threading.Thread(target=task_block_nonlock, args=(25,)).start()

    def test_4(self):
        threading.Thread(target=task_nonblock_nonlock, args=(31,)).start()
        threading.Thread(target=task_nonblock_nonlock, args=(32,)).start()
        threading.Thread(target=task_nonblock_nonlock, args=(33,)).start()
        threading.Thread(target=task_nonblock_nonlock, args=(34,)).start()
        threading.Thread(target=task_nonblock_nonlock, args=(35,)).start()

if __name__ == '__main__':
    unittest.main()



