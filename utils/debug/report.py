from anthill.framework.core.exceptions import ImproperlyConfigured
from anthill.framework.utils.encoding import force_text
from anthill.framework.utils import timezone
from tornado.template import Loader
from tornado.escape import to_basestring
from tornado.web import RequestHandler
from pprint import pformat
from pathlib import Path
import tornado
import sys
import re


def pprint(value):
    """A wrapper around pprint.pprint -- for debugging, really."""
    try:
        return pformat(value)
    except Exception as e:
        return "Error in formatting: %s: %s" % (e.__class__.__name__, e)


CURRENT_DIR = Path(__file__).parent


class ExceptionReporter:
    """Organize and coordinate reporting on exceptions."""
    html_template_name = 'technical_500.html'
    text_template_name = 'technical_500.txt'

    def __init__(self, handler=None, exc_info=None, is_email=False):
        if handler is not None and not isinstance(handler, RequestHandler):
            raise ImproperlyConfigured(
                '`handler` argument must be a `tornado.web.RequestHandler` instance')

        from anthill.framework.apps import app

        self.app = app
        self.handler = handler
        self.is_email = is_email

        self.exc_info = exc_info or sys.exc_info()
        self.exc_type, self.exc_value, self.tb = self.exc_info

        if self.html_template_name is None:
            raise ImproperlyConfigured('`html_template_name` required')
        if self.text_template_name is None:
            raise ImproperlyConfigured('`text_template_name` required')

        template_loader = Loader(Path(CURRENT_DIR, 'templates'))
        self._html_template = template_loader.load(self.html_template_name)
        self._text_template = template_loader.load(self.text_template_name)

    def get_traceback_data(self):
        """Return a dictionary containing traceback information."""
        frames = self.get_traceback_frames()
        for i, frame in enumerate(frames):
            if 'vars' in frame:
                frame_vars = []
                for k, v in frame['vars']:
                    v = pprint(v)
                    # Trim large blobs of data
                    if len(v) > 4096:
                        v = '%s... <trimmed %d bytes string>' % (v[0:4096], len(v))
                    frame_vars.append((k, v))
                frame['vars'] = frame_vars
            frames[i] = frame

        unicode_hint = ''
        if self.exc_type and issubclass(self.exc_type, UnicodeError):
            start = getattr(self.exc_value, 'start', None)
            end = getattr(self.exc_value, 'end', None)
            if start is not None and end is not None:
                unicode_str = self.exc_value.args[1]
                unicode_hint = force_text(
                    unicode_str[max(start - 5, 0):min(end + 5, len(unicode_str))],
                    'ascii', errors='replace'
                )

        from anthill.framework import get_version

        context = {
            'is_email': self.is_email,
            'unicode_hint': unicode_hint,
            'frames': frames,
            'application': self.app,
            'app_version': self.app.version,
            'user_str': None,
            'handler': None,
            'request': None,
            'sys_executable': sys.executable,
            'sys_version_info': '%d.%d.%d' % sys.version_info[0:3],
            'server_time': timezone.now(),
            'sys_path': sys.path,
            'tornado_version_info': tornado.version,
            'anthill_framework_version_info': get_version(),
            'exception_type': None,
            'exception_value': None,
            'headers': None,
            'request_variables': None,
        }
        if self.handler:
            context['handler'] = self.handler
            context['request'] = self.handler.request
            context['request_variables'] = {
                k: self.handler.decode_argument(v[0]) for k, v
                in self.handler.request.arguments.items()
            }
            if self.handler.request is None:
                user_str = None
            else:
                try:
                    user_str = str(self.handler.current_user)
                except Exception:
                    user_str = '[unable to retrieve the current user]'
            context['user_str'] = user_str
        if self.exc_type:
            context['exception_type'] = self.exc_type.__name__
        if self.exc_value:
            context['exception_value'] = str(self.exc_value)
        if frames:
            context['lastframe'] = frames[-1]
        return context

    @staticmethod
    def _get_lines_from_file(filename, lineno, context_lines, loader=None, module_name=None):
        """
        Return context_lines before and after lineno from file.
        Return (pre_context_lineno, pre_context, context_line, post_context).
        """
        source = None
        if hasattr(loader, 'get_source'):
            try:
                source = loader.get_source(module_name)
            except ImportError:
                pass
            if source is not None:
                source = source.splitlines()
        if source is None:
            try:
                with open(filename, 'rb') as fp:
                    source = fp.read().splitlines()
            except (OSError, IOError):
                pass
        if source is None:
            return None, [], None, []

        # If we just read the source from a file, or if the loader did not
        # apply tokenize.detect_encoding to decode the source into a
        # string, then we should do that ourselves.
        if isinstance(source[0], bytes):
            encoding = 'ascii'
            for line in source[:2]:
                # File coding may be specified. Match pattern from PEP-263
                # (http://www.python.org/dev/peps/pep-0263/)
                match = re.search(br'coding[:=]\s*([-\w.]+)', line)
                if match:
                    encoding = match.group(1).decode('ascii')
                    break
            source = [str(sline, encoding, 'replace') for sline in source]

        lower_bound = max(0, lineno - context_lines)
        upper_bound = lineno + context_lines

        pre_context = source[lower_bound:lineno]
        context_line = source[lineno]
        post_context = source[lineno + 1:upper_bound]

        return lower_bound, pre_context, context_line, post_context

    def get_traceback_frames(self):
        def explicit_or_implicit_cause(exc_value):
            explicit = getattr(exc_value, '__cause__', None)
            implicit = getattr(exc_value, '__context__', None)
            return explicit or implicit

        # Get the exception and all its causes
        exceptions = []
        exc_value = self.exc_value
        while exc_value:
            exceptions.append(exc_value)
            exc_value = explicit_or_implicit_cause(exc_value)

        frames = []
        # No exceptions were supplied to ExceptionReporter
        if not exceptions:
            return frames

        # In case there's just one exception, take the traceback from self.tb
        exc_value = exceptions.pop()
        tb = self.tb if not exceptions else exc_value.__traceback__

        while tb is not None:
            # Support for __traceback_hide__ which is used by a few libraries
            # to hide internal frames.
            if tb.tb_frame.f_locals.get('__traceback_hide__'):
                tb = tb.tb_next
                continue
            filename = tb.tb_frame.f_code.co_filename
            function = tb.tb_frame.f_code.co_name
            lineno = tb.tb_lineno - 1
            loader = tb.tb_frame.f_globals.get('__loader__')
            module_name = tb.tb_frame.f_globals.get('__name__') or ''
            pre_context_lineno, pre_context, context_line, post_context = self._get_lines_from_file(
                filename, lineno, 7, loader, module_name,
            )
            if pre_context_lineno is None:
                pre_context_lineno = lineno
                pre_context = []
                context_line = '<source code not available>'
                post_context = []
            frames.append({
                'exc_cause': explicit_or_implicit_cause(exc_value),
                'exc_cause_explicit': getattr(exc_value, '__cause__', True),
                'tb': tb,
                'filename': filename,
                'function': function,
                'lineno': lineno + 1,
                'id': id(tb),
                'pre_context': pre_context,
                'context_line': context_line,
                'post_context': post_context,
                'pre_context_lineno': pre_context_lineno + 1,
            })

            # If the traceback for current exception is consumed, try the
            # other exception.
            if not tb.tb_next and exceptions:
                exc_value = exceptions.pop()
                tb = exc_value.__traceback__
            else:
                tb = tb.tb_next

        return frames

    def get_traceback_text(self):
        """Return plain text version of debug 500 HTTP error page."""
        return to_basestring(self._text_template.generate(
            **self.get_traceback_data()))

    def get_traceback_html(self):
        """Return HTML version of debug 500 HTTP error page."""
        return to_basestring(self._html_template.generate(
            **self.get_traceback_data()))
