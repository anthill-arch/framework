from anthill.framework.conf import settings
from anthill.framework.auth.models import AnonymousUser
from logging.handlers import RotatingFileHandler
from tornado.log import LogFormatter
import logging
import functools
import os


__all__ = ['get_user_logger', 'ApplicationLogger']


USER_LOGGING_ROOT_DIR = getattr(settings, 'USER_LOGGING_ROOT_DIR', '')
USER_LOGGING_MAX_FILE_SIZE = getattr(settings, 'USER_LOGGING_MAX_FILE_SIZE', 50 * 1024 * 1024)
USER_LOGGING_BACKUP_COUNT = getattr(settings, 'USER_LOGGING_BACKUP_COUNT', 10)


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


def get_user_logger(user, root_dir=USER_LOGGING_ROOT_DIR,
                    max_file_size=USER_LOGGING_MAX_FILE_SIZE,
                    backup_count=USER_LOGGING_BACKUP_COUNT):

    username = 'anonymous' if isinstance(user, AnonymousUser) else user.username
    logger = logging.getLogger('user.%s' % username)

    handler_settings = {
        'filename': os.path.join(root_dir, '%s.log' % username),
        'maxBytes': max_file_size,
        'backupCount': backup_count,
    }
    try:
        handler = UserRotatingFileHandler(**handler_settings)
    except FileNotFoundError:
        logger.disabled = True
        if not settings.DEBUG:
            raise
    else:
        formatter_settings = {
            'fmt': '[%(levelname)1.1s %(asctime)s %(module)s:%(lineno)d] %(message)s',
            'datefmt': '%Y-%m-%d %H:%M:%S',
        }
        formatter = UserFormatter(**formatter_settings)

        handler.setLevel(logging.INFO)
        handler.setFormatter(formatter)
        handler.addFilter(RequireDebugFalse)

        if not logger.handlers:
            logger.addHandler(handler)

    return logger


class ApplicationLogger:
    def __init__(self, user, logger=None):
        self._user = user
        self._logger = logger or logging.getLogger('anthill.application')

    def __getattr__(self, name):
        attr = getattr(self._logger, name)
        if name in ('debug', 'info', 'warning', 'error', 'critical', 'exception', 'log'):
            return functools.partial(attr, extra={'username': self._user.username})
        else:
            return attr
