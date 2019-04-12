from anthill.framework.conf import settings
from anthill.framework.core import mail
from anthill.framework.core.mail import get_connection
from anthill.framework.utils.debug.report import ExceptionReporter
from anthill.framework.utils.module_loading import import_string
from tornado.log import LogFormatter
from copy import copy
import os
import logging
import logging.config  # needed when logging_config doesn't start with logging.config


def current_log_level():
    return ('debug' if settings.DEBUG
            else os.environ.get('ANTHILL_LOG_LEVEL', 'info')).upper()


# Default logging. This sends an email to the site admins on every
# HTTP 500 error. Depending on DEBUG, all other log records are either sent to
# the console (DEBUG=True) or discarded (DEBUG=False) by means of the
# require_debug_true filter.
DEFAULT_LOGGING = {
    'version': 1,
    'disable_existing_loggers': False,
    'filters': {
        'require_debug_false': {
            '()': 'anthill.framework.utils.log.RequireDebugFalse',
        },
        'require_debug_true': {
            '()': 'anthill.framework.utils.log.RequireDebugTrue',
        },
    },
    'formatters': {
        'anthill.server': {
            '()': 'anthill.framework.utils.log.ServerFormatter',
            'fmt': '%(color)s[%(levelname)1.1s %(asctime)s %(module)s:%(lineno)d]%(end_color)s %(message)s',
            'datefmt': '%Y-%m-%d %H:%M:%S'
        }
    },
    'handlers': {
        'console': {
            'level': 'DEBUG',
            'filters': ['require_debug_true'],
            'class': 'logging.StreamHandler',
            'formatter': 'anthill.server',
        },
        'anthill.server': {
            'level': 'DEBUG',
            'class': 'logging.StreamHandler',
            'formatter': 'anthill.server',
        },
        'mail_admins': {
            'level': 'ERROR',
            'filters': ['require_debug_false'],
            'class': 'anthill.framework.utils.log.AdminEmailHandler'
        }
    },
    'loggers': {
        'anthill': {
            'handlers': ['console', 'mail_admins'],
            'level': 'INFO',
        },
        'anthill.application': {
            'handlers': ['anthill.server'],
            'level': current_log_level(),
            'propagate': False
        },
        'tornado.access': {
            'handlers': ['anthill.server'],
            'level': current_log_level(),
            'propagate': False
        },
        'tornado.application': {
            'handlers': ['anthill.server'],
            'level': current_log_level(),
            'propagate': False
        },
        'tornado.general': {
            'handlers': ['anthill.server'],
            'level': current_log_level(),
            'propagate': False
        }
    }
}


def configure_logging(logging_config, logging_settings):
    if logging_config:
        # First find the logging configuration function ...
        logging_config_func = import_string(logging_config)

        logging.config.dictConfig(DEFAULT_LOGGING)

        # ... then invoke it with the logging settings
        if logging_settings:
            logging_config_func(logging_settings)


class AdminEmailHandler(logging.Handler):
    """
    An exception log handler that emails log entries to site admins.
    """

    def __init__(self, include_html=False, email_backend=None):
        super().__init__()
        self.include_html = include_html
        self.email_backend = email_backend

    def emit(self, record):
        subject = '%s: %s' % (record.levelname, record.getMessage())
        subject = self.format_subject(subject)

        # Since we add a nicely formatted traceback on our own, create a copy
        # of the log record without the exception data.
        no_exc_record = copy(record)
        no_exc_record.exc_info = None
        no_exc_record.exc_text = None

        if record.exc_info:
            exc_info = record.exc_info
        else:
            exc_info = (None, record.getMessage(), None)

        handler = getattr(record, 'handler', None)

        reporter = ExceptionReporter(handler, exc_info=exc_info, is_email=True)
        message = "%s\n\n%s" % (self.format(no_exc_record), reporter.get_traceback_text())
        html_message = reporter.get_traceback_html() if self.include_html else None
        self.send_mail(subject, message, fail_silently=True, html_message=html_message)

    def send_mail(self, subject, message, *args, **kwargs):
        mail.mail_admins(subject, message, *args, connection=self.connection(), **kwargs)

    def connection(self):
        return get_connection(backend=self.email_backend, fail_silently=True)

    # noinspection PyMethodMayBeStatic
    def format_subject(self, subject):
        """Escape CR and LF characters."""
        return subject.replace('\n', '\\n').replace('\r', '\\r')


class CallbackFilter(logging.Filter):
    """
    A logging filter that checks the return value of a given callable (which
    takes the record-to-be-logged as its only parameter) to decide whether to
    log a record.
    """

    def __init__(self, callback):
        super().__init__()
        self.callback = callback

    def filter(self, record):
        if self.callback(record):
            return 1
        return 0


class RequireDebugFalse(logging.Filter):
    def filter(self, record):
        return not settings.DEBUG


class RequireDebugTrue(logging.Filter):
    def filter(self, record):
        return settings.DEBUG


class ServerFormatter(LogFormatter):
    DEFAULT_FORMAT = \
        '%(color)s[%(levelname)1.1s %(asctime)s %(module)s:%(lineno)d]%(end_color)s %(message)s'
    DEFAULT_USER_FORMAT = \
        '%(color)s[%(levelname)1.1s %(asctime)s %(username)s %(module)s:%(lineno)d]%(end_color)s %(message)s'
    DEFAULT_DATE_FORMAT = '%Y-%m-%d %H:%M:%S'

    def format(self, record):
        if hasattr(record, 'username'):
            self._fmt = self.DEFAULT_USER_FORMAT
            if not record.username:
                record.username = 'anonymous'
        else:
            self._fmt = self.DEFAULT_FORMAT
        return super(ServerFormatter, self).format(record)
