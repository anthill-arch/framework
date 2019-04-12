from anthill.framework.conf import settings
from anthill.framework.auth.models import AnonymousUser
from logging.handlers import RotatingFileHandler
from tornado.log import LogFormatter
import logging
import functools
import os

__all__ = ['get_user_logger', 'ApplicationLogger']

USER_LOGGING_ROOT_DIR = getattr(settings, 'USER_LOGGING_ROOT_DIR', '')


class UserFormatter(LogFormatter):
    def __init__(self, color=False, **kwargs):
        super().__init__(color=color, **kwargs)


class UserRotatingFileHandler(RotatingFileHandler):
    pass


class RequireDebugFalse(logging.Filter):
    def filter(self, record):
        return not settings.DEBUG


class RequireDebugTrue(logging.Filter):
    def filter(self, record):
        return settings.DEBUG


def get_user_logger(user):
    username = 'anonymous' if isinstance(user, AnonymousUser) else user.username
    logger = logging.getLogger('user.' + username)

    formatter_settings = {
        'fmt': '[%(levelname)1.1s %(asctime)s %(module)s:%(lineno)d] %(message)s',
        'datefmt': '%Y-%m-%d %H:%M:%S',
    }
    formatter = UserFormatter(**formatter_settings)

    handler_settings = {
        'filename': os.path.join(USER_LOGGING_ROOT_DIR, username + '.log'),
        'maxBytes': 50 * 1024 * 1024,  # 50 MiB
        'backupCount': 10,
    }
    try:
        handler = UserRotatingFileHandler(**handler_settings)
    except FileNotFoundError:
        logger.disabled = True
        if not settings.DEBUG:
            raise
    else:
        handler.setLevel(logging.INFO)
        handler.setFormatter(formatter)
        handler.addFilter(RequireDebugFalse)
        logger.addHandler(handler)

    return logger


class ApplicationLogger:
    def __init__(self, user):
        self._user = user
        self._logger = logging.getLogger('anthill.application')

    def __getattr__(self, name):
        attr = getattr(self._logger, name)
        names = ('debug', 'info', 'warning', 'error', 'critical', 'exception', 'log')
        if name in names:
            return functools.partial(attr, extra={'username': self._user.username})
        else:
            return attr
