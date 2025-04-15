import threading
import time


class Result:
    def __init__(self, val=None, err=None, shared=False):
        self.value = val
        self.error = err
        self.shared = shared


class Call:
    def __init__(self, fn):
        self.fn = fn
        self.wg = threading.Event()
        self.result = Result()
        threading.Thread(target=self._run).start()

    def _run(self):
        try:
            self.result.value = self.fn()
        except Exception as e:
            self.result.error = e
        finally:
            self.wg.set()

    def wait(self):
        self.wg.wait()
        return self.result


class Group:
    def __init__(self, cache_ttl=60):
        self.mu = threading.Lock()
        self.m = {}
        self.cache = {}
        self.cache_ttl = cache_ttl

    def do(self, key, fn):
        now = time.time()
        with self.mu:
            if key in self.cache:
                cached = self.cache[key]
                if now < cached["expiry"]:
                    result = cached["result"]
                    result.shared = True
                    return result
                else:
                    del self.cache[key]

            if key in self.m:
                call = self.m[key]
                result = call.wait()
                if key in self.cache and self.cache[key]["expiry"] > now:
                    result = self.cache[key]["result"]
                    result.shared = True
                else:
                    self._update_cache(key, result, now)
                return result

            call = Call(fn)
            self.m[key] = call

        result = call.wait()

        with self.mu:
            self._update_cache(key, result, now)
            del self.m[key]

        return result

    def _update_cache(self, key, result, timestamp):
        self.cache[key] = {
            "result": result,
            "expiry": timestamp + self.cache_ttl
        }
