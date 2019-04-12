from tornado.concurrent import Future, chain_future
from concurrent.futures import ThreadPoolExecutor
from tornado.process import cpu_count
from tornado.ioloop import IOLoop
from functools import wraps

__all__ = [
    'ThreadPoolExecution', 'thread_pool_exec', 'as_future'
]


class ThreadPoolExecution:
    """Tiny wrapper around ThreadPoolExecutor."""

    def __init__(self, max_workers=None):
        self._max_workers = max_workers or (cpu_count() or 1) * 5
        self._pool = ThreadPoolExecutor(max_workers=self._max_workers)

    def set_max_workers(self, count):
        if self._pool:
            self._pool.shutdown(wait=True)
        self._max_workers = count or (cpu_count() or 1) * 5
        self._pool = ThreadPoolExecutor(max_workers=self._max_workers)

    def _as_future(self, blocking_func, *args, **kwargs):
        c_future = self._pool.submit(blocking_func, *args, **kwargs)
        t_future = Future()
        IOLoop.current().add_future(c_future, lambda f: chain_future(f, t_future))
        return t_future

    def __call__(self, blocking_func, *args, **kwargs):
        return self._as_future(blocking_func, *args, **kwargs)

    def as_future(self, blocking_func):
        @wraps(blocking_func)
        def wrapper(*args, **kwargs):
            return self._as_future(blocking_func, *args, **kwargs)

        return wrapper


thread_pool_exec = ThreadPoolExecution()
as_future = thread_pool_exec.as_future
