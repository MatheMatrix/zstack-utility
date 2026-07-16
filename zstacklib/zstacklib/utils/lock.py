'''

@author: Frank
'''

import weakref
import threading
import functools
import log
import os
import fcntl
import errno
import time
#import typing

_internal_lock = threading.RLock()
_locks = weakref.WeakValueDictionary()

logger = log.get_logger(__name__)

def _get_lock(name):
    with _internal_lock:
        lock = _locks.get(name, threading.RLock())
        if not name in _locks:
            _locks[name] = lock
        return lock

class LockTimeout(Exception):
    pass


class NamedLock(object):
    def __init__(self, name, timeout=None, interval=0.2):
        self.name = name
        self.lock = None
        self.timeout = timeout
        self.interval = interval

    def __enter__(self):
        self.lock = _get_lock(self.name)
        if self.timeout is None:
            self.lock.acquire()
            return

        deadline = time.time() + self.timeout
        while True:
            if self.lock.acquire(False):
                return
            if time.time() >= deadline:
                raise LockTimeout("unable to acquire named lock %s in %ss" %
                                  (self.name, self.timeout))
            time.sleep(self.interval)
        #logger.debug('%s got lock %s' % (threading.current_thread().name, self.name))

    def __exit__(self, type, value, traceback):
        self.lock.release()
        #logger.debug('%s released lock %s' % (threading.current_thread().name, self.name))


def lock(name='defaultLock'):
    def wrap(f):
        @functools.wraps(f)
        def inner(*args, **kwargs):
            with NamedLock(name):
                retval = f(*args, **kwargs)
            return retval
        return inner
    return wrap


class Locker(object):
    def lock(self, lock_file):
        raise Exception('function lock not be implemented')

    def unlock(self, lock_file):
        raise Exception('function unlock not be implemented')


class Flock(Locker):
    def __init__(self, timeout=None, interval=0.2):
        self.timeout = timeout
        self.interval = interval

    def lock(self, lock_file):
        if self.timeout is None:
            fcntl.flock(lock_file, fcntl.LOCK_EX)
            return

        deadline = time.time() + self.timeout
        while True:
            try:
                fcntl.flock(lock_file, fcntl.LOCK_EX | fcntl.LOCK_NB)
                return
            except (IOError, OSError) as e:
                if e.errno not in (errno.EACCES, errno.EAGAIN):
                    raise
                if time.time() >= deadline:
                    raise LockTimeout("unable to acquire file lock %s in %ss" %
                                      (lock_file.name, self.timeout))
                time.sleep(self.interval)

    def unlock(self, lock_file):
        fcntl.flock(lock_file, fcntl.LOCK_UN)


class Lockf(Locker):
    def lock(self, lock_file):
        fcntl.lockf(lock_file, fcntl.LOCK_EX)

    def unlock(self, lock_file):
        fcntl.lockf(lock_file, fcntl.LOCK_UN)


# NOTE(weiw): caller should manually clean up lock file if not need anymore
def file_lock(name, locker=Lockf(), debug=False):
    def wrap(f):
        @functools.wraps(f)
        def inner(*args, **kwargs):
            lock_timeout = getattr(locker, 'timeout', None)
            with NamedLock(name, timeout=lock_timeout):
                if debug:
                    logger.debug("entering named lock %s with function %s.%s" % (name, f.__module__, f.__name__))
                with FileLock(name, locker):
                    retval = f(*args, **kwargs)
                if debug:
                    logger.debug("exit named lock %s with function %s.%s" % (name, f.__module__, f.__name__))
            return retval
        return inner
    return wrap

class FileLock(object):
    LOCK_DIR = '/var/lib/zstack/lock/'

    def __init__(self, lock_prefix, locker=Lockf()):
        def _prepare_lock_file(dname, fname):
            if not os.path.exists(dname):
                os.makedirs(dname, 0755)

            lock_file_path = os.path.join(dname, fname)
            self.lock_file = open(lock_file_path, 'w')
            os.chmod(lock_file_path, 0o600)

        self.locker = locker
        if os.path.isabs(lock_prefix):
            _prepare_lock_file(os.path.dirname(lock_prefix), os.path.basename(lock_prefix))
        else:
            _prepare_lock_file(self.LOCK_DIR, '%s.lock' % lock_prefix)

    def lock(self):
        self.locker.lock(self.lock_file)

    def unlock(self):
        try:
            self.locker.unlock(self.lock_file)
        finally:
            self.lock_file.close()

    def __enter__(self):
        self.lock()

    def __exit__(self, exc_type, exc_val, exc_tb):
        self.unlock()

class NonBlockNamedLock(object):
    def __init__(self, name):
        self.name = name
        self.acquired = False
        self.lock = None

    def __enter__(self):
        self.lock = _get_lock(self.name)
        self.acquired = self.lock.acquire(blocking=False)
        return self

    def __exit__(self, type, value, traceback):
        if not self.acquired:
            return
        try:
            self.lock.release()
        except Exception as e:
            logger.debug('%s released lock %s error: %s' % (threading.current_thread().name, self.name, str(e)))

