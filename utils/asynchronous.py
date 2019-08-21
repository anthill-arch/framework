from tornado.concurrent import Future, chain_future
from concurrent.futures import ThreadPoolExecutor
from tornado.process import cpu_count
from tornado.ioloop import IOLoop
from functools import wraps

__all__ = ['ThreadPoolExecution', 'thread_pool_exec', 'as_future']


CPU_COUNT = (cpu_count() or 1) * 5


class ThreadPoolExecution:
    """Tiny wrapper around ThreadPoolExecutor."""

    def __init__(self, max_workers=None):
        self._max_workers = max_workers or CPU_COUNT
        self._pool = ThreadPoolExecutor(max_workers=self._max_workers)

    def set_max_workers(self, count):
        if self._pool:
            self._pool.shutdown(wait=True)
        if count:
            self._max_workers = count
        self._pool = ThreadPoolExecutor(max_workers=self._max_workers)

    def _as_future(self, func, *args, **kwargs):
        c_future = self._pool.submit(func, *args, **kwargs)
        # Concurrent Futures are not usable with await. Wrap this in a
        # Tornado Future instead, using self.add_future for thread-safety.
        t_future = Future()
        IOLoop.current().add_future(c_future, lambda f: chain_future(f, t_future))
        return t_future

    def __call__(self, func, *args, **kwargs):
        return self._as_future(func, *args, **kwargs)

    def as_future(self, func):
        @wraps(func)
        def wrapper(*args, **kwargs):
            return self._as_future(func, *args, **kwargs)
        return wrapper


thread_pool_exec = ThreadPoolExecution()
as_future = thread_pool_exec.as_future
