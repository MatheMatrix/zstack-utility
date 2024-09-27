import threading
import time


class MultiSingleFlight:
    def __init__(self):
        self.flights = {}
        self.lock = threading.Lock()

    def get_or_create_flight(self, key, cache_time):
        with self.lock:
            if key not in self.flights:
                self.flights[key] = SingleFlight(cache_time)
            return self.flights[key]

    def do(self, key, cache_time, func, *args, **kwargs):
        flight = self.get_or_create_flight(key, cache_time)
        return flight.do(func, *args, **kwargs)


class SingleFlight:
    def __init__(self, cache_time):
        self.lock = threading.Lock()
        self.cache_time = cache_time
        self.last_call_time = 0
        self.cached_result = None
        self.in_flight = False
        self.event = threading.Event()

    def do(self, func, *args, **kwargs):
        with self.lock:
            current_time = time.time()
            if current_time - self.last_call_time < self.cache_time and self.cached_result is not None:
                return self.cached_result

            if self.in_flight:
                self.lock.release()
                self.event.wait()
                self.event.clear()
                self.lock.acquire()
                return self.cached_result

            self.in_flight = True

        try:
            result = func(*args, **kwargs)
            with self.lock:
                self.cached_result = result
                self.last_call_time = time.time()
                return result
        finally:
            with self.lock:
                self.in_flight = False
                self.event.set()


multi_sf = MultiSingleFlight()
