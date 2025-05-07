from zstacklib.utils import lock
import unittest
import threading
import time

args = []
@lock.lock(blocking=True)
def func(arg1, arg2):
    args.extend((arg1, arg2))
    print("func execute ,arg1 %s , arg2 %s....." % (arg1, arg2))
    time.sleep(2)

@lock.lock(blocking=False)
def func2(arg1, arg2):
    args.extend((arg1, arg2))
    print("func2 execute ,arg1 %s , arg2 %s....." % (arg1, arg2))

def handle(f, *args, **kwargs):
    print("%s failed to execute ,args %s....." % (f.__name__, args))

@lock.lock(blocking=False, fail_lock_handler=handle)
def func3(arg1, arg2):
    args.extend((arg1, arg2))
    print("func3 execute ,arg1 %s , arg2 %s....." % (arg1, arg2))

@lock.lock(blocking=False, lock_retry_count=6, fail_lock_handler=handle)
def func4(arg1, arg2):
    args.extend((arg1, arg2))
    print("func4 execute ,arg1 %s , arg2 %s....." % (arg1, arg2))

class Test(unittest.TestCase):
    def test(self):
        threading.Thread(target=func, args=(1, 2,)).start()
        threading.Thread(target=func, args=(3, 4,)).start()
        threading.Thread(target=func2, args=(5, 6,)).start() # will not execute
        threading.Thread(target=func4, args=(7, 8,)).start() # will not execute
        time.sleep(8)
        threading.Thread(target=func3, args=(9, 10,)).start()
        threading.Thread(target=func, args=(11, 12,)).start()
        time.sleep(5)

if __name__ == "__main__":
    unittest.main()
