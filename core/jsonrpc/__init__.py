"""Originated from https://github.com/pavlov99/json-rpc"""
from .manager import JSONRPCResponseManager
from .dispatcher import Dispatcher

__version = (1, 11, 0)

__version__ = version = '.'.join(map(str, __version))
__project__ = PROJECT = __name__

dispatcher = Dispatcher()
